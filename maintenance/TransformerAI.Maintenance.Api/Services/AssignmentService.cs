using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Services;

/// <summary>
/// Bir iş emri için en uygun teknisyeni seçer.
/// </summary>
/// <remarks>
/// WorkOrderPlanner gibi bu sınıf da SAFTIR: HTTP ve veritabanı bilmez.
/// Girdi teknisyen yükleri + iş emri + trafo konumu, çıktı bir seçim.
/// Böylece "TR-01'in işi kime gitmeli?" sorusu veritabanı olmadan test edilir.
/// </remarks>
public class AssignmentService
{
    /// <summary>Şehir → bölge eşlemesi.</summary>
    /// <remarks>
    /// Trafo konumu "İstanbul-Avrupa" gibi gelir; teknisyen bölgesi
    /// "Marmara" olarak tutulur. Eşleme burada, tek yerde.
    /// </remarks>
    private static readonly Dictionary<string, string> CityToRegion = new()
    {
        ["İstanbul"] = "Marmara",
        ["Kocaeli"] = "Marmara",
        ["Bursa"] = "Marmara",
        ["Gebze"] = "Marmara",
        ["Çanakkale"] = "Marmara",
        ["İzmir"] = "Ege",
        ["Ankara"] = "İç Anadolu",
        ["Mersin"] = "Akdeniz",
    };

    /// <summary>Seçim ve gerekçesi.</summary>
    public record Assignment(Technician Technician, int Score, string Reason);

    /// <summary>Konumdan bölge çıkarır; bilinmiyorsa null.</summary>
    public static string? RegionOf(string? location)
    {
        if (string.IsNullOrWhiteSpace(location))
        {
            return null;
        }

        // "İstanbul-Avrupa" -> "İstanbul". Split('-') ilk parçayı verir.
        var city = location.Split('-')[0].Trim();
        return CityToRegion.GetValueOrDefault(city);
    }

    /// <summary>Arıza ailesine göre hangi uzmanlık gerekir?</summary>
    public static Specialty RequiredSpecialty(WorkOrderKind kind, string? family)
    {
        if (kind == WorkOrderKind.Sampling)
        {
            return Specialty.Sampling;
        }

        return family switch
        {
            "Deşarj" => Specialty.Electrical,
            "Termal" => Specialty.Thermal,
            _ => Specialty.General,
        };
        // switch ifadesi: Python'daki match/case veya sözlük araması gibi.
        // "_" varsayılan dal (Python'daki else).
    }

    /// <summary>
    /// Adaylar arasından en uygun teknisyeni seçer.
    /// </summary>
    /// <param name="workloads">Teknisyenler ve anlık açık iş sayıları.</param>
    /// <param name="kind">İşin türü.</param>
    /// <param name="location">Trafonun konumu (ML servisinden).</param>
    /// <param name="family">Arıza ailesi: Deşarj / Termal / Normal.</param>
    /// <returns>Uygun kimse yoksa null.</returns>
    public Assignment? Choose(IReadOnlyList<TechnicianWorkload> workloads,
                              WorkOrderKind kind,
                              string? location,
                              string? family)
    {
        var region = RegionOf(location);
        var needed = RequiredSpecialty(kind, family);

        // Kapasitesi dolu ve pasif olanlar elenir.
        var candidates = workloads
            .Where(w => w.Technician.IsActive && w.HasCapacity)
            .ToList();

        if (candidates.Count == 0)
        {
            return null;
        }

        // Puanlama: yüksek puan daha iyi.
        //   bölge eşleşmesi     +10  (yol süresi en pahalı kalem)
        //   uzmanlık eşleşmesi   +5
        //   genel uzmanlık       +1  (her işi yapar ama uzman tercih edilir)
        // Puan eşitse yükü az olan kazanır — böylece iş dağılır.
        var scored = candidates
            .Select(w =>
            {
                var score = 0;
                var reasons = new List<string>();

                if (region is not null && w.Technician.Region == region)
                {
                    score += 10;
                    reasons.Add($"bölge eşleşti ({region})");
                }

                if (w.Technician.Specialty == needed)
                {
                    score += 5;
                    reasons.Add($"uzmanlık eşleşti ({needed})");
                }
                else if (w.Technician.Specialty == Specialty.General)
                {
                    score += 1;
                    reasons.Add("genel uzmanlık");
                }

                reasons.Add($"açık iş {w.OpenOrders}/{w.Technician.MaxOpenOrders}");
                return new Assignment(w.Technician, score,
                                      string.Join(", ", reasons));
            })
            .OrderByDescending(a => a.Score)
            .ThenBy(a => workloads.First(w => w.Technician.Id == a.Technician.Id)
                                  .OpenOrders)
            .ThenBy(a => a.Technician.Id)   // eşitlikte deterministik olsun
            .ToList();

        return scored.FirstOrDefault();
    }
}
