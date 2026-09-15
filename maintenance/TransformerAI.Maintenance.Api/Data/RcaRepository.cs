using Microsoft.EntityFrameworkCore;
using TransformerAI.Maintenance.Api.Models;
using TransformerAI.Maintenance.Api.Services;

namespace TransformerAI.Maintenance.Api.Data;

/// <summary>Kök neden analizi veri erişimi. (Faz 12.5)</summary>
/// <remarks>
/// Kurallar burada DEĞİL, <see cref="RcaRules"/> içinde. Depo yalnızca
/// "ne kayıtlı?" sorusunu cevaplar ve yazar.
/// </remarks>
public class RcaRepository
{
    private readonly MaintenanceDbContext _db;

    public RcaRepository(MaintenanceDbContext db)
    {
        _db = db;
    }

    /// <summary>Kayıtlı analizler — en yeni üstte. Süzgeçler isteğe bağlı.</summary>
    public async Task<List<RootCauseAnalysis>> ListAsync(string? transformerId = null,
                                                         FailureMode? mode = null,
                                                         CancellationToken ct = default)
    {
        // AsNoTracking: yalnızca okuyoruz. EF Core'un değişiklik izleme
        // kaydını tutmasına gerek yok; daha az bellek, daha hızlı sorgu.
        var query = _db.RootCauseAnalyses.AsNoTracking().AsQueryable();

        if (!string.IsNullOrWhiteSpace(transformerId))
            query = query.Where(r => r.TransformerId == transformerId);

        if (mode is not null)
            query = query.Where(r => r.FailureMode == mode);

        return await query.OrderByDescending(r => r.RecordedAt).ToListAsync(ct);
    }

    public Task<RootCauseAnalysis?> GetByWorkOrderAsync(string workOrderId,
                                                       CancellationToken ct = default) =>
        _db.RootCauseAnalyses.AsNoTracking()
            .FirstOrDefaultAsync(r => r.WorkOrderId == workOrderId, ct);

    /// <summary>Kaydeder; aynı iş emrine az önce başka bir analiz yazıldıysa null.</summary>
    /// <remarks>
    /// "Önce var mı diye bak, sonra yaz" iki eşzamanlı isteği ayırt edemez.
    /// WorkOrderId üzerindeki BENZERSİZ indeks ikinciyi reddeder; burada
    /// o reddi yakalayıp 409'a çeviriyoruz. (İş emri sıra numarasında da
    /// aynı ders: doğruluğu veritabanına yaptır.)
    /// </remarks>
    public async Task<RootCauseAnalysis?> AddAsync(RootCauseAnalysis rca,
                                                   CancellationToken ct = default)
    {
        _db.RootCauseAnalyses.Add(rca);
        try
        {
            await _db.SaveChangesAsync(ct);
            return rca;
        }
        catch (DbUpdateException)
        {
            _db.ChangeTracker.Clear();
            return null;
        }
    }

    /// <summary>Analiz bekleyen işler: tamamlanmış, RCA'sı yok, RCA gerektiriyor.</summary>
    /// <remarks>
    /// "Tamamlanmış ve analizi yok" kısmı veritabanında süzülür (tek SQL,
    /// <c>NOT EXISTS</c>). "Gerekli mi?" kısmı bellekte, çünkü kural
    /// <see cref="RcaRules"/> içinde yaşıyor ve SQL'e ikinci kez yazılırsa
    /// iki kural bir gün ayrışır.
    /// </remarks>
    public async Task<List<WorkOrder>> PendingAsync(CancellationToken ct = default)
    {
        var done = await _db.WorkOrders.AsNoTracking()
            .Include(o => o.Technician)
            .Where(o => o.Status == WorkOrderStatus.Done
                        && !_db.RootCauseAnalyses.Any(r => r.WorkOrderId == o.Id))
            .ToListAsync(ct);

        // En uzun bekleyen üstte: kök neden, iş kapandıktan sonra ne kadar
        // geç yazılırsa o kadar az hatırlanır.
        return done.Where(RcaRules.IsRequired)
            .OrderBy(o => o.CompletedAt)
            .ToList();
    }
}
