// TransformerAI — Bakım Planlama Servisi
//
// Uygulamanın başladığı yer. Python tarafındaki app/main.py'nin karşılığı.
// "Minimal API" stili: uç noktalar doğrudan burada tanımlanıyor.
// FastAPI'deki @app.get(...) dekoratörünün karşılığı app.MapGet(...).

using System.Text.Json.Serialization;
using Microsoft.EntityFrameworkCore;
using TransformerAI.Maintenance.Api.Data;
using TransformerAI.Maintenance.Api.Models;

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
    mlService = "Python/FastAPI (risk ve tanı buradan okunur)",
    storage = "SQLite (maintenance.db) — ölçüm verisinden ayrı",
})
.WithName("ServiceInfo");

app.MapGet("/health", () => new { status = "ok" })
   .WithName("Health");

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
