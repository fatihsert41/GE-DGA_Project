using TransformerAI.Maintenance.Api.Models;
using TransformerAI.Maintenance.Api.Services;

namespace TransformerAI.Maintenance.Tests;

/// <summary>Belirteç imza anahtarı ve belirteç yükü. (Güvenlik sertleştirme)</summary>
/// <remarks>
/// En tehlikeli yapılandırma hatası, üretim sunucusunun kaynak koddaki
/// geliştirme anahtarıyla SESSİZCE açılmasıdır: her şey çalışır görünür ama
/// herkes geçerli belirteç üretebilir. Bu testler "gürültüyle başarısız ol"
/// kuralını koruyor. Python tarafında aynı kurallar test_auth_hardening.py'de.
/// </remarks>
public class TokenIssuerTests
{
    private const string Secret = "test-anahtari-en-az-otuz-iki-karakter-uzun";
    private static readonly DateTime Now = new(2026, 9, 15, 8, 0, 0, DateTimeKind.Utc);

    [Fact]
    public void Gelistirmede_anahtar_yoksa_gelistirme_anahtari_kullanilir()
    {
        var (secret, isDev) = TokenIssuer.ResolveSecret(null, isDevelopment: true);
        Assert.Equal(TokenIssuer.DevelopmentSecret, secret);
        Assert.True(isDev);
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("   ")]
    public void Uretimde_anahtar_zorunlu(string? configured)
    {
        Assert.Throws<InvalidOperationException>(
            () => TokenIssuer.ResolveSecret(configured, isDevelopment: false));
    }

    [Fact]
    public void Uretimde_gelistirme_anahtari_reddedilir()
    {
        Assert.Throws<InvalidOperationException>(
            () => TokenIssuer.ResolveSecret(TokenIssuer.DevelopmentSecret, isDevelopment: false));
    }

    [Theory]
    [InlineData(true)]
    [InlineData(false)]
    public void Kisa_anahtar_her_ortamda_reddedilir(bool isDevelopment)
    {
        // Geliştirmede bile: kısa anahtar bir yazım hatasıdır, sessizce kabul
        // edilirse Python'daki anahtarla uyuşmadığı fark edilmez.
        Assert.Throws<InvalidOperationException>(
            () => TokenIssuer.ResolveSecret("parola123", isDevelopment));
    }

    [Fact]
    public void Yeterli_anahtar_kabul_edilir()
    {
        var (secret, isDev) = TokenIssuer.ResolveSecret(Secret, isDevelopment: false);
        Assert.Equal(Secret, secret);
        Assert.False(isDev);
    }

    [Fact]
    public void Belirtec_uretim_zamanini_tasir()
    {
        // Python belirteç yaşını bu alandan ölçüyor; eksik olsaydı her
        // belirteci reddederdi.
        var issuer = new TokenIssuer(Secret, isDevelopment: false);
        var person = new Technician { EmployeeNo = "10247", Name = "Test", Department = Department.OilLaboratory };

        var token = issuer.Issue(person, Now, Now.AddHours(1));
        var payload = issuer.Verify(token, Now);

        Assert.NotNull(payload);
        Assert.Equal(new DateTimeOffset(Now).ToUnixTimeSeconds(), payload!.IssuedAtUnix);
        Assert.Contains(Permissions.TestsOil, payload.Permissions!);
    }

    [Fact]
    public void Baska_anahtarla_imzalanan_belirtec_reddedilir()
    {
        var a = new TokenIssuer(Secret, isDevelopment: false);
        var b = new TokenIssuer(Secret + "-farkli", isDevelopment: false);
        var token = a.Issue(new Technician { EmployeeNo = "1", Name = "x" }, Now, Now.AddHours(1));

        Assert.NotNull(a.Verify(token, Now));
        Assert.Null(b.Verify(token, Now));
    }

    [Fact]
    public void Suresi_dolan_belirtec_reddedilir()
    {
        var issuer = new TokenIssuer(Secret, isDevelopment: false);
        var token = issuer.Issue(new Technician { EmployeeNo = "1", Name = "x" }, Now, Now.AddMinutes(10));
        Assert.Null(issuer.Verify(token, Now.AddMinutes(10)));
    }
}
