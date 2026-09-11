using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Services;

/// <summary>İmzalı oturum belirteci üretir ve doğrular. (Faz 9.0b)</summary>
/// <remarks>
/// <b>NEDEN İMZALI BELİRTEÇ — mimari bir zorunluluk</b>
///
/// Faz 7'de bir kural koymuştuk: <i>Python servisi .NET'i bilmez; .NET
/// onu dışarıdan tüketir.</i> Bu kural sayesinde .NET kapalıyken Python
/// çalışmaya devam ediyor.
///
/// Kimlik doğrulama bu kuralı tehdit ediyor: Python'un da "bu belirteç
/// geçerli mi?" sorusunu cevaplaması gerek. Naif çözüm Python'un .NET'e
/// HTTP isteği atması olurdu — ama o zaman <b>bağımlılık yönü tersine
/// döner</b> ve .NET kapandığında Python'a kayıt girilemez. Faz 7'de
/// özellikle kaçındığımız şey buydu.
///
/// Çözüm: belirteci <b>kendi kendini doğrulayabilir</b> hâle getirmek.
/// Belirteç iki parçadan oluşur:
///
/// <code>
///     &lt;yük(base64)&gt;.&lt;imza(base64)&gt;
/// </code>
///
/// Yük kimliği açıkça taşır (sicil, ad, rol, bitiş). İmza, paylaşılan
/// gizli anahtarla hesaplanan HMAC-SHA256'dır. Anahtarı bilmeden geçerli
/// bir imza üretilemez, dolayısıyla yük kurcalanamaz. Python anahtarı
/// bildiği için imzayı <b>tek başına</b> doğrular — ağ isteği yok,
/// bağımlılık yok.
///
/// <b>Bedeli ve onu neden kabul ediyoruz</b>
///
/// İmzalı belirteç <i>iptal edilemez</i>: Python, .NET'te oturumun
/// kapatıldığını bilemez. Yani bir belirteç kapatıldıktan sonra da
/// süresi dolana kadar Python tarafında geçerli kalır.
///
/// Bu yüzden .NET <b>her iki mekanizmayı birden</b> kullanır: imzayı
/// doğrular VE oturum satırının hâlâ var olduğunu kontrol eder. Böylece
/// .NET tarafında iptal anında etkilidir; Python tarafında iptal
/// penceresi belirtecin ömrü kadardır.
///
/// Bu, dağıtık sistemlerdeki klasik ödünleşimdir ve bilinçli seçilmiştir:
/// <b>Python'un ayakta kalması, Python tarafındaki anlık iptalden daha
/// değerlidir.</b> Kaydın kim tarafından girildiğini yanlış bilmek değil
/// söz konusu olan; en fazla, işten ayrılmış birinin belirteci birkaç
/// saat daha kayıt girebilir — ve o kayıt yine kendi adına yazılır,
/// yani izlenebilirlik bozulmaz.
///
/// ⚠ GİZLİ ANAHTAR: Demo için sabit bir geliştirme anahtarı kullanılıyor
/// ve bu, kaynak koda gömülü olduğu için <b>gizli değildir</b>. Gerçek
/// kurulumda ortam değişkeninden ya da bir sır yöneticisinden okunmalı.
/// Uygulama, geliştirme anahtarıyla çalışırken açılışta uyarı basar.
/// </remarks>
public class TokenIssuer
{
    /// <summary>Geliştirme anahtarı — GİZLİ DEĞİLDİR.</summary>
    public const string DevelopmentSecret = "transformerai-dev-secret-degistirin";

    private readonly byte[] _key;

    /// <summary>Geliştirme anahtarı mı kullanılıyor?</summary>
    public bool IsDevelopmentSecret { get; }

    public TokenIssuer(IConfiguration config)
    {
        // Öncelik: ortam değişkeni > appsettings > geliştirme anahtarı.
        var secret = Environment.GetEnvironmentVariable("TRANSFORMERAI_AUTH_SECRET")
                     ?? config["Auth:SharedSecret"];

        IsDevelopmentSecret = string.IsNullOrWhiteSpace(secret);
        if (IsDevelopmentSecret) secret = DevelopmentSecret;

        _key = Encoding.UTF8.GetBytes(secret!);
    }

    /// <summary>Belirteç yükü — kimliğin kendisi.</summary>
    /// <remarks>
    /// <c>nonce</c> (tek kullanımlık rastgele değer) neden var? Aynı
    /// kişi, aynı saniyede iki kez giriş yaparsa aynı belirteç üretilirdi
    /// ve ikisi tek oturum satırına düşerdi (birincil anahtar çakışması).
    /// Ayrıca belirtecin tahmin edilebilirliğini de kırar.
    /// </remarks>
    public record Payload(
        string EmployeeNo,
        string Name,
        string Role,
        long ExpiresAtUnix,
        string Nonce);

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
    };

    /// <summary>Bir personel için imzalı belirteç üretir.</summary>
    public string Issue(Technician person, DateTime expiresAtUtc)
    {
        var payload = new Payload(
            person.EmployeeNo,
            person.Name,
            person.Role.ToString(),
            new DateTimeOffset(expiresAtUtc, TimeSpan.Zero).ToUnixTimeSeconds(),
            Convert.ToBase64String(RandomNumberGenerator.GetBytes(12)));

        var json = JsonSerializer.SerializeToUtf8Bytes(payload, JsonOpts);
        var body = Base64Url(json);
        return $"{body}.{Base64Url(Sign(body))}";
    }

    /// <summary>İmzayı ve süreyi doğrular; geçersizse null.</summary>
    public Payload? Verify(string? token, DateTime nowUtc)
    {
        if (string.IsNullOrWhiteSpace(token)) return null;

        var parts = token.Split('.');
        if (parts.Length != 2) return null;

        byte[] expected;
        try { expected = FromBase64Url(parts[1]); }
        catch (FormatException) { return null; }

        // Sabit süreli karşılaştırma — zamanlama saldırısına karşı.
        if (!CryptographicOperations.FixedTimeEquals(Sign(parts[0]), expected))
            return null;

        Payload? payload;
        try
        {
            payload = JsonSerializer.Deserialize<Payload>(
                FromBase64Url(parts[0]), JsonOpts);
        }
        catch (Exception e) when (e is FormatException or JsonException)
        {
            return null;
        }

        if (payload is null) return null;

        var expires = DateTimeOffset.FromUnixTimeSeconds(payload.ExpiresAtUnix);
        return expires.UtcDateTime <= nowUtc ? null : payload;
    }

    private byte[] Sign(string body) =>
        HMACSHA256.HashData(_key, Encoding.UTF8.GetBytes(body));

    // Base64Url: standart base64'teki '+', '/' ve '=' karakterleri URL ve
    // HTTP başlıklarında sorun çıkarır. Bu varyant onları değiştirir.
    private static string Base64Url(byte[] data) =>
        Convert.ToBase64String(data)
               .TrimEnd('=').Replace('+', '-').Replace('/', '_');

    private static byte[] FromBase64Url(string text)
    {
        var s = text.Replace('-', '+').Replace('_', '/');
        return Convert.FromBase64String(s.PadRight((s.Length + 3) / 4 * 4, '='));
    }
}
