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
/// döner</b> ve .NET kapandığında Python'a kayıt girilemez.
///
/// Çözüm: belirteci <b>kendi kendini doğrulayabilir</b> hâle getirmek.
///
/// <code>
///     &lt;yük(base64)&gt;.&lt;imza(base64)&gt;
/// </code>
///
/// Yük kimliği açıkça taşır. İmza, paylaşılan gizli anahtarla hesaplanan
/// HMAC-SHA256'dır. Anahtarı bilmeden geçerli bir imza üretilemez.
///
/// <b>Bedeli: iptal penceresi — ve nasıl daraltıldı</b>
///
/// İmzalı belirteç tek başına <i>iptal edilemez</i>: Python, .NET'te
/// oturumun kapatıldığını bilemez. İlk sürümde bu pencere belirtecin
/// ömrü kadardı (9 saat).
///
/// Güvenlik sertleştirmesiyle belirtece <b>üretim zamanı</b>
/// (<c>issued_at_unix</c>) eklendi. Python en fazla 20 dakikalık belirteci
/// kabul ediyor; arayüz 10 dakikada bir <c>/auth/refresh</c> ile yeni
/// belirteç alıyor. Yenileme .NET'te oturum satırına bakar — kapatılmış
/// oturum yenilenemez. Böylece iptal penceresi 9 saatten <b>en fazla
/// 20 dakikaya</b> indi ve Python hâlâ .NET'e hiç sormuyor.
///
/// <b>GİZLİ ANAHTAR — hızlı başarısızlık</b>
///
/// Geliştirme anahtarı kaynak kodda ve <b>gizli değildir</b>. Onunla
/// çalışan bir üretim sunucusunda HERKES geçerli belirteç üretebilir.
/// Bu yüzden geliştirme ortamı DIŞINDA anahtar yoksa, geliştirme anahtarı
/// verilmişse ya da anahtar kısaysa servis açılmayı REDDEDER. Sessizce
/// güvensiz çalışmaktansa gürültüyle çalışmamak iyidir.
/// </remarks>
public class TokenIssuer
{
    /// <summary>Geliştirme anahtarı — GİZLİ DEĞİLDİR. Yalnızca Development ortamında.</summary>
    public const string DevelopmentSecret = "transformerai-dev-secret-degistirin";

    /// <summary>Gerçek anahtarın en az uzunluğu.</summary>
    /// <remarks>
    /// HMAC-SHA256 için 256 bit (32 bayt) anahtar önerilir. Karakter sayısı
    /// bayt sayısına eşit değil ama "en az 32 karakter" kısa, tahmin
    /// edilebilir anahtarları ("parola123") eler. Python tarafında aynı sınır.
    /// </remarks>
    public const int MinSecretLength = 32;

    /// <summary>Ortam değişkeninin adı — Python tarafıyla AYNI.</summary>
    public const string SecretVariable = "TRANSFORMERAI_AUTH_SECRET";

    private readonly byte[] _key;

    /// <summary>Geliştirme anahtarı mı kullanılıyor?</summary>
    public bool IsDevelopmentSecret { get; }

    /// <summary>Uygulamanın kullandığı kurucu (bağımlılık enjeksiyonu).</summary>
    public TokenIssuer(IConfiguration config, IHostEnvironment env)
        : this(Environment.GetEnvironmentVariable(SecretVariable) ?? config["Auth:SharedSecret"],
               env.IsDevelopment())
    {
    }

    /// <summary>Anahtarı doğrudan alan kurucu — testler için.</summary>
    public TokenIssuer(string? configuredSecret, bool isDevelopment)
    {
        var (secret, isDevSecret) = ResolveSecret(configuredSecret, isDevelopment);
        IsDevelopmentSecret = isDevSecret;
        _key = Encoding.UTF8.GetBytes(secret);
    }

    /// <summary>Kullanılacak anahtarı seçer; güvensiz yapılandırmada İSTİSNA fırlatır.</summary>
    /// <remarks>Saf fonksiyon: ortam okumaz, test edilebilir. Python'daki
    /// <c>auth.resolve_secret</c> ile aynı kurallar.</remarks>
    public static (string Secret, bool IsDevelopmentSecret) ResolveSecret(string? configured,
                                                                          bool isDevelopment)
    {
        if (string.IsNullOrWhiteSpace(configured))
        {
            if (isDevelopment)
                return (DevelopmentSecret, true);

            throw new InvalidOperationException(
                $"Belirteç imza anahtarı tanımlı değil. Geliştirme ortamı dışında " +
                $"{SecretVariable} ortam değişkeni ZORUNLU (en az {MinSecretLength} karakter). " +
                "Geliştirme anahtarı kaynak kodda ve gizli değildir; onunla çalışmak " +
                "herkesin geçerli belirteç üretebilmesi demektir.");
        }

        if (configured == DevelopmentSecret)
        {
            if (isDevelopment)
                return (DevelopmentSecret, true);
            throw new InvalidOperationException(
                "Geliştirme anahtarı geliştirme ortamı dışında kullanılamaz: kaynak kodda yazılı.");
        }

        if (configured.Length < MinSecretLength)
            throw new InvalidOperationException(
                $"Belirteç imza anahtarı çok kısa ({configured.Length} karakter); " +
                $"en az {MinSecretLength} karakter olmalı.");

        return (configured, false);
    }

    /// <summary>Belirteç yükü — kimliğin kendisi.</summary>
    /// <remarks>
    /// <c>nonce</c>: aynı kişi aynı saniyede iki kez giriş yaparsa aynı
    /// belirteç üretilmesin (oturum tablosunda birincil anahtar çakışması).
    ///
    /// <b>Yetkiler neden belirtecin içinde? (Faz 10)</b> Python servisi
    /// "bu kişi yağ testi girebilir mi?" sorusunu .NET'e sormadan
    /// cevaplamalı. İmza yükü kurcalanamaz kıldığı için güvenli.
    ///
    /// <b><c>IssuedAtUnix</c> (güvenlik sertleştirme):</b> Python'un
    /// belirteç yaşını ölçebilmesi için. 0 = eski belirteç (yaşı bilinmiyor);
    /// Python bunu REDDEDER.
    /// </remarks>
    public record Payload(
        string EmployeeNo,
        string Name,
        string Role,
        long ExpiresAtUnix,
        string Nonce,
        string Department = "",
        string DepartmentName = "",
        IReadOnlyList<string>? Permissions = null,
        long IssuedAtUnix = 0);

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.SnakeCaseLower,
    };

    /// <summary>Bir personel için imzalı belirteç üretir.</summary>
    /// <param name="person">Belirtecin sahibi.</param>
    /// <param name="issuedAtUtc">Üretim zamanı — Python yaşı buna göre ölçer.</param>
    /// <param name="expiresAtUtc">Bitiş zamanı (oturumun sonu).</param>
    /// <param name="permissions">Belirtece yazılacak yetkiler. Verilmezse
    /// departmanın yetkileri. Geçici parolalı oturumda BOŞ liste verilir.</param>
    public string Issue(Technician person, DateTime issuedAtUtc, DateTime expiresAtUtc,
                        IReadOnlyList<string>? permissions = null)
    {
        var payload = new Payload(
            person.EmployeeNo,
            person.Name,
            person.Role.ToString(),
            ToUnix(expiresAtUtc),
            Convert.ToBase64String(RandomNumberGenerator.GetBytes(12)),
            person.Department.ToString(),
            DepartmentCatalog.Name(person.Department),
            permissions ?? Models.Permissions.For(person.Department),
            ToUnix(issuedAtUtc));

        var json = JsonSerializer.SerializeToUtf8Bytes(payload, JsonOpts);
        var body = Base64Url(json);
        return $"{body}.{Base64Url(Sign(body))}";
    }

    /// <summary>İmzayı ve süreyi doğrular; geçersizse null.</summary>
    /// <remarks>
    /// Yaş sınırı burada YOK, bilinçli: .NET her istekte oturum satırına da
    /// baktığı için iptal anında etkili. Yaş sınırı yalnızca oturum tablosunu
    /// göremeyen Python için gerekli.
    /// </remarks>
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

    private static long ToUnix(DateTime utc) =>
        new DateTimeOffset(DateTime.SpecifyKind(utc, DateTimeKind.Utc)).ToUnixTimeSeconds();

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
