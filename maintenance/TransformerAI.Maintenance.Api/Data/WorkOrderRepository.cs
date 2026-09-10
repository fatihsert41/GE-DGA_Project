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
        var query = _db.WorkOrders.AsQueryable();

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
        // FindAsync birincil anahtarla arar ve önce bellekteki izlemeye bakar;
        // veritabanına gitmeden bulabilirse gitmez.
        return await _db.WorkOrders.FindAsync(id);
    }

    public async Task<WorkOrder> AddAsync(CreateWorkOrderRequest request)
    {
        var order = new WorkOrder
        {
            Id = await NextIdAsync(),
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

    public async Task<WorkOrder?> UpdateStatusAsync(string id,
                                                    UpdateStatusRequest request)
    {
        var order = await _db.WorkOrders.FindAsync(id);
        if (order is null)
        {
            return null;
        }

        order.Status = request.Status;

        if (request.AssignedTo is not null)
        {
            order.AssignedTo = request.AssignedTo;
        }

        order.CompletedAt = request.Status == WorkOrderStatus.Done
            ? DateTime.UtcNow
            : null;

        // Nesneyi "güncelle" diye bildirmemize gerek yok: EF Core, FindAsync
        // ile getirdiği nesneyi İZLER (change tracking) ve neyin değiştiğini
        // kendisi bulup sadece o sütunlar için UPDATE üretir.
        await _db.SaveChangesAsync();
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

    /// <summary>Sıradaki iş emri numarası: WO-0001, WO-0002 ...</summary>
    private async Task<string> NextIdAsync()
    {
        // Bellekteki sayaç kalıcı değildi; veritabanındaki en büyük numarayı
        // okuyup bir artırıyoruz. Tek örnek çalışan bir servis için yeterli.
        // (Birden çok kopya çalışsaydı yarış durumu oluşurdu; o zaman
        // veritabanı dizisi (sequence) kullanılırdı.)
        var last = await _db.WorkOrders
            .OrderByDescending(o => o.Id)
            .Select(o => o.Id)
            .FirstOrDefaultAsync();

        var next = 1;
        if (last is not null && int.TryParse(last[3..], out var n))
        {
            next = n + 1;
        }

        // last[3..] = "WO-0007" dizisinin 3. karakterinden sonrası -> "0007".
        // Buna "range" (aralık) söz dizimi denir; Python'daki last[3:] ile aynı.
        return $"WO-{next:D4}";
    }
}
