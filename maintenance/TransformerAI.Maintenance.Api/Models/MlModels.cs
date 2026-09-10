namespace TransformerAI.Maintenance.Api.Models;

/// <summary>
/// Python ML servisinden gelen verinin C# karşılıkları.
/// </summary>
/// <remarks>
/// Bunlar bizim varlıklarımız DEĞİL — başka bir servisin cevabının şeklidir.
/// Veritabanına yazılmazlar, bu yüzden hepsi <c>record</c>: gelen veri
/// değişmez bir paket.
///
/// <b>İsimlendirme farkı:</b> Python <c>snake_case</c> kullanır
/// (risk_level, needs_review), C# ise <c>PascalCase</c> (RiskLevel,
/// NeedsReview). İkisini elle eşlemek yerine JSON okuyucuya bir
/// "isimlendirme politikası" veriyoruz (bkz. MlServiceClient) ve dönüşüm
/// otomatik oluyor. Her alana ayrı ayrı öznitelik yazmaya gerek kalmıyor.
///
/// <b>Neden hepsi nullable (?) veya varsayılan değerli?</b> Karşı servis
/// bizim kontrolümüzde değil. Bir alan eksik gelirse uygulama çökmemeli.
/// Servisler arası sınırda savunmacı olmak gerekir.
/// </remarks>
public record TransformerRisk(
    string Id,
    string? Name,
    string? Location,
    string? AssetClass,
    string? AssetClassName,
    double? Mva,
    string? Prediction,
    string? PredictionLabel,
    string? PredictionFamily,
    // Ölçümü olmayan trafoda null gelir. Bu alan "double" iken hiç
    // ölçülmemiş bir varlık eklendiğinde TÜM filo çözümlemesi çöküyordu —
    // tek bir kayıt yüzünden servis komple 500 veriyordu. Servisler arası
    // sınırda savunmacı olmanın somut karşılığı.
    double? Confidence,
    bool NeedsReview,
    bool Severe,
    string? RiskLevel,
    string? RiskLevelTr,
    int? RiskCondition,
    double Priority,
    bool SamplingOverdue,
    string? SamplingStatus,
    int? DaysSinceSample,
    int SamplingMonths,
    int MeasurementCount,
    bool HasData);

/// <summary>Filo özeti — Python'daki /fleet/overview cevabının "summary" kısmı.</summary>
public record FleetSummary(
    int Total,
    int WithData,
    int TotalMeasurements,
    int NeedsAttention,
    int NeedsReview,
    int SamplingOverdue);

/// <summary>/fleet/overview cevabının tamamı.</summary>
public record FleetOverview(
    FleetSummary Summary,
    List<TransformerRisk> Transformers);
