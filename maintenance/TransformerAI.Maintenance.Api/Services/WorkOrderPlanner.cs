using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Services;

/// <summary>
/// Filoya bakıp hangi trafolar için iş emri açılması gerektiğine karar verir.
/// </summary>
/// <remarks>
/// <b>Neden ayrı bir sınıf?</b> Kurallar uç noktanın (Program.cs) içine
/// yazılabilirdi. Yazmıyoruz çünkü:
///
/// 1. <b>Test edilebilirlik.</b> Bu sınıf HTTP bilmez, veritabanı bilmez.
///    Girdi: filo + mevcut iş emirleri. Çıktı: öneri listesi. Saf bir
///    fonksiyon gibi test edilir. (Python tarafında da aynısını yapmıştık:
///    <c>fleet.build_overview</c> saf hesap, <c>overview</c> I/O sarmalayıcı.)
///
/// 2. <b>Kurallar bir arada okunur.</b> Bir bakım mühendisi "sistem hangi
///    durumda iş emri açıyor?" diye sorduğunda tek dosya gösterilir.
///
/// Python tarafındaki <c>services/</c> klasörünün karşılığıdır.
/// </remarks>
public class WorkOrderPlanner
{
    /// <summary>Bir kuralın ürettiği öneri. Henüz kaydedilmemiş bir iş emri.</summary>
    public record Suggestion(
        string TransformerId,
        WorkOrderKind Kind,
        string Title,
        string Reason,
        double Priority,
        DateOnly DueDate,
        string Rule);

    // Kural tetiklendiğinde işin ne kadar sürede yapılması gerektiği.
    // Sabitleri tek yerde tutmak: eşik değişirse tek satır değişir.
    private const int DueDaysSevere = 3;
    private const int DueDaysCritical = 7;
    private const int DueDaysHigh = 14;
    private const int DueDaysRoutine = 30;

    // Ölçümü olmayan varlığın önceliği hesaplanamaz (kondisyon yok).
    // Sıfır bırakmak onu listenin dibine atardı; makul bir orta değer
    // veriyoruz ki görünür kalsın. Gerçek öncelik ilk ölçümde belirlenir.
    private const double AssumedPriorityUnknown = 1.5;

    /// <summary>
    /// Filo durumundan öneri listesi üretir.
    /// </summary>
    /// <param name="fleet">ML servisinden gelen güncel filo.</param>
    /// <param name="existing">Veritabanındaki mevcut iş emirleri.</param>
    /// <param name="today">Bugünün tarihi — dışarıdan alınıyor ki testte
    /// sabitlenebilsin. Kod içinde DateTime.Today çağırsaydık testin sonucu
    /// hangi gün çalıştırıldığına bağlı olurdu.</param>
    public IReadOnlyList<Suggestion> Suggest(FleetOverview fleet,
                                             IReadOnlyList<WorkOrder> existing,
                                             DateOnly today)
    {
        // Zaten AÇIK iş emri olan (trafo, tür) çiftlerini topla.
        // Aynı iş için ikinci emir açmak saha ekibini boğar; bu kontrol
        // öneriyi "idempotent" yapar: kaç kez çalıştırırsan çalıştır,
        // aynı iş için tek emir çıkar.
        var openPairs = existing
            .Where(o => o.Status is WorkOrderStatus.Planned
                            or WorkOrderStatus.InProgress)
            .Select(o => (o.TransformerId, o.Kind))
            .ToHashSet();
        // HashSet: Python'daki set. Aranması O(1); listede aramak O(n) olurdu.

        var suggestions = new List<Suggestion>();

        foreach (var t in fleet.Transformers)
        {
            // Ölçümü olmayan trafo için tanıya dayalı kural çalıştıramayız;
            // ama numune alma kuralı yine de geçerli olabilir.
            if (t.HasData)
            {
                AddFaultRules(t, today, openPairs, suggestions);
            }

            AddSamplingRule(t, today, openPairs, suggestions);
        }

        // En acil olan başta.
        return suggestions
            .OrderByDescending(s => s.Priority)
            .ThenBy(s => s.DueDate)
            .ToList();
    }

    /// <summary>Tanı ve riske dayalı kurallar.</summary>
    private static void AddFaultRules(TransformerRisk t, DateOnly today,
                                      HashSet<(string, WorkOrderKind)> openPairs,
                                      List<Suggestion> output)
    {
        // KURAL 1 — Ciddi arıza sınıfı (D2 ark / T3 >700 °C).
        // Bunlar aciliyet bildirir: risk seviyesi ne olursa olsun doğrulanmalı.
        if (t.Severe)
        {
            Add(output, openPairs, new Suggestion(
                t.Id, WorkOrderKind.Inspection,
                $"Acil inceleme — {t.Prediction}",
                $"Ciddi arıza sınıfı ({t.PredictionLabel}). "
                    + $"Risk: {t.RiskLevelTr}, öncelik {t.Priority:0.00}.",
                t.Priority, today.AddDays(DueDaysSevere), "severe-fault"));
            return;   // aynı trafo için ikinci inceleme önerme
        }

        // KURAL 2 — Yüksek veya kritik risk.
        if (t.RiskLevel is "critical" or "high")
        {
            var days = t.RiskLevel == "critical" ? DueDaysCritical : DueDaysHigh;
            Add(output, openPairs, new Suggestion(
                t.Id, WorkOrderKind.Inspection,
                $"İnceleme — {t.Prediction}",
                $"{t.RiskLevelTr} risk (kondisyon {t.RiskCondition}), "
                    + $"tanı {t.PredictionLabel}.",
                t.Priority, today.AddDays(days), "high-risk"));
            return;
        }

        // KURAL 3 — Model kararsız.
        // Risk düşük görünse bile modelin emin olmadığı vaka insan gözü ister.
        // TR-09 tam olarak böyle: "Normal" değil ama güven düşük.
        if (t.NeedsReview)
        {
            Add(output, openPairs, new Suggestion(
                t.Id, WorkOrderKind.Inspection,
                "Doğrulama incelemesi — model kararsız",
                $"Model güveni %{(t.Confidence ?? 0) * 100:0}, eşiğin altında. "
                    + $"Tanı: {t.PredictionLabel}.",
                t.Priority, today.AddDays(DueDaysRoutine), "low-confidence"));
        }
    }

    /// <summary>Numune alma: hiç alınmamış mı, yoksa aralık mı geçmiş?</summary>
    /// <remarks>
    /// İki ayrı durum, iki ayrı kural. Önceden "hiç numune alınmamış" durumu
    /// hiçbir öneri üretmiyordu: <c>sampling_overdue</c> false dönüyordu ve
    /// varlık plan dışında kalıyordu. Oysa temel çizgi numunesi olmayan bir
    /// trafo hakkında HİÇBİR ŞEY bilmiyoruz — bu, gecikmiş numuneden daha
    /// acildir.
    /// </remarks>
    private static void AddSamplingRule(TransformerRisk t, DateOnly today,
                                        HashSet<(string, WorkOrderKind)> openPairs,
                                        List<Suggestion> output)
    {
        if (t.SamplingStatus == "never_sampled")
        {
            Add(output, openPairs, new Suggestion(
                t.Id, WorkOrderKind.Sampling,
                "Temel çizgi numunesi al — hiç ölçüm yok",
                "Bu varlıktan hiç yağ numunesi alınmamış; tanı ve trend "
                    + "üretilemiyor. Temel çizgi ölçümü gerekiyor.",
                // Tam öncelik: risk bilinmediği için yarıya indirmiyoruz.
                // Bilinmeyen risk, düşük risk değildir.
                t.Priority > 0 ? t.Priority : AssumedPriorityUnknown,
                today.AddDays(DueDaysHigh), "never-sampled"));
            return;
        }

        if (!t.SamplingOverdue)
        {
            return;
        }

        var months = (t.DaysSinceSample ?? 0) / 30;
        Add(output, openPairs, new Suggestion(
            t.Id, WorkOrderKind.Sampling,
            "Yağ numunesi al — aralık aşıldı",
            $"Son numuneden {months} ay geçti; {t.AssetClass} sınıfı için "
                + $"aralık {t.SamplingMonths} ay.",
            // Numune alma önceliği varlık ağırlığından gelir ama risk kadar
            // acil değildir; yarıya indiriyoruz ki inceleme emirleri öne geçsin.
            Math.Round(t.Priority / 2, 2),
            today.AddDays(DueDaysRoutine), "sampling-overdue"));
    }

    /// <summary>Aynı iş için açık emir yoksa öneriyi listeye ekler.</summary>
    private static void Add(List<Suggestion> output,
                            HashSet<(string, WorkOrderKind)> openPairs,
                            Suggestion suggestion)
    {
        if (openPairs.Contains((suggestion.TransformerId, suggestion.Kind)))
        {
            return;
        }

        output.Add(suggestion);

        // Aynı çalıştırmada iki kuralın aynı öneriyi üretmesini de engelle.
        openPairs.Add((suggestion.TransformerId, suggestion.Kind));
    }

    /// <summary>Öneriyi kaydedilebilir bir isteğe çevirir.</summary>
    public static CreateWorkOrderRequest ToRequest(Suggestion s) =>
        new(s.TransformerId, s.Kind, s.Title, s.Reason, s.Priority, s.DueDate);
}
