using System.Security.Cryptography;

namespace TransformerAI.Maintenance.Api.Services;

/// <summary>Parola özetleme ve doğrulama. (Faz 9.0b'de PIN için yazıldı)</summary>
/// <remarks>
/// Sistem Yönetimi fazında 4 haneli PIN'den en az 10 karakterli parolaya
/// geçildi. Algoritma DEĞİŞMEDİ — değişmesine gerek de yoktu: özetleme,
/// neyin özetlendiğinden bağımsızdır. Değişen, girdinin gücü.
///
/// <b>ÖZETLEME (hashing) ŞİFRELEME DEĞİLDİR.</b> Bu ayrım öğrenilmesi
/// gereken en önemli şey:
///
/// <list type="bullet">
/// <item>Şifreleme <i>geri döndürülebilir</i>: anahtarla açarsın.</item>
/// <item>Özetleme <i>tek yönlüdür</i>: geri döndürülemez.</item>
/// </list>
///
/// Parolayı şifreleyip saklamak YANLIŞ olurdu, çünkü sistemin anahtarı
/// olsaydı sistemi ele geçiren parolaları da açardı. Özetlemede böyle bir
/// anahtar yok — veritabanı bütünüyle sızsa bile parolalar okunamaz.
/// Doğrulama, girilen parolanın özetini hesaplayıp saklanan özetle
/// karşılaştırarak yapılır. Bu yüzden Sistem Yöneticisi de kimsenin
/// parolasını GÖREMEZ; yalnızca sıfırlayabilir.
///
/// <b>TUZ (salt) neden gerekli?</b> Özetleme aynı girdiye hep aynı
/// çıktıyı verir. Tuz olmasaydı, parolası aynı olan herkesin özeti aynı
/// olurdu — saldırgan bir tanesini çözse hepsini çözerdi. Kişiye özel tuz,
/// her kaydı ayrı bir probleme dönüştürür ve önceden hesaplanmış
/// tabloları (rainbow table) işe yaramaz kılar.
///
/// <b>Neden PBKDF2 ve neden 100.000 tur?</b> SHA-256 gibi hızlı bir
/// özetleyici burada DEZAVANTAJDIR: saldırgan saniyede milyarlarca
/// deneme yapar. PBKDF2 özetlemeyi kasten yavaşlatır. 100.000 tur,
/// giriş yapan kullanıcı için fark edilmez (~100 ms) ama kaba kuvvet
/// saldırısının maliyetini 100.000 katına çıkarır.
/// </remarks>
public static class PasswordHasher
{
    // Tur sayısı. Donanım hızlandıkça artırılmalı; bu yüzden sabit tek
    // yerde duruyor.
    private const int Iterations = 100_000;
    private const int SaltBytes = 16;
    private const int HashBytes = 32;

    private static readonly HashAlgorithmName Algorithm = HashAlgorithmName.SHA256;

    /// <summary>Yeni bir parola için tuz ve özet üretir.</summary>
    public static (string Hash, string Salt) Hash(string password)
    {
        if (string.IsNullOrWhiteSpace(password))
            throw new ArgumentException("Parola boş olamaz.", nameof(password));

        // RandomNumberGenerator: kriptografik olarak güvenli rastgelelik.
        // Random sınıfı BURADA KULLANILMAZ — tahmin edilebilir üretir ve
        // tuzun tüm amacı tahmin edilemez olmasıdır.
        var salt = RandomNumberGenerator.GetBytes(SaltBytes);
        var hash = Derive(password, salt);

        return (Convert.ToBase64String(hash), Convert.ToBase64String(salt));
    }

    /// <summary>Girilen parola, saklanan özetle eşleşiyor mu?</summary>
    public static bool Verify(string password, string hash, string salt)
    {
        if (string.IsNullOrWhiteSpace(password) ||
            string.IsNullOrWhiteSpace(hash) ||
            string.IsNullOrWhiteSpace(salt))
            return false;

        // Aşırı uzun girdi: özetlemeden ÖNCE reddedilir. 1 MB'lık bir
        // "parola" ile 100.000 tur PBKDF2, tek istekle sunucuyu meşgul
        // edebilirdi (hizmet dışı bırakma).
        if (password.Length > PasswordPolicy.MaxLength)
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

        var actual = Derive(password, saltBytes);

        // FixedTimeEquals: karşılaştırmayı SABİT SÜREDE yapar.
        //
        // Neden normal karşılaştırma olmuyor? Sıradan bir karşılaştırma
        // ilk farklı bayta rastlayınca durur. Saldırgan yanıt süresini
        // ölçerek "ilk bayt doğruydu, ikincisi yanlıştı" bilgisini
        // çıkarabilir ve özeti bayt bayt tahmin edebilir (zamanlama
        // saldırısı). Bu fonksiyon her zaman aynı süreyi harcar.
        return CryptographicOperations.FixedTimeEquals(actual, expected);
    }

    private static byte[] Derive(string password, byte[] salt) =>
        Rfc2898DeriveBytes.Pbkdf2(password, salt, Iterations, Algorithm, HashBytes);
}
