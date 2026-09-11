using TransformerAI.Maintenance.Api.Models;
using TransformerAI.Maintenance.Api.Services;

namespace TransformerAI.Maintenance.Tests;

/// <summary>DGA dışı bulguların iş emrine dönüşmesi. (Faz 9.1)</summary>
/// <remarks>
/// Faz 8 boyunca sisteme dört bağımsız duyu eklendi (DGA, yağ, kağıt,
/// elektriksel) ama iş emri üreten kurallar yalnızca gaz analizine
/// bakıyordu. Sistem "B fazında kısa devre spir var" diyor, kimse için
/// bir iş çıkmıyordu. Bu testler o boşluğun kapandığını doğrular.
/// </remarks>
public class ConditionRuleTests
{
    private static readonly DateOnly Today = new(2026, 9, 11);
    private readonly WorkOrderPlanner _planner = new();

    private List<WorkOrderPlanner.Suggestion> Plan(TransformerRisk risk) =>
        _planner.Suggest(TestData.Fleet(risk),
                         Array.Empty<WorkOrder>(), Today).ToList();

    [Fact]
    public void Elektriksel_ariza_is_emri_uretir()
    {
        // TR-05 senaryosu: DGA sakin, yağ temiz, ama B fazında spir kaybı.
        // Eski hâlde HİÇBİR iş emri üretilmiyordu.
        var s = Plan(TestData.Risk("TR-05",
            electricalOverall: "kötü",
            electricalProblems: new List<string> { "B fazı beklenenden %1.40 düşük" }));

        var found = Assert.Single(s, x => x.Rule == "electrical-fault");
        Assert.Equal(WorkOrderKind.Repair, found.Kind);
        Assert.Contains("B fazı", found.Reason);
        // 3 gün: ciddi DGA arızasıyla aynı aciliyet.
        Assert.Equal(Today.AddDays(3), found.DueDate);
    }

    [Fact]
    public void Elektriksel_ariza_onceligi_DGA_ya_bagli_DEGIL()
    {
        // Bu kuralın var oluş sebebi. Gazı sakin bir trafoda Priority
        // düşüktür (kondisyon 1 × ağırlık); bulguyu o önceliğe bağlamak
        // onu listenin dibine gömerdi.
        var s = Plan(TestData.Risk("TR-05", riskCondition: 1, priority: 0.7,
                                   assetWeight: 0.7, electricalOverall: "kötü"));

        var found = Assert.Single(s, x => x.Rule == "electrical-fault");
        Assert.True(found.Priority > 0.7,
            "Elektriksel arıza, sakin DGA önceliğine mahkûm olmamalı.");
        Assert.Equal(4.0 * 0.7, found.Priority, 3);
    }

    [Fact]
    public void Supheli_olcum_ariza_degil_TEST_TEKRARI_uretir()
    {
        // Fiziksel olarak imkânsız bir ölçümden "arıza" çıkarmak, boş
        // yere kesinti planlatır. Yapılacak iş "trafoya git" değil
        // "testi tekrarla".
        var s = Plan(TestData.Risk("TR-09",
            electricalOverall: "kötü", electricalDataSuspect: true));

        var found = Assert.Single(s, x => x.Rule == "electrical-data-suspect");
        Assert.Equal(WorkOrderKind.Test, found.Kind);
        // Ve arıza kuralı TETİKLENMEMELİ:
        Assert.DoesNotContain(s, x => x.Rule == "electrical-fault");
    }

    [Fact]
    public void Kagit_omru_yenileme_emri_uretir()
    {
        var s = Plan(TestData.Risk("TR-09", lifeConsumedPct: 81.6,
                                   paperBand: "ileri", assetWeight: 0.45));

        var found = Assert.Single(s, x => x.Rule == "paper-end-of-life");
        Assert.Equal(WorkOrderKind.Replacement, found.Kind);
        // Aciliyet düşük ama önem yüksek: tedarik süresi aylarla ölçülür.
        Assert.Equal(Today.AddDays(180), found.DueDate);
    }

    [Fact]
    public void Saglik_endeksi_kritikse_butunsel_degerlendirme_istenir()
    {
        // Tek bir boyut sınırı aşmasa bile birleşik durum kötü olabilir.
        var s = Plan(TestData.Risk("TR-07", healthScore: 24.1,
                                   healthBand: "critical"));
        Assert.Single(s, x => x.Rule == "health-critical");
    }

    [Fact]
    public void Temel_cizgi_testi_olmayan_varlik_isaretlenir()
    {
        var s = Plan(TestData.Risk("TR-09", hasElectricalTest: false,
                                   electricalOverall: null));

        var found = Assert.Single(s, x => x.Rule == "no-electrical-baseline");
        Assert.Equal(WorkOrderKind.Test, found.Kind);
    }

    [Fact]
    public void Saglikli_varlik_hicbir_kosul_emri_uretmez()
    {
        var s = Plan(TestData.Risk("TR-02"));
        Assert.DoesNotContain(s, x => x.Rule.StartsWith("electrical")
                                   || x.Rule.StartsWith("paper")
                                   || x.Rule.StartsWith("health"));
    }

    [Fact]
    public void DGA_incelemesi_acikken_elektriksel_emir_yine_de_acilir()
    {
        // Farklı TÜR kullanmalarının sebebi bu: idempotens anahtarı
        // (trafo, tür). Aynı türü kullansalardı biri diğerini sessizce
        // bastırır ve elektriksel bulgu kaybolurdu.
        var open = new[] { TestData.Order("TR-05", WorkOrderKind.Inspection) };
        var s = _planner.Suggest(
            TestData.Fleet(TestData.Risk("TR-05", riskLevel: "high",
                                         electricalOverall: "kötü")),
            open, Today).ToList();

        Assert.DoesNotContain(s, x => x.Kind == WorkOrderKind.Inspection);
        Assert.Contains(s, x => x.Kind == WorkOrderKind.Repair
                             && x.Rule == "electrical-fault");
    }

    [Fact]
    public void Kosul_emirleri_de_idempotent()
    {
        var open = new[]
        {
            TestData.Order("TR-05", WorkOrderKind.Repair),
            TestData.Order("TR-05", WorkOrderKind.Test),
        };
        var s = _planner.Suggest(
            TestData.Fleet(TestData.Risk("TR-05", electricalOverall: "kötü",
                                         hasElectricalTest: false)),
            open, Today).ToList();

        Assert.DoesNotContain(s, x => x.Rule == "electrical-fault");
        Assert.DoesNotContain(s, x => x.Rule == "no-electrical-baseline");
    }

    [Fact]
    public void Olcumsuz_trafoda_da_kosul_kurallari_calisir()
    {
        // Elektriksel test ve yağ analizi DGA'dan BAĞIMSIZ kaynaklardır:
        // hiç gaz ölçümü olmayan bir trafonun sargı arızası olabilir.
        var s = Plan(TestData.Risk("TR-YENI", hasData: false,
                                   riskLevel: null, riskCondition: null,
                                   electricalOverall: "kötü"));
        Assert.Contains(s, x => x.Rule == "electrical-fault");
    }
}
