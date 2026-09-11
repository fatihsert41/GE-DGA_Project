namespace TransformerAI.Maintenance.Api.Services;

/// <summary>Bekleyen bildirimleri arka planda gönderir. (Faz 9.2)</summary>
/// <remarks>
/// <b>BackgroundService NEDİR?</b>
///
/// Şimdiye kadarki her kod bir HTTP isteğine cevap olarak çalıştı: biri
/// bir adrese istek attı, kod çalıştı, cevap döndü. <c>BackgroundService</c>
/// ise <b>kimse istemeden</b>, uygulama açık olduğu sürece çalışır.
///
/// Python'daki karşılığı ayrı bir zamanlayıcı süreç olurdu (cron, Celery).
/// .NET'te uygulamanın içinde yaşar ve uygulamayla birlikte başlar/durur.
///
/// <b>Neden gönderimi isteğin içinde yapmıyoruz?</b>
///
/// İş emri açan kullanıcının isteği, e-posta sunucusunun cevabını
/// beklememelidir. Sunucu yavaşsa iş emri açma yavaşlar; çökerse iş emri
/// de açılamaz. Oysa bildirim gitmese bile iş emri açılmalıdır — bunlar
/// farklı öneme sahip işler.
///
/// Outbox deseninin ikinci yarısı bu: yazma işi istekte, gönderme işi
/// burada. Aralarındaki tek bağ veritabanı.
///
/// <b>Scope (kapsam) tuzağı — en yaygın .NET hatası</b>
///
/// <c>BackgroundService</c> uygulama ömrü boyunca YAŞAR (singleton).
/// <c>DbContext</c> ise istek başına yaratılır (scoped). Singleton bir
/// sınıfa scoped bir bağımlılık enjekte etmek, o DbContext'i sonsuza
/// kadar canlı tutar: değişiklik izleyicisi şişer, bellek sızar ve
/// bağlantı havuzu tükenir.
///
/// Doğrusu: her turda <c>CreateScope()</c> ile YENİ bir kapsam açmak.
/// Bu yüzden aşağıda <c>IServiceScopeFactory</c> enjekte ediliyor,
/// doğrudan <c>NotificationService</c> değil.
/// </remarks>
public class NotificationDispatcher : BackgroundService
{
    private readonly IServiceScopeFactory _scopes;
    private readonly ILogger<NotificationDispatcher> _log;

    /// <summary>Kuyruk kontrol aralığı.</summary>
    /// <remarks>
    /// 30 saniye: bildirim gecikmesi insan ölçeğinde fark edilmez, ama
    /// veritabanını sürekli yoklamaz. Gerçek sistemlerde bu genelde bir
    /// mesaj kuyruğuyla (RabbitMQ, Azure Service Bus) olay tabanlı
    /// yapılır; yoklama basit ve bu ölçekte yeterli.
    /// </remarks>
    private static readonly TimeSpan Interval = TimeSpan.FromSeconds(30);

    public NotificationDispatcher(IServiceScopeFactory scopes,
                                  ILogger<NotificationDispatcher> log)
    {
        _scopes = scopes;
        _log = log;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _log.LogInformation("Bildirim gonderici basladi ({Interval} sn).",
                            Interval.TotalSeconds);

        while (!stoppingToken.IsCancellationRequested)
        {
            try
            {
                await DispatchOnceAsync(stoppingToken);
            }
            catch (OperationCanceledException)
            {
                break;   // uygulama kapanıyor: normal çıkış
            }
            catch (Exception e)
            {
                // Arka plan servisinde YAKALANMAYAN bir istisna, servisi
                // sessizce durdurur ve bir daha hiç çalışmaz. Uygulama
                // ayakta görünür ama bildirimler birikir ve kimse fark
                // etmez. Bu yüzden döngünün içi mutlaka korunmalı.
                _log.LogError(e, "Bildirim gonderim turu basarisiz.");
            }

            try { await Task.Delay(Interval, stoppingToken); }
            catch (OperationCanceledException) { break; }
        }

        _log.LogInformation("Bildirim gonderici durdu.");
    }

    /// <summary>Tek bir gönderim turu. Testten de çağrılabilir.</summary>
    public async Task<int> DispatchOnceAsync(CancellationToken ct = default)
    {
        // Her tur YENİ kapsam: yukarıdaki "scope tuzağı" notuna bakın.
        using var scope = _scopes.CreateScope();
        var service = scope.ServiceProvider
                           .GetRequiredService<NotificationService>();
        var sender = scope.ServiceProvider
                          .GetRequiredService<INotificationSender>();

        var pending = await service.PendingAsync(ct: ct);
        if (pending.Count == 0) return 0;

        var sent = 0;
        foreach (var note in pending)
        {
            if (ct.IsCancellationRequested) break;

            var error = await sender.SendAsync(note, ct);
            await service.RecordSendAsync(note, error, DateTime.UtcNow, ct);
            if (error is null) sent++;
        }

        if (sent > 0)
            _log.LogInformation("{Count} bildirim gonderildi.", sent);

        return sent;
    }
}
