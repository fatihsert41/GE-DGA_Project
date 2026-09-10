using Microsoft.EntityFrameworkCore;
using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Data;

/// <summary>
/// İş emri veri erişimi. 7.2'deki bellek deposunun (WorkOrderStore) yerini alır.
/// </summary>
/// <remarks>
/// <b>Neden "repository" (depo) deseni?</b> Uç noktalar veritabanının nasıl
/// çalıştığını bilmesin diye. Program.cs "iş emri listesi ver" der; bunun
/// SQLite'tan mı PostgreSQL'den mi geldiği onu ilgilendirmez. Python
/// tarafında da aynısını yapmıştık: routers/ HTTP'yi, services/ iş
/// mantığını, database.py veriyi biliyordu.
///
/// <b>Neden her metot <c>async</c>?</b> Veritabanı bir DOSYAYA gider ve
/// cevap gelene kadar milisaniyeler geçer. Senkron yazarsak o süre boyunca
/// iş parçacığı (thread) boş boş bekler; 100 eşzamanlı istek gelirse 100
/// iş parçacığı bekliyor olur ve sunucu tıkanır.
///
/// <c>await</c> ile iş parçacığı serbest kalır, başka isteklere bakar,
/// veritabanı cevap verince kaldığı yerden devam eder. Python'daki
/// <c>async def</c> / <c>await</c> ile aynı mantık — ama .NET'te bu bir
/// tercih değil, veri erişiminin STANDART yazım biçimidir.
///
/// Kural: <c>async</c> bir metot <c>Task</c> döndürür.
/// <c>Task&lt;WorkOrder&gt;</c> = "ileride bir WorkOrder verecek olan iş".
/// Python'daki <c>Awaitable[WorkOrder]</c> ile aynı fikir.
/// </remarks>
public class WorkOrderRepository
{
    private readonly MaintenanceDbContext _db;

    public WorkOrderRepository(MaintenanceDbContext db)
    {
        _db = db;
    }

    /// <summary>Süzülmüş ve önceliğe göre sıralı iş emirleri.</summary>
    public async Task<List<WorkOrder>> ListAsync(WorkOrderStatus? status = null,
                                                 string? transformerId = null)
    {
        // AsQueryable: sorguyu parça parça kurmaya başla.
        // Buradaki Where/OrderBy çağrıları BELLEKTE çalışmaz — EF Core
        // hepsini biriktirip TEK bir SQL cümlesine çevirir ve veritabanına
        // öyle gönderir. Yani 1000 satır çekip sonra süzmüyoruz.
        // Include: atanan teknisyeni de getir. Olmadan order.Technician
        // null gelir ve arayüzde "atanmadı" yazar — ilişkiyi kurmuş olmak
        // yetmiyor, o sorguda İSTEMEK gerekiyor.
        var query = _db.WorkOrders.Include(o => o.Technician).AsQueryable();

        if (status is not null)
        {
            query = query.Where(o => o.Status == status);
        }

        if (!string.IsNullOrWhiteSpace(transformerId))
        {
            query = query.Where(o => o.TransformerId == transformerId);
        }

        // ToListAsync sorguyu ÇALIŞTIRAN adımdır. O ana kadar hiçbir şey
        // veritabanına gitmedi (LINQ tembeldir — 7.2'de görmüştük).
        return await query
            .OrderByDescending(o => o.Priority)
            .ThenBy(o => o.CreatedAt)
            .ToListAsync();
    }

    public async Task<WorkOrder?> GetAsync(string id)
    {
        // FindAsync Include desteklemez (önce belleğe bakar), bu yüzden
        // ilişkili veri gerektiğinde normal sorgu kullanılır.
        return await _db.WorkOrders
            .Include(o => o.Technician)
            .FirstOrDefaultAsync(o => o.Id == id);
    }

    /// <summary>Kimlik çakışmasında kaç kez yeniden denenecek.</summary>
    private const int MaxIdRetries = 5;

    public async Task<WorkOrder> AddAsync(CreateWorkOrderRequest request)
    {
        // Eşzamanlı iki istek aynı sıra numarasını alabilir. Veritabanındaki
        // TEKİL indeks ikinciyi reddeder; burada yeniden deniyoruz.
        // "Önce kontrol et, sonra yaz" yaklaşımı yarışı çözmez — iki istek
        // aynı anda kontrol edip ikisi de boş bulabilir. Doğru çözüm:
        // veritabanına yazdır, reddedilirse tekrar dene.
        for (var attempt = 0; ; attempt++)
        {
            try
            {
                return await TryAddAsync(request);
            }
            catch (DbUpdateException) when (attempt < MaxIdRetries)
            {
                // Numara kapılmış; izlenen nesneyi bırak ve yeniden dene.
                _db.ChangeTracker.Clear();
            }
        }
    }

    private async Task<WorkOrder> TryAddAsync(CreateWorkOrderRequest request)
    {
        var nextSeq = await NextSeqAsync();
        var order = new WorkOrder
        {
            Seq = nextSeq,
            Id = $"WO-{nextSeq:D4}",
            TransformerId = request.TransformerId.Trim(),
            Kind = request.Kind,
            Title = request.Title.Trim(),
            Reason = request.Reason,
            Priority = request.Priority,
            DueDate = request.DueDate,
            Status = WorkOrderStatus.Planned,
            CreatedAt = DateTime.UtcNow,
        };

        _db.WorkOrders.Add(order);

        // Add() henüz veritabanına yazmaz; sadece "bunu ekleyeceğim" der.
        // Yazma işi SaveChangesAsync'te olur ve TEK BİR İŞLEM (transaction)
        // içinde gerçekleşir: ya hepsi yazılır ya hiçbiri.
        await _db.SaveChangesAsync();
        return order;
    }

    /// <summary>Durum güncelleme sonucu — neden reddedildiğini de taşır.</summary>
    public record StatusResult(WorkOrder? Order, string? Error);

    public async Task<StatusResult> UpdateStatusAsync(string id,
                                                      UpdateStatusRequest request)
    {
        var order = await _db.WorkOrders
            .Include(o => o.Technician)
            .FirstOrDefaultAsync(o => o.Id == id);
        if (order is null)
        {
            return new StatusResult(null, null);   // bulunamadı
        }

        // Geçiş kuralı: durum makinesi dışına çıkılamaz.
        if (!WorkOrderTransitions.IsAllowed(order.Status, request.Status))
        {
            return new StatusResult(
                order, WorkOrderTransitions.Explain(order.Status, request.Status));
        }

        // Tamamlanma kanıtı: yapılan işin kaydı olmadan kapatma yok.
        if (request.Status == WorkOrderStatus.Done
            && string.IsNullOrWhiteSpace(request.Note))
        {
            return new StatusResult(
                order, "İş emrini tamamlamak için yapılan işi anlatan bir "
                       + "not (note) zorunludur.");
        }

        order.Status = request.Status;
        if (!string.IsNullOrWhiteSpace(request.Note))
        {
            order.CompletionNote = request.Note.Trim();
        }

        order.CompletedAt = request.Status == WorkOrderStatus.Done
            ? DateTime.UtcNow
            : null;

        // Nesneyi "güncelle" diye bildirmemize gerek yok: EF Core, FindAsync
        // ile getirdiği nesneyi İZLER (change tracking) ve neyin değiştiğini
        // kendisi bulup sadece o sütunlar için UPDATE üretir.
        await _db.SaveChangesAsync();
        return new StatusResult(order, null);
    }

    /// <summary>Mevcut bir emrin aciliyetini yükseltir.</summary>
    /// <remarks>
    /// Yeni emir AÇMAZ, mevcut olanı günceller. Sebep alanına eklenen not
    /// geçmişi korur: emrin neden ve ne zaman yükseltildiği görünür kalır.
    /// </remarks>
    public async Task<WorkOrder?> EscalateAsync(string id, double newPriority,
                                                DateOnly newDueDate,
                                                string reason,
                                                CancellationToken ct = default)
    {
        var order = await _db.WorkOrders
            .Include(o => o.Technician)
            .FirstOrDefaultAsync(o => o.Id == id, ct);
        if (order is null)
        {
            return null;
        }

        order.Priority = newPriority;
        order.DueDate = newDueDate;

        var stamp = DateTime.UtcNow.ToString("yyyy-MM-dd");
        // Yeni not ALTA eklenir, eskisi silinmez: emrin neden ve ne
        // zaman yükseltildiği geçmişte kalmalı.
        order.Reason = string.IsNullOrWhiteSpace(order.Reason)
            ? $"[{stamp}] {reason}"
            : order.Reason + Environment.NewLine + $"[{stamp}] {reason}";

        await _db.SaveChangesAsync(ct);
        return order;
    }

    /// <summary>Panoda gösterilecek özet sayımlar.</summary>
    public async Task<object> SummaryAsync()
    {
        // GroupBy veritabanında çalışır: SELECT status, COUNT(*) ... GROUP BY
        var counts = await _db.WorkOrders
            .GroupBy(o => o.Status)
            .Select(g => new { Status = g.Key, Count = g.Count() })
            .ToListAsync();

        var byStatus = Enum.GetValues<WorkOrderStatus>()
            .ToDictionary(
                s => s.ToString(),
                // Sayımı olmayan durum için 0 yaz: API'nin ŞEKLİ sabit
                // kalmalı, yoksa arayüzdeki grafik sütunları kayar.
                // (Python tarafında risk dağılımında da aynısını yapmıştık.)
                s => counts.FirstOrDefault(c => c.Status == s)?.Count ?? 0);

        return new
        {
            total = counts.Sum(c => c.Count),
            byStatus,
            open = byStatus["Planned"] + byStatus["InProgress"],
        };
    }

    /// <summary>Sıradaki sayısal sıra numarası.</summary>
    /// <remarks>
    /// SAYI üzerinde MAX alıyoruz, metin üzerinde değil. Eskiden kimlik
    /// metni sıralanıyordu ve alfabetik olarak WO-9999 > WO-10001 çıkıyordu;
    /// 9999'dan sonra üretici aynı numarayı tekrar veriyordu.
    ///
    /// Yarış durumu burada ÇÖZÜLMEZ — çözümü tekil indeks + yeniden deneme
    /// (bkz. AddAsync). Bu metot yalnızca makul bir aday üretir.
    /// </remarks>
    private async Task<int> NextSeqAsync()
    {
        var max = await _db.WorkOrders
            .Select(o => (int?)o.Seq)
            .MaxAsync();
        return (max ?? 0) + 1;
    }
}
