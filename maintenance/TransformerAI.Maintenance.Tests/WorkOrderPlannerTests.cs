using TransformerAI.Maintenance.Api.Models;
using TransformerAI.Maintenance.Api.Services;
using static TransformerAI.Maintenance.Tests.TestData;

namespace TransformerAI.Maintenance.Tests;

/// <summary>
/// İş emri öneri kurallarının testleri.
/// </summary>
/// <remarks>
/// <b>xUnit ile pytest karşılaştırması:</b>
/// <code>
/// # pytest                          // xUnit
/// def test_seyi_yapar():            [Fact]
///     assert x == y                 public void SeyiYapar() { Assert.Equal(y, x); }
///
/// @pytest.mark.parametrize(...)     [Theory] + [InlineData(...)]
/// </code>
///
/// Bu testlerin hiçbiri veritabanı veya HTTP kullanmıyor. Sebebi
/// WorkOrderPlanner'ın SAF tasarlanmış olması: girdi filo + mevcut emirler
/// + tarih, çıktı öneri listesi. Milisaniyeler içinde çalışırlar.
/// </remarks>
public class WorkOrderPlannerTests
{
    private readonly WorkOrderPlanner _planner = new();

    // Sabit tarih: testin sonucu hangi gün çalıştırıldığına bağlı olmamalı.
    // Planner'ın "today" parametresi almasının tek sebebi buydu.
    private static readonly DateOnly Today = new(2026, 9, 10);

    [Fact]
    public void CiddiAriza_UcGunIcinde_AcilInceleme()
    {
        var fleet = Fleet(Risk("TR-01", severe: true, prediction: "D2",
                               predictionFamily: "Deşarj",
                               riskLevel: "critical", riskCondition: 4,
                               priority: 4.0));

        var result = _planner.Suggest(fleet, [], Today);

        var s = Assert.Single(result);      // tam olarak bir öneri bekliyoruz
        Assert.Equal("severe-fault", s.Rule);
        Assert.Equal(WorkOrderKind.Inspection, s.Kind);
        Assert.Equal(Today.AddDays(3), s.DueDate);
    }

    // [Theory] + [InlineData]: aynı testi farklı girdilerle çalıştırır.
    // Python'daki @pytest.mark.parametrize ile aynı iş.
    [Theory]
    [InlineData("critical", 7)]
    [InlineData("high", 14)]
    public void RiskSeviyesi_SonTarihiBelirler(string riskLevel, int expectedDays)
    {
        var fleet = Fleet(Risk("TR-02", riskLevel: riskLevel, riskCondition: 3,
                               prediction: "T2", predictionFamily: "Termal"));

        var result = _planner.Suggest(fleet, [], Today);

        var s = Assert.Single(result);
        Assert.Equal("high-risk", s.Rule);
        Assert.Equal(Today.AddDays(expectedDays), s.DueDate);
    }

    [Fact]
    public void DusukRisk_AmaModelKararsiz_DogrulamaOnerir()
    {
        // TR-09 senaryosu: risk düşük görünüyor ama model emin değil.
        // Projenin Faz 6'daki bulgusunun iş emrine dönüştüğü yer.
        var fleet = Fleet(Risk("TR-09", riskLevel: "low", riskCondition: 1,
                               needsReview: true, confidence: 0.54,
                               prediction: "D1", predictionFamily: "Deşarj"));

        var result = _planner.Suggest(fleet, [], Today);

        var s = Assert.Single(result);
        Assert.Equal("low-confidence", s.Rule);
        Assert.Contains("kararsız", s.Title);
    }

    [Fact]
    public void SakinTrafo_OneriUretmez()
    {
        var fleet = Fleet(Risk("TR-05", riskLevel: "low", riskCondition: 1));

        var result = _planner.Suggest(fleet, [], Today);

        Assert.Empty(result);
    }

    [Fact]
    public void NumuneGecikmesi_AyriBirOneri()
    {
        var fleet = Fleet(Risk("TR-06", riskLevel: "medium", riskCondition: 2,
                               samplingOverdue: true, daysSinceSample: 420,
                               samplingMonths: 12, priority: 1.4));

        var result = _planner.Suggest(fleet, [], Today);

        var s = Assert.Single(result);
        Assert.Equal(WorkOrderKind.Sampling, s.Kind);
        // Numune önceliği yarıya iner ki inceleme emirleri öne geçsin.
        Assert.Equal(0.7, s.Priority);
        Assert.Contains("14 ay", s.Reason);
    }

    [Fact]
    public void AcikEmriOlanTrafoya_AyniTurdenIkinciEmirOnerilmez()
    {
        // İdempotens: bu davranış olmadan planlayıcı her çalıştığında
        // aynı iş için yeni emir açar ve saha ekibi boğulur.
        var fleet = Fleet(Risk("TR-01", severe: true, riskLevel: "critical",
                               riskCondition: 4, priority: 4.0));
        var existing = new[] { Order("TR-01", WorkOrderKind.Inspection) };

        var result = _planner.Suggest(fleet, existing, Today);

        Assert.Empty(result);
    }

    [Fact]
    public void KapanmisEmir_YeniOneriyiEngellemez()
    {
        // Tamamlanmış iş emri "artık bu iş yapılıyor" anlamına gelmez;
        // arıza sürüyorsa yeni emir açılmalı.
        var fleet = Fleet(Risk("TR-01", severe: true, riskLevel: "critical",
                               riskCondition: 4, priority: 4.0));
        var existing = new[]
        {
            Order("TR-01", WorkOrderKind.Inspection, WorkOrderStatus.Done),
        };

        var result = _planner.Suggest(fleet, existing, Today);

        Assert.Single(result);
    }

    [Fact]
    public void FarkliTurdenEmir_Engellemez()
    {
        // TR-09'un açık NUMUNE emri var ama düşük güven için ayrı bir
        // İNCELEME önerilebilmeli — farklı işler.
        var fleet = Fleet(Risk("TR-09", needsReview: true, confidence: 0.6,
                               samplingOverdue: true));
        var existing = new[] { Order("TR-09", WorkOrderKind.Sampling) };

        var result = _planner.Suggest(fleet, existing, Today);

        var s = Assert.Single(result);
        Assert.Equal(WorkOrderKind.Inspection, s.Kind);
    }

    [Fact]
    public void Oneriler_OncelikSirasinaGoreDoner()
    {
        var fleet = Fleet(
            Risk("TR-A", riskLevel: "high", riskCondition: 3, priority: 1.0),
            Risk("TR-B", severe: true, riskLevel: "critical",
                 riskCondition: 4, priority: 4.0),
            Risk("TR-C", riskLevel: "high", riskCondition: 3, priority: 2.5));

        var result = _planner.Suggest(fleet, [], Today);

        Assert.Equal(["TR-B", "TR-C", "TR-A"],
                     result.Select(s => s.TransformerId));
    }

    [Fact]
    public void OlcumsuzTrafo_SadeceNumuneKuraliCalisir()
    {
        // Ölçümü yoksa tanıya dayalı kural çalıştırılamaz; ama numune
        // alma zaten tam da bu yüzden gerekiyor olabilir.
        var fleet = Fleet(Risk("TR-YENI", hasData: false, severe: true,
                               riskLevel: "critical", samplingOverdue: true));

        var result = _planner.Suggest(fleet, [], Today);

        var s = Assert.Single(result);
        Assert.Equal(WorkOrderKind.Sampling, s.Kind);
    }
}
