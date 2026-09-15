using TransformerAI.Maintenance.Api.Services;

namespace TransformerAI.Maintenance.Tests;

/// <summary>Parola özetleme testleri. (Faz 9.0b'de PIN için yazıldı)</summary>
/// <remarks>
/// Güvenlik kodunun hataları SESSİZDİR: düz metin saklayan, tuz
/// kullanmayan ya da yanlış karşılaştıran bir uygulama hiçbir ekranda
/// belli olmadan çalışmaya devam eder. Bu yüzden burada test edilen şey
/// "çalışıyor mu" değil, <b>doğru şekilde mi çalışıyor</b>.
/// </remarks>
public class PasswordHasherTests
{
    private const string Password = "Kademe-Revizyon-2026";

    [Fact]
    public void Dogru_parola_dogrulanir()
    {
        var (hash, salt) = PasswordHasher.Hash(Password);
        Assert.True(PasswordHasher.Verify(Password, hash, salt));
    }

    [Fact]
    public void Yanlis_parola_reddedilir()
    {
        var (hash, salt) = PasswordHasher.Hash(Password);
        Assert.False(PasswordHasher.Verify("Kademe-Revizyon-2025", hash, salt));
        Assert.False(PasswordHasher.Verify("", hash, salt));
        Assert.False(PasswordHasher.Verify(Password + " ", hash, salt));
        // Büyük/küçük harf duyarlı:
        Assert.False(PasswordHasher.Verify(Password.ToLowerInvariant(), hash, salt));
    }

    [Fact]
    public void Parola_duz_metin_olarak_SAKLANMAZ()
    {
        var (hash, salt) = PasswordHasher.Hash(Password);
        Assert.DoesNotContain("Kademe", hash);
        Assert.DoesNotContain("Kademe", salt);
    }

    [Fact]
    public void Ayni_parola_farkli_ozet_uretir()
    {
        // Tuzun varlık sebebi: aynı parolayı seçen iki kişinin kaydı aynı
        // görünmemeli, biri çözülünce diğeri çözülmemeli.
        var a = PasswordHasher.Hash(Password);
        var b = PasswordHasher.Hash(Password);

        Assert.NotEqual(a.Salt, b.Salt);
        Assert.NotEqual(a.Hash, b.Hash);
        Assert.True(PasswordHasher.Verify(Password, a.Hash, a.Salt));
        Assert.True(PasswordHasher.Verify(Password, b.Hash, b.Salt));
    }

    [Fact]
    public void Yanlis_tuzla_dogrulama_basarisiz()
    {
        var a = PasswordHasher.Hash(Password);
        var b = PasswordHasher.Hash(Password);
        Assert.False(PasswordHasher.Verify(Password, a.Hash, b.Salt));
    }

    [Fact]
    public void Bozuk_kayit_dogrulamayi_patlatmaz()
    {
        // Bozuk tek bir kayıt giriş uç noktasını tamamen düşürmemeli.
        Assert.False(PasswordHasher.Verify(Password, "bu-base64-degil!", "***"));
        Assert.False(PasswordHasher.Verify(Password, "", ""));
    }

    [Fact]
    public void Asiri_uzun_girdi_ozetlenmeden_reddedilir()
    {
        // 1 MB'lık "parola" ile 100.000 tur PBKDF2, tek istekle sunucuyu
        // meşgul edebilirdi.
        var (hash, salt) = PasswordHasher.Hash(Password);
        Assert.False(PasswordHasher.Verify(new string('a', 1_000_000), hash, salt));
    }

    [Fact]
    public void Bos_parola_ozetlenemez()
    {
        Assert.Throws<ArgumentException>(() => PasswordHasher.Hash(""));
        Assert.Throws<ArgumentException>(() => PasswordHasher.Hash("   "));
    }
}
