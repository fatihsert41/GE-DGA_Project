using System.Security.Cryptography;
using Microsoft.EntityFrameworkCore;
using TransformerAI.Maintenance.Api.Data;
using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Services;

/// <summary>Giriş, oturum ve kilitleme. (Faz 9.0b)</summary>
/// <remarks>
/// <b>Bu sınıf sistemin en hassas parçasıdır</b>, çünkü hataları
/// SESSİZDİR: yanlış yazılmış bir güvenlik kontrolü hiçbir test
/// kırmadan, hiçbir ekranda görünmeden çalışmaya devam eder. Bu yüzden
/// buradaki her karar gerekçesiyle yazılı.
///
/// <b>Neden servis, uç nokta değil?</b> <c>WorkOrderPlanner</c> ile aynı
/// gerekçe: kural HTTP'den ayrı dursun ki doğrudan test edilebilsin.
/// </remarks>
public class AuthService
{
    private readonly MaintenanceDbContext _db;
    private readonly TokenIssuer _tokens;

    /// <summary>Kaç yanlış denemeden sonra kilitlenir.</summary>
    /// <remarks>
    /// 5 seçildi: bir insan PIN'ini birkaç kez yanlış girebilir (sayı
    /// tuşları, yanlış sicil), ama 5'ten fazlası kaba kuvvettir. Çok
    /// düşük tutmak gerçek kullanıcıyı sürekli kilitler ve sistem
    /// kullanılmaz hâle gelir — güvenlik önlemi, işi durdurduğu anda
    /// devre dışı bırakılır.
    /// </remarks>
    public const int MaxFailedAttempts = 5;

    /// <summary>Kilit süresi.</summary>
    /// <remarks>
    /// 15 dakika, 10.000 olasılıklı bir PIN'i kaba kuvvetle denemeyi
    /// pratikte imkânsız kılar: 5 denemede 15 dakika beklemek, tüm
    /// olasılıkları denemek için ~20 gün eder.
    /// </remarks>
    public static readonly TimeSpan LockDuration = TimeSpan.FromMinutes(15);

    /// <summary>Oturum ömrü.</summary>
    /// <remarks>
    /// Vardiya süresine yakın. Uzun tutmak çalınan belirtecin işe
    /// yarayacağı süreyi uzatır; kısa tutmak kullanıcıyı gün içinde
    /// tekrar tekrar giriş yapmaya zorlar.
    /// </remarks>
    public static readonly TimeSpan SessionLifetime = TimeSpan.FromHours(9);

    public AuthService(MaintenanceDbContext db, TokenIssuer tokens)
    {
        _db = db;
        _tokens = tokens;
    }

    /// <summary>Sicil + PIN ile giriş.</summary>
    /// <returns>Başarılıysa <c>LoginResponse</c>, değilse <c>LoginFailure</c>.</returns>
    public async Task<(LoginResponse? Ok, LoginFailure? Error)> LoginAsync(
        string employeeNo, string pin, DateTime now, CancellationToken ct = default)
    {
        var person = await _db.Technicians
            .FirstOrDefaultAsync(t => t.EmployeeNo == employeeNo, ct);

        // ⚠ "Sicil yok" ile "PIN yanlış" AYNI mesajı döndürür.
        //
        // Ayrı mesaj verseydik saldırgan hangi sicillerin var olduğunu
        // tek tek deneyerek öğrenirdi (kullanıcı sayımı / user
        // enumeration). Var olan sicilleri bilmek, saldırının yarısıdır.
        const string generic = "Sicil numarası veya PIN hatalı.";

        if (person is null)
        {
            // Sabit gecikme: var olmayan sicil ANINDA reddedilirse, yanıt
            // süresi farkından "bu sicil var" çıkarımı yapılabilir.
            // PIN doğrulaması ~100 ms sürdüğü için burada da bekliyoruz.
            await Task.Delay(100, ct);
            return (null, new LoginFailure(generic));
        }

        if (!person.IsActive)
            return (null, new LoginFailure(
                "Bu personel kaydı pasif durumda. Yöneticinize başvurun."));

        // Kilit kontrolü PIN doğrulamasından ÖNCE: kilitliyken doğru PIN
        // girilse bile açılmamalı, yoksa kilitlemenin anlamı kalmaz.
        if (person.LockedUntil is { } until && until > now)
            return (null, new LoginFailure(
                $"Çok fazla hatalı deneme. Giriş {(until - now).TotalMinutes:F0} " +
                "dakika sonra tekrar denenebilir.", until));

        if (string.IsNullOrEmpty(person.PinHash))
            return (null, new LoginFailure(
                "Bu personel için PIN tanımlanmamış. Yöneticinize başvurun."));

        if (!PinHasher.Verify(pin, person.PinHash, person.PinSalt))
        {
            person.FailedAttempts += 1;
            if (person.FailedAttempts >= MaxFailedAttempts)
            {
                person.LockedUntil = now.Add(LockDuration);
                person.FailedAttempts = 0;      // kilit açılınca sıfırdan başlar
                await _db.SaveChangesAsync(ct);
                return (null, new LoginFailure(
                    $"Çok fazla hatalı deneme. Giriş {LockDuration.TotalMinutes:F0} " +
                    "dakika kilitlendi.", person.LockedUntil));
            }

            await _db.SaveChangesAsync(ct);
            var left = MaxFailedAttempts - person.FailedAttempts;
            return (null, new LoginFailure($"{generic} Kalan deneme: {left}."));
        }

        // Başarılı giriş: sayaç ve kilit temizlenir.
        person.FailedAttempts = 0;
        person.LockedUntil = null;

        // Belirteç İMZALIDIR (bkz. TokenIssuer). Böylece Python servisi
        // .NET'e sormadan doğrulayabiliyor ve Faz 7'deki bağımlılık
        // yönü korunuyor: Python, .NET'i bilmek zorunda kalmıyor.
        var expiresAt = now.Add(SessionLifetime);
        var token = _tokens.Issue(person, expiresAt);

        _db.Sessions.Add(new Session
        {
            TokenHash = HashToken(token),   // belirtecin KENDİSİ saklanmaz
            TechnicianId = person.Id,
            CreatedAt = now,
            ExpiresAt = expiresAt,
            LastSeenAt = now,
        });
        await _db.SaveChangesAsync(ct);

        return (new LoginResponse(
            token, expiresAt, person.EmployeeNo, person.Name,
            person.Role.ToString(), person.Region,
            person.Specialty.ToString()), null);
    }

    /// <summary>Belirteci doğrular ve sahibini döndürür.</summary>
    public async Task<Technician?> ResolveAsync(string? token, DateTime now,
                                                CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(token)) return null;

        // İKİ KATMANLI DOĞRULAMA — ve ikisi de gerekli:
        //
        // 1) İmza: belirtecin kurcalanmadığını ve süresinin dolmadığını
        //    kanıtlar. Python da bu kadarını yapabiliyor.
        // 2) Oturum satırı: belirtecin İPTAL EDİLMEDİĞİNİ kanıtlar.
        //    İmza tek başına bunu söyleyemez — çıkış yapılmış bir
        //    belirtecin imzası hâlâ geçerlidir.
        //
        // .NET her ikisini de yapar, çünkü yapabilir (veritabanı burada).
        // Python yalnızca birincisini yapar; bedeli, iptalin Python
        // tarafında belirteç süresi kadar gecikmesidir.
        if (_tokens.Verify(token, now) is null) return null;

        var session = await _db.Sessions
            .Include(x => x.Technician)
            .FirstOrDefaultAsync(x => x.TokenHash == HashToken(token), ct);

        if (session is null || session.ExpiresAt <= now) return null;
        if (session.Technician is null || !session.Technician.IsActive) return null;

        // Son kullanım güncellenir; "kimse kullanmıyorsa kapat" için.
        session.LastSeenAt = now;
        await _db.SaveChangesAsync(ct);

        return session.Technician;
    }

    /// <summary>Oturumu kapatır (belirteci iptal eder).</summary>
    public async Task<bool> LogoutAsync(string? token,
                                        CancellationToken ct = default)
    {
        if (string.IsNullOrWhiteSpace(token)) return false;

        var session = await _db.Sessions
            .FirstOrDefaultAsync(x => x.TokenHash == HashToken(token), ct);
        if (session is null) return false;

        // İşte JWT yerine sunucu oturumu seçmenin karşılığı: tek satır
        // silinerek belirteç ANINDA geçersiz olur.
        _db.Sessions.Remove(session);
        await _db.SaveChangesAsync(ct);
        return true;
    }

    /// <summary>Süresi dolmuş oturumları siler; silinen sayısını döndürür.</summary>
    public async Task<int> PurgeExpiredAsync(DateTime now,
                                             CancellationToken ct = default)
    {
        var stale = await _db.Sessions.Where(x => x.ExpiresAt <= now)
                                      .ToListAsync(ct);
        if (stale.Count == 0) return 0;

        _db.Sessions.RemoveRange(stale);
        await _db.SaveChangesAsync(ct);
        return stale.Count;
    }

    /// <summary>Belirteç özeti.</summary>
    /// <remarks>
    /// Burada PBKDF2 DEĞİL düz SHA-256 yeterli — ve doğrusu bu.
    /// PBKDF2'nin yavaşlığı, <i>tahmin edilebilir</i> girdileri (kısa
    /// PIN'ler) korumak içindir. Belirteç 256 bit rastgele; kaba kuvvetle
    /// bulunması zaten imkânsız. Her istekte 100 ms harcamak, güvenlik
    /// kazancı olmadan sistemi yavaşlatırdı.
    ///
    /// Kural: <b>yavaş özetleme düşük entropili sırlar için, hızlı
    /// özetleme yüksek entropili sırlar için.</b>
    /// </remarks>
    private static string HashToken(string token) =>
        Convert.ToBase64String(
            SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(token)));
}
