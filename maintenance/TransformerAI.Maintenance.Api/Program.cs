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
// Faz 12.5 — kök neden analizi. Scoped: DbContext taşıyor.
builder.Services.AddScoped<RcaRepository>();

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

// --- Bildirim altyapısı (Faz 9.2) ------------------------------------------
// NotificationPlanner saf bir kural sınıfı -> Singleton yeterli.
builder.Services.AddSingleton<NotificationPlanner>();
builder.Services.AddScoped<NotificationService>();

// ARAYÜZE kayıt: kodun geri kalanı INotificationSender bilir, hangi
// uygulamanın kullanıldığını bilmez. E-postaya geçmek istendiğinde
// DEĞİŞECEK TEK SATIR burasıdır — bağımlılık ters çevirmenin somut
// karşılığı budur.
builder.Services.AddScoped<INotificationSender, LoggingNotificationSender>();

// Arka plan servisi: uygulama açık olduğu sürece kuyruğu boşaltır.
//
// ⚠ ÖĞRENİLEN TUZAK: `AddHostedService<NotificationDispatcher>()` sınıfı
// yalnızca IHostedService olarak kaydeder, NotificationDispatcher olarak
// DEĞİL. Uç noktada `NotificationDispatcher dispatcher` parametresi
// yazınca ASP.NET onu bir servis değil, istek GÖVDESİ sandı ve
// "Implicit body inferred for parameter" hatası verdi.
//
// Doğrusu: önce Singleton olarak kaydet, sonra aynı örneği hosted
// service olarak göster. Tek örnek hem arka planda çalışır hem de
// enjekte edilebilir.
builder.Services.AddSingleton<NotificationDispatcher>();
builder.Services.AddHostedService(sp =>
    sp.GetRequiredService<NotificationDispatcher>());

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

    // --- Demo geçici parolaları (Sistem Yönetimi) ----------------------------
    //
    // Parolası olmayan hesaplara GEÇİCİ parola atanır ve ilk girişte
    // değiştirilmesi zorunlu kılınır.
    //
    // Neden migration'ın HasData'sında değil? Parola özeti RASTGELE tuz
    // içerir; migration ise deterministik olmalıdır (aynı dosya her yerde
    // aynı sonucu üretmeli).
    //
    // ⚠ DEMO KURALI: geçici parola = "Demo-" + sicil (ör. Demo-10502).
    // Tahmin edilebilir olması bilinçli ve ZARARSIZ: bu parolayla açılan
    // oturumun yetki listesi BOŞTUR, kullanıcı kendi parolasını belirlemeden
    // hiçbir işlem yapamaz. Gerçek kurulumda Sistem Yöneticisi her kişiye
    // AD01 ekranından rastgele geçici parola üretir.
    var passwordless = db.Technicians.Where(t => t.PasswordHash == "").ToList();
    foreach (var person in passwordless)
    {
        var (hash, salt) = PasswordHasher.Hash(DemoTemporaryPassword(person.EmployeeNo));
        person.PasswordHash = hash;
        person.PasswordSalt = salt;
        person.MustChangePassword = true;
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

    if (passwordless.Count > 0)
    {
        db.SaveChanges();
        Console.WriteLine(
            $"[DEMO] {passwordless.Count} hesaba gecici parola atandi. " +
            "Ilk giriste degistirilmesi zorunlu.");
        foreach (var person in passwordless)
            Console.WriteLine($"  {person.EmployeeNo}  {person.Department,-20} " +
                              $"gecici parola: {DemoTemporaryPassword(person.EmployeeNo)}");
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
    async (MaintenanceDbContext db, AuthService auth, HttpRequest http,
           string employeeNo, CancellationToken ct) =>
{
    // Sistem Yönetimi: parola ile girişe geçilince bu uç nokta KİMLİKSİZ
    // kalamazdı — hangi sicillerin var olduğunu herkese söylüyordu
    // (kullanıcı sayımı). Artık personel görme yetkisi istiyor.
    var (_, denied) = await RequireAsync(auth, http, Permissions.PersonnelView, ct);
    if (denied is not null) return denied;

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
            role = w.Technician.Role.ToString(),
            specialty = w.Technician.Specialty.ToString(),
            department = w.Technician.Department.ToString(),
            departmentName = DepartmentCatalog.Name(w.Technician.Department),
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
           AuthService auth, HttpRequest http,
           string id, AssignRequest? request, CancellationToken ct) =>
{
    // Faz 10: işi kime vereceğine planlamacı karar verir.
    var (_, denied) = await RequireAsync(auth, http, Permissions.WorkOrdersPlan, ct);
    if (denied is not null) return denied;

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
           NotificationService notifications, CancellationToken ct) =>
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
           NotificationService notifications, AuthService auth, HttpRequest http,
           CancellationToken ct) =>
{
    // Önermek herkese açık (GET), UYGULAMAK planlama yetkisi ister.
    // İki ayrı uç nokta olmasının Faz 7.5'teki gerekçesi tam olarak buydu.
    var (_, denied) = await RequireAsync(auth, http, Permissions.WorkOrdersPlan, ct);
    if (denied is not null) return denied;

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

    var now = DateTime.UtcNow;
    var notified = 0;

    var created = new List<WorkOrder>();
    foreach (var suggestion in plan.Suggestions)
    {
        var order = await repo.AddAsync(WorkOrderPlanner.ToRequest(suggestion));
        created.Add(order);
        // Bildirim burada yalnızca KUYRUĞA ALINIR (outbox deseni).
        // Gönderimi arka plandaki NotificationDispatcher üstlenir; bu
        // sayede e-posta sunucusu kapalı olsa bile iş emri açılır.
        notified += await notifications.QueueForOrderAsync(
            order, "work-order-created", now, ct);
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
            // Aciliyet yükselmesi AYRI bir tetikleyici: "bu iş artık
            // daha acil" bilgisi, ilk açılış bildirimi okunmuş olsa bile
            // yeniden haber vermeyi hak eder.
            notified += await notifications.QueueForOrderAsync(
                updated, "work-order-escalated", now, ct);
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
        notificationsQueued = notified,
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
                                  AuthService auth, HttpRequest http,
                                  CreateWorkOrderRequest request,
                                  CancellationToken ct) =>
{
    var (_, denied) = await RequireAsync(auth, http, Permissions.WorkOrdersPlan, ct);
    if (denied is not null) return denied;

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
    async (WorkOrderRepository repo, AuthService auth, HttpRequest http,
           string id, UpdateStatusRequest request, CancellationToken ct) =>
{
    var (me, denied) = await RequireAsync(auth, http, Permissions.WorkOrdersExecute, ct);
    if (denied is not null) return denied;

    // Saha personeli yalnızca KENDİSİNE atanan işi yürütür. Planlama
    // yetkisi olan (planlamacı, yönetim) her işin durumunu değiştirebilir:
    // örneğin hastalanan birinin işini iptal etmek gerekebilir.
    if (!Permissions.Has(me!.Department, Permissions.WorkOrdersPlan))
    {
        var current = await repo.GetAsync(id);
        if (current is null)
            return Results.NotFound(new { message = $"İş emri bulunamadı: {id}" });
        if (current.TechnicianId != me.Id)
            return Results.Json(new
            {
                message = "Bu iş emri size atanmadı. Yalnızca kendinize atanan " +
                          "işlerin durumunu değiştirebilirsiniz.",
                requiredPermission = Permissions.WorkOrdersPlan,
            }, statusCode: StatusCodes.Status403Forbidden);
    }

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
    var (ok, error) = await auth.LoginAsync(request.EmployeeNo, request.Password,
                                            DateTime.UtcNow, ct);
    // 401: kimlik doğrulanamadı. Kilitlenme de 401 döner (403 değil),
    // çünkü kullanıcı hâlâ kimliğini kanıtlayamamış durumda.
    return ok is not null ? Results.Ok(ok) : Results.Json(error, statusCode: 401);
})
.WithSummary("Sicil numarası ve parola ile giriş.");

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
        role = person.Role.ToString(),
        specialty = person.Specialty.ToString(),
        // Faz 10: departman VERİTABANINDAN okunuyor, belirteçten değil.
        // Yönetim birinin departmanını değiştirdiyse arayüz bunu sayfa
        // yenilenince görür.
        department = person.Department.ToString(),
        departmentName = DepartmentCatalog.Name(person.Department),
        // Geçici parolalıysa boş: arayüz menü yerine parola ekranını açar.
        permissions = AuthService.EffectivePermissions(person),
        mustChangePassword = person.MustChangePassword,
    });
})
.WithSummary("Belirtecin sahibini döndürür (oturum kontrolü).");

// Kullanıcının kendi parolasını değiştirmesi. Yetki İSTEMEZ (geçici
// parolalı oturumun tek yapabildiği iş bu), ama geçerli oturum ve mevcut
// parola ister. Başarılıysa bütün oturumlar kapanır, yeni belirteç döner.
app.MapPost("/auth/change-password",
    async (AuthService auth, HttpRequest http, ChangePasswordRequest request,
           CancellationToken ct) =>
{
    var result = await auth.ChangePasswordAsync(ReadToken(http), request, DateTime.UtcNow, ct);
    return result.Status == 200
        ? Results.Ok(result.Ok)
        : Results.Json(new { message = result.Message, problems = result.Problems },
                       statusCode: result.Status);
})
.WithSummary("Kendi parolasını değiştirir; eski oturumlar kapanır, yeni belirteç döner.");



// ---------------------------------------------------------------------------
// Bildirimler (Faz 9.2)
// ---------------------------------------------------------------------------
//
// Bildirim, iş emrinin EKİDİR: bağımsız bir mesajlaşma sistemi değil.
// Her bildirim bir iş emrine bağlıdır ve "şunu yapman gerekiyor" der.
// Bağlantısı olmayan bir uyarı kutusu, bir süre sonra kapatılan bir
// uyarı kutusudur.

app.MapGet("/notifications", async (AuthService auth, NotificationService svc,
                                    HttpRequest http, bool? unreadOnly,
                                    CancellationToken ct) =>
{
    var me = await auth.ResolveAsync(ReadToken(http), DateTime.UtcNow, ct);
    if (me is null) return Results.Json(
        new { message = "Oturum gerekli." }, statusCode: 401);

    var items = await svc.InboxAsync(me.Id, unreadOnly ?? false, ct: ct);
    return Results.Ok(new
    {
        count = items.Count,
        unread = await svc.UnreadCountAsync(me.Id, ct),
        items,
    });
})
.WithSummary("Oturum sahibinin gelen kutusu.");

app.MapPost("/notifications/{id}/read",
    async (AuthService auth, NotificationService svc, HttpRequest http,
           string id, CancellationToken ct) =>
{
    var me = await auth.ResolveAsync(ReadToken(http), DateTime.UtcNow, ct);
    if (me is null) return Results.Json(
        new { message = "Oturum gerekli." }, statusCode: 401);

    // Alıcı kimliği servise geçiliyor: kimse BAŞKASININ bildirimini
    // okundu işaretleyememeli. Kontrol hem burada hem sorguda var.
    var result = await svc.MarkReadAsync(id, me.Id, DateTime.UtcNow, ct);
    if (!result.Found)
        return Results.NotFound(new { message = "Bildirim bulunamadı." });

    return Results.Ok(new { ok = true, alreadyRead = result.AlreadyRead });
})
.WithSummary("Bildirimi okundu işaretler.");

app.MapPost("/notifications/dispatch",
    async (NotificationDispatcher dispatcher, CancellationToken ct) =>
{
    // Arka plan servisi 30 saniyede bir çalışıyor; bu uç nokta demo ve
    // test için "hemen çalıştır" düğmesi. Üretimde gerekmez ama
    // kuyruğun çalıştığını göstermenin en hızlı yolu.
    var sent = await dispatcher.DispatchOnceAsync(ct);
    return Results.Ok(new { sent });
})
.WithSummary("Bekleyen bildirimleri hemen gönderir (demo).");


// ---------------------------------------------------------------------------
// Departmanlar ve yetkiler (Faz 10)
// ---------------------------------------------------------------------------

// Katalog herkese açık: arayüz "bu işlemi hangi departman yapar?"
// sorusunu buradan cevaplıyor. Yetki haritasını arayüzde tekrar yazmak
// iki farklı gerçek yaratırdı.
app.MapGet("/departments", () => Results.Ok(new
{
    departments = DepartmentCatalog.All(),
    permissions = Permissions.Catalog,
}))
.WithSummary("Departmanlar, verdikleri yetkiler ve yetki adları.");

app.MapPut("/technicians/{id}/department",
    async (AuthService auth, HttpRequest http, MaintenanceDbContext db,
           string id, ChangeDepartmentRequest request, CancellationToken ct) =>
{
    var (me, denied) = await RequireAsync(auth, http, Permissions.PersonnelManage, ct);
    if (denied is not null) return denied;

    var all = await db.Technicians.ToListAsync(ct);
    var person = all.FirstOrDefault(t => t.Id == id);
    if (person is null)
        return Results.NotFound(new { message = $"Personel bulunamadı: {id}" });

    // Kurallar UserAdminRules içinde (Sistem Yönetimi fazında taşındı):
    //   * kişi KENDİ departmanını değiştiremez — yetki yükseltme koruması
    //   * son aktif Yönetim ve son aktif Sistem Yöneticisi taşınamaz
    if (UserAdminRules.CanChangeDepartment(me!.Id, person, request.Department, all) is { } block)
        return Results.Json(new { message = block.Message }, statusCode: block.Status);

    var previous = person.Department;
    var changed = previous != request.Department;
    person.Department = request.Department;
    if (changed)
        db.UserAuditEvents.Add(AuthService.Audit(
            UserAuditActions.DepartmentChanged, person, me, DateTime.UtcNow,
            $"{DepartmentCatalog.Name(previous)} → {DepartmentCatalog.Name(request.Department)}"));
    await db.SaveChangesAsync(ct);

    // Yetkiler değişti: açık oturumlar kapatılır ki kişi yeni yetkilerle
    // yeniden girsin. Kapatılmasaydı arayüzdeki menü eski yetkilerle kalırdı.
    var closedSessions = changed ? await auth.RevokeAllSessionsAsync(person.Id, ct) : 0;

    return Results.Ok(new
    {
        person.Id,
        person.EmployeeNo,
        person.Name,
        department = person.Department.ToString(),
        departmentName = DepartmentCatalog.Name(person.Department),
        previousDepartment = previous.ToString(),
        permissions = Permissions.For(person.Department),
        closedSessions,
        // Belirteç imzalı olduğu için Python tarafındaki eski yetkiler, eski
        // belirtecin süresi dolana kadar geçerli kalabilir (bkz. TokenIssuer).
        note = "Kişinin açık oturumları kapatıldı; yeni yetkiler yeniden girişte geçerli. " +
               "Ölçüm servisindeki eski belirteç süresi dolana kadar eski yetkiyi taşıyabilir.",
    });
})
.WithSummary("Personelin departmanını değiştirir (yönetim).");


// ---------------------------------------------------------------------------
// Elle bildirim gönderme — "e-posta yaz" (Faz 10)
// ---------------------------------------------------------------------------

app.MapPost("/notifications/messages",
    async (AuthService auth, HttpRequest http, MaintenanceDbContext db,
           NotificationService svc, SendMessageRequest request,
           CancellationToken ct) =>
{
    var (me, denied) = await RequireAsync(auth, http, Permissions.NotificationsSend, ct);
    if (denied is not null) return denied;

    var personnel = await db.Technicians.AsNoTracking().ToListAsync(ct);
    var (recipients, problems) = MessageRules.Resolve(request, personnel, me!.Id);
    if (problems.Count > 0)
        return Results.BadRequest(new { message = "Bildirim gönderilemedi.", problems });

    var (messageId, created) = await svc.SendMessageAsync(
        me, request, recipients, DateTime.UtcNow, ct);

    return Results.Ok(new
    {
        messageId,
        sent = created,
        recipients = recipients.Select(r => new
        {
            r.EmployeeNo,
            r.Name,
            department = DepartmentCatalog.Name(r.Department),
        }),
    });
})
.WithSummary("Seçilen kişilere / departmanlara bildirim gönderir.");

app.MapGet("/notifications/sent",
    async (AuthService auth, HttpRequest http, NotificationService svc,
           CancellationToken ct) =>
{
    var (me, denied) = await RequireAsync(auth, http, Permissions.NotificationsSend, ct);
    if (denied is not null) return denied;

    var items = await svc.SentAsync(me!.Id, ct: ct);
    return Results.Ok(new { count = items.Count, items });
})
.WithSummary("Oturum sahibinin gönderdiği mesajlar ve okunma durumları.");


// ---------------------------------------------------------------------------
// Sistem Yönetimi — kullanıcı hesapları (AD01)
// ---------------------------------------------------------------------------
//
// Hepsi `users.manage` ister; bu yetki YALNIZCA Sistem Yönetimi
// departmanında (Yönetim'de bile yok). Kurallar Services/UserAdminRules.cs
// içinde; burada yalnızca veritabanı ve HTTP.
//
// Kayıt SİLİNMEZ, pasife alınır: iş emirleri, testler ve kök neden
// analizleri kişiye bağlı. Silmek geçmişi sahipsiz bırakırdı.

app.MapGet("/admin/users", async (AuthService auth, HttpRequest http,
                                  MaintenanceDbContext db, CancellationToken ct) =>
{
    var (_, denied) = await RequireAsync(auth, http, Permissions.UsersManage, ct);
    if (denied is not null) return denied;

    var now = DateTime.UtcNow;
    var people = await db.Technicians.AsNoTracking()
        .OrderBy(t => t.EmployeeNo)
        .ToListAsync(ct);
    return Results.Ok(new { count = people.Count, items = people.Select(p => UserView(p, now)) });
})
.WithSummary("Kullanıcı hesapları (Sistem Yönetimi).");

app.MapPost("/admin/users",
    async (AuthService auth, HttpRequest http, MaintenanceDbContext db,
           CreateUserRequest request, CancellationToken ct) =>
{
    var (me, denied) = await RequireAsync(auth, http, Permissions.UsersManage, ct);
    if (denied is not null) return denied;

    var (draft, problems) = UserAdminRules.ValidateCreate(request);
    if (problems.Count > 0)
        return Results.BadRequest(new { message = "Kullanıcı oluşturulamadı.", problems });

    var user = draft!;
    if (await db.Technicians.AnyAsync(t => t.EmployeeNo == user.EmployeeNo, ct))
        return Results.Conflict(new { message = $"Bu sicil numarası zaten kayıtlı: {user.EmployeeNo}" });

    // Geçici parolayı SİSTEM üretir ve yalnızca bu cevapta, bir kez gösterir.
    // Veritabanına yalnızca özeti yazılır; kaybedilirse sıfırlanır.
    var temporary = UserAdminRules.GenerateTemporaryPassword();
    var now = DateTime.UtcNow;
    (user.PasswordHash, user.PasswordSalt) = PasswordHasher.Hash(temporary);
    user.MustChangePassword = true;
    user.CreatedAt = now;
    user.CreatedByName = $"{me!.Name} ({me.EmployeeNo})";

    // İç kimlik (TK-nn) eşzamanlı iki istekte çakışabilir: birincil anahtar
    // ikinciyi reddeder, yeniden deneriz (iş emri numarasındaki desen).
    for (var attempt = 0; ; attempt++)
    {
        user.Id = UserAdminRules.NextId(await db.Technicians.Select(t => t.Id).ToListAsync(ct));
        db.Technicians.Add(user);
        db.UserAuditEvents.Add(AuthService.Audit(UserAuditActions.Created, user, me, now,
            $"{DepartmentCatalog.Name(user.Department)} · {user.Role}"));
        try
        {
            await db.SaveChangesAsync(ct);
            break;
        }
        catch (DbUpdateException) when (attempt < 5)
        {
            db.ChangeTracker.Clear();
            if (await db.Technicians.AnyAsync(t => t.EmployeeNo == user.EmployeeNo, ct))
                return Results.Conflict(new { message = $"Bu sicil numarası az önce kaydedildi: {user.EmployeeNo}" });
        }
    }

    return Results.Created($"/admin/users/{user.Id}", new
    {
        user = UserView(user, now),
        temporaryPassword = temporary,
        note = "Geçici parola YALNIZCA şimdi gösteriliyor ve hiçbir yerde saklanmıyor. " +
               "Kullanıcıya güvenli bir yoldan iletin; ilk girişte değiştirmesi zorunlu.",
    });
})
.WithSummary("Yeni kullanıcı; geçici parolayı sistem üretir ve bir kez gösterir.");

app.MapPost("/admin/users/{id}/reset-password",
    async (AuthService auth, HttpRequest http, MaintenanceDbContext db,
           string id, CancellationToken ct) =>
{
    var (me, denied) = await RequireAsync(auth, http, Permissions.UsersManage, ct);
    if (denied is not null) return denied;

    var person = await db.Technicians.FirstOrDefaultAsync(t => t.Id == id, ct);
    if (person is null)
        return Results.NotFound(new { message = $"Kullanıcı bulunamadı: {id}" });
    if (UserAdminRules.CanResetPassword(me!.Id, person) is { } block)
        return Results.Json(new { message = block.Message }, statusCode: block.Status);

    var temporary = UserAdminRules.GenerateTemporaryPassword();
    var now = DateTime.UtcNow;
    (person.PasswordHash, person.PasswordSalt) = PasswordHasher.Hash(temporary);
    person.MustChangePassword = true;
    person.FailedAttempts = 0;
    person.LockedUntil = null;
    db.UserAuditEvents.Add(AuthService.Audit(UserAuditActions.PasswordReset, person, me, now, null));
    await db.SaveChangesAsync(ct);

    // Eski parolayla açılmış oturumlar kapanır: sıfırlamanın sebebi çoğu
    // zaman "parola başkasının elinde olabilir"dir.
    var closedSessions = await auth.RevokeAllSessionsAsync(person.Id, ct);

    return Results.Ok(new
    {
        user = UserView(person, now),
        temporaryPassword = temporary,
        closedSessions,
        note = "Yeni geçici parola YALNIZCA şimdi gösteriliyor. Kişinin açık oturumları kapatıldı.",
    });
})
.WithSummary("Parolayı sıfırlar; yeni geçici parola bir kez gösterilir, oturumlar kapanır.");

app.MapPost("/admin/users/{id}/unlock",
    async (AuthService auth, HttpRequest http, MaintenanceDbContext db,
           string id, CancellationToken ct) =>
{
    var (me, denied) = await RequireAsync(auth, http, Permissions.UsersManage, ct);
    if (denied is not null) return denied;

    var person = await db.Technicians.FirstOrDefaultAsync(t => t.Id == id, ct);
    if (person is null)
        return Results.NotFound(new { message = $"Kullanıcı bulunamadı: {id}" });

    var now = DateTime.UtcNow;
    if (person.LockedUntil is not { } until || until <= now)
        return Results.Conflict(new { message = $"{person.Name} kilitli değil." });

    person.LockedUntil = null;
    person.FailedAttempts = 0;
    db.UserAuditEvents.Add(AuthService.Audit(UserAuditActions.Unlocked, person, me, now, null));
    await db.SaveChangesAsync(ct);

    return Results.Ok(new { user = UserView(person, now) });
})
.WithSummary("Hatalı denemeler nedeniyle kilitlenen hesabın kilidini açar.");

app.MapPost("/admin/users/{id}/deactivate",
    async (AuthService auth, HttpRequest http, MaintenanceDbContext db,
           string id, DeactivateUserRequest request, CancellationToken ct) =>
{
    var (me, denied) = await RequireAsync(auth, http, Permissions.UsersManage, ct);
    if (denied is not null) return denied;

    var all = await db.Technicians.ToListAsync(ct);
    var person = all.FirstOrDefault(t => t.Id == id);
    if (person is null)
        return Results.NotFound(new { message = $"Kullanıcı bulunamadı: {id}" });
    if (UserAdminRules.CanDeactivate(me!.Id, person, all, request.Reason) is { } block)
        return Results.Json(new { message = block.Message }, statusCode: block.Status);

    var now = DateTime.UtcNow;
    person.IsActive = false;
    person.DeactivatedAt = now;
    person.DeactivationReason = request.Reason!.Trim();
    db.UserAuditEvents.Add(AuthService.Audit(UserAuditActions.Deactivated, person, me, now,
        person.DeactivationReason));
    await db.SaveChangesAsync(ct);

    var closedSessions = await auth.RevokeAllSessionsAsync(person.Id, ct);

    // Pasif kişinin üzerindeki açık işler kendiliğinden BAŞKASINA ATANMAZ:
    // kime gideceği planlamanın kararı. Ama görünür kılınır.
    var openOrders = await db.WorkOrders.CountAsync(o => o.TechnicianId == person.Id
        && (o.Status == WorkOrderStatus.Planned || o.Status == WorkOrderStatus.InProgress), ct);

    return Results.Ok(new
    {
        user = UserView(person, now),
        closedSessions,
        openOrders,
        warning = openOrders > 0
            ? $"{person.Name} üzerinde {openOrders} açık iş emri var. Bakım Planlama bu işleri başka birine atamalı."
            : null,
        note = "Bakım servisinde anında geçerli. Ölçüm servisindeki belirteç süresi dolana kadar geçerli kalabilir.",
    });
})
.WithSummary("Hesabı pasife alır (silmez); oturumlar kapanır.");

app.MapPost("/admin/users/{id}/activate",
    async (AuthService auth, HttpRequest http, MaintenanceDbContext db,
           string id, CancellationToken ct) =>
{
    var (me, denied) = await RequireAsync(auth, http, Permissions.UsersManage, ct);
    if (denied is not null) return denied;

    var person = await db.Technicians.FirstOrDefaultAsync(t => t.Id == id, ct);
    if (person is null)
        return Results.NotFound(new { message = $"Kullanıcı bulunamadı: {id}" });
    if (person.IsActive)
        return Results.Conflict(new { message = $"{person.Name} zaten aktif." });

    // Yeniden etkinleştirmede eski parola GEÇERLİ OLMAZ: hesap uzun süre
    // kapalı kaldıysa eski parola çoktan sızmış olabilir.
    var temporary = UserAdminRules.GenerateTemporaryPassword();
    var now = DateTime.UtcNow;
    (person.PasswordHash, person.PasswordSalt) = PasswordHasher.Hash(temporary);
    person.IsActive = true;
    person.MustChangePassword = true;
    person.FailedAttempts = 0;
    person.LockedUntil = null;
    var previousReason = person.DeactivationReason;
    person.DeactivatedAt = null;
    person.DeactivationReason = null;
    db.UserAuditEvents.Add(AuthService.Audit(UserAuditActions.Activated, person, me, now,
        previousReason is null ? null : $"Önceki pasife alma gerekçesi: {previousReason}"));
    await db.SaveChangesAsync(ct);

    return Results.Ok(new
    {
        user = UserView(person, now),
        temporaryPassword = temporary,
        note = "Hesap etkinleştirildi. Yeni geçici parola YALNIZCA şimdi gösteriliyor.",
    });
})
.WithSummary("Pasif hesabı etkinleştirir; yeni geçici parola üretir.");

app.MapGet("/admin/audit", async (AuthService auth, HttpRequest http,
                                  MaintenanceDbContext db, int? limit, CancellationToken ct) =>
{
    var (_, denied) = await RequireAsync(auth, http, Permissions.UsersManage, ct);
    if (denied is not null) return denied;

    var take = Math.Clamp(limit ?? 100, 1, 500);
    var events = await db.UserAuditEvents.AsNoTracking()
        .OrderByDescending(e => e.At)
        .ThenByDescending(e => e.Id)
        .Take(take)
        .ToListAsync(ct);

    return Results.Ok(new
    {
        count = events.Count,
        items = events.Select(e => new
        {
            e.Id, e.At, e.Action,
            actionLabel = UserAuditActions.Label(e.Action),
            e.TargetId, e.TargetEmployeeNo, e.TargetName,
            e.ActorEmployeeNo, e.ActorName, e.Detail,
        }),
    });
})
.WithSummary("Kullanıcı hesabı denetim izi — en yeni üstte.");

// ---------------------------------------------------------------------------
// Kök neden analizi — MH04 (Faz 12.5)
// ---------------------------------------------------------------------------
//
// Okuma uç noktaları açık (iş emirleri gibi): bir arızanın neden olduğu
// bilgisi saklanacak bir şey değil, öğrenilecek bir şeydir. Yazmak
// `engineering.rca` ister.
//
// Sıra önemli: sabit yollar (/rca/schema, /rca/pending, /rca/similar)
// parametreli bir yoldan önce tanımlanmalı. Burada /rca/{id} yok, ama
// /workorders/summary'deki dersi unutmamak için yine de üstte.

app.MapGet("/rca/schema", () => Results.Ok(new
{
    failureModes = Enum.GetValues<FailureMode>()
        .Select(m => new { code = m.ToString(), label = RcaRules.Label(m) }),
    textMin = RcaRules.TextMin,
    textMax = RcaRules.TextMax,
    criticalPriority = RcaRules.CriticalPriority,
    requiredWhen = new[]
    {
        $"Tamamlanmış iş emrinin önceliği ≥ {RcaRules.CriticalPriority:0.0}",
        "Tamamlanmış onarım ya da değişim işi",
    },
}))
.WithSummary("Arıza türleri ve RCA kuralları.");

app.MapGet("/rca/pending", async (RcaRepository repo, CancellationToken ct) =>
{
    var orders = await repo.PendingAsync(ct);
    var now = DateTime.UtcNow;
    return Results.Ok(new
    {
        count = orders.Count,
        items = orders.Select(o => new
        {
            workOrder = o,
            requiredBecause = RcaRules.RequiredBecause(o),
            waitingDays = o.CompletedAt is null
                ? (int?)null
                : (int)(now - o.CompletedAt.Value).TotalDays,
        }),
    });
})
.WithSummary("Kök neden analizi bekleyen tamamlanmış kritik işler.");

app.MapGet("/rca", async (RcaRepository repo, string? transformerId,
                          string? failureMode, CancellationToken ct) =>
{
    FailureMode? mode = Enum.TryParse<FailureMode>(failureMode, out var m) ? m : null;
    var items = await repo.ListAsync(transformerId, mode, ct);
    return Results.Ok(new { count = items.Count, items });
})
.WithSummary("Kayıtlı kök neden analizleri.");

app.MapGet("/rca/similar", async (RcaRepository repo, string transformerId,
                                  string? failureMode, string? excludeWorkOrderId,
                                  CancellationToken ct) =>
{
    FailureMode? mode = Enum.TryParse<FailureMode>(failureMode, out var m) ? m : null;
    var past = await repo.ListAsync(ct: ct);
    var items = RcaRules.Similar(transformerId, mode, past, excludeWorkOrderId);
    return Results.Ok(new { count = items.Count, items });
})
.WithSummary("Benzer geçmiş analizler (aynı arıza türü / aynı trafo).");

app.MapGet("/workorders/{id}/rca",
    async (WorkOrderRepository orders, RcaRepository repo, string id, CancellationToken ct) =>
{
    var order = await orders.GetAsync(id);
    if (order is null)
        return Results.NotFound(new { message = $"İş emri bulunamadı: {id}" });

    var rca = await repo.GetByWorkOrderAsync(id, ct);
    var past = await repo.ListAsync(ct: ct);
    return Results.Ok(new
    {
        workOrder = order,
        required = RcaRules.IsRequired(order),
        requiredBecause = RcaRules.RequiredBecause(order),
        rca,
        similar = RcaRules.Similar(order.TransformerId, rca?.FailureMode, past, id),
    });
})
.WithSummary("İş emrinin kök neden analizi (varsa) ve benzer geçmiş analizler.");

app.MapPost("/workorders/{id}/rca",
    async (WorkOrderRepository orders, RcaRepository repo, AuthService auth,
           HttpRequest http, string id, CreateRcaRequest request, CancellationToken ct) =>
{
    var (me, denied) = await RequireAsync(auth, http, Permissions.EngineeringRca, ct);
    if (denied is not null) return denied;

    var order = await orders.GetAsync(id);
    var existing = order is null ? null : await repo.GetByWorkOrderAsync(id, ct);
    if (RcaRules.CanRecord(order, existing is not null) is { } block)
        return Results.Json(new { message = block.Message }, statusCode: block.Status);

    var (mode, problems) = RcaRules.Validate(request);
    if (problems.Count > 0)
        return Results.BadRequest(new { message = "Kök neden analizi kaydedilemedi.", problems });

    var rca = new RootCauseAnalysis
    {
        Id = $"RCA-{order!.Seq:D4}",
        WorkOrderId = order.Id,
        TransformerId = order.TransformerId,
        FailureMode = mode!.Value,
        Finding = request.Finding!.Trim(),
        RootCause = request.RootCause!.Trim(),
        CorrectiveAction = request.CorrectiveAction!.Trim(),
        PreventiveAction = string.IsNullOrWhiteSpace(request.PreventiveAction)
            ? null
            : request.PreventiveAction.Trim(),
        RecordedAt = DateTime.UtcNow,
        RecordedById = me!.Id,
        RecordedByName = me.Name,
        RecordedByEmployeeNo = me.EmployeeNo,
    };

    var saved = await repo.AddAsync(rca, ct);
    return saved is null
        ? Results.Conflict(new { message = "Bu iş emri için az önce başka bir kök neden analizi kaydedildi." })
        : Results.Created($"/workorders/{id}/rca", saved);
})
.WithSummary("Tamamlanmış iş emrine kök neden analizi yazar (Mühendislik).");

app.Run();

// Belirteç "Authorization: Bearer <token>" başlığından okunur.
// Standart biçim; ileride gerçek bir kimlik sağlayıcıya geçilirse
// istemci tarafında değişiklik gerekmez.
// Kullanıcı hesabının yönetim ekranındaki görünümü. Technician nesnesini
// doğrudan döndürmüyoruz: kimlik alanları [JsonIgnore] ile gizli, ama
// yönetim ekranı kilit ve son giriş bilgisini GÖRMELİ. Neyi açtığımızı tek
// yerde, açıkça seçiyoruz. Parola özeti ve tuzu burada da YOK.
static object UserView(Technician t, DateTime now) => new
{
    t.Id,
    t.EmployeeNo,
    t.Name,
    role = t.Role.ToString(),
    specialty = t.Specialty.ToString(),
    department = t.Department.ToString(),
    departmentName = DepartmentCatalog.Name(t.Department),
    t.MaxOpenOrders,
    t.IsActive,
    mustChangePassword = t.MustChangePassword,
    locked = t.LockedUntil is { } until && until > now,
    lockedUntil = t.LockedUntil,
    failedAttempts = t.FailedAttempts,
    lastLoginAt = t.LastLoginAt,
    passwordChangedAt = t.PasswordChangedAt,
    createdAt = t.CreatedAt,
    createdByName = t.CreatedByName,
    deactivatedAt = t.DeactivatedAt,
    deactivationReason = t.DeactivationReason,
};

// ⚠ DEMO geçici parola kuralı. Bu parolayla açılan oturumun yetki listesi
// boş olduğu için tahmin edilebilir olması zarar vermez (bkz. açılış bloğu).
static string DemoTemporaryPassword(string employeeNo) => $"Demo-{employeeNo}";

static string? ReadToken(HttpRequest http)
{
    var header = http.Headers.Authorization.ToString();
    if (string.IsNullOrWhiteSpace(header)) return null;
    return header.StartsWith("Bearer ", StringComparison.OrdinalIgnoreCase)
        ? header["Bearer ".Length..].Trim()
        : header.Trim();
}

// Oturum ve yetki kontrolü (Faz 10).
//
// Her korunan uç nokta ilk satırında bunu çağırır. İki farklı cevap var:
//   401 — "kim olduğunu bilmiyorum" (giriş yok ya da oturum bitmiş)
//   403 — "kim olduğunu biliyorum ama bu işe yetkin yok"
// Arayüz birinde giriş ekranına, diğerinde "yetkiniz yok" mesajına gider.
//
// Ret mesajı işi KİME yönlendireceğini de söyler: "yetkiniz yok" tek
// başına kullanıcıyı çıkmazda bırakır.
static async Task<(Technician? Me, IResult? Denied)> RequireAsync(
    AuthService auth, HttpRequest http, string permission, CancellationToken ct)
{
    var me = await auth.ResolveAsync(ReadToken(http), DateTime.UtcNow, ct);
    if (me is null)
        return (null, Results.Json(
            new { message = "Oturum gerekli. Lütfen giriş yapın." },
            statusCode: StatusCodes.Status401Unauthorized));

    // Geçici parolalı oturum HİÇBİR korumalı işlem yapamaz. Bu kontrol
    // şart, çünkü .NET yetkiyi belirteçten değil DEPARTMANDAN okuyor:
    // belirteçteki boş yetki listesi burada tek başına işe yaramazdı.
    if (me.MustChangePassword)
        return (me, Results.Json(new
        {
            message = "Önce geçici parolanızı değiştirmelisiniz.",
            code = "password_change_required",
            requiredPermission = permission,
        }, statusCode: StatusCodes.Status403Forbidden));

    if (!Permissions.Has(me.Department, permission))
        return (me, Results.Json(new
        {
            message = $"Bu işlem için yetkiniz yok: {Permissions.Label(permission)}. " +
                      $"Departmanınız: {DepartmentCatalog.Name(me.Department)}.",
            requiredPermission = permission,
            department = me.Department.ToString(),
            grantedTo = DepartmentCatalog.WithPermission(permission),
        }, statusCode: StatusCodes.Status403Forbidden));

    return (me, null);
}