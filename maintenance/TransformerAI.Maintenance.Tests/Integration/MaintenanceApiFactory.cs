using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Data.Sqlite;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.DependencyInjection;
using TransformerAI.Maintenance.Api.Data;

namespace TransformerAI.Maintenance.Tests.Integration;

/// <summary>Uygulamayı BELLEKTE, gerçek HTTP boru hattıyla başlatır. (Zayıf yanlar 2/4)</summary>
/// <remarks>
/// <b>WebApplicationFactory nedir?</b> <c>Program.cs</c>'yi olduğu gibi
/// çalıştırır — bağımlılık enjeksiyonu, yetki kontrolü, JSON, migration,
/// açılış bloğu dahil — ama gerçek bir port açmaz. Testin <c>HttpClient</c>'ı
/// istekleri doğrudan bellekteki sunucuya verir. Python'daki
/// <c>fastapi.testclient.TestClient</c>'ın karşılığı.
///
/// Önceki .NET testleri saf sınıfları sınıyordu; bu testler "uç nokta doğru
/// yetkiyi istiyor mu, doğru HTTP kodunu dönüyor mu, JSON'u doğru yazıyor mu"
/// sorularını sınar. Daha önce bunları elle çalıştırdığım geçici betiklerle
/// denemiştim; artık her test çalıştırmasında otomatik.
///
/// <b>İzolasyon:</b> her fabrika kendi geçici SQLite DOSYASINI kullanır ve
/// kapanınca siler. Testler birbirinin kullanıcısını kilitleyemez, parolasını
/// değiştiremez.
///
/// <b>Ortam "Testing":</b> geliştirme DEĞİL, yani geliştirme anahtarı reddedilir
/// ve anahtar zorunludur — testler güvenlik kurallarını üretimdeki gibi sınar.
/// </remarks>
public sealed class MaintenanceApiFactory : WebApplicationFactory<Program>
{
    public const string TestSecret = "entegrasyon-testi-anahtari-en-az-32-karakter";

    private readonly string _dbPath =
        Path.Combine(Path.GetTempPath(), $"tai-it-{Guid.NewGuid():N}.db");

    private readonly string? _secret;

    /// <param name="secret">İmza anahtarı; <c>null</c> verilirse anahtarsız başlatılır
    /// (uygulamanın açılmayı reddettiğini sınamak için).</param>
    public MaintenanceApiFactory(string? secret = TestSecret)
    {
        _secret = secret;
    }

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Testing");
        if (_secret is not null)
            builder.UseSetting("Auth:SharedSecret", _secret);

        builder.ConfigureServices(services =>
        {
            // Program.cs'deki veritabanı kaydını test dosyasıyla DEĞİŞTİR.
            // Yalnızca yenisini eklemek yetmez: EF Core yapılandırmaları
            // biriktirir ve iki UseSqlite çağrısı arasında hangisinin geçerli
            // olacağı sıraya bağlı kalırdı.
            var existing = services.Where(d =>
                    d.ServiceType == typeof(DbContextOptions<MaintenanceDbContext>)
                    || d.ServiceType == typeof(DbContextOptions)
                    || (d.ServiceType.IsGenericType
                        && d.ServiceType.GetGenericTypeDefinition().Name
                            .StartsWith("IDbContextOptionsConfiguration", StringComparison.Ordinal)))
                .ToList();
            foreach (var descriptor in existing)
                services.Remove(descriptor);

            services.AddDbContext<MaintenanceDbContext>(options =>
                options.UseSqlite($"Data Source={_dbPath}"));
        });
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        // SQLite bağlantı havuzu dosyayı açık tutar; önce havuzu boşalt.
        SqliteConnection.ClearAllPools();
        foreach (var suffix in new[] { "", "-wal", "-shm" })
        {
            try { File.Delete(_dbPath + suffix); }
            catch (IOException) { /* temizlik başarısızsa test sonucu etkilenmez */ }
        }
    }
}
