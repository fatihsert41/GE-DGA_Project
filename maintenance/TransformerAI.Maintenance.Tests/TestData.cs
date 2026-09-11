using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Tests;

/// <summary>
/// Testler için sahte veri üreten yardımcılar.
/// </summary>
/// <remarks>
/// <c>TransformerRisk</c> 21 alanlı bir record. Her testte hepsini yazmak
/// testi okunmaz yapardı; burada makul varsayılanlar veriliyor ve test
/// yalnızca ÖNEMSEDİĞİ alanı belirtiyor:
///
/// <code>Risk("TR-01", riskLevel: "critical", severe: true)</code>
///
/// Bu, testin niyetini görünür kılar: "kritik ve ciddi olduğunda ne olur?"
/// Diğer alanlar gürültü olarak kalmaz.
///
/// C#'ta bu, adlandırılmış argüman (named argument) özelliğiyle yapılır —
/// Python'daki anahtar kelimeli argümanların karşılığı.
/// </remarks>
public static class TestData
{
    public static TransformerRisk Risk(
        string id,
        string? location = "İstanbul-Avrupa",
        string? assetClass = "MPT",
        string? prediction = "Normal",
        string? predictionFamily = "Normal",
        double confidence = 0.99,
        bool needsReview = false,
        bool severe = false,
        string? riskLevel = "low",
        int? riskCondition = 1,
        double priority = 1.0,
        bool samplingOverdue = false,
        string? samplingStatus = "current",
        int? daysSinceSample = 30,
        int samplingMonths = 12,
        bool hasData = true,
        // --- Faz 9.1: DGA disi bulgular --------------------------------
        // Varsayilanlar "bulgu yok" demeli ki eski testler etkilenmesin;
        // ama hasElectricalTest varsayilani TRUE, yoksa her eski test
        // istemeden "temel cizgi yok" onerisi uretirdi.
        string? electricalOverall = "iyi",
        List<string>? electricalProblems = null,
        bool hasElectricalTest = true,
        bool electricalDataSuspect = false,
        string? oilOverall = "iyi",
        double? lifeConsumedPct = 10.0,
        string? paperBand = "saglikli",
        double? healthScore = 90.0,
        string? healthBand = "excellent",
        double assetWeight = 0.7,
        string? lifecyclePhase = "field",
        string? lifecycleStatus = "in_service",
        bool lifecycleMonitored = true,
        string? physicalOverall = "iyi",
        List<string>? physicalFindings = null,
        bool hasInspection = true,
        string? componentOverall = "iyi",
        List<string>? componentProblems = null,
        bool hasComponentTest = true)
        => new(
            Id: id,
            Name: $"Trafo {id}",
            Location: location,
            AssetClass: assetClass,
            AssetClassName: assetClass,
            Mva: 50,
            Prediction: prediction,
            PredictionLabel: prediction,
            PredictionFamily: predictionFamily,
            Confidence: confidence,
            NeedsReview: needsReview,
            Severe: severe,
            RiskLevel: riskLevel,
            RiskLevelTr: riskLevel,
            RiskCondition: riskCondition,
            Priority: priority,
            SamplingOverdue: samplingOverdue,
            SamplingStatus: samplingStatus,
            DaysSinceSample: daysSinceSample,
            SamplingMonths: samplingMonths,
            MeasurementCount: 12,
            HasData: hasData,
            ElectricalOverall: electricalOverall,
            ElectricalProblems: electricalProblems,
            HasElectricalTest: hasElectricalTest,
            ElectricalDataSuspect: electricalDataSuspect,
            OilOverall: oilOverall,
            LifeConsumedPct: lifeConsumedPct,
            PaperBand: paperBand,
            HealthScore: healthScore,
            HealthBand: healthBand,
            AssetWeight: assetWeight,
            LifecycleStatus: lifecycleStatus,
            LifecyclePhase: lifecyclePhase,
            LifecycleMonitored: lifecycleMonitored,
            PhysicalOverall: physicalOverall,
            PhysicalFindings: physicalFindings,
            HasInspection: hasInspection,
            ComponentOverall: componentOverall,
            ComponentProblems: componentProblems,
            HasComponentTest: hasComponentTest);

    public static FleetOverview Fleet(params TransformerRisk[] transformers)
        => new(
            new FleetSummary(transformers.Length, transformers.Length,
                             120, 0, 0, 0),
            transformers.ToList());

    public static WorkOrder Order(string transformerId, WorkOrderKind kind,
                                  WorkOrderStatus status = WorkOrderStatus.Planned)
        => new()
        {
            Id = $"WO-{transformerId}-{kind}",
            TransformerId = transformerId,
            Kind = kind,
            Title = "test",
            Status = status,
        };

    public static Technician Tech(string id, Specialty specialty,
                                  int maxOpen = 3, bool active = true)
        => new()
        {
            Id = id,
            Name = $"Teknisyen {id}",
            Specialty = specialty,
            MaxOpenOrders = maxOpen,
            IsActive = active,
        };

    public static TechnicianWorkload Load(Technician t, int open)
        => new(t, open, open < t.MaxOpenOrders);
}
