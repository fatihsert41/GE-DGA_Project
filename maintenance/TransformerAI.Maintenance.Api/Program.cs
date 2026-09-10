// TransformerAI — Bakım Planlama Servisi
//
// Uygulamanın başladığı yer. Python tarafındaki app/main.py'nin karşılığı.
//
// Bu dosyada "Minimal API" yazım stili kullanılıyor: uç noktalar doğrudan
// burada tanımlanıyor. FastAPI'deki @app.get(...) dekoratörünün karşılığı
// app.MapGet(...) çağrısıdır.

// 1) İnşaatçı (builder): uygulamanın kurulum aşaması.
//    Python'da "app = FastAPI()" tek satırdı; .NET bunu ikiye ayırır —
//    önce SERVİSLERİ kaydedersin, sonra uygulamayı inşa edersin.
var builder = WebApplication.CreateBuilder(args);

// 2) Servis kaydı. Buraya kaydedilen her şey uygulamanın her yerinden
//    istenebilir hale gelir (bağımlılık enjeksiyonu — 7.4'te detaylıca).
//    AddOpenApi: /openapi/v1.json adresinde API şeması üretir.
//    FastAPI'nin otomatik /docs sayfasının muadili.
builder.Services.AddOpenApi();

// 3) İnşa: artık uygulama hazır, uç nokta tanımlamaya geçebiliriz.
var app = builder.Build();

// 4) Sadece geliştirme ortamında API şemasını yayınla.
//    Üretimde iç yapıyı dışarı açmamak iyi bir alışkanlıktır.
if (app.Environment.IsDevelopment())
{
    app.MapOpenApi();
}

// ---------------------------------------------------------------------------
// Uç noktalar
// ---------------------------------------------------------------------------

// Kök: servis kimliği. Python tarafındaki "/" ile aynı işi yapıyor.
app.MapGet("/", () => new
{
    name = "TransformerAI Bakım Planlama Servisi",
    version = "0.1.0",
    role = "İş emri, teknisyen atama ve bakım planlama",
    mlService = "Python/FastAPI (risk ve tanı buradan okunur)",
})
.WithName("ServiceInfo");

// Sağlık kontrolü: servis ayakta mı? İzleme araçları bu adresi yoklar.
app.MapGet("/health", () => new { status = "ok" })
   .WithName("Health");

app.Run();
