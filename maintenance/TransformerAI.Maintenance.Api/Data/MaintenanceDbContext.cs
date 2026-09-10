using Microsoft.EntityFrameworkCore;
using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Data;

/// <summary>
/// Veritabanı bağlamı (context) — bakım servisinin veritabanına açılan kapısı.
/// </summary>
/// <remarks>
/// Python tarafındaki <c>app/database.py</c>'nin karşılığıdır, ama iki büyük farkla:
///
/// 1. <b>SQL yazmıyoruz.</b> Orada elle CREATE TABLE ve INSERT yazdık. Burada
///    C# sınıfını tanımlıyoruz, EF Core tabloyu ve sorguları kendisi üretiyor.
///    Buna ORM denir (Object-Relational Mapper) — SQLAlchemy'nin muadili.
///
/// 2. <b>Şema değişiklikleri sürümlenir.</b> Python tarafında yeni sütun
///    eklerken <c>_ensure_column</c> yardımcısını ELLE yazmıştık. EF Core'da
///    bunun adı "migration"dır ve otomatik üretilir: her şema değişikliği
///    tarihli bir dosya olur, geri alınabilir, takım arkadaşına aktarılabilir.
///
/// Not: Bu veritabanı Python servisininkinden AYRIDIR. İş emirleri burada,
/// ölçümler orada durur. Ortak veritabanı kullanmak mikroservis mimarisinin
/// en yaygın hatasıdır: iki servis birbirinin tablosuna yazmaya başlayınca
/// ayrı olmalarının anlamı kalmaz.
/// </remarks>
public class MaintenanceDbContext : DbContext
{
    // Kurucu (constructor): ayarlar dışarıdan verilir, sınıf kendi
    // bağlantı adresini bilmez. Bağımlılık enjeksiyonunun ilk örneği —
    // 7.4'te kavramı ayrıntılı anlatacağız.
    public MaintenanceDbContext(DbContextOptions<MaintenanceDbContext> options)
        : base(options)
    {
    }

    /// <summary>work_orders tablosu.</summary>
    /// <remarks>
    /// <c>DbSet&lt;T&gt;</c> = bir tablo. Üzerinde LINQ yazarsın, EF Core
    /// onu SQL'e çevirir:
    ///   <c>WorkOrders.Where(o =&gt; o.Status == Planned)</c>
    ///   -&gt; <c>SELECT * FROM work_orders WHERE status = 0</c>
    /// Yani 7.2'de öğrendiğin LINQ, artık veritabanında çalışıyor.
    /// </remarks>
    public DbSet<WorkOrder> WorkOrders => Set<WorkOrder>();

    /// <summary>Tablo/sütun ayrıntılarını burada tanımlıyoruz.</summary>
    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        var wo = modelBuilder.Entity<WorkOrder>();

        wo.ToTable("work_orders");
        wo.HasKey(o => o.Id);

        // MaxLength: SQLite bunu zorlamaz ama şemayı belgelemiş oluruz ve
        // ileride PostgreSQL'e geçersek kural hazır olur.
        wo.Property(o => o.Id).HasMaxLength(20);
        wo.Property(o => o.TransformerId).HasMaxLength(20).IsRequired();
        wo.Property(o => o.Title).HasMaxLength(200).IsRequired();
        wo.Property(o => o.Reason).HasMaxLength(500);
        wo.Property(o => o.AssignedTo).HasMaxLength(100);

        // Enum'ları veritabanına METİN olarak yaz.
        // Varsayılan davranış sayıdır (0,1,2) ve kırılgandır: enum'a ortadan
        // yeni bir değer eklersen eski satırların anlamı kayar. Metin
        // saklamak hem güvenli hem de veritabanına elle bakınca okunur.
        wo.Property(o => o.Status).HasConversion<string>().HasMaxLength(20);
        wo.Property(o => o.Kind).HasConversion<string>().HasMaxLength(20);

        // Sık sorgulanan sütunlara indeks. Python tarafında bunu hiç
        // düşünmemiştik; 9 trafoda fark etmez ama alışkanlık doğru olsun.
        wo.HasIndex(o => o.TransformerId);
        wo.HasIndex(o => o.Status);
    }
}
