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
    bool HasData,

    // --- Faz 9.1: DGA DIŞINDAKİ bulgular -----------------------------
    //
    // Faz 8 boyunca sisteme dört bağımsız duyu eklendi (DGA, yağ, kağıt,
    // elektriksel) ama iş emri üreten kurallar yalnızca DGA'ya
    // bakıyordu. Sistem gördüğünü söylüyor ama yapılacak işe
    // çeviremiyordu — bir izleme sisteminin yapabileceği en sessiz hata.
    //
    // Bu alanlar Python'un /fleet/overview cevabında ZATEN vardı;
    // .NET onları okumuyordu. Yeni bir uç nokta gerekmedi.

    /// <summary>Elektriksel test genel hükmü: iyi / kabul / kötü.</summary>
    string? ElectricalOverall = null,

    /// <summary>Elektriksel bulgular — iş emri açıklamasına girer.</summary>
    List<string>? ElectricalProblems = null,

    bool HasElectricalTest = false,

    /// <summary>Ölçümün kendisi şüpheli mi? (fiziksel olarak imkânsız değer)</summary>
    /// <remarks>
    /// Ayrı bir alan olmasının sebebi, YAPILACAK İŞİN farklı olması:
    /// bulgu gerçekse "trafoya git", ölçüm şüpheliyse "testi tekrarla".
    /// İkisini aynı iş emri saymak, boş yere kesinti planlatır.
    /// </remarks>
    bool ElectricalDataSuspect = false,

    /// <summary>Yağ kalitesi genel hükmü.</summary>
    string? OilOverall = null,

    /// <summary>Kağıdın tüketilen ömrü (%). Geri dönüşsüz.</summary>
    double? LifeConsumedPct = null,

    string? PaperBand = null,

    /// <summary>Sağlık endeksi 0-100. Null: hesaplanamadı.</summary>
    double? HealthScore = null,

    /// <summary>excellent / good / fair / poor / critical</summary>
    string? HealthBand = null,

    /// <summary>Varlık sınıfı ağırlığı (LPT 1.0 / MPT 0.7 / SPT 0.45).</summary>
    /// <remarks>
    /// DGA dışı kuralların önceliği hesaplaması için gerekli.
    /// <c>Priority</c> = IEEE kondisyonu × ağırlık formülünden geliyor,
    /// yani DGA'ya bağlı. DGA'sı sakin ama sargısı bozuk bir trafoda
    /// Priority düşüktür ve o iş emrini listenin dibine atardı. Ağırlığı
    /// ayrı almak, "elektriksel arıza da kritik kondisyondur" demeyi
    /// mümkün kılıyor.
    /// </remarks>
    double AssetWeight = 1.0);

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
