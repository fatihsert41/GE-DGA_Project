using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Services;

/// <summary>
/// Picks the most suitable technician for a work order.
/// </summary>
/// <remarks>
/// Like WorkOrderPlanner, this class is PURE: it knows nothing about HTTP or
/// the database. Input: technician workloads + work order + location;
/// output: a choice. That lets "who should handle TR-01?" be unit-tested
/// without a database.
/// </remarks>
public class AssignmentService
{
    /// <summary>The chosen technician and the reasoning.</summary>
    public record Assignment(Technician Technician, int Score, string Reason);

    /// <summary>Which specialty does this fault family require?</summary>
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
        // Switch expression: similar to Python's match/case or a dict lookup.
        // "_" is the default arm (Python's else).
    }

    /// <summary>
    /// Selects the best technician among the candidates.
    /// </summary>
    /// <param name="workloads">Technicians and their current open-order counts.</param>
    /// <param name="kind">Type of work.</param>
    /// <param name="location">Transformer location (from the ML service).</param>
    /// <param name="family">Fault family: Deşarj (discharge) / Termal (thermal) / Normal.</param>
    /// <returns>null when nobody is eligible.</returns>
    public Assignment? Choose(IReadOnlyList<TechnicianWorkload> workloads,
                              WorkOrderKind kind,
                              string? location,
                              string? family)
    {
        var needed = RequiredSpecialty(kind, family);

        // Filter out anyone who is inactive, at capacity, or NOT PERMITTED
        // to execute work orders.
        //
        // ⚠ Bug found in Phase 12: when departments arrived in Phase 10 this
        // filter was missing. The system could assign a work order to an oil
        // laboratory engineer; when that person pressed "Start" the server
        // returned 403 — the order looked assigned but could never be run.
        // Assignment and authorization must follow the same rule.
        var candidates = workloads
            .Where(w => w.Technician.IsActive && w.HasCapacity
                        && Permissions.Has(w.Technician.Department,
                                           Permissions.WorkOrdersExecute))
            .ToList();

        if (candidates.Count == 0)
        {
            return null;
        }

        // Scoring: higher is better.
        //   specialty match      +5
        //   general specialty    +1  (can do any job, but specialists win)
        // On a tie the least-loaded technician wins, spreading the work.
        //
        // ⚠ REMOVED RULE: there used to be a "region match +10" bonus
        // (travel time is the most expensive item). All staff in this
        // installation share one region, so the rule no longer
        // discriminated — and because transformer locations differ, it
        // silently favoured some assets. It belongs back in a multi-region
        // operation; in a single region it behaves wrongly.
        var scored = candidates
            .Select(w =>
            {
                var score = 0;
                var reasons = new List<string>();

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
            .ThenBy(a => a.Technician.Id)   // deterministic on ties
            .ToList();

        return scored.FirstOrDefault();
    }
}
