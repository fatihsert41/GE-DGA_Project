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

    /// <summary>technicians tablosu.</summary>
    public DbSet<Technician> Technicians => Set<Technician>();

    public DbSet<Session> Sessions => Set<Session>();

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
        wo.Property(o => o.CompletionNote).HasMaxLength(1000);

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
        // Tekil indeks: eşzamanlı iki isteğin aynı numarayı almasını
        // veritabanı seviyesinde engeller.
        wo.HasIndex(o => o.Seq).IsUnique();

        // --- Teknisyen ---------------------------------------------------
        var tech = modelBuilder.Entity<Technician>();
        tech.ToTable("technicians");
        tech.HasKey(t => t.Id);
        tech.Property(t => t.Id).HasMaxLength(20);
        tech.Property(t => t.Name).HasMaxLength(100).IsRequired();
        tech.Property(t => t.Region).HasMaxLength(50).IsRequired();
        tech.Property(t => t.Specialty).HasConversion<string>().HasMaxLength(20);

        // Sicil numarası ve rol (Faz 9.0).
        tech.Property(t => t.EmployeeNo).HasMaxLength(20).IsRequired();
        tech.Property(t => t.Role).HasConversion<string>().HasMaxLength(20);

        // BENZERSİZ indeks: aynı sicil iki kişide olamaz. Veritabanı
        // seviyesinde zorlamak şart — uygulama katmanındaki kontrol,
        // iki istek aynı anda gelirse yetersiz kalır. (İş emri sıra
        // numarasında da aynı gerekçeyle unique index kullanılmıştı.)
        tech.HasIndex(t => t.EmployeeNo).IsUnique();

        // PIN alanları (Faz 9.0b). Özet ve tuz base64 metin olarak durur.
        tech.Property(t => t.PinHash).HasMaxLength(100);
        tech.Property(t => t.PinSalt).HasMaxLength(50);

        // --- Oturumlar (Faz 9.0b) ----------------------------------------
        var sess = modelBuilder.Entity<Session>();
        sess.ToTable("sessions");
        // Anahtar belirtecin ÖZETİ: belirtecin kendisi veritabanında
        // hiçbir zaman bulunmaz. Sızma hâlinde açık oturumlar ele
        // geçirilemesin diye — PIN'dekiyle aynı mantık.
        sess.HasKey(x => x.TokenHash);
        sess.Property(x => x.TokenHash).HasMaxLength(100);
        sess.Property(x => x.TechnicianId).HasMaxLength(20).IsRequired();
        sess.HasIndex(x => x.TechnicianId);
        sess.HasIndex(x => x.ExpiresAt);

        // Personel silinirse oturumları da gitsin. İş emirlerinde
        // SetNull kullanmıştık (geçmiş korunmalı), ama oturum geçmiş
        // değil, anlık bir yetkidir: personel yoksa oturumu da olmamalı.
        sess.HasOne(x => x.Technician)
            .WithMany()
            .HasForeignKey(x => x.TechnicianId)
            .OnDelete(DeleteBehavior.Cascade);

        // --- İlişki: bir teknisyenin ÇOK iş emri olur (one-to-many) ------
        tech.HasMany(t => t.WorkOrders)      // teknisyenin iş emirleri
            .WithOne(o => o.Technician)      // her iş emrinin bir teknisyeni
            .HasForeignKey(o => o.TechnicianId)
            // Teknisyen silinirse iş emirleri SİLİNMEZ, ataması boşalır.
            // Varsayılan davranış silmek olsaydı bir personel kaydını
            // kaldırmak bakım geçmişini yok ederdi — kabul edilemez.
            .OnDelete(DeleteBehavior.SetNull);

        wo.HasIndex(o => o.TechnicianId);

        // --- Demo teknisyenleri ------------------------------------------
        // HasData: başlangıç verisi migration'ın İÇİNE yazılır. Ayrı bir
        // "seed" betiği çalıştırmaya gerek kalmaz; veritabanı nerede
        // kurulursa kurulsun bu kayıtlar hazır gelir.
        // (Python tarafında bunu ml/seed.py ile elle yapıyorduk.)
        tech.HasData(
            new Technician { Id = "TK-01", EmployeeNo = "10247", Name = "Ahmet Yılmaz",
                Region = "Marmara", Specialty = Specialty.Electrical,
                Role = PersonnelRole.Technician,
                MaxOpenOrders = 3, IsActive = true },
            new Technician { Id = "TK-02", EmployeeNo = "10318", Name = "Elif Demir",
                Region = "Marmara", Specialty = Specialty.Thermal,
                Role = PersonnelRole.Engineer,
                MaxOpenOrders = 3, IsActive = true },
            new Technician { Id = "TK-03", EmployeeNo = "10455", Name = "Mehmet Kaya",
                Region = "Marmara", Specialty = Specialty.Sampling,
                Role = PersonnelRole.Technician,
                MaxOpenOrders = 5, IsActive = true },
            new Technician { Id = "TK-04", EmployeeNo = "10502", Name = "Zeynep Şahin",
                Region = "Ege", Specialty = Specialty.General,
                Role = PersonnelRole.Supervisor,
                MaxOpenOrders = 4, IsActive = true },
            new Technician { Id = "TK-05", EmployeeNo = "10611", Name = "Burak Aydın",
                Region = "İç Anadolu", Specialty = Specialty.General,
                Role = PersonnelRole.Technician,
                MaxOpenOrders = 4, IsActive = true },
            new Technician { Id = "TK-06", EmployeeNo = "10740", Name = "Selin Öztürk",
                Region = "Akdeniz", Specialty = Specialty.Sampling,
                Role = PersonnelRole.Engineer,
                MaxOpenOrders = 4, IsActive = true });
    }
}
