using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Data;

/// <summary>
/// İş emirlerini BELLEKTE tutan geçici depo.
/// </summary>
/// <remarks>
/// Bu sınıf 7.3'te EF Core + SQLite ile değiştirilecek. Şimdilik bellekte
/// olması bilinçli: tek seferde tek kavram öğreniyoruz. Önce modelin ve
/// uç noktaların şeklini oturtuyoruz, veritabanı sonra geliyor.
///
/// Uygulama yeniden başlayınca veriler kaybolur — beklenen davranış.
/// </remarks>
public class WorkOrderStore
{
    // List<WorkOrder> = "WorkOrder tutan liste". Python'daki list ile aynı,
    // farkı: İÇİNE NE KOYULACAĞI tipte yazılı. Yanlış tipte bir şey eklemek
    // derlenmez. Buna "generic" (jenerik) denir; <T> kısmı tip parametresidir.
    private readonly List<WorkOrder> _orders = new();

    private int _counter;

    // _lock: aynı anda birden çok HTTP isteği gelirse listeyi bozmasınlar
    // diye kilit. Web sunucusu istekleri PARALEL işler; Python'da GIL
    // sayesinde bu risk daha az görünürdü, .NET'te gerçek çoklu iş parçacığı
    // (thread) vardır ve bunu düşünmek zorundayız.
    private readonly Lock _lock = new();

    /// <summary>Tüm iş emirleri; istenirse duruma ve trafoya göre süzülür.</summary>
    public IReadOnlyList<WorkOrder> List(WorkOrderStatus? status = null,
                                         string? transformerId = null)
    {
        lock (_lock)
        {
            // ── LINQ ──────────────────────────────────────────────────────
            // C#'ın en sevilen özelliği: koleksiyonları zincirleme sorgulama.
            // Python karşılığı:
            //   [o for o in orders if o.status == status]
            //   sorted(..., key=lambda o: (-o.priority, o.created_at))
            //
            // Where  -> filtrele      (Python: if ... / filter)
            // OrderByDescending -> büyükten küçüğe sırala
            // ThenBy -> eşitlik durumunda ikinci ölçüt
            // ToList -> sorguyu çalıştır ve listeye çevir
            //
            // LINQ TEMBELDİR: ToList() çağrılana kadar hiçbir şey çalışmaz.
            // Bu sayede zincirin tamamı tek geçişte işlenebilir.
            return _orders
                .Where(o => status is null || o.Status == status)
                .Where(o => transformerId is null || o.TransformerId == transformerId)
                .OrderByDescending(o => o.Priority)
                .ThenBy(o => o.CreatedAt)
                .ToList();
        }
    }

    public WorkOrder? Get(string id)
    {
        lock (_lock)
        {
            // FirstOrDefault: eşleşen ilk öğe, yoksa null.
            // Python'daki next((o for o in orders if ...), None) karşılığı.
            return _orders.FirstOrDefault(o => o.Id == id);
        }
    }

    public WorkOrder Add(CreateWorkOrderRequest request)
    {
        lock (_lock)
        {
            _counter++;
            var order = new WorkOrder
            {
                // WO-0001 biçimi: D4 = "4 haneye tamamla, başına sıfır koy".
                Id = $"WO-{_counter:D4}",
                TransformerId = request.TransformerId,
                Kind = request.Kind,
                Title = request.Title,
                Reason = request.Reason,
                Priority = request.Priority,
                DueDate = request.DueDate,
                Status = WorkOrderStatus.Planned,
                CreatedAt = DateTimeOffset.UtcNow,
            };
            // $"..." = Python'daki f-string. Aynı iş, aynı mantık.

            _orders.Add(order);
            return order;
        }
    }

    /// <summary>Durumu günceller; iş emri yoksa null döner.</summary>
    public WorkOrder? UpdateStatus(string id, UpdateStatusRequest request)
    {
        lock (_lock)
        {
            var order = _orders.FirstOrDefault(o => o.Id == id);
            if (order is null)
            {
                return null;
            }

            order.Status = request.Status;

            if (request.AssignedTo is not null)
            {
                order.AssignedTo = request.AssignedTo;
            }

            // Tamamlandıysa zamanı damgala; geri alınırsa damgayı temizle.
            order.CompletedAt = request.Status == WorkOrderStatus.Done
                ? DateTimeOffset.UtcNow
                : null;

            return order;
        }
    }

    /// <summary>Panoda gösterilecek özet sayımlar.</summary>
    public object Summary()
    {
        lock (_lock)
        {
            return new
            {
                total = _orders.Count,
                // GroupBy + ToDictionary: Python'daki Counter'ın karşılığı.
                // Sonuç {"Planned": 3, "Done": 1} gibi bir sözlük olur.
                byStatus = Enum.GetValues<WorkOrderStatus>()
                    .ToDictionary(s => s.ToString(),
                                  s => _orders.Count(o => o.Status == s)),
                open = _orders.Count(o => o.Status is WorkOrderStatus.Planned
                                              or WorkOrderStatus.InProgress),
                // "is ... or ..." = Python'daki "in (a, b)" ifadesi.
            };
        }
    }
}
