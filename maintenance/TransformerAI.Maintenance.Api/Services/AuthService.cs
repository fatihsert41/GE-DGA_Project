using System.Security.Cryptography;
using Microsoft.EntityFrameworkCore;
using TransformerAI.Maintenance.Api.Data;
using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Services;

/// <summary>Giriş, oturum, kilitleme ve parola değiştirme. (Faz 9.0b, Sistem Yönetimi)</summary>
/// <remarks>
/// <b>Bu sınıf sistemin en hassas parçasıdır</b>, çünkü hataları
/// SESSİZDİR: yanlış yazılmış bir güvenlik kontrolü hiçbir ekranda
/// görünmeden çalışmaya devam eder. Bu yüzden buradaki her karar
/// gerekçesiyle yazılı ve <c>AuthServiceTests</c> gerçek bir (bellek içi)
/// veritabanıyla sınıyor.
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
    /// 5 seçildi: bir insan parolasını birkaç kez yanlış girebilir, ama
    /// 5'ten fazlası kaba kuvvettir. Çok düşük tutmak gerçek kullanıcıyı
    /// sürekli kilitler — güvenlik önlemi, işi durdurduğu anda devre dışı
    /// bırakılır.
    /// </remarks>
    public const int MaxFailedAttempts = 5;

    /// <summary>Kilit süresi.</summary>
    public static readonly TimeSpan LockDuration = TimeSpan.FromMinutes(15);

    /// <summary>Normal oturum ömrü — vardiya süresine yakın.</summary>
    public static readonly TimeSpan SessionLifetime = TimeSpan.FromHours(9);

    /// <summary>Geçici parolayla açılan oturumun ömrü.</summary>
    /// <remarks>
    /// Bu oturumun tek işi parola değiştirmek. 9 saat açık kalması, geçici
    /// parolayı bilen ikinci kişiye (onu veren admin) gereksiz bir pencere
    /// bırakırdı.
    /// </remarks>
    public static readonly TimeSpan PasswordChangeSessionLifetime = TimeSpan.FromMinutes(15);

    public AuthService(MaintenanceDbContext db, TokenIssuer tokens)
    {
        _db = db;
        _tokens = tokens;
    }

    /// <summary>Kişinin şu anda KULLANABİLECEĞİ yetkiler.</summary>
    /// <remarks>
    /// Parolası geçiciyse BOŞ. Belirtece bu liste yazılır; Python servisi
    /// yetkiyi belirteçten okuduğu için geçici parolalı bir oturum Python'da
    /// da hiçbir şey yazamaz. (.NET tarafında ayrıca <c>RequireAsync</c>
    /// kontrol ediyor, çünkü orada yetki departmandan okunuyor.)
    /// </remarks>
    public static IReadOnlyList<string> EffectivePermissions(Technician person) =>
        person.MustChangePassword ? Array.Empty<string>() : Permissions.For(person.Department);

    /// <summary>Sicil + parola ile giriş.</summary>
    public async Task<(LoginResponse? Ok, LoginFailure? Error)> LoginAsync(
        string? employeeNo, string? password, DateTime now, CancellationToken ct = default)
    {
        // ⚠ "Sicil yok" ile "parola yanlış" AYNI mesajı döndürür (kullanıcı sayımı).
        const string generic = "Sicil numarası veya parola hatalı.";

        var no = employeeNo?.Trim() ?? "";
        var person = no.Length == 0
            ? null
            : await _db.Technicians.FirstOrDefaultAsync(t => t.EmployeeNo == no, ct);

        if (person is null)
        {
            // Sabit gecikme: var olmayan sicil ANINDA reddedilirse, yanıt
            // süresi farkından "bu sicil var" çıkarımı yapılabilir.
            // Parola doğrulaması ~100 ms sürdüğü için burada da bekliyoruz.
            await Task.Delay(100, ct);
            return (null, new LoginFailure(generic));
        }

        // Kilit kontrolü parola doğrulamasından ÖNCE: kilitliyken doğru
        // parola girilse bile açılmamalı, yoksa kilitlemenin anlamı kalmaz.
        if (person.LockedUntil is { } until && until > now)
            return (null, new LoginFailure(
                $"Çok fazla hatalı deneme. Giriş {Math.Ceiling((until - now).TotalMinutes):F0} " +
                "dakika sonra tekrar denenebilir.", until));

        if (string.IsNullOrEmpty(person.PasswordHash))
            return (null, new LoginFailure(
                "Bu hesap için parola tanımlanmamış. Sistem Yöneticinize başvurun."));

        if (!PasswordHasher.Verify(password ?? "", person.PasswordHash, person.PasswordSalt))
        {
            var locked = await RegisterFailureAsync(person, now, ct);
            if (locked)
                return (null, new LoginFailure(
                    $"Çok fazla hatalı deneme. Giriş {LockDuration.TotalMinutes:F0} " +
                    "dakika kilitlendi.", person.LockedUntil));

            var left = MaxFailedAttempts - person.FailedAttempts;
            return (null, new LoginFailure($"{generic} Kalan deneme: {left}."));
        }

        // Pasif hesap kontrolü parola DOĞRULANDIKTAN SONRA: önce yapılsaydı
        // "bu hesap pasif" cevabı, parolayı bilmeyen birine de sicilin
        // var olduğunu söylerdi.
        if (!person.IsActive)
            return (null, new LoginFailure(
                "Bu hesap pasif durumda. Sistem Yöneticinize başvurun."));

        person.FailedAttempts = 0;
        person.LockedUntil = null;
        person.LastLoginAt = now;

        return (await OpenSessionAsync(person, now, ct), null);
    }

    /// <summary>Parola değiştirme sonucu.</summary>
    public record ChangePasswordResult(int Status, LoginResponse? Ok, string? Message,
                                       IReadOnlyList<string>? Problems = null);

    /// <summary>Kullanıcının kendi parolasını değiştirmesi.</summary>
    /// <remarks>
    /// Başarılı olunca kişinin BÜTÜN oturumları kapanır — bu istekteki de
    /// dahil — ve yeni bir belirteç döner. Neden hepsi? Parola değiştirmenin
    /// en yaygın sebebi "biri parolamı biliyor olabilir"dir; o kişinin açık
    /// oturumu kalırsa değiştirmenin anlamı kalmaz.
    /// </remarks>
    public async Task<ChangePasswordResult> ChangePasswordAsync(
        string? token, ChangePasswordRequest request, DateTime now, CancellationToken ct = default)
    {
        // Geçici parolalı oturum da buraya girebilmeli: ResolveAsync
        // yetkiye bakmaz, yalnızca oturumun geçerli olduğuna bakar.
        var person = await ResolveAsync(token, now, ct);
        if (person is null)
            return new(401, null, "Oturum gerekli. Lütfen giriş yapın.");

        // Mevcut parola sorulur: açık bırakılmış bir oturumu ele geçiren
        // biri parolayı değiştirip hesabı sahiplenemesin. Yanlış denemeler
        // girişle AYNI sayaca yazılır; yoksa bu uç nokta kilitlenmeyen bir
        // parola deneme kapısı olurdu.
        if (!PasswordHasher.Verify(request.CurrentPassword ?? "", person.PasswordHash, person.PasswordSalt))
        {
            if (await RegisterFailureAsync(person, now, ct))
            {
                await RevokeAllSessionsAsync(person.Id, ct);
                return new(401, null,
                    "Çok fazla hatalı deneme. Hesap kilitlendi ve oturum kapatıldı.");
            }
            return new(400, null, "Mevcut parola hatalı.");
        }

        var problems = PasswordPolicy.Check(request.NewPassword, person.EmployeeNo, person.Name).ToList();
        if (request.NewPassword == request.CurrentPassword)
            problems.Add("Yeni parola mevcut parolayla aynı olamaz.");
        if (problems.Count > 0)
            return new(400, null, "Yeni parola kabul edilmedi.", problems);

        var (hash, salt) = PasswordHasher.Hash(request.NewPassword!);
        person.PasswordHash = hash;
        person.PasswordSalt = salt;
        person.MustChangePassword = false;
        person.PasswordChangedAt = now;
        person.FailedAttempts = 0;
        person.LockedUntil = null;
        _db.UserAuditEvents.Add(Audit(UserAuditActions.PasswordChanged, person, person, now, null));

        await RevokeAllSessionsAsync(person.Id, ct);
        return new(200, await OpenSessionAsync(person, now, ct), null);
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
        if (_tokens.Verify(token, now) is null) return null;

        var session = await _db.Sessions
            .Include(x => x.Technician)
            .FirstOrDefaultAsync(x => x.TokenHash == HashToken(token), ct);

        if (session is null || session.ExpiresAt <= now) return null;
        if (session.Technician is null || !session.Technician.IsActive) return null;

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

        _db.Sessions.Remove(session);
        await _db.SaveChangesAsync(ct);
        return true;
    }

    /// <summary>Bir kişinin BÜTÜN oturumlarını kapatır; kapatılan sayısını döner.</summary>
    /// <remarks>
    /// Parola sıfırlama, pasife alma, departman değişikliği ve parola
    /// değiştirmede kullanılır. Hepsinde ortak soru: "eski yetkiyle ya da
    /// eski parolayla açılmış bir oturum hâlâ çalışmalı mı?" Cevap hayır.
    ///
    /// ⚠ SINIR: Python servisi oturum tablosunu bilmez, belirteci yalnızca
    /// imzasından doğrular. Kapatılan oturumun belirteci Python tarafında
    /// süresi dolana kadar geçerli kalır (bkz. TokenIssuer — bilinçli ödünleşim).
    /// </remarks>
    public async Task<int> RevokeAllSessionsAsync(string technicianId,
                                                  CancellationToken ct = default)
    {
        var sessions = await _db.Sessions
            .Where(x => x.TechnicianId == technicianId)
            .ToListAsync(ct);
        _db.Sessions.RemoveRange(sessions);
        await _db.SaveChangesAsync(ct);
        return sessions.Count;
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

    /// <summary>Denetim olayı üretir (kaydetmez).</summary>
    public static UserAuditEvent Audit(string action, Technician target, Technician? actor,
                                       DateTime at, string? detail) => new()
    {
        At = at,
        Action = action,
        TargetId = target.Id,
        TargetEmployeeNo = target.EmployeeNo,
        TargetName = target.Name,
        ActorId = actor?.Id,
        ActorEmployeeNo = actor?.EmployeeNo,
        ActorName = actor?.Name,
        Detail = detail,
    };

    /// <summary>Hatalı denemeyi sayar; kilitlendiyse true.</summary>
    private async Task<bool> RegisterFailureAsync(Technician person, DateTime now, CancellationToken ct)
    {
        person.FailedAttempts += 1;
        var locked = person.FailedAttempts >= MaxFailedAttempts;
        if (locked)
        {
            person.LockedUntil = now.Add(LockDuration);
            person.FailedAttempts = 0;      // kilit açılınca sıfırdan başlar
            // Kilitlenmeyi bir KİŞİ değil sistem yapar: actor boş. Sistem
            // Yöneticisi "bu hesap neden kilitli?" sorusunu buradan görür —
            // tekrarlanan kilitlenme bir saldırı işareti olabilir.
            _db.UserAuditEvents.Add(Audit(UserAuditActions.Locked, person, null, now,
                $"{MaxFailedAttempts} hatalı deneme"));
        }
        await _db.SaveChangesAsync(ct);
        return locked;
    }

    /// <summary>Oturum açar ve giriş cevabını üretir.</summary>
    private async Task<LoginResponse> OpenSessionAsync(Technician person, DateTime now, CancellationToken ct)
    {
        var lifetime = person.MustChangePassword ? PasswordChangeSessionLifetime : SessionLifetime;
        var expiresAt = now.Add(lifetime);
        var permissions = EffectivePermissions(person);

        // Belirteç İMZALIDIR (bkz. TokenIssuer). Python servisi .NET'e
        // sormadan doğrulayabiliyor; yetki listesi de belirtecin içinde.
        var token = _tokens.Issue(person, expiresAt, permissions);

        _db.Sessions.Add(new Session
        {
            TokenHash = HashToken(token),   // belirtecin KENDİSİ saklanmaz
            TechnicianId = person.Id,
            CreatedAt = now,
            ExpiresAt = expiresAt,
            LastSeenAt = now,
        });
        await _db.SaveChangesAsync(ct);

        return new LoginResponse(
            token, expiresAt, person.EmployeeNo, person.Name,
            person.Role.ToString(),
            person.Specialty.ToString(),
            person.Department.ToString(),
            DepartmentCatalog.Name(person.Department),
            permissions,
            person.MustChangePassword);
    }

    /// <summary>Belirteç özeti.</summary>
    /// <remarks>
    /// Burada PBKDF2 DEĞİL düz SHA-256 yeterli — ve doğrusu bu.
    /// PBKDF2'nin yavaşlığı, <i>tahmin edilebilir</i> girdileri (insanın
    /// seçtiği parolalar) korumak içindir. Belirteç 256 bit rastgele; kaba
    /// kuvvetle bulunması zaten imkânsız.
    ///
    /// Kural: <b>yavaş özetleme düşük entropili sırlar için, hızlı
    /// özetleme yüksek entropili sırlar için.</b>
    /// </remarks>
    private static string HashToken(string token) =>
        Convert.ToBase64String(
            SHA256.HashData(System.Text.Encoding.UTF8.GetBytes(token)));
}
