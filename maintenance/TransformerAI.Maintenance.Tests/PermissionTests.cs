using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Tests;

/// <summary>Departman → yetki haritası. (Faz 10, Sistem Yönetimi ile güncellendi)</summary>
/// <remarks>
/// Yetki hataları SESSİZDİR: yanlış açılmış bir kapı hiçbir ekranda
/// hata vermez, sadece yetkisi olmayan birinin işlem yapmasına izin
/// verir. Bu testler haritanın niyetini yazılı hâle getiriyor — biri
/// haritayı değiştirdiğinde hangi kuralı bozduğunu anında görür.
/// </remarks>
public class PermissionTests
{
    private static readonly string[] TestPermissions =
    {
        Permissions.TestsDga, Permissions.TestsOil, Permissions.TestsElectrical,
        Permissions.TestsComponents, Permissions.TestsInspection,
    };

    /// <summary>Operasyon yetkileri: işi yapan tarafın elinde olanlar.</summary>
    private static readonly string[] OperationalPermissions =
    {
        Permissions.ManagerView, Permissions.AnalysisRun,
        Permissions.TestsDga, Permissions.TestsOil, Permissions.TestsElectrical,
        Permissions.TestsComponents, Permissions.TestsInspection,
        Permissions.AssetsEdit, Permissions.WorkOrdersPlan, Permissions.WorkOrdersExecute,
        Permissions.EngineeringApprove, Permissions.EngineeringReviewModel,
        Permissions.EngineeringLimits, Permissions.EngineeringRca,
    };

    [Fact]
    public void Yonetim_kullanici_yonetimi_disinda_her_yetkiye_sahip()
    {
        foreach (var p in Permissions.Catalog.Where(p => p.Key != Permissions.UsersManage))
            Assert.True(Permissions.Has(Department.Management, p.Key),
                        $"Yönetimde eksik yetki: {p.Key}");

        // "İşi yapan" ile "hesabı veren" ayrı: Yönetim hesap açamaz.
        Assert.False(Permissions.Has(Department.Management, Permissions.UsersManage));
    }

    [Fact]
    public void Kullanici_yonetimi_yalnizca_sistem_yonetiminde()
    {
        var owners = Enum.GetValues<Department>()
            .Where(d => Permissions.Has(d, Permissions.UsersManage));
        Assert.Equal(new[] { Department.SystemAdmin }, owners);
    }

    [Fact]
    public void Sistem_yonetimi_operasyona_dokunmaz()
    {
        // Hesap verebilen biri ölçüm de girebilseydi, kendine sahte bir hesap
        // açıp o hesapla kayıt girebilirdi. İki yetki aynı elde olmamalı.
        foreach (var perm in OperationalPermissions)
            Assert.False(Permissions.Has(Department.SystemAdmin, perm),
                         $"Sistem Yönetimi {perm} yetkisine sahip olmamalı");
    }

    [Fact]
    public void Her_test_turu_tek_bir_test_departmanina_ait()
    {
        // "Her testin farklı personeli olabilir": yönetim dışında her test
        // türünü TAM OLARAK bir departman girer.
        foreach (var perm in TestPermissions)
        {
            var owners = Enum.GetValues<Department>()
                .Where(d => d != Department.Management && Permissions.Has(d, perm))
                .ToList();
            Assert.True(owners.Count == 1,
                $"{perm} yetkisi {owners.Count} departmanda: {string.Join(", ", owners)}");
        }
    }

    [Theory]
    [InlineData(Department.OilLaboratory, Permissions.TestsElectrical)]
    [InlineData(Department.OilLaboratory, Permissions.WorkOrdersPlan)]
    [InlineData(Department.ElectricalTesting, Permissions.TestsOil)]
    [InlineData(Department.ElectricalTesting, Permissions.TestsDga)]
    [InlineData(Department.MaintenancePlanning, Permissions.TestsOil)]
    [InlineData(Department.MaintenancePlanning, Permissions.TestsElectrical)]
    [InlineData(Department.FieldService, Permissions.WorkOrdersPlan)]
    [InlineData(Department.FieldService, Permissions.PersonnelManage)]
    [InlineData(Department.Engineering, Permissions.UsersManage)]
    public void Departman_baskasinin_isini_yapamaz(Department department, string permission)
    {
        Assert.False(Permissions.Has(department, permission));
    }

    [Theory]
    [InlineData(Department.OilLaboratory, Permissions.TestsDga)]
    [InlineData(Department.OilLaboratory, Permissions.TestsOil)]
    [InlineData(Department.ElectricalTesting, Permissions.TestsElectrical)]
    [InlineData(Department.ElectricalTesting, Permissions.TestsComponents)]
    [InlineData(Department.MaintenancePlanning, Permissions.WorkOrdersPlan)]
    [InlineData(Department.MaintenancePlanning, Permissions.NotificationsSend)]
    [InlineData(Department.FieldService, Permissions.WorkOrdersExecute)]
    [InlineData(Department.FieldService, Permissions.TestsInspection)]
    [InlineData(Department.SystemAdmin, Permissions.UsersManage)]
    [InlineData(Department.SystemAdmin, Permissions.PersonnelView)]
    public void Departman_kendi_isini_yapabilir(Department department, string permission)
    {
        Assert.True(Permissions.Has(department, permission));
    }

    [Fact]
    public void Kayitli_herkes_bildirim_gonderebilir()
    {
        // Kullanıcı kararı: bildirim göndermek herkesin iletişim hakkı.
        // Yeni bir departman eklenip bu yetki unutulursa bu test söyler.
        foreach (var d in Enum.GetValues<Department>())
            Assert.True(Permissions.Has(d, Permissions.NotificationsSend),
                        $"{d} bildirim gönderemiyor");
    }

    [Fact]
    public void Departman_degistirme_yonetim_ve_sistem_yonetiminde()
    {
        var owners = Enum.GetValues<Department>()
            .Where(d => Permissions.Has(d, Permissions.PersonnelManage))
            .OrderBy(d => d);
        Assert.Equal(new[] { Department.Management, Department.SystemAdmin }, owners);
    }

    [Fact]
    public void Bilinmeyen_yetki_reddedilir()
    {
        foreach (var d in Enum.GetValues<Department>())
            Assert.False(Permissions.Has(d, "tests.oli"));
    }

    [Fact]
    public void Her_departmanin_adi_ve_aciklamasi_var()
    {
        foreach (var info in DepartmentCatalog.All())
        {
            Assert.False(string.IsNullOrWhiteSpace(info.Name));
            Assert.False(string.IsNullOrWhiteSpace(info.Description));
            Assert.NotEqual(info.Code, info.Name);   // Türkçe ad girilmiş mi
        }
    }

    [Fact]
    public void Ret_mesaji_isi_kime_yonlendirecegini_soyler()
    {
        var owners = DepartmentCatalog.WithPermission(Permissions.TestsOil);
        Assert.Contains("Yağ Laboratuvarı", owners);
        Assert.Contains("Yönetim", owners);
        Assert.DoesNotContain("Elektriksel Test", owners);
    }

    [Fact]
    public void Yeni_personel_en_dar_yetkiyle_baslar()
    {
        var person = new Technician();
        Assert.Equal(Department.FieldService, person.Department);
        Assert.False(Permissions.Has(person.Department, Permissions.PersonnelManage));
        Assert.False(Permissions.Has(person.Department, Permissions.UsersManage));
    }
}
