using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Services;

/// <summary>Bildirimi dış dünyaya ileten şey. (Faz 9.2)</summary>
/// <remarks>
/// <b>ARAYÜZ (interface) NEDİR VE NEDEN BURADA GEREKLİ?</b>
///
/// Bir arayüz, "bu işi yapabilen her şeyin uyması gereken sözleşme"dir.
/// Gövdesi yoktur, yalnızca imzası. Bunu uygulayan sınıflar işi farklı
/// şekillerde yapar.
///
/// Burada gereken şu: bildirim gönderme işi <i>bugün</i> sadece günlüğe
/// yazıyor, <i>yarın</i> e-posta ya da SMS gönderecek. Eğer gönderme
/// kodunu doğrudan <c>NotificationService</c>'in içine yazsaydık, bir
/// gün e-postaya geçmek için o servisi değiştirmek gerekirdi — ve o
/// servisin testleri gerçek e-posta göndermeye başlardı.
///
/// <b>BAĞIMLILIK TERS ÇEVİRME (dependency inversion)</b>
///
/// Normalde üst seviye kod alt seviye koda bağımlıdır:
/// <code>
///     NotificationService  ──►  SmtpEmailSender   (somut sınıfa bağımlı)
/// </code>
/// Arayüzle bu ok TERS çevrilir:
/// <code>
///     NotificationService  ──►  INotificationSender  ◄──  SmtpEmailSender
///                                    (sözleşme)            LoggingSender
/// </code>
/// Artık ikisi de <i>sözleşmeye</i> bağımlı; birbirlerini tanımıyorlar.
/// Hangi uygulamanın kullanılacağına <c>Program.cs</c> karar veriyor.
///
/// Python'da bunu genelde "ördek tipleme" ile yaparız: aynı metoda sahip
/// herhangi bir nesneyi geçiririz, ayrı bir sözleşme yazmayız. C# derleme
/// zamanında kontrol ettiği için sözleşmenin açıkça yazılması gerekir.
/// Karşılığında: uyumsuz bir sınıf geçirmek derlenmez bile.
/// </remarks>
public interface INotificationSender
{
    /// <summary>Bu gönderici hangi kanalı üstleniyor?</summary>
    NotificationChannel Channel { get; }

    /// <summary>Bildirimi gönderir.</summary>
    /// <returns>Başarılıysa null, değilse hata açıklaması.</returns>
    /// <remarks>
    /// İstisna FIRLATMAK yerine hata METNİ döndürüyor. Sebep: gönderim
    /// hatası burada beklenen bir durumdur (ağ kesilir, sunucu kapalıdır),
    /// istisnai bir durum değil. Beklenen hataları istisnayla yönetmek,
    /// çağıran tarafı her seferinde try/catch yazmaya zorlar ve hatayı
    /// yutmayı kolaylaştırır.
    /// </remarks>
    Task<string?> SendAsync(Notification notification,
                            CancellationToken ct = default);
}

/// <summary>Demo gönderici: gerçekten göndermez, günlüğe yazar.</summary>
/// <remarks>
/// ⚠ Gerçek e-posta/SMS göndermek dış servis, kimlik bilgisi ve alan adı
/// doğrulaması ister — bu projenin kapsamı dışında. Ama <b>bildirimin
/// üretilmesi, saklanması, sıraya alınması, okunması ve denetlenmesi</b>
/// gerçek: yalnızca son adım taklit.
///
/// Bu, kasten seçilmiş bir sınır. "Gönderiyormuş gibi yapmak" yerine
/// gönderim adımını açıkça yalıtmak, hem dürüst hem de test edilebilir.
/// <c>SmtpNotificationSender</c> yazıldığı gün tek satır değişecek:
/// <c>Program.cs</c>'teki kayıt satırı.
/// </remarks>
public class LoggingNotificationSender : INotificationSender
{
    private readonly ILogger<LoggingNotificationSender> _log;

    public LoggingNotificationSender(ILogger<LoggingNotificationSender> log)
        => _log = log;

    public NotificationChannel Channel => NotificationChannel.InApp;

    public Task<string?> SendAsync(Notification n, CancellationToken ct = default)
    {
        _log.LogInformation(
            "[BILDIRIM] -> {Employee} {Name} | {Subject} | is emri {WorkOrder}",
            n.RecipientEmployeeNo, n.RecipientName, n.Subject, n.WorkOrderId);

        // Uygulama içi bildirim zaten veritabanında; "gönderim" onu
        // görünür kılmaktan ibaret. Bu yüzden hiç başarısız olmaz.
        return Task.FromResult<string?>(null);
    }
}
