using System.Net;
using System.Text.Json;

namespace TransformerAI.Maintenance.Tests.Integration;

/// <summary>Sistem Yönetimi (AD01) — HTTP üzerinden. Elle çalıştırılan 36 adımlık betiğin kalıcı hâli.</summary>
public sealed class AdminHttpTests : IDisposable
{
    private readonly MaintenanceApiFactory _factory = new();
    private readonly ApiClient _api;

    private const string AdminPassword = "Sistem-Yonetimi-2026";
    private const string ManagerPassword = "Filo-Yonetimi-2026";

    public AdminHttpTests()
    {
        _api = new ApiClient(_factory.CreateClient());
    }

    public void Dispose() => _factory.Dispose();

    private static object NewLabUser(string employeeNo = "10960") => new
    {
        employeeNo, name = "Ayşe Kara", department = "OilLaboratory", role = "Technician",
    };

    private async Task<HashSet<string>> AuditActions(string admin)
    {
        var audit = await _api.Get("/admin/audit?limit=200", admin);
        Assert.Equal(HttpStatusCode.OK, audit.Status);
        return audit.Get("items").EnumerateArray()
            .Select(e => e.GetProperty("action").GetString()!).ToHashSet();
    }

    private static JsonElement UserByNo(ApiClient.Response users, string employeeNo) =>
        users.Get("items").EnumerateArray()
            .First(u => u.GetProperty("employeeNo").GetString() == employeeNo);

    [Fact]
    public async Task Gorev_ayriligi_ve_kullanici_ekleme()
    {
        var manager = await _api.ActivateAsync("10502", ManagerPassword);
        var admin = await _api.ActivateAsync("10001", AdminPassword);

        // İşi yapan (Yönetim) hesap açamaz; hesap açan (Sistem Yönetimi) operasyona dokunmaz.
        Assert.DoesNotContain("users.manage", manager.Strings("permissions"));
        Assert.Contains("users.manage", admin.Strings("permissions"));
        Assert.DoesNotContain("tests.oil", admin.Strings("permissions"));
        Assert.Equal(HttpStatusCode.Forbidden, (await _api.Get("/admin/users", manager.Str("token"))).Status);

        var users = await _api.Get("/admin/users", admin.Str("token"));
        Assert.Equal(HttpStatusCode.OK, users.Status);
        Assert.Equal(9, users.Get("count").GetInt32());
        // Kimlik doğrulama alanları hiçbir cevap gövdesine girmez.
        Assert.DoesNotContain("passwordHash", users.Get("items")[0].GetRawText(), StringComparison.OrdinalIgnoreCase);
        Assert.DoesNotContain("pinHash", users.Get("items")[0].GetRawText(), StringComparison.OrdinalIgnoreCase);

        var created = await _api.Post("/admin/users", NewLabUser(), admin.Str("token"));
        Assert.Equal(HttpStatusCode.Created, created.Status);
        var temporary = created.Str("temporaryPassword");
        Assert.Equal(12, temporary.Length);
        Assert.Equal("TK-10", created.Get("user").GetProperty("id").GetString());

        Assert.Equal(HttpStatusCode.Conflict, (await _api.Post("/admin/users", NewLabUser(), admin.Str("token"))).Status);

        var invalid = await _api.Post("/admin/users",
            new { employeeNo = "12", name = "X", department = "Muhasebe", role = "Technician" }, admin.Str("token"));
        Assert.Equal(HttpStatusCode.BadRequest, invalid.Status);
        Assert.True(invalid.Strings("problems").Count >= 3);

        // Yeni kullanıcı: geçici parolayla yetkisiz, kendi parolasıyla yağ testi yetkisi.
        var first = await _api.Login("10960", temporary);
        Assert.True(first.Get("mustChangePassword").GetBoolean());
        var own = await _api.Post("/auth/change-password",
            new { currentPassword = temporary, newPassword = "Numune-Laboratuvar-7" }, first.Str("token"));
        Assert.Equal(HttpStatusCode.OK, own.Status);
        Assert.Contains("tests.oil", own.Strings("permissions"));

        var actions = await AuditActions(admin.Str("token"));
        Assert.Contains("created", actions);
        Assert.Contains("password_changed", actions);
    }

    [Fact]
    public async Task Sifirlama_kilit_ve_pasife_alma()
    {
        var admin = await _api.TokenFor("10001", AdminPassword);

        var created = await _api.Post("/admin/users", NewLabUser(), admin);
        var id = created.Get("user").GetProperty("id").GetString()!;
        var temp = created.Str("temporaryPassword");
        var userLogin = await _api.Login("10960", temp);
        var userToken = (await _api.Post("/auth/change-password",
            new { currentPassword = temp, newPassword = "Numune-Laboratuvar-7" }, userLogin.Str("token"))).Str("token");

        // Sıfırlama: yeni geçici parola, açık oturumlar kapanır.
        var reset = await _api.Post($"/admin/users/{id}/reset-password", token: admin);
        Assert.Equal(HttpStatusCode.OK, reset.Status);
        Assert.True(reset.Get("closedSessions").GetInt32() >= 1);
        Assert.Equal(HttpStatusCode.Unauthorized, (await _api.Get("/auth/me", userToken)).Status);
        Assert.Equal(HttpStatusCode.Unauthorized, (await _api.Login("10960", "Numune-Laboratuvar-7")).Status);
        Assert.Equal(HttpStatusCode.Conflict, (await _api.Post("/admin/users/TK-09/reset-password", token: admin)).Status);

        // Kilit: 5 hatalı deneme → doğru parola da girmez → admin açar.
        for (var i = 0; i < 5; i++)
            await _api.Login("10247", $"yanlis-parola-{i}");
        var users = await _api.Get("/admin/users", admin);
        var ahmet = UserByNo(users, "10247");
        Assert.True(ahmet.GetProperty("locked").GetBoolean());
        var lockedLogin = await _api.Login("10247", "Demo-10247");
        Assert.Equal(HttpStatusCode.Unauthorized, lockedLogin.Status);
        Assert.Contains("tekrar denenebilir", lockedLogin.Message);
        Assert.Equal(HttpStatusCode.OK,
            (await _api.Post($"/admin/users/{ahmet.GetProperty("id").GetString()}/unlock", token: admin)).Status);
        Assert.Equal(HttpStatusCode.OK, (await _api.Login("10247", "Demo-10247")).Status);

        // Pasife alma: kendini alamaz, gerekçe zorunlu, pasif hesap girmez.
        Assert.Equal(HttpStatusCode.Conflict,
            (await _api.Post("/admin/users/TK-09/deactivate", new { reason = "kendimi kapatiyorum" }, admin)).Status);
        Assert.Equal(HttpStatusCode.BadRequest,
            (await _api.Post($"/admin/users/{id}/deactivate", new { reason = "kısa" }, admin)).Status);
        Assert.Equal(HttpStatusCode.OK,
            (await _api.Post($"/admin/users/{id}/deactivate", new { reason = "Deneme hesabı, entegrasyon testi." }, admin)).Status);
        var inactive = await _api.Login("10960", reset.Str("temporaryPassword"));
        Assert.Equal(HttpStatusCode.Unauthorized, inactive.Status);
        Assert.Contains("pasif", inactive.Message);

        var activated = await _api.Post($"/admin/users/{id}/activate", token: admin);
        Assert.Equal(HttpStatusCode.OK, activated.Status);
        Assert.Equal(12, activated.Str("temporaryPassword").Length);

        var actions = await AuditActions(admin);
        foreach (var expected in new[] { "password_reset", "locked", "unlocked", "deactivated", "activated" })
            Assert.Contains(expected, actions);

        // Kilitlenmeyi bir kişi değil sistem yaptı.
        var audit = await _api.Get("/admin/audit?limit=200", admin);
        var locked = audit.Get("items").EnumerateArray().First(e => e.GetProperty("action").GetString() == "locked");
        Assert.Equal(JsonValueKind.Null, locked.GetProperty("actorName").ValueKind);
    }

    [Fact]
    public async Task Yetki_yukseltme_ve_kilitlenme_korumasi()
    {
        var admin = await _api.TokenFor("10001", AdminPassword);
        var manager = await _api.TokenFor("10502", ManagerPassword);

        // Admin kendini Yönetim'e taşıyıp her yetkiyi alamaz.
        var self = await _api.Put("/technicians/TK-09/department", new { department = "Management" }, admin);
        Assert.Equal(HttpStatusCode.Forbidden, self.Status);

        // Son aktif Sistem Yöneticisi taşınamaz — yoksa kimse hesap yönetemezdi.
        var last = await _api.Put("/technicians/TK-09/department", new { department = "FieldService" }, manager);
        Assert.Equal(HttpStatusCode.Conflict, last.Status);

        // Başkasının departmanı değişebilir; açık oturumları kapanır.
        var tech = await _api.TokenFor("10247", "Elektrik-Testi-2026");
        var moved = await _api.Put("/technicians/TK-01/department", new { department = "OilLaboratory" }, admin);
        Assert.Equal(HttpStatusCode.OK, moved.Status);
        Assert.True(moved.Get("closedSessions").GetInt32() >= 1);
        Assert.Equal(HttpStatusCode.Unauthorized, (await _api.Get("/auth/me", tech)).Status);
    }
}
