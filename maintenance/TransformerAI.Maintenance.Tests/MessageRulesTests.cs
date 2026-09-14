using TransformerAI.Maintenance.Api.Models;
using TransformerAI.Maintenance.Api.Services;

namespace TransformerAI.Maintenance.Tests;

/// <summary>Elle gönderilen bildirimin alıcı ve doğrulama kuralları. (Faz 10)</summary>
public class MessageRulesTests
{
    private static Technician P(string id, Department dept, bool active = true)
        => new()
        {
            Id = id, EmployeeNo = id.Replace("TK-", "10"), Name = $"Kişi {id}",
            Department = dept, IsActive = active,
        };

    private static readonly Technician Manager = P("TK-04", Department.Management);
    private static readonly Technician Lab1 = P("TK-03", Department.OilLaboratory);
    private static readonly Technician Lab2 = P("TK-06", Department.OilLaboratory);
    private static readonly Technician Electrical = P("TK-01", Department.ElectricalTesting);
    private static readonly Technician LabRetired =
        P("TK-09", Department.OilLaboratory, active: false);

    private static readonly List<Technician> Everyone =
        new() { Manager, Lab1, Lab2, Electrical, LabRetired };

    private static SendMessageRequest Msg(
        List<string>? ids = null, List<string>? depts = null, bool all = false,
        string subject = "Vardiya değişikliği", string body = "Yarın 07:00.")
        => new(subject, body, ids, depts, all);

    [Fact]
    public void Departman_secilince_aktif_uyelerine_gider()
    {
        var (to, problems) = MessageRules.Resolve(
            Msg(depts: new() { "OilLaboratory" }), Everyone, senderId: "TK-04");

        Assert.Empty(problems);
        Assert.Equal(new[] { "TK-03", "TK-06" }, to.Select(t => t.Id).OrderBy(x => x));
    }

    [Fact]
    public void Ayni_kisi_iki_yoldan_secilse_de_tek_bildirim_alir()
    {
        // Hem departmanı hem kendisi seçilmiş: iki kopya gitmemeli.
        var (to, _) = MessageRules.Resolve(
            Msg(ids: new() { "TK-03" }, depts: new() { "OilLaboratory" }),
            Everyone, senderId: "TK-04");

        Assert.Equal(to.Select(t => t.Id).Distinct().Count(), to.Count);
        Assert.Equal(2, to.Count);
    }

    [Fact]
    public void Pasif_personele_departman_yoluyla_da_gitmez()
    {
        var (to, _) = MessageRules.Resolve(
            Msg(depts: new() { "OilLaboratory" }), Everyone, senderId: "TK-04");
        Assert.DoesNotContain(to, t => t.Id == "TK-09");
    }

    [Fact]
    public void Pasif_kisi_elle_secilirse_acikca_bildirilir()
    {
        // Sessizce atlamak, gönderene "haber verdim" sandırırdı.
        var (_, problems) = MessageRules.Resolve(
            Msg(ids: new() { "TK-09" }), Everyone, senderId: "TK-04");
        Assert.Contains(problems, p => p.Contains("pasif"));
    }

    [Fact]
    public void Gonderen_kendine_gondermez()
    {
        var (to, _) = MessageRules.Resolve(Msg(all: true), Everyone, senderId: "TK-04");
        Assert.DoesNotContain(to, t => t.Id == "TK-04");
        Assert.Equal(3, to.Count);   // pasif ve gönderen hariç herkes
    }

    [Fact]
    public void Alici_yoksa_gonderilmez()
    {
        var (to, problems) = MessageRules.Resolve(Msg(), Everyone, senderId: "TK-04");
        Assert.Empty(to);
        Assert.Contains(problems, p => p.Contains("alıcı"));
    }

    [Fact]
    public void Tek_alici_gonderenin_kendisiyse_de_gonderilmez()
    {
        var (_, problems) = MessageRules.Resolve(
            Msg(depts: new() { "Management" }), Everyone, senderId: "TK-04");
        Assert.NotEmpty(problems);
    }

    [Theory]
    [InlineData("", "metin")]
    [InlineData("   ", "metin")]
    [InlineData("Konu", "")]
    public void Bos_konu_veya_metin_reddedilir(string subject, string body)
    {
        var (_, problems) = MessageRules.Resolve(
            Msg(ids: new() { "TK-03" }, subject: subject, body: body),
            Everyone, senderId: "TK-04");
        Assert.NotEmpty(problems);
    }

    [Fact]
    public void Cok_uzun_konu_reddedilir()
    {
        var (_, problems) = MessageRules.Resolve(
            Msg(ids: new() { "TK-03" }, subject: new string('x', MessageRules.SubjectMax + 1)),
            Everyone, senderId: "TK-04");
        Assert.Contains(problems, p => p.Contains("Konu"));
    }

    [Fact]
    public void Bilinmeyen_kisi_ve_departman_bildirilir()
    {
        var (_, problems) = MessageRules.Resolve(
            Msg(ids: new() { "TK-99" }, depts: new() { "Muhasebe" }),
            Everyone, senderId: "TK-04");
        Assert.Contains(problems, p => p.Contains("TK-99"));
        Assert.Contains(problems, p => p.Contains("Muhasebe"));
    }

    [Theory]
    [InlineData("normal", 1.0)]
    [InlineData("high", 2.5)]
    [InlineData("urgent", 4.0)]
    [InlineData(null, 1.0)]
    [InlineData("saçma", 1.0)]
    public void Oncelik_is_emri_olcegiyle_ayni(string? priority, double expected)
    {
        Assert.Equal(expected, MessageRules.PriorityValue(priority));
    }
}
