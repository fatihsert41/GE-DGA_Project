namespace TransformerAI.Maintenance.Api.Models;

// namespace = Python'daki modül yolu (app.models gibi). C#'ta klasör yapısı
// ile namespace'in eşleşmesi gelenektir: Models/ klasörü -> .Models namespace.

/// <summary>
/// İş emrinin yaşam döngüsü. Bir iş emri bu dört durumdan birindedir.
/// </summary>
/// <remarks>
/// <c>enum</c>, "sadece şu değerlerden biri olabilir" demenin C# yoludur.
/// Python'da string kullanırdık ("planned", "done") ve yanlış yazınca
/// ancak çalışma anında fark ederdik. Burada <c>Status = "dnoe"</c> yazmak
/// DERLENMEZ. Python'ın <c>enum.Enum</c> sınıfına benzer ama dilin
/// çekirdeğinde olduğu için her yerde bedava tip güvenliği sağlar.
/// </remarks>
public enum WorkOrderStatus
{
    Planned = 0,      // planlandı, henüz başlanmadı
    InProgress = 1,   // saha ekibi işe başladı
    Done = 2,         // tamamlandı
    Cancelled = 3,    // iptal edildi (ör. arıza teyit edilmedi)
}

/// <summary>
/// Yapılacak işin türü. Bakım kararı bu seviyede verilir.
/// </summary>
public enum WorkOrderKind
{
    Inspection = 0,   // detaylı inceleme
    Sampling = 1,     // yağ numunesi alma (numunesi gecikmiş trafolar)
    Repair = 2,       // onarım
    Replacement = 3,  // ünite değişimi
}

/// <summary>
/// Bir bakım iş emri. Sistemin çekirdek varlığı (entity).
/// </summary>
/// <remarks>
/// Neden <c>record</c> değil <c>class</c>?
/// <c>record</c> DEĞİŞMEYEN veri taşımak içindir (bir istek gövdesi gibi).
/// İş emri ise yaşayan bir şeydir: durumu değişir, teknisyen atanır,
/// tamamlanma tarihi dolar. Kimliği (Id) sabit kalırken içeriği değişen
/// nesnelere .NET'te <c>class</c> denir. 7.3'te veritabanına bunu
/// bağlayacağız; EF Core da <c>class</c> bekler.
/// </remarks>
public class WorkOrder
{
    /// <summary>Benzersiz iş emri numarası, ör. WO-0001.</summary>
    public string Id { get; set; } = string.Empty;

    /// <summary>Hangi trafo için açıldı (Python servisindeki id: TR-01).</summary>
    public string TransformerId { get; set; } = string.Empty;

    public WorkOrderKind Kind { get; set; }

    public string Title { get; set; } = string.Empty;

    /// <summary>Neden açıldı: tanı, risk, gecikmiş numune vb.</summary>
    public string? Reason { get; set; }

    public WorkOrderStatus Status { get; set; } = WorkOrderStatus.Planned;

    /// <summary>Python servisinden okunan öncelik skoru (kondisyon × ağırlık).</summary>
    public double Priority { get; set; }

    public string? AssignedTo { get; set; }

    public DateTimeOffset CreatedAt { get; set; } = DateTimeOffset.UtcNow;

    public DateOnly? DueDate { get; set; }

    public DateTimeOffset? CompletedAt { get; set; }

    // { get; set; } yazımına "property" (özellik) denir. Python'da
    // self.title = title ile alan tanımlarsın; C#'ta property hem alanı
    // hem de okuma/yazma erişimini tek satırda tanımlar.
    //
    // "= string.Empty" varsayılan değerdir. Zorunlu çünkü <Nullable>enable
    // açık: derleyici "bu string null kalabilir mi?" diye sorar ve
    // cevaplanmazsa uyarır. string? (soru işaretli) olanlar null olabilir.
}

/// <summary>
/// Yeni iş emri oluşturma isteği — istemciden gelen gövde.
/// </summary>
/// <remarks>
/// Burada <c>record</c> kullanıyoruz: gelen istek değişmez bir veri
/// paketidir. Python tarafındaki Pydantic modellerinin (schemas.py)
/// karşılığıdır.
///
/// Neden ayrı bir tip? İstemcinin Id, CreatedAt veya Status göndermesini
/// İSTEMİYORUZ — onları sunucu belirler. Varlık ile istek tipini ayırmak
/// bu yüzden standarttır (buna DTO denir: Data Transfer Object).
/// </remarks>
public record CreateWorkOrderRequest(
    string TransformerId,
    WorkOrderKind Kind,
    string Title,
    string? Reason = null,
    double Priority = 0,
    DateOnly? DueDate = null);

/// <summary>Durum güncelleme isteği.</summary>
public record UpdateStatusRequest(WorkOrderStatus Status, string? AssignedTo = null);
