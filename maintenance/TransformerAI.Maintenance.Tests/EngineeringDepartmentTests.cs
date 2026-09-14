using TransformerAI.Maintenance.Api.Models;
using TransformerAI.Maintenance.Api.Services;

namespace TransformerAI.Maintenance.Tests;

/// <summary>Mühendislik departmanı ve atama–yetki uyumu. (Faz 12.1)</summary>
public class EngineeringDepartmentTests
{
    private static readonly string[] EngineeringPermissions =
    {
        Permissions.EngineeringApprove, Permissions.EngineeringReviewModel,
        Permissions.EngineeringLimits, Permissions.EngineeringRca,
    };

    private static readonly string[] TestPermissions =
    {
        Permissions.TestsDga, Permissions.TestsOil, Permissions.TestsElectrical,
        Permissions.TestsComponents, Permissions.TestsInspection,
    };

    [Fact]
    public void Muhendislik_kararlari_yalnizca_muhendislik_ve_yonetimde()
    {
        foreach (var perm in EngineeringPermissions)
        {
            var owners = Enum.GetValues<Department>()
                .Where(d => Permissions.Has(d, perm))
                .OrderBy(d => d)
                .ToArray();
            Assert.Equal(new[] { Department.Management, Department.Engineering }, owners);
        }
    }

    [Fact]
    public void Muhendislik_test_girmez()
    {
        // Dört göz ilkesi: ölçen ile onaylayan ayrı kişiler olmalı. Mühendis
        // test de girebilseydi kendi ölçümünü kendisi onaylayabilirdi.
        foreach (var perm in TestPermissions)
            Assert.False(Permissions.Has(Department.Engineering, perm),
                         $"Mühendislik {perm} yetkisine sahip olmamalı");
    }

    [Fact]
    public void Muhendislik_is_emri_yurutmez_ve_planlamaz()
    {
        Assert.False(Permissions.Has(Department.Engineering, Permissions.WorkOrdersExecute));
        Assert.False(Permissions.Has(Department.Engineering, Permissions.WorkOrdersPlan));
    }

    [Fact]
    public void Muhendislik_katalogda_adiyla_var()
    {
        var info = DepartmentCatalog.Info(Department.Engineering);
        Assert.Equal("Mühendislik", info.Name);
        Assert.False(info.FullAccess);
        Assert.Contains(Permissions.EngineeringApprove, info.Permissions);
    }

    // --- Atama yalnızca işi yürütebilecek kişiye gider ----------------------

    private static Technician Person(string id, Department dept,
                                     Specialty specialty = Specialty.Electrical)
        => new()
        {
            Id = id, Name = $"Kişi {id}", Department = dept,
            Specialty = specialty, MaxOpenOrders = 3, IsActive = true,
        };

    [Fact]
    public void Otomatik_atama_is_yurutme_yetkisi_olmayana_gitmez()
    {
        // Mühendisin uzmanlığı işe TAM uyuyor (+5 puan) ve yükü sıfır.
        // Eski kodda iş ona giderdi; o da "Başlat" deyince 403 alırdı.
        var engineer = Person("TK-07", Department.Engineering, Specialty.Electrical);
        var field = Person("TK-05", Department.FieldService, Specialty.General);

        var choice = new AssignmentService().Choose(
            new[] { TestData.Load(engineer, 0), TestData.Load(field, 2) },
            WorkOrderKind.Inspection, location: null, family: "Deşarj");

        Assert.NotNull(choice);
        Assert.Equal("TK-05", choice!.Technician.Id);
    }

    [Fact]
    public void Yurutebilecek_kimse_yoksa_atama_yapilmaz()
    {
        // Sessizce yetkisiz birine atamaktansa "uygun kimse yok" demek
        // doğru: uç nokta bunu 409 olarak planlamacıya gösteriyor.
        var lab = Person("TK-03", Department.OilLaboratory, Specialty.Sampling);
        var engineer = Person("TK-08", Department.Engineering, Specialty.Thermal);

        var choice = new AssignmentService().Choose(
            new[] { TestData.Load(lab, 0), TestData.Load(engineer, 0) },
            WorkOrderKind.Sampling, location: null, family: null);

        Assert.Null(choice);
    }
}
