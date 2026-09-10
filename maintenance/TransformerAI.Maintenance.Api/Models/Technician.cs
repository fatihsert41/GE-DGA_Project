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

/// <summary>Saha teknisyeni.</summary>
/// <remarks>
/// <c>WorkOrder</c> gibi bir varlık (entity), o yüzden <c>class</c>.
/// </remarks>
public class Technician
{
    public string Id { get; set; } = string.Empty;

    public string Name { get; set; } = string.Empty;

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
    /// </remarks>
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
