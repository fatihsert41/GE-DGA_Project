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

/// <summary>Personel — sistemin kullanıcı hesabı.</summary>
/// <remarks>
/// <c>WorkOrder</c> gibi bir varlık (entity), o yüzden <c>class</c>.
/// Sınıfın adı tarihsel olarak "Technician" kaldı (Faz 7.6'da yalnızca
/// saha teknisyenleri vardı); bugün her departmandan kullanıcıyı temsil
/// ediyor. Adı değiştirmek tablo, ilişki ve migration zincirine dokunurdu
/// ve hiçbir davranış kazandırmazdı.
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

    public Specialty Specialty { get; set; }

    /// <summary>Çalıştığı birim — sistemde NE YAPABİLECEĞİNİ belirler. (Faz 10)</summary>
    /// <remarks>
    /// Yetki haritası <c>Models/Department.cs</c> içinde. Varsayılan
    /// <c>FieldService</c>: yeni açılan bir kayıt en dar yetkiyle başlar,
    /// genişletmek yönetimin kararıdır. Tersi (varsayılan tam yetki)
    /// unutulan her kaydı açık bir kapıya çevirirdi.
    /// </remarks>
    public Department Department { get; set; } = Department.FieldService;

    /// <summary>Aynı anda üstlenebileceği açık iş sayısı.</summary>
    /// <remarks>
    /// Kapasite olmadan otomatik atama tek kişiyi ezer. Gerçek planlama
    /// sistemlerinde bu bir takvim hesabıdır; burada basit bir sayı.
    /// </remarks>
    public int MaxOpenOrders { get; set; } = 3;

    public bool IsActive { get; set; } = true;

    // --- Kimlik doğrulama -------------------------------------------------
    //
    // Parolanın KENDİSİ hiçbir zaman saklanmaz; yalnızca özeti ve tuzu.
    // Ayrıntılı gerekçe: Services/PasswordHasher.cs
    //
    // Faz 9.0b'de bu alanlar 4 haneli PIN içindi. Sistem Yönetimi fazında
    // parolaya geçildi; C# adları değişti, veritabanı sütun adları
    // (PinHash / PinSalt) KORUNDU — bkz. DbContext. Sütun yeniden
    // adlandırmak hiçbir davranış kazandırmadan migration riski eklerdi.
    //
    // ⚠ [JsonIgnore] ŞART (Faz 10'da fark edilen açık): iş emri JSON'a
    // çevrilirken içindeki Technician nesnesi BÜTÜN alanlarıyla
    // yazılıyordu. Kural: kimlik doğrulama alanları hiçbir cevap
    // gövdesine girmez.

    /// <summary>Parola özeti (PBKDF2). Düz metin parola asla saklanmaz.</summary>
    [JsonIgnore]
    public string PasswordHash { get; set; } = string.Empty;

    /// <summary>Kişiye özel tuz — aynı parola farklı özet üretsin diye.</summary>
    [JsonIgnore]
    public string PasswordSalt { get; set; } = string.Empty;

    /// <summary>Parola geçici mi — ilk girişte değiştirilmeli mi?</summary>
    /// <remarks>
    /// Yeni hesapta ve sıfırlamada <c>true</c>. Bu durumdayken verilen
    /// belirtecin yetki listesi BOŞTUR: kullanıcı parolasını değiştirmeden
    /// hiçbir işlem yapamaz — Python servisinde bile, çünkü Python yetkiyi
    /// belirteçten okuyor.
    ///
    /// Neden gerekli? Geçici parolayı iki kişi bilir: kullanıcı ve onu
    /// veren admin. Kullanıcı değiştirene kadar hesap "yalnızca onun" değildir.
    /// </remarks>
    [JsonIgnore]
    public bool MustChangePassword { get; set; }

    [JsonIgnore]
    public DateTime? PasswordChangedAt { get; set; }

    /// <summary>Arka arkaya yanlış parola denemesi sayısı.</summary>
    /// <remarks>
    /// Özetleme tek başına yetmez: sınırsız deneme hakkı olan bir betik
    /// zayıf parolayı eninde sonunda bulur. Başarılı girişte SIFIRLANIR.
    /// </remarks>
    [JsonIgnore]
    public int FailedAttempts { get; set; }

    /// <summary>Bu ana kadar giriş kapalı (null ise kapalı değil).</summary>
    [JsonIgnore]
    public DateTime? LockedUntil { get; set; }

    /// <summary>Son başarılı giriş — "bu hesap hiç kullanıldı mı?"</summary>
    [JsonIgnore]
    public DateTime? LastLoginAt { get; set; }

    // --- Hesap yaşam döngüsü (Sistem Yönetimi) ------------------------------
    //
    // DateTime? ve BAŞLANGIÇ DEĞERİ YOK — bilinçli. "= DateTime.UtcNow"
    // yazsaydık, HasData ile gelen demo kayıtları her migration üretiminde
    // "değişmiş" görünür ve EF her seferinde yeni bir veri güncelleme
    // migration'ı üretirdi. Kurulumla gelen kayıtlarda null = "sistemle
    // birlikte geldi".

    [JsonIgnore]
    public DateTime? CreatedAt { get; set; }

    [JsonIgnore]
    public string? CreatedByName { get; set; }

    [JsonIgnore]
    public DateTime? DeactivatedAt { get; set; }

    [JsonIgnore]
    public string? DeactivationReason { get; set; }

    /// <summary>Bu teknisyene atanmış iş emirleri.</summary>
    /// <remarks>
    /// <b>Navigation property (gezinme özelliği).</b> Veritabanında böyle bir
    /// sütun YOKTUR; ilişki <c>work_orders.TechnicianId</c> sütununda durur.
    ///
    /// [JsonIgnore] ŞART: iş emri JSON'a çevrilirken içindeki teknisyeni de
    /// yazar, teknisyen de iş emirlerini yazar... Sonsuz döngü.
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
/// </remarks>
public record RecordedBy(string EmployeeNo, string Name, string Role);
