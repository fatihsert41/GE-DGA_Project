using Microsoft.EntityFrameworkCore;
using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Data;

/// <summary>Teknisyen verisi ve yük hesapları.</summary>
public class TechnicianRepository
{
    private readonly MaintenanceDbContext _db;

    public TechnicianRepository(MaintenanceDbContext db)
    {
        _db = db;
    }

    public async Task<List<Technician>> ListAsync(CancellationToken ct = default)
    {
        return await _db.Technicians
            .OrderBy(t => t.Region)
            .ThenBy(t => t.Id)
            .ToListAsync(ct);
    }

    public async Task<Technician?> GetAsync(string id,
                                            CancellationToken ct = default)
    {
        return await _db.Technicians.FindAsync([id], ct);
    }

    /// <summary>Her teknisyenin açık iş sayısıyla birlikte listesi.</summary>
    public async Task<List<TechnicianWorkload>> WorkloadsAsync(
        CancellationToken ct = default)
    {
        var technicians = await _db.Technicians.ToListAsync(ct);

        // Açık iş sayılarını TEK sorguda al.
        // Alternatif, her teknisyen için ayrı sorgu açmaktı: 6 teknisyen ->
        // 7 sorgu. Buna "N+1 sorgu problemi" denir ve ORM kullanan
        // projelerdeki en yaygın performans hatasıdır.
        var openCounts = await _db.WorkOrders
            .Where(o => o.TechnicianId != null
                        && (o.Status == WorkOrderStatus.Planned
                            || o.Status == WorkOrderStatus.InProgress))
            .GroupBy(o => o.TechnicianId!)
            .Select(g => new { TechnicianId = g.Key, Count = g.Count() })
            .ToListAsync(ct);

        var counts = openCounts.ToDictionary(x => x.TechnicianId, x => x.Count);

        return technicians
            .Select(t =>
            {
                var open = counts.GetValueOrDefault(t.Id, 0);
                return new TechnicianWorkload(t, open,
                                              open < t.MaxOpenOrders);
            })
            .OrderBy(w => w.Technician.Region)
            .ThenBy(w => w.Technician.Id)
            .ToList();
    }

    /// <summary>İş emrine teknisyen atar.</summary>
    public async Task<WorkOrder?> AssignAsync(string workOrderId,
                                              string technicianId,
                                              CancellationToken ct = default)
    {
        var order = await _db.WorkOrders
            // Include: ilişkili teknisyeni de getir (JOIN).
            // Olmadan order.Technician null gelirdi — EF Core ilişkileri
            // istemeden yüklemez, çünkü her sorguda tüm ilişkileri çekmek
            // veritabanını gereksiz yorar.
            .Include(o => o.Technician)
            .FirstOrDefaultAsync(o => o.Id == workOrderId, ct);

        if (order is null)
        {
            return null;
        }

        order.TechnicianId = technicianId;
        await _db.SaveChangesAsync(ct);

        // Atamadan sonra navigation'ı tazele ki cevapta teknisyen adı görünsün.
        await _db.Entry(order).Reference(o => o.Technician).LoadAsync(ct);
        return order;
    }
}
