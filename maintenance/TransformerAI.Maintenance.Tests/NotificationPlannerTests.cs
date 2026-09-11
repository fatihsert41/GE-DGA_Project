using TransformerAI.Maintenance.Api.Models;
using TransformerAI.Maintenance.Api.Services;

namespace TransformerAI.Maintenance.Tests;

/// <summary>Bildirimin KİME gideceği kuralları. (Faz 9.2)</summary>
/// <remarks>
/// Bu kuralların hatası sessizdir: yanlış kişiye giden bildirim gürültü
/// yapar ve fark edilir, ama <b>hiç kimseye gitmeyen</b> bildirim hiçbir
/// iz bırakmaz. Sistemin sessiz kalabileceği en tehlikeli durum budur —
/// kural bir iş emri üretmiştir, ama kimsenin gelen kutusunda yoktur.
/// </remarks>
public class NotificationPlannerTests
{
    private readonly NotificationPlanner _planner = new();

    private static Technician Person(string id, string employeeNo, string name,
                                     PersonnelRole role, bool active = true)
        => new()
        {
            Id = id, EmployeeNo = employeeNo, Name = name, Role = role,
            IsActive = active,
        };

    private static readonly Technician Tech =
        Person("TK-01", "10247", "Ahmet Yılmaz", PersonnelRole.Technician);
    private static readonly Technician Engineer =
        Person("TK-02", "10318", "Elif Demir", PersonnelRole.Engineer);
    private static readonly Technician Supervisor =
        Person("TK-04", "10502", "Zeynep Şahin", PersonnelRole.Supervisor);

    private static readonly List<Technician> Everyone =
        new() { Tech, Engineer, Supervisor };

    private static WorkOrder Order(double priority = 1.0,
                                   string? technicianId = null,
                                   WorkOrderKind kind = WorkOrderKind.Inspection)
        => new()
        {
            Id = "WO-1", TransformerId = "TR-05", Kind = kind,
            Title = "Elektriksel bulgu", Reason = "B fazında spir kaybı",
            Priority = priority, TechnicianId = technicianId,
            DueDate = new DateOnly(2026, 9, 14),
        };

    [Fact]
    public void Atanan_teknisyene_bildirim_gider()
    {
        var targets = _planner.Recipients(Order(technicianId: "TK-01"), Everyone);
        Assert.Contains(targets, t => t.Recipient.Id == "TK-01");
    }

    [Fact]
    public void Atanmamis_is_havada_KALMAZ()
    {
        // Sistemin sessiz kalabileceği en tehlikeli durum: iş emri var
        // ama kimse atanmadığı için kimsenin gelen kutusunda yok.
        var targets = _planner.Recipients(Order(technicianId: null), Everyone);

        Assert.NotEmpty(targets);
        Assert.All(targets, t => Assert.Contains("atanmadı", t.Reason));
        // Karar verebilecek roller haberdar olmalı:
        Assert.Contains(targets, t => t.Recipient.Role == PersonnelRole.Engineer);
        Assert.Contains(targets, t => t.Recipient.Role == PersonnelRole.Supervisor);
    }

    [Fact]
    public void Yuksek_oncelikli_iste_supervizor_de_haberdar_olur()
    {
        var targets = _planner.Recipients(
            Order(priority: 2.8, technicianId: "TK-01"), Everyone);

        Assert.Contains(targets, t => t.Recipient.Id == "TK-01");
        Assert.Contains(targets, t => t.Recipient.Id == "TK-04");
    }

    [Fact]
    public void Rutin_iste_supervizor_rahatsiz_edilmez()
    {
        // Süpervizöre her şeyi bildirmek, hiçbir şeyi bildirmemekle aynı
        // kapıya çıkar: bir süre sonra kimse okumaz.
        var targets = _planner.Recipients(
            Order(priority: 1.0, technicianId: "TK-01"), Everyone);

        Assert.Single(targets);
        Assert.Equal("TK-01", targets[0].Recipient.Id);
    }

    [Fact]
    public void Ayni_kisiye_iki_kez_bildirim_gitmez()
    {
        // Süpervizör hem atanmış hem de yüksek öncelik kuralına giriyor.
        var targets = _planner.Recipients(
            Order(priority: 3.0, technicianId: "TK-04"), Everyone);

        Assert.Equal(targets.Select(t => t.Recipient.Id).Distinct().Count(),
                     targets.Count);
    }

    [Fact]
    public void Pasif_personele_bildirim_gitmez()
    {
        var people = new List<Technician>
        {
            Person("TK-09", "10999", "Ayrılmış Kişi", PersonnelRole.Supervisor,
                   active: false),
            Tech,
        };

        var targets = _planner.Recipients(Order(priority: 3.0), people);
        Assert.DoesNotContain(targets, t => t.Recipient.Id == "TK-09");
    }

    [Fact]
    public void Atanan_kisi_pasifse_is_havada_kalmaz()
    {
        // İnce ama önemli: atanmış kişi işten ayrılmışsa iş emri
        // sahipsizdir. "Atandı" diye bildirimi kesmek, işi görünmez kılar.
        var people = new List<Technician>
        {
            Person("TK-01", "10247", "Ayrılmış", PersonnelRole.Technician,
                   active: false),
            Engineer, Supervisor,
        };

        var targets = _planner.Recipients(Order(technicianId: "TK-01"), people);

        Assert.DoesNotContain(targets, t => t.Recipient.Id == "TK-01");
        Assert.NotEmpty(targets);
        Assert.All(targets, t => Assert.Contains("atanmadı", t.Reason));
    }

    [Fact]
    public void Bildirim_metni_eyleme_donuk()
    {
        // "Bir iş emri oluşturuldu" işe yaramaz; alıcı konuyu okuyup ne
        // yapacağını anlamalı.
        var (subject, body) = _planner.Compose(
            Order(priority: 2.8, kind: WorkOrderKind.Repair),
            "İş emri size atandı.");

        Assert.Contains("TR-05", subject);
        Assert.Contains("Onarım", subject);
        Assert.Contains("14 Eylül", subject);
        Assert.Contains("spir kaybı", body);
    }

    [Fact]
    public void Son_tarihi_olmayan_is_emri_metni_patlatmaz()
    {
        var order = Order();
        order.DueDate = null;

        var (subject, _) = _planner.Compose(order, "test");
        Assert.Contains("tarih belirlenmedi", subject);
    }

    [Fact]
    public void Elektriksel_test_turu_metinde_dogru_adlandirilir()
    {
        var (subject, _) = _planner.Compose(
            Order(kind: WorkOrderKind.Test), "test");
        Assert.Contains("Elektriksel test", subject);
    }
}
