using System.Text.Json.Serialization;

namespace TransformerAI.Maintenance.Api.Models;

/// <summary>Bildirimin gönderim durumu.</summary>
public enum NotificationStatus
{
    /// <summary>Kaydedildi, henüz gönderilmedi.</summary>
    Pending = 0,
    Sent = 1,
    /// <summary>Gönderim başarısız; yeniden denenecek.</summary>
    Failed = 2,
    /// <summary>Alıcı okudu.</summary>
    Read = 3,
}

/// <summary>Bildirim kanalı.</summary>
/// <remarks>
/// Kanal, gönderimi YAPAN sınıftan ayrı bir kavram. Aynı bildirim
/// e-postayla da SMS'le de gidebilir; kanal "nasıl" sorusunu, gönderici
/// "kim yapacak" sorusunu cevaplar.
/// </remarks>
public enum NotificationChannel
{
    /// <summary>Uygulama içi — her zaman çalışır, dış servis istemez.</summary>
    InApp = 0,
    Email = 1,
    Sms = 2,
}

/// <summary>Bir iş emri hakkında kişiye gönderilen bildirim. (Faz 9.2)</summary>
/// <remarks>
/// <b>NEDEN VERİTABANINA YAZIYORUZ — "outbox" (giden kutusu) deseni</b>
///
/// Sezgisel çözüm, iş emri açılırken doğrudan e-posta göndermek olurdu.
/// Bu üç şeyi birden bozar:
///
/// <list type="number">
/// <item><b>Gönderim başarısız olursa bildirim KAYBOLUR.</b> E-posta
/// sunucusu o an kapalıysa kimse haberdar olmaz ve kimse bunu fark
/// etmez — sessiz kayıp.</item>
/// <item><b>İş emri işlemi dış servise bağlanır.</b> E-posta sunucusu
/// yavaşsa iş emri açma isteği de yavaşlar; çökerse iş emri de
/// açılamaz. Oysa bildirim gitmese bile iş emri açılmalıdır.</item>
/// <item><b>Denetim izi kalmaz.</b> "Bu arıza kime, ne zaman
/// bildirildi?" sorusunun cevabı hiçbir yerde durmaz.</item>
/// </list>
///
/// Outbox deseninde bildirim önce <b>veritabanına yazılır</b> (iş emriyle
/// aynı işlemde), gönderimi ayrı bir süreç üstlenir. Gönderim başarısız
/// olursa kayıt <c>Failed</c> kalır ve tekrar denenir; hiçbir şey
/// kaybolmaz ve her şey görülebilir.
///
/// ⚠ Bu demoda gerçek e-posta/SMS GÖNDERİLMEZ — dış servis ve kimlik
/// bilgisi gerektirir. Gönderici arayüzü (<c>INotificationSender</c>)
/// hazır; gerçek bir adaptör sonradan takılabilir. Kurumsal sistemlerde
/// de böyle kurulur, çünkü aksi hâlde test edilemez.
/// </remarks>
public class Notification
{
    public string Id { get; set; } = string.Empty;

    /// <summary>Hangi iş emri hakkında.</summary>
    public string WorkOrderId { get; set; } = string.Empty;

    [JsonIgnore]
    public WorkOrder? WorkOrder { get; set; }

    /// <summary>Alıcı personel.</summary>
    public string RecipientId { get; set; } = string.Empty;

    [JsonIgnore]
    public Technician? Recipient { get; set; }

    /// <summary>Alıcının o anki adı ve sicili — ANLIK GÖRÜNTÜ.</summary>
    /// <remarks>
    /// Faz 9.0'daki kimlik kararıyla aynı gerekçe: personel ayrılsa bile
    /// "bu bildirim kime gitti" sorusu cevaplanabilir kalmalı.
    /// </remarks>
    public string RecipientName { get; set; } = string.Empty;
    public string RecipientEmployeeNo { get; set; } = string.Empty;

    public NotificationChannel Channel { get; set; } = NotificationChannel.InApp;
    public NotificationStatus Status { get; set; } = NotificationStatus.Pending;

    public string Subject { get; set; } = string.Empty;
    public string Body { get; set; } = string.Empty;

    /// <summary>Bildirimi doğuran olay: work-order-created, escalated…</summary>
    public string Trigger { get; set; } = string.Empty;

    /// <summary>Aciliyet — okunmamışlar bu sıraya göre gösterilir.</summary>
    public double Priority { get; set; }

    public DateTime CreatedAt { get; set; }
    public DateTime? SentAt { get; set; }
    public DateTime? ReadAt { get; set; }

    /// <summary>Kaç kez gönderilmeye çalışıldı.</summary>
    /// <remarks>
    /// Sonsuza kadar denemek, kalıcı olarak hatalı bir adres yüzünden
    /// sistemi sürekli meşgul eder. Bir üst sınır gerekir.
    /// </remarks>
    public int Attempts { get; set; }

    public string? LastError { get; set; }
}

/// <summary>Bildirimi okundu işaretleme sonucu.</summary>
public record NotificationReadResult(bool Found, bool AlreadyRead);
