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

    /// <summary>Mevcut bir emrin aciliyetinin yükseltilmesi gerektiği bulgusu.</summary>
    /// <remarks>
    /// Önceden açık emri olan (trafo, tür) çifti tamamen ATLANIYORDU.
    /// Bu idempotens için doğruydu ama bir boşluk bırakıyordu: "izlemede"
    /// diye 30 günlük açılmış bir emir, trafo kritik hâle gelse bile eski
    /// son tarihiyle kalıyordu. Kötüleşen risk sessiz kalmamalı.
    /// </remarks>
    public record Escalation(
        string WorkOrderId,
        string TransformerId,
        double OldPriority,
        double NewPriority,
        DateOnly? OldDueDate,
        DateOnly NewDueDate,
        string Reason,
        string Rule);

    /// <summary>Planlama sonucu: yeni öneriler + aciliyet yükseltmeleri.</summary>
    public record PlanResult(
        IReadOnlyList<Suggestion> Suggestions,
        IReadOnlyList<Escalation> Escalations);

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
    /// <summary>Yeni açılması gereken iş emirleri (geriye uyumlu kısayol).</summary>
    public IReadOnlyList<Suggestion> Suggest(FleetOverview fleet,
                                             IReadOnlyList<WorkOrder> existing,
                                             DateOnly today)
        => Plan(fleet, existing, today).Suggestions;

    /// <summary>
    /// Filo durumundan planlama sonucu üretir: yeni öneriler + yükseltmeler.
    /// </summary>
    /// <param name="fleet">ML servisinden gelen güncel filo.</param>
    /// <param name="existing">Veritabanındaki mevcut iş emirleri.</param>
    /// <param name="today">Bugünün tarihi — dışarıdan alınıyor ki testte
    /// sabitlenebilsin.</param>
    public PlanResult Plan(FleetOverview fleet,
                           IReadOnlyList<WorkOrder> existing,
                           DateOnly today)
    {
        // Açık emirleri (trafo, tür) anahtarıyla indeksle. Eskiden yalnızca
        // "var mı yok mu" bakılıyordu; artık emrin KENDİSİ lazım, çünkü
        // aciliyetini karşılaştıracağız.
        var openOrders = existing
            .Where(o => o.Status is WorkOrderStatus.Planned
                            or WorkOrderStatus.InProgress)
            .GroupBy(o => (o.TransformerId, o.Kind))
            // Aynı çiftte birden çok açık emir varsa en acili (en erken
            // son tarihli) temel alınır.
            .ToDictionary(g => g.Key,
                          g => g.OrderBy(o => o.DueDate ?? DateOnly.MaxValue)
                                .First());

        // Kuralların ürettiği "olması gereken" işler — henüz mevcut
        // emirlerle karşılaştırılmadı.
        var desired = new List<Suggestion>();
        var claimed = new HashSet<(string, WorkOrderKind)>();

        foreach (var t in fleet.Transformers)
        {
            // Ölçümü olmayan trafo için tanıya dayalı kural çalıştıramayız;
            // ama numune alma kuralı yine de geçerli olabilir.
            if (t.HasData)
            {
                AddFaultRules(t, today, claimed, desired);
            }

            AddSamplingRule(t, today, claimed, desired);
        }

        var suggestions = new List<Suggestion>();
        var escalations = new List<Escalation>();

        foreach (var d in desired)
        {
            if (!openOrders.TryGetValue((d.TransformerId, d.Kind), out var open))
            {
                suggestions.Add(d);          // açık emir yok -> yeni öneri
                continue;
            }

            // Açık emir var. Kuralın istediği iş DAHA MI ACİL?
            var noDeadline = open.DueDate is null;
            var earlier = open.DueDate is not null && d.DueDate < open.DueDate;
            var higher = d.Priority > open.Priority + 0.001;

            if (!noDeadline && !earlier && !higher)
            {
                continue;   // ne daha acil ne daha önemli -> dokunma (idempotens)
            }

            // ÖNCELİK ASLA DÜŞÜRÜLMEZ. Kural bu kez daha düşük bir öncelik
            // hesaplasa bile (ör. numune kuralı yarıya indiriyor), açık emrin
            // mevcut önceliği korunur. "Yükseltme" adı gereği tek yönlüdür;
            // aksi halde bir emir sessizce önemsizleştirilebilirdi.
            var newPriority = Math.Max(d.Priority, open.Priority);

            var reason = noDeadline
                ? $"Son tarih belirlenmemişti; kural gereği belirlendi: {d.Reason}"
                : $"Durum kötüleşti: {d.Reason}";

            escalations.Add(new Escalation(
                open.Id, d.TransformerId, open.Priority, newPriority,
                open.DueDate, d.DueDate, reason, d.Rule));
        }

        return new PlanResult(
            suggestions.OrderByDescending(s => s.Priority)
                       .ThenBy(s => s.DueDate).ToList(),
            escalations.OrderByDescending(e => e.NewPriority)
                       .ThenBy(e => e.NewDueDate).ToList());
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

    /// <summary>Aynı (trafo, tür) için ikinci kez iş üretilmesini engeller.</summary>
    /// <remarks>
    /// Artık yalnızca AYNI ÇALIŞTIRMA içindeki tekrarı engelliyor. Mevcut
    /// açık emirlerle karşılaştırma <see cref="Plan"/> içinde yapılıyor —
    /// çünkü orada "atla" ile "aciliyeti yükselt" ayrımı var.
    /// </remarks>
    private static void Add(List<Suggestion> output,
                            HashSet<(string, WorkOrderKind)> claimed,
                            Suggestion suggestion)
    {
        if (!claimed.Add((suggestion.TransformerId, suggestion.Kind)))
        {
            return;   // bu çalıştırmada zaten üretildi
        }

        output.Add(suggestion);
    }

    /// <summary>Öneriyi kaydedilebilir bir isteğe çevirir.</summary>
    public static CreateWorkOrderRequest ToRequest(Suggestion s) =>
        new(s.TransformerId, s.Kind, s.Title, s.Reason, s.Priority, s.DueDate);
}
