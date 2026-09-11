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
    // Faz 9.1: elektriksel test yapılması/tekrarlanması. Inspection'dan
    // ayrı, çünkü farklı bir iş: ekipman ve planlı kesinti gerektirir,
    // ayrıca sonucu "bir şey bul" değil "ölçümü doğrula".
    Test = 4,
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

    /// <summary>Sayısal sıra numarası — kimliğin kaynağı.</summary>
    /// <remarks>
    /// Neden ayrı bir sayı? Kimlik metin olarak sıralandığında
    /// <c>WO-9999 &gt; WO-10001</c> çıkıyordu (alfabetik sıra). Üretici
    /// "en büyük" olarak WO-9999'u görüp tekrar WO-10000 veriyordu ve
    /// birincil anahtar çakışıyordu. Sayı üzerinde sıralama bu sorunu
    /// tanım gereği ortadan kaldırır.
    ///
    /// Üzerinde TEKİL indeks var: iki paralel istek aynı numarayı almaya
    /// çalışırsa veritabanı ikincisini reddeder ve depo yeniden dener.
    /// Doğruluğu uygulamaya değil veritabanına yaptırmak daha güvenli.
    /// </remarks>
    public int Seq { get; set; }

    /// <summary>Hangi trafo için açıldı (Python servisindeki id: TR-01).</summary>
    public string TransformerId { get; set; } = string.Empty;

    public WorkOrderKind Kind { get; set; }

    public string Title { get; set; } = string.Empty;

    /// <summary>Neden açıldı: tanı, risk, gecikmiş numune vb.</summary>
    public string? Reason { get; set; }

    public WorkOrderStatus Status { get; set; } = WorkOrderStatus.Planned;

    /// <summary>Python servisinden okunan öncelik skoru (kondisyon × ağırlık).</summary>
    public double Priority { get; set; }

    /// <summary>Atanan teknisyenin kimliği — yabancı anahtar (foreign key).</summary>
    /// <remarks>
    /// Önce burada serbest metin vardı ("Ahmet Y."). Sorunu şuydu: yazım
    /// hatası kimseyi rahatsız etmezdi, teknisyenin yükü hesaplanamazdı,
    /// adı değişince eski kayıtlar eski adı taşırdı.
    ///
    /// Şimdi Technician tablosuna işaret eden bir ANAHTAR. Veritabanı,
    /// olmayan bir teknisyene atama yapılmasına izin vermez — bu kurala
    /// "bütünlük kısıtı" (referential integrity) denir ve doğruluğu
    /// uygulamaya değil veritabanına yaptırmak her zaman daha güvenlidir.
    ///
    /// Nullable (?) çünkü yeni açılan iş emri henüz atanmamış olabilir.
    /// </remarks>
    public string? TechnicianId { get; set; }

    /// <summary>Atanan teknisyen — navigation property.</summary>
    public Technician? Technician { get; set; }

    // DateTimeOffset DEĞİL DateTime (UTC): SQLite, DateTimeOffset tipine
    // göre ORDER BY yapamıyor ve sorgu çalışma anında patlıyor. Biz zaten
    // her yerde UTC kullanıyoruz, saat dilimi farkını taşımaya gerek yok.
    // Ders: ORM soyutlaması sızdırır — veritabanının sınırlarını bilmek gerek.
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;

    public DateOnly? DueDate { get; set; }

    public DateTime? CompletedAt { get; set; }

    /// <summary>Tamamlanırken yazılan iş notu — bakım kaydının kanıtı.</summary>
    public string? CompletionNote { get; set; }

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
/// <remarks>
/// Teknisyen ataması ayrı bir uç noktadan yapılıyor
/// (POST /workorders/{id}/assign): bir isteğin tek bir işi olmalı.
///
/// <c>Note</c>, işi TAMAMLANDI'ya taşırken zorunludur: yapılan işin kaydı
/// olmadan iş emri kapatmak, denetlenemeyen bir bakım geçmişi üretir.
/// </remarks>
public record UpdateStatusRequest(WorkOrderStatus Status, string? Note = null);


/// <summary>İş emri durum makinesi — hangi geçiş serbest?</summary>
/// <remarks>
/// Önceden hiçbir kural yoktu: <c>Planned → Done</c> doğrudan yapılabiliyor,
/// tamamlanmış bir iş sessizce geri alınabiliyordu. Bakım kaydının
/// denetlenebilir olması için geçişlerin kısıtlı olması gerekir.
///
/// <code>
///   Planned ──► InProgress ──► Done
///      │             │
///      └─────────────┴────────► Cancelled ──► Planned (yeniden aç)
/// </code>
///
/// Done son durumdur: yanlışlıkla kapatılan bir iş "geri alınmaz", yeni
/// bir iş emri açılır. Böylece geçmiş silinmez.
/// </remarks>
public static class WorkOrderTransitions
{
    private static readonly Dictionary<WorkOrderStatus, WorkOrderStatus[]> Allowed =
        new()
        {
            [WorkOrderStatus.Planned] =
                [WorkOrderStatus.InProgress, WorkOrderStatus.Cancelled],
            [WorkOrderStatus.InProgress] =
                [WorkOrderStatus.Done, WorkOrderStatus.Cancelled],
            [WorkOrderStatus.Done] = [],
            [WorkOrderStatus.Cancelled] = [WorkOrderStatus.Planned],
        };

    public static bool IsAllowed(WorkOrderStatus from, WorkOrderStatus to) =>
        from == to || Allowed.GetValueOrDefault(from, []).Contains(to);

    public static IReadOnlyList<WorkOrderStatus> Next(WorkOrderStatus from) =>
        Allowed.GetValueOrDefault(from, []);

    /// <summary>Geçiş neden reddedildi? Kullanıcıya gösterilecek açıklama.</summary>
    public static string Explain(WorkOrderStatus from, WorkOrderStatus to)
    {
        var next = Next(from);
        if (next.Count == 0)
        {
            return $"'{from}' son durumdur; buradan geçiş yapılamaz. "
                   + "Yeni bir iş emri açın.";
        }

        return $"'{from}' durumundan '{to}' durumuna geçilemez. "
               + $"İzin verilen: {string.Join(", ", next)}.";
    }
}
