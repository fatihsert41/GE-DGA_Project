using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Services;

/// <summary>Benzer geçmiş analiz — neden benzer bulunduğuyla birlikte.</summary>
public record SimilarRca(RootCauseAnalysis Rca, int Score, IReadOnlyList<string> Why);

/// <summary>Kök neden analizi kuralları. (Faz 12.5)</summary>
/// <remarks>
/// <c>MessageRules</c> ve <c>WorkOrderPlanner</c> gibi SAF bir sınıf:
/// veritabanı ve HTTP bilmez, doğrudan test edilir.
///
/// <b>Üç soru cevaplıyor:</b>
/// <list type="number">
/// <item>Bu iş emri için RCA <b>gerekli mi</b>? (kuyruğu besler)</item>
/// <item>RCA <b>yazılabilir mi</b>, yazılan <b>yeterli mi</b>?</item>
/// <item>Geçmişte <b>benzer</b> bir analiz var mı? — yol haritasındaki
/// "aynı arıza tekrarladığında geçmiş RCA'lar önerilir" maddesi.</item>
/// </list>
/// </remarks>
public static class RcaRules
{
    /// <summary>Bu öncelik ve üstündeki iş emri "kritik" sayılır.</summary>
    /// <remarks>
    /// Öncelik Python'dan gelen kondisyon × varlık ağırlığıdır (0–4).
    /// 2.5, bildirimlerde "yüksek" sayılan eşikle AYNI (<c>MessageRules</c>):
    /// iki ayrı "kritik" tanımı olsaydı gelen kutusunda acil görünen bir
    /// iş RCA kuyruğuna düşmeyebilirdi.
    /// </remarks>
    public const double CriticalPriority = 2.5;

    public const int TextMin = 20;
    public const int TextMax = 2000;
    public const int SimilarLimit = 5;

    // Arıza türü eşleşmesi trafodan AĞIR basar: yol haritasının sorusu
    // "aynı ARIZA tekrarlıyor mu?" — başka bir trafoda aynı kademe
    // arızası, aynı trafodaki ilgisiz bir soğutma arızasından daha
    // öğreticidir. İkisi birden tutarsa en üste çıkar.
    private const int ScoreSameMode = 3;
    private const int ScoreSameTransformer = 2;

    public static readonly IReadOnlyDictionary<FailureMode, string> FailureModeLabels =
        new Dictionary<FailureMode, string>
        {
            [FailureMode.Insulation] = "Yalıtım (kağıt / pres tahtası)",
            [FailureMode.Winding] = "Sargı",
            [FailureMode.Core] = "Nüve",
            [FailureMode.Bushing] = "Buşing",
            [FailureMode.TapChanger] = "Kademe değiştirici",
            [FailureMode.Cooling] = "Soğutma",
            [FailureMode.Oil] = "Yağ",
            [FailureMode.Protection] = "Koruma ve kontrol",
            [FailureMode.External] = "Dış etken (yıldırım, şebeke, çevre)",
            [FailureMode.Undetermined] = "Belirlenemedi",
        };

    public static string Label(FailureMode mode) =>
        FailureModeLabels.TryGetValue(mode, out var label) ? label : mode.ToString();

    // --- 1. Gerekli mi? -------------------------------------------------------

    /// <summary>RCA'yı zorunlu kılan sebepler; boşsa zorunlu değil.</summary>
    /// <remarks>
    /// Sebepler LİSTE olarak dönüyor, tek bir evet/hayır değil: mühendis
    /// kuyrukta "neden benden analiz isteniyor?" sorusunun cevabını görmeli.
    ///
    /// Her kapanan işe RCA istemek YANLIŞ olurdu: rutin numune alma işine
    /// kök neden yazılmaz, yazılsa da "numune zamanı gelmişti" olur. Kuyruk
    /// şişer, analizler anlamsızlaşır (Faz 12.2'deki "damga yorgunluğu").
    /// </remarks>
    public static IReadOnlyList<string> RequiredBecause(WorkOrder order)
    {
        var reasons = new List<string>();
        if (order.Priority >= CriticalPriority)
            reasons.Add($"Öncelik {order.Priority:0.00} ≥ {CriticalPriority:0.0}: kritik iş emri.");
        if (order.Kind is WorkOrderKind.Repair or WorkOrderKind.Replacement)
            reasons.Add("Onarım / değişim işi: arıza gerçekleşmiş.");
        return reasons;
    }

    public static bool IsRequired(WorkOrder order) => RequiredBecause(order).Count > 0;

    // --- 2. Yazılabilir mi, yeterli mi? ---------------------------------------

    /// <summary>Bu iş emrine RCA yazılabilir mi? Sorun varsa (HTTP kodu, mesaj).</summary>
    public static (int Status, string Message)? CanRecord(WorkOrder? order, bool alreadyRecorded)
    {
        if (order is null)
            return (404, "İş emri bulunamadı.");

        if (order.Status == WorkOrderStatus.Cancelled)
            return (409, "İptal edilen iş emrine kök neden analizi yazılmaz: iptal, "
                         + "gerçekleşmiş bir arızanın değil yapılmayan bir işin kaydıdır.");

        if (order.Status != WorkOrderStatus.Done)
            return (409, "Kök neden analizi yalnızca TAMAMLANMIŞ iş emrine yazılır "
                         + $"(şu an: {order.Status}). Sebep, iş bitmeden kesin bilinmez.");

        if (alreadyRecorded)
            return (409, "Bu iş emrinin kök neden analizi zaten kayıtlı. Kayıt "
                         + "değiştirilemez: denetim izi korunmalı.");

        return null;
    }

    /// <summary>İsteği doğrular; arıza türünü çözer. Sorun listesi boşsa kaydedilebilir.</summary>
    public static (FailureMode? Mode, IReadOnlyList<string> Problems) Validate(CreateRcaRequest request)
    {
        var problems = new List<string>();
        FailureMode? mode = null;

        var raw = request.FailureMode?.Trim();
        if (string.IsNullOrEmpty(raw))
        {
            problems.Add("Arıza türü seçilmelidir.");
        }
        // Yalnızca harf: Enum.TryParse "3" ya da "Winding, Core" gibi girdileri
        // de kabul eder ve ikincisini sessizce 1|2 = 3 = Bushing'e çevirir.
        else if (raw.All(char.IsLetter)
                 && Enum.TryParse<FailureMode>(raw, ignoreCase: false, out var parsed)
                 && Enum.IsDefined(parsed))
        {
            mode = parsed;
        }
        else
        {
            problems.Add($"Bilinmeyen arıza türü: {raw}");
        }

        CheckText(problems, request.Finding, "Bulgu (ne görüldü)", required: true);
        CheckText(problems, request.RootCause, "Kök neden (neden oldu)", required: true);
        CheckText(problems, request.CorrectiveAction, "Alınan önlem (ne yapıldı)", required: true);
        CheckText(problems, request.PreventiveAction, "Tekrarı önleme", required: false);

        return (mode, problems);
    }

    private static void CheckText(List<string> problems, string? value, string label, bool required)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            if (required)
                problems.Add($"{label} zorunludur (en az {TextMin} karakter).");
            return;
        }

        var length = value.Trim().Length;
        // En az uzunluk yalnızca zorunlu alanlarda. "Arıza giderildi" gibi
        // bir cümle, aynı arıza tekrarladığında kimseye yol göstermez.
        if (required && length < TextMin)
            problems.Add($"{label} en az {TextMin} karakter olmalı (şu an {length}).");
        if (length > TextMax)
            problems.Add($"{label} en fazla {TextMax} karakter olabilir.");
    }

    // --- 3. Benzer geçmiş analizler ---------------------------------------------

    /// <summary>Geçmişteki benzer analizler — en benzeri ve en yenisi üstte.</summary>
    /// <param name="transformerId">Analizi yazılacak trafonun kimliği.</param>
    /// <param name="mode">Seçilen arıza türü; henüz seçilmediyse null (yalnızca trafo eşleşir).</param>
    /// <param name="past">Kayıtlı analizler.</param>
    /// <param name="excludeWorkOrderId">Kendi analizini "benzer" diye göstermemek için.</param>
    /// <remarks>
    /// "Belirlenemedi" bir arıza türü eşleşmesi SAYILMAZ: iki sebebi
    /// bilinmeyen olay birbirine benzemez, sadece ikisi de bilinmiyordur.
    /// </remarks>
    public static IReadOnlyList<SimilarRca> Similar(string transformerId, FailureMode? mode,
                                                    IEnumerable<RootCauseAnalysis> past,
                                                    string? excludeWorkOrderId = null)
    {
        var results = new List<SimilarRca>();
        foreach (var rca in past)
        {
            if (excludeWorkOrderId is not null && rca.WorkOrderId == excludeWorkOrderId)
                continue;

            var score = 0;
            var why = new List<string>();

            if (mode is { } m && m != FailureMode.Undetermined && rca.FailureMode == m)
            {
                score += ScoreSameMode;
                why.Add($"Aynı arıza türü: {Label(m)}");
            }

            if (string.Equals(rca.TransformerId, transformerId, StringComparison.OrdinalIgnoreCase))
            {
                score += ScoreSameTransformer;
                why.Add("Aynı trafo");
            }

            if (score > 0)
                results.Add(new SimilarRca(rca, score, why));
        }

        return results
            .OrderByDescending(s => s.Score)
            .ThenByDescending(s => s.Rca.RecordedAt)
            .Take(SimilarLimit)
            .ToList();
    }
}
