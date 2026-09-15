using System.Net;

namespace TransformerAI.Maintenance.Tests.Integration;

/// <summary>Giriş, geçici parola, yenileme ve kimliksiz istekler — HTTP üzerinden.</summary>
/// <remarks>
/// <c>AuthServiceTests</c> kuralları sınıyordu; bunlar kuralların UÇ NOKTAYA
/// doğru bağlandığını sınar: <c>RequireAsync</c> geçici parolalı oturumu
/// durduruyor mu, JSON'da tarih "Z" ile mi yazılıyor, eski belirteç gerçekten
/// geçersiz mi?
/// </remarks>
public sealed class AuthHttpTests : IDisposable
{
    private readonly MaintenanceApiFactory _factory = new();
    private readonly ApiClient _api;

    public AuthHttpTests()
    {
        _api = new ApiClient(_factory.CreateClient());
    }

    public void Dispose() => _factory.Dispose();

    [Fact]
    public async Task Gecici_parola_akisi_uctan_uca()
    {
        // Migration eski PIN'leri siliyor; yeni kurulumda da PIN yok.
        var pin = await _api.Login("10502", "0502");
        Assert.Equal(HttpStatusCode.Unauthorized, pin.Status);

        var temp = await _api.Login("10502", "Demo-10502");
        Assert.Equal(HttpStatusCode.OK, temp.Status);
        Assert.True(temp.Get("mustChangePassword").GetBoolean());
        Assert.Empty(temp.Strings("permissions"));

        // .NET yetkiyi departmandan okuyor: belirteçteki boş liste burada
        // tek başına işe yaramazdı, RequireAsync ayrıca durdurmalı.
        var blocked = await _api.Post("/workorders",
            new { transformerId = "TR-X", kind = "Inspection", title = "deneme" }, temp.Str("token"));
        Assert.Equal(HttpStatusCode.Forbidden, blocked.Status);
        Assert.Equal("password_change_required", blocked.Str("code"));

        var weak = await _api.Post("/auth/change-password",
            new { currentPassword = "Demo-10502", newPassword = "Sahin-10502-parola" }, temp.Str("token"));
        Assert.Equal(HttpStatusCode.BadRequest, weak.Status);
        Assert.NotEmpty(weak.Strings("problems"));

        var changed = await _api.Post("/auth/change-password",
            new { currentPassword = "Demo-10502", newPassword = "Filo-Yonetimi-2026" }, temp.Str("token"));
        Assert.Equal(HttpStatusCode.OK, changed.Status);
        Assert.Contains("workorders.plan", changed.Strings("permissions"));

        Assert.Equal(HttpStatusCode.Unauthorized, (await _api.Get("/auth/me", temp.Str("token"))).Status);
        var me = await _api.Get("/auth/me", changed.Str("token"));
        Assert.Equal(HttpStatusCode.OK, me.Status);
        Assert.False(me.Get("mustChangePassword").GetBoolean());
    }

    [Fact]
    public async Task Yenileme_dondurur_UTC_yazar_ve_kapanan_oturum_yenilenmez()
    {
        var session = await _api.ActivateAsync("10318", "Planlama-Parolasi-2026");
        var first = session.Str("token");

        var refreshed = await _api.Post("/auth/refresh", token: first);
        Assert.Equal(HttpStatusCode.OK, refreshed.Status);
        var second = refreshed.Str("token");
        Assert.NotEqual(first, second);

        // Oturum sonu değişmez ve UTC olarak ("Z") yazılır. "Z" olmasaydı
        // tarayıcı yerel saat sanıp 3 saat kaydırırdı (canlı testte bulunan hata).
        Assert.Equal(session.Str("expiresAt"), refreshed.Str("expiresAt"));
        Assert.EndsWith("Z", refreshed.Str("expiresAt"));

        Assert.Equal(HttpStatusCode.Unauthorized, (await _api.Get("/auth/me", first)).Status);
        Assert.Equal(HttpStatusCode.OK, (await _api.Get("/auth/me", second)).Status);

        Assert.Equal(HttpStatusCode.OK, (await _api.Post("/auth/logout", token: second)).Status);
        Assert.Equal(HttpStatusCode.Unauthorized, (await _api.Post("/auth/refresh", token: second)).Status);
    }

    [Theory]
    [InlineData("GET", "/personnel/by-employee-no/10502")]   // kullanıcı sayımı kapalı
    [InlineData("GET", "/admin/users")]
    [InlineData("GET", "/admin/audit")]
    [InlineData("POST", "/workorders/WO-0001/rca")]
    public async Task Kimliksiz_istek_reddedilir(string method, string path)
    {
        var response = await _api.SendAsync(new HttpMethod(method), path,
            method == "POST" ? new { failureMode = "Oil" } : null);
        Assert.Equal(HttpStatusCode.Unauthorized, response.Status);
    }

    [Fact]
    public void Uretim_benzeri_ortamda_anahtarsiz_uygulama_acilmaz()
    {
        // Sessizce geliştirme anahtarıyla açılmak, herkesin belirteç
        // üretebilmesi demekti. Açılış bloğu TokenIssuer'ı çözdüğü anda patlar.
        using var noSecret = new MaintenanceApiFactory(secret: null);
        var error = Record.Exception(() => noSecret.CreateClient());
        Assert.NotNull(error);
        Assert.Contains("TRANSFORMERAI_AUTH_SECRET", error!.ToString());
    }
}
