using System.Net;

namespace TransformerAI.Maintenance.Tests.Integration;

/// <summary>Kök neden analizi (MH04) — HTTP üzerinden. Elle çalıştırılan 20 adımlık betiğin kalıcı hâli.</summary>
public sealed class RcaHttpTests : IDisposable
{
    private readonly MaintenanceApiFactory _factory = new();
    private readonly ApiClient _api;

    public RcaHttpTests()
    {
        _api = new ApiClient(_factory.CreateClient());
    }

    public void Dispose() => _factory.Dispose();

    private async Task<string> CompletedOrder(string manager, string kind, double priority, string title)
    {
        var created = await _api.Post("/workorders",
            new { transformerId = "TR-IT", kind, title, priority }, manager);
        Assert.Equal(HttpStatusCode.Created, created.Status);
        var id = created.Str("id");

        Assert.Equal(HttpStatusCode.OK,
            (await _api.Patch($"/workorders/{id}/status", new { status = "InProgress" }, manager)).Status);
        Assert.Equal(HttpStatusCode.OK,
            (await _api.Patch($"/workorders/{id}/status", new { status = "Done", note = "İş tamamlandı." }, manager)).Status);
        return id;
    }

    [Fact]
    public async Task Kok_neden_analizi_akisi()
    {
        var manager = await _api.TokenFor("10502", "Filo-Yonetimi-2026");
        var field = await _api.TokenFor("10611", "Saha-Bakimi-2026");
        var engineer = await _api.TokenFor("10833", "Muhendislik-Karari-2026");

        // Tamamlanmamış işe RCA yazılmaz.
        var open = await _api.Post("/workorders",
            new { transformerId = "TR-IT", kind = "Repair", title = "Kademe kontağı onarımı", priority = 1.0 }, manager);
        var openId = open.Str("id");
        var early = await _api.Post($"/workorders/{openId}/rca", new { failureMode = "TapChanger" }, engineer);
        Assert.Equal(HttpStatusCode.Conflict, early.Status);

        // Notsuz tamamlama reddedilir (arayüzdeki "Bitir" hatasının sebebi).
        await _api.Patch($"/workorders/{openId}/status", new { status = "InProgress" }, manager);
        Assert.Equal(HttpStatusCode.Conflict,
            (await _api.Patch($"/workorders/{openId}/status", new { status = "Done" }, manager)).Status);
        Assert.Equal(HttpStatusCode.OK,
            (await _api.Patch($"/workorders/{openId}/status", new { status = "Done", note = "Kontak takımı değiştirildi." }, manager)).Status);

        // Onarım işi düşük öncelikte bile kuyruğa düşer.
        var pending = await _api.Get("/rca/pending");
        Assert.Contains(pending.Get("items").EnumerateArray(),
            i => i.GetProperty("workOrder").GetProperty("id").GetString() == openId);

        Assert.Equal(HttpStatusCode.Forbidden,
            (await _api.Post($"/workorders/{openId}/rca", new { failureMode = "TapChanger" }, field)).Status);

        var invalid = await _api.Post($"/workorders/{openId}/rca", new
        {
            failureMode = "Winding, Core",     // Enum.TryParse bunu sessizce Bushing yapardı
            finding = "kısa",
            rootCause = new string('x', 25),
            correctiveAction = new string('x', 25),
        }, engineer);
        Assert.Equal(HttpStatusCode.BadRequest, invalid.Status);
        Assert.Equal(2, invalid.Strings("problems").Count);

        var good = new
        {
            failureMode = "TapChanger",
            finding = "Kademe değiştirici kontaklarında erime izi görüldü.",
            rootCause = "Revizyon aralığı aşılmış, kontak basıncı düşmüş.",
            correctiveAction = "Kontak takımı değiştirildi, direnç ölçümü tekrarlandı.",
        };
        var rca = await _api.Post($"/workorders/{openId}/rca", good, engineer);
        Assert.Equal(HttpStatusCode.Created, rca.Status);
        Assert.StartsWith("RCA-", rca.Str("id"));
        Assert.Equal("Kademe değiştirici", rca.Str("failureModeLabel"));
        Assert.Equal("10833", rca.Str("recordedByEmployeeNo"));

        Assert.Equal(HttpStatusCode.Conflict, (await _api.Post($"/workorders/{openId}/rca", good, engineer)).Status);

        pending = await _api.Get("/rca/pending");
        Assert.DoesNotContain(pending.Get("items").EnumerateArray(),
            i => i.GetProperty("workOrder").GetProperty("id").GetString() == openId);

        // Aynı trafoda ikinci arıza: eski analiz en üstte, iki sebeple önerilir.
        var second = await CompletedOrder(manager, "Replacement", 3.0, "Kademe değişimi");
        var similar = await _api.Get($"/rca/similar?transformerId=TR-IT&failureMode=TapChanger&excludeWorkOrderId={second}");
        Assert.Equal(HttpStatusCode.OK, similar.Status);
        var top = similar.Get("items")[0];
        Assert.Equal(rca.Str("id"), top.GetProperty("rca").GetProperty("id").GetString());
        Assert.Equal(2, top.GetProperty("why").GetArrayLength());

        Assert.Equal(HttpStatusCode.NotFound, (await _api.Get("/workorders/YOK-999/rca")).Status);
    }
}
