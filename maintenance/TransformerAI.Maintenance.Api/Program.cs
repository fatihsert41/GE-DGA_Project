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
builder.Services.AddSingleton<AssignmentService>();
builder.Services.AddScoped<TechnicianRepository>();
// TokenIssuer Singleton: gizli anahtar bir kez okunur, istekler
// arasında değişmez. AuthService Scoped, çünkü DbContext kullanıyor.
builder.Services.AddSingleton<TokenIssuer>();
builder.Services.AddScoped<AuthService>();

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

    // --- Demo PIN'leri (Faz 9.0b) ------------------------------------------
    //
    // Neden migration'ın HasData'sında değil? Çünkü PIN özeti RASTGELE tuz
    // içerir; migration ise deterministik olmalıdır (aynı dosya her yerde
    // aynı sonucu üretmeli). Sabit bir özet gömseydik, tuzun tüm amacı
    // ortadan kalkardı — herkes aynı tuzu kullanırdı.
    //
    // ⚠ DEMO KURALI: PIN = sicil numarasının SON DÖRT HANESİ.
    // Gerçek bir sistemde PIN kullanıcıya kapalı zarfla verilir ve ilk
    // girişte değiştirtilir. Burada tahmin edilebilir olması bilinçli:
    // bu bir güvenlik gösterimi değil, izlenebilirlik altyapısıdır.
    var pinless = db.Technicians.Where(t => t.PinHash == "").ToList();
    foreach (var person in pinless)
    {
        var demoPin = person.EmployeeNo.Length >= 4
            ? person.EmployeeNo[^4..]
            : person.EmployeeNo.PadLeft(4, '0');
        var (hash, salt) = PinHasher.Hash(demoPin);
        person.PinHash = hash;
        person.PinSalt = salt;
    }
    var issuer = scope.ServiceProvider.GetRequiredService<TokenIssuer>();
    if (issuer.IsDevelopmentSecret)
    {
        Console.WriteLine(
            "[UYARI] Belirtec imzasi GELISTIRME anahtariyla yapiliyor; bu " +
            "anahtar kaynak kodda ve GIZLI DEGILDIR.");
        Console.WriteLine(
            "        Gercek kurulumda TRANSFORMERAI_AUTH_SECRET ortam " +
            "degiskenini ayarlayin (Python tarafinda da ayni deger).");
    }

    if (pinless.Count > 0)
    {
        db.SaveChanges();
        Console.WriteLine(
            $"[DEMO] {pinless.Count} personele PIN atandi. " +
            "PIN = sicil numarasinin son 4 hanesi.");
        foreach (var person in pinless)
            Console.WriteLine($"  {person.EmployeeNo}  {person.Name,-16} " +
                              $"rol={person.Role}  PIN={person.EmployeeNo[^4..]}");
    }
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
// Teknisyenler
// ---------------------------------------------------------------------------

// --- Kimlik (Faz 9.0) ------------------------------------------------------
//
// ⚠ BU BİR KİMLİK DOĞRULAMA DEĞİLDİR. Parola yoktur; sicil numarasını
// bilen herkes o kişi olarak sisteme girebilir. Amaç GÜVENLİK değil
// İZLENEBİLİRLİK: bir kaydın sorumlusunu belirlemek.
//
// Neden yine de değerli? Çünkü veri modelinin doğru kurulmasını sağlıyor.
// Kayıtlar bugünden itibaren "kim girdi" bilgisi taşıyor. Gerçek oturum
// açma sonradan bunun ÜSTÜNE takılabilir. Tersi mümkün değil: kimliksiz
// kurulan bir modelde geçmiş kayıtlar sonsuza kadar sahipsiz kalır.
app.MapGet("/personnel/by-employee-no/{employeeNo}",
    async (MaintenanceDbContext db, string employeeNo, CancellationToken ct) =>
{
    var person = await db.Technicians
        .AsNoTracking()
        .FirstOrDefaultAsync(t => t.EmployeeNo == employeeNo, ct);

    if (person is null)
        return Results.NotFound(new { message = $"Sicil bulunamadı: {employeeNo}" });

    if (!person.IsActive)
        return Results.BadRequest(new
        {
            message = $"{person.Name} ({employeeNo}) pasif durumda; " +
                      "sisteme giriş yapamaz."
        });

    return Results.Ok(new
    {
        person.Id,
        person.EmployeeNo,
        person.Name,
        person.Region,
        role = person.Role.ToString(),
        specialty = person.Specialty.ToString(),
    });
})
.WithSummary("Sicil numarasıyla personel bulur (giriş ekranı için).");

app.MapGet("/technicians", async (TechnicianRepository repo, CancellationToken ct) =>
{
    var workloads = await repo.WorkloadsAsync(ct);
    return Results.Ok(new
    {
        count = workloads.Count,
        // Sadece ihtiyacımız olan alanları döndürüyoruz. Technician nesnesini
        // doğrudan verseydik içindeki WorkOrders listesi de serileşmeye
        // çalışır ve döngüye girerdi (iş emri -> teknisyen -> iş emri...).
        items = workloads.Select(w => new
        {
            w.Technician.Id,
            w.Technician.EmployeeNo,
            w.Technician.Name,
            w.Technician.Region,
            role = w.Technician.Role.ToString(),
            specialty = w.Technician.Specialty.ToString(),
            w.Technician.MaxOpenOrders,
            w.Technician.IsActive,
            openOrders = w.OpenOrders,
            hasCapacity = w.HasCapacity,
        }),
    });
})
.WithName("ListTechnicians");

// İş emrine teknisyen atama.
// Gövdede technicianId verilirse o kişi atanır (insanın kararı üstündür);
// verilmezse sistem en uygun kişiyi seçer.
app.MapPost("/workorders/{id}/assign",
    async (WorkOrderRepository orders, TechnicianRepository techs,
           AssignmentService assigner, MlServiceClient ml,
           string id, AssignRequest? request, CancellationToken ct) =>
{
    var order = await orders.GetAsync(id);
    if (order is null)
    {
        return Results.NotFound(new { message = $"İş emri bulunamadı: {id}" });
    }

    string technicianId;
    string reason;
    string? warning = null;

    if (!string.IsNullOrWhiteSpace(request?.TechnicianId))
    {
        // Elle atama: teknisyen gerçekten var mı?
        var chosen = await techs.GetAsync(request.TechnicianId, ct);
        if (chosen is null)
        {
            return Results.BadRequest(new
            {
                message = $"Teknisyen bulunamadı: {request.TechnicianId}",
            });
        }

        technicianId = chosen.Id;
        reason = "elle atandı";

        // Elle atama kapasiteyi AŞABİLİR — planlama mühendisi bazen
        // mecbur kalır ve sistem onun kararını engellememeli. Ama sessizce
        // geçmek de yanlış: aşım görünür olmalı ki yük dengesizliği
        // fark edilsin.
        var load = (await techs.WorkloadsAsync(ct))
            .FirstOrDefault(w => w.Technician.Id == chosen.Id);
        if (load is not null && !load.HasCapacity)
        {
            warning = $"{chosen.Name} kapasitesi dolu "
                      + $"({load.OpenOrders}/{chosen.MaxOpenOrders}); "
                      + "atama yine de yapıldı.";
        }
    }
    else
    {
        // Otomatik atama: trafonun konumu ve arıza ailesi ML servisinden.
        // Ulaşılamazsa atama yine yapılır, sadece bölge/uzmanlık puanı
        // olmadan — bağımlılığın kapalı olması işi tamamen durdurmamalı.
        var risk = await ml.GetTransformerAsync(order.TransformerId, ct);
        var workloads = await techs.WorkloadsAsync(ct);

        var assignment = assigner.Choose(workloads, order.Kind,
                                         risk?.Location, risk?.PredictionFamily);
        if (assignment is null)
        {
            return Results.Problem(
                title: "Uygun teknisyen yok",
                detail: "Tüm teknisyenlerin kapasitesi dolu veya pasif.",
                statusCode: StatusCodes.Status409Conflict);
        }

        technicianId = assignment.Technician.Id;
        reason = assignment.Reason;
    }

    var updated = await techs.AssignAsync(id, technicianId, ct);

    return Results.Ok(new
    {
        workOrder = new
        {
            updated!.Id,
            updated.TransformerId,
            updated.Title,
            status = updated.Status.ToString(),
            kind = updated.Kind.ToString(),
            updated.Priority,
            updated.DueDate,
            technician = updated.Technician is null ? null : new
            {
                updated.Technician.Id,
                updated.Technician.Name,
                updated.Technician.Region,
                specialty = updated.Technician.Specialty.ToString(),
            },
        },
        reason,
        warning,
    });
})
.WithName("AssignWorkOrder");

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
    var plan = planner.Plan(fleet, existing, today);

    return Results.Ok(new
    {
        count = plan.Suggestions.Count,
        suggestions = plan.Suggestions,
        // Açık emri olan ama durumu kötüleşen trafolar. Bunlar için yeni
        // emir AÇILMAZ, mevcut emrin aciliyeti yükseltilir.
        escalationCount = plan.Escalations.Count,
        escalations = plan.Escalations,
    });
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
    var plan = planner.Plan(fleet, existing, today);

    var created = new List<WorkOrder>();
    foreach (var suggestion in plan.Suggestions)
    {
        created.Add(await repo.AddAsync(WorkOrderPlanner.ToRequest(suggestion)));
    }

    // Kötüleşen durumlar için YENİ emir açmıyoruz; mevcut emri güncelliyoruz.
    var escalated = new List<WorkOrder>();
    foreach (var e in plan.Escalations)
    {
        var updated = await repo.EscalateAsync(e.WorkOrderId, e.NewPriority,
                                               e.NewDueDate, e.Reason, ct);
        if (updated is not null)
        {
            escalated.Add(updated);
        }
    }

    // Bu uç nokta güvenle tekrar çağrılabilir: durum değişmediyse ikinci
    // çağrıda hem created hem escalated boş döner.
    return Results.Ok(new
    {
        created = created.Count,
        items = created,
        escalated = escalated.Count,
        escalatedItems = escalated,
    });
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
    var result = await repo.UpdateStatusAsync(id, request);

    if (result.Order is null)
    {
        return Results.NotFound(new { message = $"İş emri bulunamadı: {id}" });
    }

    // Geçiş kuralı ihlali 409 Conflict: istek biçimsel olarak geçerli
    // (400 değil) ama kaydın MEVCUT DURUMU buna izin vermiyor.
    if (result.Error is not null)
    {
        return Results.Conflict(new
        {
            message = result.Error,
            currentStatus = result.Order.Status.ToString(),
            allowedNext = WorkOrderTransitions.Next(result.Order.Status)
                .Select(x => x.ToString()),
        });
    }

    return Results.Ok(result.Order);
})
.WithName("UpdateWorkOrderStatus");


// ---------------------------------------------------------------------------
// Kimlik doğrulama (Faz 9.0b)
// ---------------------------------------------------------------------------
//
// ⚠ BU KATMANIN SINIRLARI — arayüzde de yazılı olmalı:
//
//   VAR: PIN özetleme (PBKDF2 + kişiye özel tuz), deneme sınırlaması ve
//        kilitleme, süreli ve iptal edilebilir oturum belirteci,
//        sabit süreli karşılaştırma, kullanıcı sayımına karşı tek mesaj.
//
//   YOK: HTTPS/TLS (demo localhost'ta çalışıyor — gerçek kurulumda ŞART,
//        aksi halde belirteç ağda açık gider), çok faktörlü doğrulama,
//        parola politikası/sıfırlama, CSRF sertleştirmesi.
//
// 4-6 haneli bir PIN güçlü bir parola değildir. Özetleme + kilitlemeyle
// birlikte banka kartı seviyesinde koruma verir: sicilini bilen birine
// karşı korur, sistemi elinde tutan birine karşı değil.

app.MapPost("/auth/login", async (AuthService auth, LoginRequest request,
                                  CancellationToken ct) =>
{
    var (ok, error) = await auth.LoginAsync(request.EmployeeNo, request.Pin,
                                            DateTime.UtcNow, ct);
    // 401: kimlik doğrulanamadı. Kilitlenme de 401 döner (403 değil),
    // çünkü kullanıcı hâlâ kimliğini kanıtlayamamış durumda.
    return ok is not null ? Results.Ok(ok) : Results.Json(error, statusCode: 401);
})
.WithSummary("Sicil numarası ve PIN ile giriş.");

app.MapPost("/auth/logout", async (AuthService auth, HttpRequest http,
                                   CancellationToken ct) =>
{
    var token = ReadToken(http);
    var done = await auth.LogoutAsync(token, ct);
    return Results.Ok(new { ok = done });
})
.WithSummary("Oturumu kapatır; belirteç anında geçersiz olur.");

app.MapGet("/auth/me", async (AuthService auth, HttpRequest http,
                              CancellationToken ct) =>
{
    var person = await auth.ResolveAsync(ReadToken(http), DateTime.UtcNow, ct);
    if (person is null)
        return Results.Json(new { message = "Oturum geçersiz veya süresi dolmuş." },
                            statusCode: 401);

    return Results.Ok(new
    {
        person.Id,
        person.EmployeeNo,
        person.Name,
        person.Region,
        role = person.Role.ToString(),
        specialty = person.Specialty.ToString(),
    });
})
.WithSummary("Belirtecin sahibini döndürür (oturum kontrolü).");

app.Run();

// Belirteç "Authorization: Bearer <token>" başlığından okunur.
// Standart biçim; ileride gerçek bir kimlik sağlayıcıya geçilirse
// istemci tarafında değişiklik gerekmez.
static string? ReadToken(HttpRequest http)
{
    var header = http.Headers.Authorization.ToString();
    if (string.IsNullOrWhiteSpace(header)) return null;
    return header.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase)
        ? header["Bearer ".Length..].Trim()
        : header.Trim();
}
