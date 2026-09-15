using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using TransformerAI.Maintenance.Api.Data;
using TransformerAI.Maintenance.Api.Models;
using TransformerAI.Maintenance.Api.Services;

namespace TransformerAI.Maintenance.Tests;

/// <summary>Giriş, kilitleme, parola değiştirme ve yenileme — GERÇEK veritabanıyla.</summary>
/// <remarks>
/// Her test kendi <b>bellek içi SQLite</b> veritabanını açıyor: gerçek EF Core
/// sorguları çalışır, dosya oluşmaz, testler birbirini etkilemez.
///
/// Neden EF'in "InMemory" sağlayıcısı değil? O, ilişkisel veritabanı DEĞİL:
/// benzersiz indeksleri ve SQL davranışını taklit etmez. SQLite gerçek bir
/// veritabanı olduğu için üretimdeki davranışı sınar.
///
/// Bağlantı test boyunca AÇIK kalmalı: bellek içi SQLite, son bağlantı
/// kapandığı anda silinir.
/// </remarks>
public class AuthServiceTests : IDisposable
{
    private static readonly DateTime Now = new(2026, 9, 15, 8, 0, 0, DateTimeKind.Utc);
    private const string Secret = "test-anahtari-en-az-otuz-iki-karakter-uzun";
    private const string Temporary = "Gecici-Parola-7";
    private const string NewPassword = "Kademe-Revizyon-2026";
    private const string Tech = "10247";   // Ahmet Yılmaz — Elektriksel Test

    private readonly SqliteConnection _connection;
    private readonly MaintenanceDbContext _db;
    private readonly TokenIssuer _tokens;
    private readonly AuthService _auth;

    public AuthServiceTests()
    {
        _connection = new SqliteConnection("DataSource=:memory:");
        _connection.Open();

        var options = new DbContextOptionsBuilder<MaintenanceDbContext>()
            .UseSqlite(_connection)
            .Options;
        _db = new MaintenanceDbContext(options);
        // EnsureCreated şemayı ve HasData ile gelen demo personeli kurar
        // (parolasız). Testte migration zincirini çalıştırmaya gerek yok.
        _db.Database.EnsureCreated();

        // Üretim kurallarıyla: testler geliştirme anahtarına dayanmasın.
        _tokens = new TokenIssuer(Secret, isDevelopment: false);
        _auth = new AuthService(_db, _tokens);

        SetPassword(Tech, Temporary, mustChange: true);
    }

    public void Dispose()
    {
        _db.Dispose();
        _connection.Dispose();
    }

    private Technician Person(string employeeNo) =>
        _db.Technicians.Single(t => t.EmployeeNo == employeeNo);

    private void SetPassword(string employeeNo, string password, bool mustChange)
    {
        var p = Person(employeeNo);
        (p.PasswordHash, p.PasswordSalt) = PasswordHasher.Hash(password);
        p.MustChangePassword = mustChange;
        _db.SaveChanges();
    }

    private async Task<LoginResponse> LoginOk(string password, DateTime? at = null)
    {
        var (ok, error) = await _auth.LoginAsync(Tech, password, at ?? Now);
        Assert.True(ok is not null, error?.Message);
        return ok!;
    }

    // --- Giriş ------------------------------------------------------------------

    [Fact]
    public async Task Olmayan_sicil_ve_yanlis_parola_ayni_mesaji_verir()
    {
        // Kullanıcı sayımı: mesajlar farklı olsaydı hangi sicillerin var
        // olduğu tek tek denenerek öğrenilirdi.
        var (_, unknown) = await _auth.LoginAsync("99999", "herhangi-bir-parola", Now);
        var (_, wrong) = await _auth.LoginAsync(Tech, "yanlis-parola-123", Now);

        const string generic = "Sicil numarası veya parola hatalı.";
        Assert.StartsWith(generic, unknown!.Message);
        Assert.StartsWith(generic, wrong!.Message);
    }

    [Fact]
    public async Task Bes_hatali_denemede_kilitlenir_ve_dogru_parola_da_acmaz()
    {
        for (var i = 0; i < AuthService.MaxFailedAttempts; i++)
            await _auth.LoginAsync(Tech, "yanlis-parola-123", Now);

        Assert.NotNull(Person(Tech).LockedUntil);
        Assert.Contains(_db.UserAuditEvents, e => e.Action == UserAuditActions.Locked
                                                  && e.ActorId == null);

        var (ok, error) = await _auth.LoginAsync(Tech, Temporary, Now.AddMinutes(1));
        Assert.Null(ok);
        Assert.Contains("tekrar denenebilir", error!.Message);

        await LoginOk(Temporary, Now.Add(AuthService.LockDuration).AddMinutes(1));
    }

    [Fact]
    public async Task Gecici_parolali_oturum_yetkisiz_ve_kisa_omurlu()
    {
        var login = await LoginOk(Temporary);

        Assert.True(login.MustChangePassword);
        Assert.Empty(login.Permissions);
        Assert.Equal(Now.Add(AuthService.PasswordChangeSessionLifetime), login.ExpiresAt);

        // Belirtecin İÇİNDEKİ yetki listesi de boş: Python servisi yetkiyi
        // buradan okuduğu için orada da hiçbir şey yazamaz.
        var payload = _tokens.Verify(login.Token, Now);
        Assert.NotNull(payload);
        Assert.Empty(payload!.Permissions!);
    }

    [Fact]
    public async Task Pasif_hesap_yanlis_parolada_varligini_belli_etmez()
    {
        var p = Person(Tech);
        p.IsActive = false;
        _db.SaveChanges();

        var (_, wrong) = await _auth.LoginAsync(Tech, "yanlis-parola-123", Now);
        Assert.StartsWith("Sicil numarası veya parola hatalı.", wrong!.Message);

        var (ok, right) = await _auth.LoginAsync(Tech, Temporary, Now);
        Assert.Null(ok);
        Assert.Contains("pasif", right!.Message);
    }

    // --- Parola değiştirme -------------------------------------------------------

    [Fact]
    public async Task Parola_degisince_eski_oturum_kapanir_ve_yetkiler_gelir()
    {
        var first = await LoginOk(Temporary);

        var result = await _auth.ChangePasswordAsync(
            first.Token, new ChangePasswordRequest(Temporary, NewPassword), Now);

        Assert.Equal(200, result.Status);
        Assert.False(result.Ok!.MustChangePassword);
        Assert.Contains(Permissions.TestsElectrical, result.Ok.Permissions);

        Assert.Null(await _auth.ResolveAsync(first.Token, Now));
        Assert.NotNull(await _auth.ResolveAsync(result.Ok.Token, Now));

        var (old, _) = await _auth.LoginAsync(Tech, Temporary, Now);
        Assert.Null(old);
        await LoginOk(NewPassword);

        Assert.Contains(_db.UserAuditEvents, e => e.Action == UserAuditActions.PasswordChanged);
    }

    [Fact]
    public async Task Politikaya_uymayan_ya_da_ayni_parola_reddedilir()
    {
        var login = await LoginOk(Temporary);

        var tooShort = await _auth.ChangePasswordAsync(
            login.Token, new ChangePasswordRequest(Temporary, "kisa"), Now);
        Assert.Equal(400, tooShort.Status);
        Assert.NotEmpty(tooShort.Problems!);

        var same = await _auth.ChangePasswordAsync(
            login.Token, new ChangePasswordRequest(Temporary, Temporary), Now);
        Assert.Equal(400, same.Status);
        Assert.Contains(same.Problems!, p => p.Contains("aynı"));

        Assert.True(Person(Tech).MustChangePassword);
    }

    [Fact]
    public async Task Mevcut_parola_yanlissa_degismez_ve_sayaca_yazilir()
    {
        var login = await LoginOk(Temporary);

        var result = await _auth.ChangePasswordAsync(
            login.Token, new ChangePasswordRequest("yanlis-parola-123", NewPassword), Now);

        Assert.Equal(400, result.Status);
        Assert.Equal(1, Person(Tech).FailedAttempts);
        await LoginOk(Temporary);
    }

    [Fact]
    public async Task Parola_degistirme_kapisi_kaba_kuvvete_kilitlenir()
    {
        var login = await LoginOk(Temporary);
        AuthService.ChangePasswordResult? last = null;
        for (var i = 0; i < AuthService.MaxFailedAttempts; i++)
            last = await _auth.ChangePasswordAsync(
                login.Token, new ChangePasswordRequest($"yanlis-{i}-parola", NewPassword), Now);

        Assert.Equal(401, last!.Status);
        Assert.NotNull(Person(Tech).LockedUntil);
        Assert.Null(await _auth.ResolveAsync(login.Token, Now));
    }

    [Fact]
    public async Task Oturumsuz_parola_degistirilemez()
    {
        var result = await _auth.ChangePasswordAsync(
            null, new ChangePasswordRequest(Temporary, NewPassword), Now);
        Assert.Equal(401, result.Status);
    }

    // --- Belirteç yenileme (güvenlik sertleştirme) --------------------------------

    [Fact]
    public async Task Yenileme_belirteci_dondurur_ve_oturumu_uzatmaz()
    {
        SetPassword(Tech, NewPassword, mustChange: false);
        var login = await LoginOk(NewPassword);
        var later = Now.AddMinutes(10);

        var refreshed = await _auth.RefreshAsync(login.Token, later);

        Assert.NotNull(refreshed);
        Assert.NotEqual(login.Token, refreshed!.Token);
        // Eski belirteç .NET'te de ANINDA geçersiz (döndürme).
        Assert.Null(await _auth.ResolveAsync(login.Token, later));
        Assert.NotNull(await _auth.ResolveAsync(refreshed.Token, later));
        // Oturumun sonu değişmez: yenileme sonsuz oturum aracı olmamalı.
        Assert.Equal(login.ExpiresAt, refreshed.ExpiresAt);
        // Yeni belirtecin yaşı yenileme anından başlar (Python bunu ölçüyor).
        Assert.Equal(new DateTimeOffset(later).ToUnixTimeSeconds(),
                     _tokens.Verify(refreshed.Token, later)!.IssuedAtUnix);
    }

    [Fact]
    public async Task Yenileme_guncel_yetkileri_yazar()
    {
        SetPassword(Tech, NewPassword, mustChange: false);
        var login = await LoginOk(NewPassword);
        Assert.DoesNotContain(Permissions.TestsOil, login.Permissions);

        var p = Person(Tech);
        p.Department = Department.OilLaboratory;
        _db.SaveChanges();

        var refreshed = await _auth.RefreshAsync(login.Token, Now.AddMinutes(10));
        Assert.Contains(Permissions.TestsOil, refreshed!.Permissions);
    }

    [Fact]
    public async Task Kapatilan_oturum_yenilenemez()
    {
        // Python'daki iptal penceresini sınırlayan kural tam olarak bu.
        SetPassword(Tech, NewPassword, mustChange: false);
        var login = await LoginOk(NewPassword);

        await _auth.RevokeAllSessionsAsync(Person(Tech).Id);

        Assert.Null(await _auth.RefreshAsync(login.Token, Now.AddMinutes(10)));
    }

    // --- Oturum iptali ---------------------------------------------------------

    [Fact]
    public async Task Butun_oturumlar_birlikte_kapatilir()
    {
        SetPassword(Tech, NewPassword, mustChange: false);
        var a = await LoginOk(NewPassword);
        var b = await LoginOk(NewPassword);

        var closed = await _auth.RevokeAllSessionsAsync(Person(Tech).Id);

        Assert.Equal(2, closed);
        Assert.Null(await _auth.ResolveAsync(a.Token, Now));
        Assert.Null(await _auth.ResolveAsync(b.Token, Now));
    }

    [Fact]
    public async Task Veritabanindan_okunan_zamanlar_UTC_isaretli()
    {
        // Canlı testte bulunan hata: SQLite tarihi metin saklar, EF okurken
        // Kind=Unspecified döner, JSON'a "Z"siz yazılır ve tarayıcı YEREL saat
        // sanar (Türkiye'de 3 saat kayma). Dönüştürücü bunu tek yerde düzeltir.
        SetPassword(Tech, NewPassword, mustChange: false);
        var login = await LoginOk(NewPassword);

        // Bellekteki izlenen nesneyi bırak: değer gerçekten veritabanından okunsun.
        _db.ChangeTracker.Clear();
        var person = _db.Technicians.Single(t => t.EmployeeNo == Tech);
        Assert.Equal(DateTimeKind.Utc, person.LastLoginAt!.Value.Kind);

        var refreshed = await _auth.RefreshAsync(login.Token, Now.AddMinutes(5));
        Assert.Equal(DateTimeKind.Utc, refreshed!.ExpiresAt.Kind);
        Assert.Equal(login.ExpiresAt, refreshed.ExpiresAt);
    }

    [Fact]
    public void Etkin_yetkiler_parola_durumuna_bagli()
    {
        var p = new Technician { Department = Department.OilLaboratory, MustChangePassword = true };
        Assert.Empty(AuthService.EffectivePermissions(p));

        p.MustChangePassword = false;
        Assert.Contains(Permissions.TestsOil, AuthService.EffectivePermissions(p));
    }
}
