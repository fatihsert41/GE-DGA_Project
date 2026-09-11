using System.Security.Cryptography;

namespace TransformerAI.Maintenance.Api.Services;

/// <summary>PIN özetleme ve doğrulama. (Faz 9.0b)</summary>
/// <remarks>
/// <b>ÖZETLEME (hashing) ŞİFRELEME DEĞİLDİR.</b> Bu ayrım öğrenilmesi
/// gereken en önemli şey:
///
/// <list type="bullet">
/// <item>Şifreleme <i>geri döndürülebilir</i>: anahtarla açarsın.</item>
/// <item>Özetleme <i>tek yönlüdür</i>: geri döndürülemez.</item>
/// </list>
///
/// PIN'i şifreleyip saklamak YANLIŞ olurdu, çünkü sistemin anahtarı
/// olsaydı sistemi ele geçiren PIN'leri de açardı. Özetlemede böyle bir
/// anahtar yok — veritabanı bütünüyle sızsa bile PIN'ler okunamaz.
/// Doğrulama, girilen PIN'in özetini hesaplayıp saklanan özetle
/// karşılaştırarak yapılır.
///
/// <b>TUZ (salt) neden gerekli?</b> Özetleme aynı girdiye hep aynı
/// çıktıyı verir. Tuz olmasaydı, PIN'i "1234" olan bütün personelin
/// özeti aynı olurdu — saldırgan bir tanesini çözse hepsini çözerdi.
/// Ayrıca 4 haneli PIN'in yalnızca 10.000 olasılığı var; önceden
/// hesaplanmış bir tablo (rainbow table) saniyeler içinde eşleştirirdi.
/// Kişiye özel tuz, her kaydı ayrı bir probleme dönüştürür.
///
/// <b>Neden PBKDF2 ve neden 100.000 tur?</b> SHA-256 gibi hızlı bir
/// özetleyici burada DEZAVANTAJDIR: saldırgan saniyede milyarlarca
/// deneme yapar. PBKDF2 özetlemeyi kasten yavaşlatır. 100.000 tur,
/// giriş yapan kullanıcı için fark edilmez (~100 ms) ama kaba kuvvet
/// saldırısının maliyetini 100.000 katına çıkarır.
///
/// ⚠ SINIR: 4-6 haneli bir PIN güçlü bir parola değildir. Bu sınıf
/// onu kabul edilebilir kılan iki şeyden birini sağlar (özetleme);
/// diğeri <b>deneme sınırlaması</b>dır ve <c>AuthService</c>'te. İkisi
/// birlikte banka kartı seviyesinde koruma verir: sicilini bilen birine
/// karşı korur, sistemi elinde tutan birine karşı değil.
/// </remarks>
public static class PinHasher
{
    // Tur sayısı. Donanım hızlandıkça artırılmalı; bu yüzden sabit tek
    // yerde ve saklanan kayıtla birlikte sürümlenebilir olmalı.
    private const int Iterations = 100_000;
    private const int SaltBytes = 16;
    private const int HashBytes = 32;

    private static readonly HashAlgorithmName Algorithm = HashAlgorithmName.SHA256;

    /// <summary>Yeni bir PIN için tuz ve özet üretir.</summary>
    public static (string Hash, string Salt) Hash(string pin)
    {
        if (string.IsNullOrWhiteSpace(pin))
            throw new ArgumentException("PIN boş olamaz.", nameof(pin));

        // RandomNumberGenerator: kriptografik olarak güvenli rastgelelik.
        // Random sınıfı BURADA KULLANILMAZ — tahmin edilebilir üretir ve
        // tuzun tüm amacı tahmin edilemez olmasıdır.
        var salt = RandomNumberGenerator.GetBytes(SaltBytes);
        var hash = Derive(pin, salt);

        return (Convert.ToBase64String(hash), Convert.ToBase64String(salt));
    }

    /// <summary>Girilen PIN, saklanan özetle eşleşiyor mu?</summary>
    public static bool Verify(string pin, string hash, string salt)
    {
        if (string.IsNullOrWhiteSpace(pin) ||
            string.IsNullOrWhiteSpace(hash) ||
            string.IsNullOrWhiteSpace(salt))
            return false;

        byte[] expected, saltBytes;
        try
        {
            expected = Convert.FromBase64String(hash);
            saltBytes = Convert.FromBase64String(salt);
        }
        catch (FormatException)
        {
            return false;      // bozuk kayıt: doğrulama başarısız sayılır
        }

        var actual = Derive(pin, saltBytes);

        // FixedTimeEquals: karşılaştırmayı SABİT SÜREDE yapar.
        //
        // Neden normal karşılaştırma olmuyor? Sıradan bir karşılaştırma
        // ilk farklı bayta rastlayınca durur. Saldırgan yanıt süresini
        // ölçerek "ilk bayt doğruydu, ikincisi yanlıştı" bilgisini
        // çıkarabilir ve özeti bayt bayt tahmin edebilir (zamanlama
        // saldırısı). Bu fonksiyon her zaman aynı süreyi harcar.
        return CryptographicOperations.FixedTimeEquals(actual, expected);
    }

    private static byte[] Derive(string pin, byte[] salt) =>
        Rfc2898DeriveBytes.Pbkdf2(pin, salt, Iterations, Algorithm, HashBytes);
}
