// TransformerAI — Bakım Planlama Servisi
//
// Uygulamanın başladığı yer. Python tarafındaki app/main.py'nin karşılığı.
//
// Bu dosyada "Minimal API" yazım stili kullanılıyor: uç noktalar doğrudan
// burada tanımlanıyor. FastAPI'deki @app.get(...) dekoratörünün karşılığı
// app.MapGet(...) çağrısıdır.

using System.Text.Json.Serialization;
using TransformerAI.Maintenance.Api.Data;
using TransformerAI.Maintenance.Api.Models;

// 1) İnşaatçı (builder): uygulamanın kurulum aşaması.
//    Python'da "app = FastAPI()" tek satırdı; .NET bunu ikiye ayırır —
//    önce SERVİSLERİ kaydedersin, sonra uygulamayı inşa edersin.
var builder = WebApplication.CreateBuilder(args);

// 2) Servis kaydı. Buraya kaydedilen her şey uygulamanın her yerinden
//    istenebilir hale gelir (bağımlılık enjeksiyonu — 7.4'te detaylıca).
builder.Services.AddOpenApi();

// JSON'da enum'lar VARSAYILAN OLARAK SAYIDIR: {"status": 0}.
// Bu hem okunmaz hem de kırılgan — sıralamayı değiştirirsek anlam kayar.
// JsonStringEnumConverter ile metne çeviriyoruz: {"status": "Planned"}.
// Hem istek gövdesini okurken hem de cevabı yazarken geçerli olur.
builder.Services.ConfigureHttpJsonOptions(options =>
{
    options.SerializerOptions.Converters.Add(new JsonStringEnumConverter());
});

// İş emri deposu. AddSingleton = "uygulama boyunca TEK bir örnek olsun".
// Bellekte tuttuğumuz için tek örnek şart: her istek yeni bir depo alsaydı
// veriler kaybolurdu. 7.3'te bunun yerini veritabanı alacak.
builder.Services.AddSingleton<WorkOrderStore>();

var app = builder.Build();

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
    version = "0.2.0",
    role = "İş emri, teknisyen atama ve bakım planlama",
    mlService = "Python/FastAPI (risk ve tanı buradan okunur)",
})
.WithName("ServiceInfo");

app.MapGet("/health", () => new { status = "ok" })
   .WithName("Health");

// ---------------------------------------------------------------------------
// İş emirleri
// ---------------------------------------------------------------------------

// Listeleme. Sorgu parametreleri (?status=Planned&transformerId=TR-01)
// doğrudan fonksiyon parametresi olarak alınır — FastAPI'deki gibi.
// ASP.NET Core metin değeri otomatik olarak enum'a çevirir; çeviremezse
// isteği 400 ile reddeder. Doğrulamayı elle yazmıyoruz, tip sistemi yapıyor.
app.MapGet("/workorders", (WorkOrderStore store,
                           WorkOrderStatus? status,
                           string? transformerId) =>
{
    var items = store.List(status, transformerId);
    return Results.Ok(new { count = items.Count, items });
})
.WithName("ListWorkOrders");

// Tekil kayıt. {id} kısmı yol parametresi (route parameter).
// Python: @app.get("/workorders/{id}")
app.MapGet("/workorders/{id}", (WorkOrderStore store, string id) =>
{
    var order = store.Get(id);

    // Results.X yardımcıları HTTP durum kodunu belirler:
    //   Ok       -> 200   NotFound -> 404
    //   Created  -> 201   BadRequest -> 400
    // FastAPI'de HTTPException fırlatırdık; burada değer olarak döndürüyoruz.
    return order is null
        ? Results.NotFound(new { message = $"İş emri bulunamadı: {id}" })
        : Results.Ok(order);
})
.WithName("GetWorkOrder");

// Oluşturma. Gövde (body) otomatik olarak CreateWorkOrderRequest'e çevrilir.
app.MapPost("/workorders", (WorkOrderStore store, CreateWorkOrderRequest request) =>
{
    // Tip sistemi "bu alan string mi?" sorusunu çözer ama "boş mu?" sorusunu
    // çözmez. İş kuralları hâlâ elle doğrulanır.
    if (string.IsNullOrWhiteSpace(request.TransformerId))
    {
        return Results.BadRequest(new { message = "transformerId zorunludur." });
    }

    if (string.IsNullOrWhiteSpace(request.Title))
    {
        return Results.BadRequest(new { message = "title zorunludur." });
    }

    var order = store.Add(request);

    // 201 Created + Location başlığı: yeni kaynağın adresini söyler.
    // REST geleneği budur; sadece 200 dönmekten daha doğrudur.
    return Results.Created($"/workorders/{order.Id}", order);
})
.WithName("CreateWorkOrder");

// Durum güncelleme. PATCH = "kaydın bir kısmını değiştir"
// (PUT ise "kaydın tamamını değiştir" demektir).
app.MapPatch("/workorders/{id}/status",
    (WorkOrderStore store, string id, UpdateStatusRequest request) =>
{
    var order = store.UpdateStatus(id, request);
    return order is null
        ? Results.NotFound(new { message = $"İş emri bulunamadı: {id}" })
        : Results.Ok(order);
})
.WithName("UpdateWorkOrderStatus");

// Özet: panoda gösterilecek sayımlar.
app.MapGet("/workorders/summary", (WorkOrderStore store) => store.Summary())
   .WithName("WorkOrderSummary");

app.Run();
