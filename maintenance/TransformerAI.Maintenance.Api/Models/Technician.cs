using System.Text.Json.Serialization;

namespace TransformerAI.Maintenance.Api.Models;

/// <summary>Teknisyenin uzmanlık alanı.</summary>
/// <remarks>
/// Arıza ailesiyle eşleşir: deşarj arızaları elektriksel, aşırı ısınma
/// termal uzmanlık ister. <c>General</c> her işi yapabilir ama eşleşme
/// puanı düşüktür — yani uzman varsa o tercih edilir.
/// </remarks>
public enum Specialty
{
    General = 0,
    Electrical = 1,   // PD, D1, D2 — deşarj ailesi
    Thermal = 2,      // T1, T2, T3 — termal aile
    Sampling = 3,     // yağ numunesi alma
}

/// <summary>Personelin sistemdeki rolü. (Faz 9.0)</summary>
/// <remarks>
/// Uzmanlıktan (<c>Specialty</c>) FARKLI bir şey. Uzmanlık "hangi işi
/// yapabilir" sorusunu, rol "sistemde ne görür, neyi onaylar" sorusunu
/// cevaplar. Bir teknisyen termal uzmanı olabilir ama süpervizör
/// olmayabilir.
///
/// GE Vernova'nın APM ürünü de ekranlarını bu üç rol üzerinden
/// tanımlıyor: operatör, güvenilirlik/performans mühendisi, süpervizör.
/// Faz 9.3'teki yönetici ekranı bu ayrıma dayanacak.
/// </remarks>
public enum PersonnelRole
{
    Technician = 0,   // saha: ölçüm alır, iş emrini yürütür
    Engineer = 1,     // değerlendirir, iş emri açar, test yorumlar
    Supervisor = 2,   // filo geneli görür, öncelik ve bütçe kararı verir
}

/// <summary>Saha teknisyeni.</summary>
/// <remarks>
/// <c>WorkOrder</c> gibi bir varlık (entity), o yüzden <c>class</c>.
/// </remarks>
public class Technician
{
    public string Id { get; set; } = string.Empty;

    /// <summary>Kurum sicil numarası. (Faz 9.0)</summary>
    /// <remarks>
    /// <c>Id</c> sistemin iç anahtarı ("TK-01"); bu ise kurumun personele
    /// verdiği numara. İkisini ayırmak önemli: sicil numarası kurumun
    /// verisidir, biz üretmeyiz ve değiştiremeyiz. Sisteme giriş bununla
    /// yapılır, çünkü sahadaki kişi kendi iç anahtarımızı bilmez.
    ///
    /// BENZERSİZ olmalı — aksi halde "bu kaydı kim girdi?" sorusunun
    /// birden çok cevabı olur ve izlenebilirlik çöker.
    /// </remarks>
    public string EmployeeNo { get; set; } = string.Empty;

    public string Name { get; set; } = string.Empty;

    /// <summary>Sistemdeki rolü — ne görür, neyi onaylar. (Faz 9.0)</summary>
    public PersonnelRole Role { get; set; } = PersonnelRole.Technician;

    /// <summary>Sorumlu olduğu bölge, ör. "Marmara".</summary>
    public string Region { get; set; } = string.Empty;

    public Specialty Specialty { get; set; }

    /// <summary>Aynı anda üstlenebileceği açık iş sayısı.</summary>
    /// <remarks>
    /// Kapasite olmadan otomatik atama tek kişiyi ezer. Gerçek planlama
    /// sistemlerinde bu bir takvim hesabıdır; burada basit bir sayı.
    /// </remarks>
    public int MaxOpenOrders { get; set; } = 3;

    public bool IsActive { get; set; } = true;

    /// <summary>Bu teknisyene atanmış iş emirleri.</summary>
    /// <remarks>
    /// <b>Navigation property (gezinme özelliği).</b> Veritabanında böyle bir
    /// sütun YOKTUR; ilişki <c>work_orders.TechnicianId</c> sütununda durur.
    /// Bu özellik, ilişkiyi C# tarafında nesne olarak gezebilmek içindir:
    /// <c>technician.WorkOrders</c> yazınca EF Core arka planda JOIN yapar.
    ///
    /// Python tarafında bunu elle yapardık: ayrı bir sorgu çalıştırıp
    /// sonuçları birleştirmek. Burada ilişki modelin parçası.
    ///
    /// [JsonIgnore] ŞART: iş emri JSON'a çevrilirken içindeki teknisyeni de
    /// yazar, teknisyen de iş emirlerini yazar, o iş emirleri de teknisyeni...
    /// Sonsuz döngü. Bu özellik SORGU için var, cevap gövdesi için değil.
    /// </remarks>
    [JsonIgnore]
    public List<WorkOrder> WorkOrders { get; set; } = new();
}

/// <summary>Bir teknisyenin anlık yükü — hesaplanan değer, tabloda durmaz.</summary>
public record TechnicianWorkload(
    Technician Technician,
    int OpenOrders,
    bool HasCapacity);

/// <summary>İş emrine teknisyen atama isteği.</summary>
/// <remarks>
/// <c>TechnicianId</c> boş bırakılırsa sistem en uygun teknisyeni kendisi
/// seçer. Dolu gelirse planlama mühendisinin kararı geçerlidir — otomatik
/// sistem insanın kararını ezmemeli.
/// </remarks>
public record AssignRequest(string? TechnicianId = null);


/// <summary>Bir kaydın "kim girdi" bilgisi — anlık görüntü. (Faz 9.0)</summary>
/// <remarks>
/// Neden yalnızca sicil no saklayıp adı personel kaydından okumuyoruz?
/// Çünkü <b>geçmiş kayıt değişmemelidir.</b> Personel işten ayrılsa,
/// soyadı değişse ya da kaydı kaldırılsa bile üç yıl önceki testin kim
/// tarafından yapıldığı okunabilir kalmalı.
///
/// Bu, Faz 8.6'daki "kayıt silinmez, geçersiz işaretlenir" kararıyla
/// aynı ilkenin devamı: geçmiş, bugünün durumuna göre yeniden yazılmaz.
///
/// ⚠ Bu bir GÜVENLİK katmanı değildir — parola yoktur, herkes herkesin
/// sicilini seçebilir. Amaç izlenebilirlik (traceability): kaydın
/// sorumlusunu belirlemek, kötü niyetliyi engellemek değil.
/// </remarks>
public record RecordedBy(string EmployeeNo, string Name, string Role);
