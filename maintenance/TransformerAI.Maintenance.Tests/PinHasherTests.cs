using TransformerAI.Maintenance.Api.Services;

namespace TransformerAI.Maintenance.Tests;

/// <summary>PIN özetleme testleri. (Faz 9.0b)</summary>
/// <remarks>
/// Güvenlik kodunun hataları SESSİZDİR: düz metin saklayan, tuz
/// kullanmayan ya da yanlış karşılaştıran bir uygulama hiçbir ekranda
/// belli olmadan çalışmaya devam eder. Bu yüzden burada test edilen şey
/// "çalışıyor mu" değil, <b>doğru şekilde mi çalışıyor</b>.
/// </remarks>
public class PinHasherTests
{
    [Fact]
    public void Dogru_pin_dogrulanir()
    {
        var (hash, salt) = PinHasher.Hash("0247");
        Assert.True(PinHasher.Verify("0247", hash, salt));
    }

    [Fact]
    public void Yanlis_pin_reddedilir()
    {
        var (hash, salt) = PinHasher.Hash("0247");
        Assert.False(PinHasher.Verify("0248", hash, salt));
        Assert.False(PinHasher.Verify("", hash, salt));
        Assert.False(PinHasher.Verify("02470", hash, salt));
    }

    [Fact]
    public void Pin_duz_metin_olarak_SAKLANMAZ()
    {
        // En temel güvenlik kontrolü: saklanan değerin içinde PIN geçmemeli.
        var (hash, salt) = PinHasher.Hash("1234");
        Assert.DoesNotContain("1234", hash);
        Assert.DoesNotContain("1234", salt);
    }

    [Fact]
    public void Ayni_pin_farkli_ozet_uretir()
    {
        // Tuzun varlık sebebi. Aynı özet çıksaydı, PIN'i "1234" olan
        // herkesin kaydı aynı görünürdü ve biri çözülünce hepsi çözülürdü.
        var a = PinHasher.Hash("1234");
        var b = PinHasher.Hash("1234");

        Assert.NotEqual(a.Salt, b.Salt);
        Assert.NotEqual(a.Hash, b.Hash);

        // Ama ikisi de kendi tuzuyla doğrulanabilmeli:
        Assert.True(PinHasher.Verify("1234", a.Hash, a.Salt));
        Assert.True(PinHasher.Verify("1234", b.Hash, b.Salt));
    }

    [Fact]
    public void Yanlis_tuzla_dogrulama_basarisiz()
    {
        var a = PinHasher.Hash("1234");
        var b = PinHasher.Hash("1234");
        // Doğru PIN + başkasının tuzu = geçersiz. Tuz özetin parçasıdır.
        Assert.False(PinHasher.Verify("1234", a.Hash, b.Salt));
    }

    [Fact]
    public void Bozuk_kayit_dogrulamayi_patlatmaz()
    {
        // Veritabanında bozuk/eksik veri olabilir; doğrulama istisna
        // fırlatmak yerine "başarısız" demeli. Aksi halde bozuk tek bir
        // kayıt giriş uç noktasını tamamen düşürürdü.
        Assert.False(PinHasher.Verify("1234", "bu-base64-degil!", "***"));
        Assert.False(PinHasher.Verify("1234", "", ""));
    }

    [Fact]
    public void Bos_pin_ozetlenemez()
    {
        Assert.Throws<ArgumentException>(() => PinHasher.Hash(""));
        Assert.Throws<ArgumentException>(() => PinHasher.Hash("   "));
    }
}
