using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Services;

/// <summary>Bir iş emri hakkında KİMİN haberdar edileceğine karar verir.
/// (Faz 9.2)</summary>
/// <remarks>
/// <c>WorkOrderPlanner</c> ve <c>AssignmentService</c> gibi SAF bir sınıf:
/// veritabanı da HTTP de bilmez, girdiyi parametre olarak alır. Bu yüzden
/// doğrudan test edilebilir ve kural değiştiğinde test anında söyler.
///
/// <b>Neden atama servisinden ayrı?</b> "Kim yapacak" ile "kim bilecek"
/// farklı sorulardır. Bir onarımı teknisyen yapar, ama kritik bir LPT
/// arızasından süpervizörün de haberi olmalıdır — üstelik kimse
/// atanmamışken bile.
/// </remarks>
public class NotificationPlanner
{
    /// <summary>Bu önceliğin üstündeki işler süpervizöre de bildirilir.</summary>
    /// <remarks>
    /// 2.5, "kritik kondisyondaki bir MPT" (4 × 0.7 = 2.8) ile "yüksek
    /// riskli bir LPT" (3 × 1.0 = 3.0) seviyesini yakalar; rutin
    /// incelemeleri yakalamaz. Süpervizöre her şeyi bildirmek, hiçbir
    /// şeyi bildirmemekle aynı kapıya çıkar: kimse okumaz.
    /// </remarks>
    public const double SupervisorThreshold = 2.5;

    /// <summary>Bir bildirimin kime, hangi gerekçeyle gideceği.</summary>
    public record Target(Technician Recipient, string Reason);

    /// <summary>İş emri için alıcıları seçer.</summary>
    /// <param name="order">Bildirime konu iş emri.</param>
    /// <param name="personnel">Tüm personel (aktif olanlar süzülür).</param>
    public IReadOnlyList<Target> Recipients(WorkOrder order,
                                            IReadOnlyList<Technician> personnel)
    {
        var targets = new List<Target>();
        var active = personnel.Where(p => p.IsActive).ToList();

        // 1) Atanmış teknisyen — işi yapacak kişi.
        var assignee = order.TechnicianId is null
            ? null
            : active.FirstOrDefault(p => p.Id == order.TechnicianId);

        if (assignee is not null)
            targets.Add(new Target(assignee, "İş emri size atandı."));

        // 2) Atanmamış ve acil bir iş, HAVADA KALMAMALI.
        //
        // Bu, sistemin sessiz kalabileceği en tehlikeli durum: kural bir
        // iş emri üretti, ama kimseye atanmadığı için kimsenin gelen
        // kutusunda görünmüyor. Kimse atanmamışsa bölge sorumlularına
        // haber verilir ki atamayı biri yapsın.
        if (assignee is null)
        {
            foreach (var person in ByRegion(active, order))
                targets.Add(new Target(person,
                    "Bu iş emri henüz kimseye atanmadı."));
        }

        // 3) Yüksek öncelikli işlerden süpervizör de haberdar olur —
        //    atansa bile. Kaynak ve kesinti kararı onda.
        if (order.Priority >= SupervisorThreshold)
        {
            foreach (var sup in active.Where(p => p.Role == PersonnelRole.Supervisor))
            {
                if (targets.Any(t => t.Recipient.Id == sup.Id)) continue;
                targets.Add(new Target(sup,
                    $"Yüksek öncelikli iş ({order.Priority:0.00})."));
            }
        }

        return targets;
    }

    /// <summary>Atama yapılmamış iş için bölge sorumluları.</summary>
    /// <remarks>
    /// Bölge bilgisi iş emrinde yok (trafoda var, o da Python tarafında).
    /// Bu yüzden mühendis ve süpervizörlerin tamamına gidiyor: az sayıda
    /// kişi, ve "kimse görmedi" riski "fazla kişi gördü" riskinden ağır
    /// basıyor. Bölge eşleşmesi, iş emrine konum eklendiğinde daraltılır.
    /// </remarks>
    private static IEnumerable<Technician> ByRegion(
        IReadOnlyList<Technician> active, WorkOrder order)
        => active.Where(p => p.Role is PersonnelRole.Engineer
                                    or PersonnelRole.Supervisor)
                 .OrderBy(p => p.EmployeeNo);

    /// <summary>Bildirim metnini üretir.</summary>
    /// <remarks>
    /// Metin KISA ve EYLEME dönük olmalı: alıcı konuyu okuyup ne
    /// yapacağını anlamalı. "Bir iş emri oluşturuldu" işe yaramaz;
    /// "TR-05 · Elektriksel bulgu · son tarih 14 Eylül" yarar.
    /// </remarks>
    public (string Subject, string Body) Compose(WorkOrder order, string reason,
                                                 string? transformerName = null)
    {
        var kind = order.Kind switch
        {
            WorkOrderKind.Inspection => "İnceleme",
            WorkOrderKind.Sampling => "Numune alma",
            WorkOrderKind.Repair => "Onarım",
            WorkOrderKind.Replacement => "Değişim",
            WorkOrderKind.Test => "Elektriksel test",
            _ => order.Kind.ToString(),
        };

        var due = order.DueDate is { } d
            ? d.ToString("d MMMM yyyy")
            : "tarih belirlenmedi";

        var subject = $"{order.TransformerId} · {kind} · son tarih {due}";

        var body =
            $"{reason}\n\n" +
            $"Varlık: {order.TransformerId}" +
            (transformerName is null ? "" : $" ({transformerName})") + "\n" +
            $"İş türü: {kind}\n" +
            $"Öncelik: {order.Priority:0.00}\n" +
            $"Son tarih: {due}\n\n" +
            $"{order.Title}\n{order.Reason}";

        return (subject, body);
    }
}
