using TransformerAI.Maintenance.Api.Models;
using TransformerAI.Maintenance.Api.Services;
using static TransformerAI.Maintenance.Tests.TestData;

namespace TransformerAI.Maintenance.Tests;

/// <summary>
/// Dış inceleme bulgularının düzeltmeleri — gerileme testleri.
/// Her test gerçekten yaşanmış bir hatayı temsil eder.
/// Bulgular: docs/DIS-INCELEME-DOGRULAMA.md
/// </summary>
public class ReviewFixTests
{
    private readonly WorkOrderPlanner _planner = new();
    private static readonly DateOnly Today = new(2026, 9, 10);

    // --- P1-7 · Durum geçiş kuralları ------------------------------------

    [Theory]
    [InlineData(WorkOrderStatus.Planned, WorkOrderStatus.InProgress, true)]
    [InlineData(WorkOrderStatus.Planned, WorkOrderStatus.Cancelled, true)]
    [InlineData(WorkOrderStatus.InProgress, WorkOrderStatus.Done, true)]
    [InlineData(WorkOrderStatus.Cancelled, WorkOrderStatus.Planned, true)]
    // Yasak geçişler: başlanmamış iş tamamlanamaz, kapanan iş geri alınamaz.
    [InlineData(WorkOrderStatus.Planned, WorkOrderStatus.Done, false)]
    [InlineData(WorkOrderStatus.Done, WorkOrderStatus.Planned, false)]
    [InlineData(WorkOrderStatus.Done, WorkOrderStatus.InProgress, false)]
    public void GecisKurallari_Uygulanir(WorkOrderStatus from,
                                         WorkOrderStatus to, bool allowed)
    {
        Assert.Equal(allowed, WorkOrderTransitions.IsAllowed(from, to));
    }

    [Fact]
    public void AyniDuruma_Gecis_Serbesttir()
    {
        // Aynı durumu tekrar göndermek hata değil; istemci tekrar deneyebilir.
        Assert.True(WorkOrderTransitions.IsAllowed(
            WorkOrderStatus.Planned, WorkOrderStatus.Planned));
    }

    [Fact]
    public void Done_SonDurumdur()
    {
        Assert.Empty(WorkOrderTransitions.Next(WorkOrderStatus.Done));
        Assert.Contains("son durumdur", WorkOrderTransitions.Explain(
            WorkOrderStatus.Done, WorkOrderStatus.Planned));
    }

    [Fact]
    public void RedGerekcesi_IzinVerilenleri_Soyler()
    {
        var msg = WorkOrderTransitions.Explain(WorkOrderStatus.Planned,
                                               WorkOrderStatus.Done);
        Assert.Contains("InProgress", msg);
        Assert.Contains("Cancelled", msg);
    }

    // --- P1-5 · Aciliyet yükseltme ---------------------------------------

    [Fact]
    public void AcikEmirVarken_DurumKotuleserse_YUKSELTILIR()
    {
        // Yaşanan boşluk: açık emir varsa öneri tamamen atlanıyordu.
        // "İzlemede" diye 30 günlük açılmış bir emir, trafo kritik hâle
        // gelse bile eski son tarihiyle kalıyordu.
        var fleet = Fleet(Risk("TR-01", severe: true, riskLevel: "critical",
                               riskCondition: 4, priority: 4.0));
        var existing = new[]
        {
            new WorkOrder
            {
                Id = "WO-0001", TransformerId = "TR-01",
                Kind = WorkOrderKind.Inspection, Title = "rutin",
                Status = WorkOrderStatus.Planned,
                Priority = 0.5, DueDate = Today.AddDays(60),
            },
        };

        var plan = _planner.Plan(fleet, existing, Today);

        Assert.Empty(plan.Suggestions);          // yeni emir AÇILMAZ
        var e = Assert.Single(plan.Escalations); // mevcut emir güncellenir
        Assert.Equal("WO-0001", e.WorkOrderId);
        Assert.Equal(4.0, e.NewPriority);
        Assert.Equal(Today.AddDays(3), e.NewDueDate);
    }

    [Fact]
    public void Yukseltme_Onceligi_ASLA_Dusurmez()
    {
        // Numune kuralı önceliği yarıya indiriyor. Açık emrin önceliği
        // bundan yüksekse korunmalı — "yükseltme" tek yönlüdür, aksi halde
        // bir emir sessizce önemsizleştirilebilirdi.
        var fleet = Fleet(Risk("TR-09", samplingStatus: "overdue",
                               samplingOverdue: true, daysSinceSample: 780,
                               riskLevel: "low", riskCondition: 1,
                               priority: 0.45));
        var existing = new[]
        {
            new WorkOrder
            {
                Id = "WO-0002", TransformerId = "TR-09",
                Kind = WorkOrderKind.Sampling, Title = "numune",
                Status = WorkOrderStatus.Planned,
                Priority = 0.45, DueDate = null,
            },
        };

        var e = Assert.Single(_planner.Plan(fleet, existing, Today).Escalations);

        Assert.True(e.NewPriority >= e.OldPriority);
        Assert.Equal(0.45, e.NewPriority);
    }

    [Fact]
    public void DurumDegismediyse_YukseltmeUretilmez()
    {
        // İdempotens korunmalı: aynı plan iki kez çalıştığında ikinci
        // seferde hiçbir şey değişmemeli.
        var fleet = Fleet(Risk("TR-01", severe: true, riskLevel: "critical",
                               riskCondition: 4, priority: 4.0));
        var existing = new[]
        {
            new WorkOrder
            {
                Id = "WO-0001", TransformerId = "TR-01",
                Kind = WorkOrderKind.Inspection, Title = "acil",
                Status = WorkOrderStatus.Planned,
                Priority = 4.0, DueDate = Today.AddDays(3),
            },
        };

        var plan = _planner.Plan(fleet, existing, Today);

        Assert.Empty(plan.Suggestions);
        Assert.Empty(plan.Escalations);
    }

    [Fact]
    public void KapanmisEmir_YukseltilmezYeniAcilir()
    {
        var fleet = Fleet(Risk("TR-01", severe: true, riskLevel: "critical",
                               riskCondition: 4, priority: 4.0));
        var existing = new[]
        {
            new WorkOrder
            {
                Id = "WO-0001", TransformerId = "TR-01",
                Kind = WorkOrderKind.Inspection, Title = "eski",
                Status = WorkOrderStatus.Done,
                Priority = 4.0, DueDate = Today.AddDays(-10),
            },
        };

        var plan = _planner.Plan(fleet, existing, Today);

        Assert.Single(plan.Suggestions);
        Assert.Empty(plan.Escalations);
    }
}
