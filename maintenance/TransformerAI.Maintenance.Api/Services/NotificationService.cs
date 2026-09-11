using Microsoft.EntityFrameworkCore;
using TransformerAI.Maintenance.Api.Data;
using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Services;

/// <summary>Bildirim üretir, kuyruğa alır, okundu işaretler. (Faz 9.2)</summary>
/// <remarks>
/// <c>NotificationPlanner</c> KİMİN haberdar olacağına karar verir (saf);
/// bu sınıf o kararı veritabanına yazar (I/O). Aynı ayrım
/// <c>WorkOrderPlanner</c> / <c>WorkOrderRepository</c> ikilisinde de var.
/// </remarks>
public class NotificationService
{
    private readonly MaintenanceDbContext _db;
    private readonly NotificationPlanner _planner;

    /// <summary>Kaç başarısız denemeden sonra vazgeçilir.</summary>
    /// <remarks>
    /// Sonsuza kadar denemek, kalıcı olarak hatalı bir adres yüzünden
    /// kuyruğu tıkar ve sağlıklı bildirimleri geciktirir.
    /// </remarks>
    public const int MaxAttempts = 5;

    public NotificationService(MaintenanceDbContext db,
                               NotificationPlanner planner)
    {
        _db = db;
        _planner = planner;
    }

    /// <summary>Bir iş emri için bildirimleri üretir (henüz göndermez).</summary>
    /// <returns>Yeni oluşturulan bildirim sayısı.</returns>
    /// <remarks>
    /// <b>Outbox deseni:</b> burada yalnızca veritabanına yazılır.
    /// Gönderimi <c>NotificationDispatcher</c> arka planda üstlenir.
    /// Böylece e-posta sunucusu kapalı olsa bile iş emri açılır ve
    /// bildirim kaybolmaz.
    /// </remarks>
    public async Task<int> QueueForOrderAsync(WorkOrder order, string trigger,
                                              DateTime now,
                                              CancellationToken ct = default)
    {
        var personnel = await _db.Technicians.AsNoTracking().ToListAsync(ct);
        var targets = _planner.Recipients(order, personnel);
        if (targets.Count == 0) return 0;

        // Aynı (iş emri, alıcı, tetikleyici) için zaten bildirim var mı?
        // Veritabanında benzersiz indeks de var; buradaki kontrol
        // istisna fırlatmadan sessizce atlamak için.
        var existing = await _db.Notifications
            .Where(n => n.WorkOrderId == order.Id && n.Trigger == trigger)
            .Select(n => n.RecipientId)
            .ToListAsync(ct);

        var created = 0;
        foreach (var target in targets)
        {
            if (existing.Contains(target.Recipient.Id)) continue;

            var (subject, body) = _planner.Compose(order, target.Reason);

            _db.Notifications.Add(new Notification
            {
                Id = Guid.NewGuid().ToString("N")[..24],
                WorkOrderId = order.Id,
                RecipientId = target.Recipient.Id,
                // Anlık görüntü: personel ayrılsa bile "kime gitti"
                // sorusu cevaplanabilir kalsın (Faz 9.0 ilkesi).
                RecipientName = target.Recipient.Name,
                RecipientEmployeeNo = target.Recipient.EmployeeNo,
                Channel = NotificationChannel.InApp,
                Status = NotificationStatus.Pending,
                Subject = subject,
                Body = body,
                Trigger = trigger,
                Priority = order.Priority,
                CreatedAt = now,
            });
            created++;
        }

        if (created > 0) await _db.SaveChangesAsync(ct);
        return created;
    }

    /// <summary>Bir kişinin gelen kutusu.</summary>
    public async Task<List<Notification>> InboxAsync(
        string technicianId, bool unreadOnly = false, int limit = 50,
        CancellationToken ct = default)
    {
        var query = _db.Notifications.AsNoTracking()
            .Where(n => n.RecipientId == technicianId);

        if (unreadOnly)
            query = query.Where(n => n.Status != NotificationStatus.Read);

        // Sıralama: önce okunmamışlar, sonra öncelik, sonra tarih.
        // Salt tarihe göre sıralamak, acil bir bildirimi rutin olanların
        // altına gömerdi.
        return await query
            .OrderBy(n => n.Status == NotificationStatus.Read)
            .ThenByDescending(n => n.Priority)
            .ThenByDescending(n => n.CreatedAt)
            .Take(limit)
            .ToListAsync(ct);
    }

    public async Task<int> UnreadCountAsync(string technicianId,
                                            CancellationToken ct = default)
        => await _db.Notifications.CountAsync(
            n => n.RecipientId == technicianId
                 && n.Status != NotificationStatus.Read, ct);

    /// <summary>Okundu işaretler.</summary>
    /// <remarks>
    /// <paramref name="technicianId"/> sorguya dahil: kimse başkasının
    /// bildirimini okundu işaretleyememeli. Yetki kontrolünü veri
    /// katmanında da yapmak, uç noktadaki bir unutkanlığı yakalar.
    /// </remarks>
    public async Task<NotificationReadResult> MarkReadAsync(
        string notificationId, string technicianId, DateTime now,
        CancellationToken ct = default)
    {
        var note = await _db.Notifications.FirstOrDefaultAsync(
            n => n.Id == notificationId && n.RecipientId == technicianId, ct);

        if (note is null) return new NotificationReadResult(false, false);
        if (note.Status == NotificationStatus.Read)
            return new NotificationReadResult(true, true);

        note.Status = NotificationStatus.Read;
        note.ReadAt = now;
        await _db.SaveChangesAsync(ct);
        return new NotificationReadResult(true, false);
    }

    /// <summary>Gönderilmeyi bekleyen bildirimleri alır.</summary>
    public Task<List<Notification>> PendingAsync(int limit = 50,
                                                 CancellationToken ct = default)
        => _db.Notifications
            .Where(n => (n.Status == NotificationStatus.Pending
                         || n.Status == NotificationStatus.Failed)
                        && n.Attempts < MaxAttempts)
            .OrderByDescending(n => n.Priority)
            .ThenBy(n => n.CreatedAt)
            .Take(limit)
            .ToListAsync(ct);

    /// <summary>Gönderim sonucunu kaydeder.</summary>
    public async Task RecordSendAsync(Notification note, string? error,
                                      DateTime now,
                                      CancellationToken ct = default)
    {
        note.Attempts += 1;
        if (error is null)
        {
            note.Status = NotificationStatus.Sent;
            note.SentAt = now;
            note.LastError = null;
        }
        else
        {
            note.Status = NotificationStatus.Failed;
            note.LastError = error;
        }
        await _db.SaveChangesAsync(ct);
    }
}
