using System.Net.Http.Json;
using System.Text.Json;
using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Services;

/// <summary>
/// Python ML servisine (FastAPI, :8000) giden istemci.
/// </summary>
/// <remarks>
/// <b>BAĞIMLILIK ENJEKSİYONU (DI) — .NET'in kalbi</b>
///
/// Bu sınıf kendi <c>HttpClient</c>'ını YARATMAZ; kurucusundan (constructor)
/// hazır alır. Fark önemli:
///
/// <code>
/// // KÖTÜ: sınıf kendi bağımlılığını yaratıyor
/// public class MlServiceClient {
///     private readonly HttpClient _http = new HttpClient();  // adres nerede?
/// }
///
/// // İYİ: dışarıdan alıyor
/// public MlServiceClient(HttpClient http) { _http = http; }
/// </code>
///
/// Neden iyi?
/// 1. <b>Test edilebilirlik.</b> Testte sahte bir HttpClient verip Python
///    servisi olmadan test yazabiliriz.
/// 2. <b>Ayar tek yerde.</b> Adres Program.cs'te, appsettings.json'dan
///    okunuyor. Sınıf "hangi adres?" sorusunu hiç bilmiyor.
/// 3. <b>Kaynak yönetimi.</b> HttpClient'ı elle <c>new</c> ile yaratmak
///    .NET'te klasik bir hatadır: soket tükenmesine yol açar. Fabrika
///    (AddHttpClient) bağlantıları havuzlar.
///
/// Python'da bunu elle yapardık: fonksiyona parametre geçmek. .NET'te
/// çerçeve otomatik yapar — sınıfın kurucusuna bakar, ihtiyacı olan
/// nesneleri bulur ve verir. Buna "enjeksiyon" denmesinin sebebi bu.
/// </remarks>
public class MlServiceClient
{
    private readonly HttpClient _http;
    private readonly ILogger<MlServiceClient> _logger;

    // JSON okuma ayarları. Python snake_case, C# PascalCase yazar;
    // bu politika ikisini otomatik eşler (needs_review -> NeedsReview).
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
        PropertyNameCaseInsensitive = true,
    };

    // ILogger de enjekte ediliyor. Python'daki logging modülünün karşılığı;
    // biz yaratmıyoruz, çerçeve veriyor.
    public MlServiceClient(HttpClient http, ILogger<MlServiceClient> logger)
    {
        _http = http;
        _logger = logger;
    }

    /// <summary>ML servisi ayakta mı?</summary>
    public async Task<bool> IsAvailableAsync(CancellationToken ct = default)
    {
        try
        {
            var response = await _http.GetAsync("/health", ct);
            return response.IsSuccessStatusCode;
        }
        catch (HttpRequestException)
        {
            // Servis kapalıysa istisna fırlar. Bu BEKLENEN bir durumdur,
            // hata değil: "şu an erişilemiyor" bilgisine çeviriyoruz.
            return false;
        }
    }

    /// <summary>Filonun tamamını riskleriyle birlikte getirir.</summary>
    /// <returns>Servise ulaşılamazsa <c>null</c>.</returns>
    public async Task<FleetOverview?> GetFleetAsync(CancellationToken ct = default)
    {
        try
        {
            // GetFromJsonAsync: iste + JSON'u oku + tipe çevir, tek satırda.
            // Python'daki httpx.get(...).json() zincirinin karşılığı, ama
            // sonuç sözlük değil, TİPLİ bir nesne. Yanlış alan adı yazarsan
            // derlenmez.
            return await _http.GetFromJsonAsync<FleetOverview>(
                "/fleet/overview", JsonOptions, ct);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            // "when" filtresi: sadece bu iki istisna türünü yakala,
            // diğerlerini yukarı bırak. Her hatayı yutmak kötü alışkanlıktır;
            // beklenmeyen hatalar görünür kalmalı.
            _logger.LogWarning(ex, "ML servisine ulaşılamadı ({BaseAddress})",
                               _http.BaseAddress);
            return null;
        }
    }

    /// <summary>Tek bir trafonun güncel risk bilgisi.</summary>
    public async Task<TransformerRisk?> GetTransformerAsync(
        string id, CancellationToken ct = default)
    {
        var fleet = await GetFleetAsync(ct);

        // ML servisinde "tek trafo" uç noktası yok; filo listesinden süzüyoruz.
        // 9 varlık için fazlasıyla yeterli. Python servisini DEĞİŞTİRMİYORUZ
        // (Faz 7 kuralı): tüketen taraf kendi ihtiyacına uyum sağlar.
        return fleet?.Transformers
            .FirstOrDefault(t => string.Equals(t.Id, id,
                                               StringComparison.OrdinalIgnoreCase));
    }
}
