// TransformerAI — Bakım Planlama Servisi
//
// Uygulamanın başladığı yer. Python tarafındaki app/main.py'nin karşılığı.
// "Minimal API" stili: uç noktalar doğrudan burada tanımlanıyor.
// FastAPI'deki @app.get(...) dekoratörünün karşılığı app.MapGet(...).

using System.Text.Json.Serialization;
using Microsoft.EntityFrameworkCore;
using TransformerAI.Maintenance.Api.Data;
using TransformerAI.Maintenance.Api.Models;
using TransformerAI.Maintenance.Api.Services;

var builder = WebApplication.CreateBuilder(args);

// ---------------------------------------------------------------------------
// Servis kaydı (kurulum aşaması)
// ---------------------------------------------------------------------------

builder.Services.AddOpenApi();

// JSON'da enum'lar varsayılan olarak SAYIDIR: {"status": 0}.
// Metne çeviriyoruz: {"status": "Planned"} — hem okunur hem kırılgan değil.
builder.Services.ConfigureHttpJsonOptions(options =>
{
    options.SerializerOptions.Converters.Add(new JsonStringEnumConverter());
});

// Veritabanı. Bağlantı adresi appsettings.json'dan okunur; yoksa varsayılan
// kullanılır. Ayarı koda gömmemek önemli: aynı kod farklı ortamlarda
// (geliştirme / üretim) farklı veritabanına bağlanabilmeli.
var connectionString = builder.Configuration.GetConnectionString("Maintenance")
                       ?? "Data Source=maintenance.db";

builder.Services.AddDbContext<MaintenanceDbContext>(options =>
    options.UseSqlite(connectionString));

// AddScoped = "her HTTP isteği için bir örnek".
// AddSingleton (7.2'de kullandığımız) = uygulama boyunca tek örnek.
// Veritabanı bağlamı asla singleton olmamalı: içinde o isteğe ait
// değişiklikleri izler, paylaşılırsa istekler birbirine karışır.
builder.Services.AddScoped<WorkOrderRepository>();

// ML servisi istemcisi. AddHttpClient bir "tipli istemci" kaydeder:
// MlServiceClient isteyen herkes, adresi ve zaman aşımı ayarlanmış bir
// HttpClient'la birlikte hazır gelir.
//
// HttpClient'ı elle "new HttpClient()" ile yaratmak .NET'te klasik bir
// hatadır: her örnek yeni bir soket açar ve yoğun yükte soketler tükenir.
// Fabrika bağlantıları havuzlar ve ömürlerini yönetir.
var mlBaseUrl = builder.Configuration["MlService:BaseUrl"]
                ?? "http://localhost:8000";
var mlTimeout = builder.Configuration.GetValue<int?>("MlService:TimeoutSeconds") ?? 10;

// Planlayıcı durumsuzdur (alan tutmaz, sadece hesap yapar), bu yüzden tek
// örnek yeterli: AddSingleton. Repository'nin Scoped olmasının sebebi
// veritabanı bağlamını taşımasıydı; burada öyle bir şey yok.
builder.Services.AddSingleton<WorkOrderPlanner>();

builder.Services.AddHttpClient<MlServiceClient>(client =>
{
    client.BaseAddress = new Uri(mlBaseUrl);
    // Zaman aşımı ŞART: karşı servis yanıt vermezse isteğimiz sonsuza
    // kadar beklememeli, hızlıca "erişilemiyor" demeli.
    client.Timeout = TimeSpan.FromSeconds(mlTimeout);
});

var app = builder.Build();

// Uygulama açılırken şemayı uygula. Migration dosyaları koddadır;
// bu satır "veritabanı bu sürüme kadar güncellensin" der.
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<MaintenanceDbContext>();
    db.Database.Migrate();
}

if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}

// ---------------------------------------------------------------------------
// Servis bilgisi
// ---------------------------------------------------------------------------

app.MapGet("/", () => new
{
    name = "TransformerAI Bakım Planlama Servisi",
    version = "0.3.0",
    role = "İş emri, teknisyen atama ve bakım planlama",
    mlService = mlBaseUrl,
    storage = "SQLite (maintenance.db) — ölçüm verisinden ayrı",
})
.WithName("ServiceInfo");

// Sağlık kontrolü artık bağımlılığı da yokluyor: bu servis ayakta olsa
// bile ML servisi kapalıysa iş emri ÖNERİSİ üretemeyiz. İzleme aracının
// bunu görmesi gerekir.
app.MapGet("/health", async (MlServiceClient ml) =>
{
    var mlUp = await ml.IsAvailableAsync();
    return Results.Ok(new
    {
        status = "ok",
        dependencies = new { mlService = mlUp ? "ok" : "unreachable" },
    });
})
.WithName("Health");

// ---------------------------------------------------------------------------
// ML servisinden okunan veriler (salt okunur ayna)
// ---------------------------------------------------------------------------

// Filo görünümü. Bu servis veriyi SAKLAMAZ, her seferinde Python'dan okur —
// tek doğruluk kaynağı orasıdır. Kopyalasaydık iki yerde iki farklı gerçek
// olurdu (mikroservis mimarisinde en pahalı hatalardan biri).
app.MapGet("/fleet", async (MlServiceClient ml, CancellationToken ct) =>
{
    var fleet = await ml.GetFleetAsync(ct);
    return fleet is null
        ? Results.Problem(
            title: "ML servisine ulaşılamıyor",
            detail: $"{mlBaseUrl} adresi yanıt vermiyor. Python servisi çalışıyor mu?",
            statusCode: StatusCodes.Status503ServiceUnavailable)
        : Results.Ok(fleet);
})
.WithName("Fleet");

// Tek trafonun riski + o trafonun açık iş emirleri bir arada.
// İKİ SERVİSİ BİRLEŞTİREN ilk uç nokta: risk Python'dan, iş emirleri
// bizim veritabanımızdan geliyor.
app.MapGet("/transformers/{id}/risk",
    async (MlServiceClient ml, WorkOrderRepository repo, string id,
           CancellationToken ct) =>
{
    var risk = await ml.GetTransformerAsync(id, ct);
    if (risk is null)
    {
        return Results.NotFound(new
        {
            message = $"Trafo bulunamadı veya ML servisine ulaşılamıyor: {id}",
        });
    }

    var orders = await repo.ListAsync(transformerId: id);

    return Results.Ok(new
    {
        transformer = risk,
        workOrders = new
        {
            total = orders.Count,
            open = orders.Count(o => o.Status is WorkOrderStatus.Planned
                                         or WorkOrderStatus.InProgress),
            items = orders,
        },
    });
})
.WithName("TransformerRisk");

// ---------------------------------------------------------------------------
// İş emirleri
//
// Uç noktalar artık "async" ve "Task" döndürüyor. Sebep: veritabanı çağrıları
// asenkron; onları beklerken iş parçacığı serbest kalıyor ve sunucu başka
// isteklere bakabiliyor.
// ---------------------------------------------------------------------------

app.MapGet("/workorders", async (WorkOrderRepository repo,
                                 WorkOrderStatus? status,
                                 string? transformerId) =>
{
    var items = await repo.ListAsync(status, transformerId);
    return Results.Ok(new { count = items.Count, items });
})
.WithName("ListWorkOrders");

// ---------------------------------------------------------------------------
// Otomatik öneri
//
// Sistem filoya bakıp hangi trafolar için iş emri açılması gerektiğini
// kendisi söylüyor. İki ayrı uç nokta olmasının sebebi: ÖNERMEK ile
// UYGULAMAK farklı yetkiler ister. Planlama mühendisi önce listeyi görür,
// sonra onaylar.
// ---------------------------------------------------------------------------

app.MapGet("/workorders/suggestions",
    async (MlServiceClient ml, WorkOrderRepository repo, WorkOrderPlanner planner,
           CancellationToken ct) =>
{
    var fleet = await ml.GetFleetAsync(ct);
    if (fleet is null)
    {
        return Results.Problem(
            title: "ML servisine ulaşılamıyor",
            detail: "Öneri üretmek için güncel filo durumu gerekiyor.",
            statusCode: StatusCodes.Status503ServiceUnavailable);
    }

    var existing = await repo.ListAsync();
    var today = DateOnly.FromDateTime(DateTime.UtcNow);
    var suggestions = planner.Suggest(fleet, existing, today);

    return Results.Ok(new { count = suggestions.Count, suggestions });
})
.WithName("SuggestWorkOrders");

// Önerileri gerçek iş emrine çevirir.
// POST çünkü sistemi DEĞİŞTİRİYOR; GET yan etkisiz olmalıdır.
app.MapPost("/workorders/suggestions/apply",
    async (MlServiceClient ml, WorkOrderRepository repo, WorkOrderPlanner planner,
           CancellationToken ct) =>
{
    var fleet = await ml.GetFleetAsync(ct);
    if (fleet is null)
    {
        return Results.Problem(
            title: "ML servisine ulaşılamıyor",
            statusCode: StatusCodes.Status503ServiceUnavailable);
    }

    var existing = await repo.ListAsync();
    var today = DateOnly.FromDateTime(DateTime.UtcNow);
    var suggestions = planner.Suggest(fleet, existing, today);

    var created = new List<WorkOrder>();
    foreach (var suggestion in suggestions)
    {
        created.Add(await repo.AddAsync(WorkOrderPlanner.ToRequest(suggestion)));
    }

    // Bu uç nokta güvenle tekrar çağrılabilir: planlayıcı zaten açık emri
    // olan (trafo, tür) çiftini atlıyor. İkinci çağrıda created boş döner.
    return Results.Ok(new { created = created.Count, items = created });
})
.WithName("ApplySuggestions");

// ---------------------------------------------------------------------------

// DİKKAT: Bu satır /workorders/{id} kuralından ÖNCE gelmeli.
// Aksi halde "summary" kelimesi bir id sanılır ve 404 döner.
// Minimal API çoğu durumda daha spesifik olanı seçer ama sıraya güvenmek
// yerine açıkça yukarı almak daha sağlam.
app.MapGet("/workorders/summary", async (WorkOrderRepository repo) =>
        await repo.SummaryAsync())
   .WithName("WorkOrderSummary");

app.MapGet("/workorders/{id}", async (WorkOrderRepository repo, string id) =>
{
    var order = await repo.GetAsync(id);
    return order is null
        ? Results.NotFound(new { message = $"İş emri bulunamadı: {id}" })
        : Results.Ok(order);
})
.WithName("GetWorkOrder");

app.MapPost("/workorders", async (WorkOrderRepository repo,
                                  CreateWorkOrderRequest request) =>
{
    if (string.IsNullOrWhiteSpace(request.TransformerId))
    {
        return Results.BadRequest(new { message = "transformerId zorunludur." });
    }

    if (string.IsNullOrWhiteSpace(request.Title))
    {
        return Results.BadRequest(new { message = "title zorunludur." });
    }

    var order = await repo.AddAsync(request);
    return Results.Created($"/workorders/{order.Id}", order);
})
.WithName("CreateWorkOrder");

app.MapPatch("/workorders/{id}/status",
    async (WorkOrderRepository repo, string id, UpdateStatusRequest request) =>
{
    var order = await repo.UpdateStatusAsync(id, request);
    return order is null
        ? Results.NotFound(new { message = $"İş emri bulunamadı: {id}" })
        : Results.Ok(order);
})
.WithName("UpdateWorkOrderStatus");

app.Run();
