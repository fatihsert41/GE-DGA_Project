using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Tests;

/// <summary>Departman → yetki haritası. (Faz 10)</summary>
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

    [Fact]
    public void Yonetim_her_yetkiye_sahip()
    {
        foreach (var p in Permissions.Catalog)
            Assert.True(Permissions.Has(Department.Management, p.Key),
                        $"Yönetimde eksik yetki: {p.Key}");
    }

    [Fact]
    public void Her_test_turu_tek_bir_test_departmanina_ait()
    {
        // "Her testin farklı personeli olabilir": yönetim dışında her test
        // türünü TAM OLARAK bir departman girer. İki departman aynı testi
        // girebilseydi "bu ölçümden kim sorumlu?" sorusu bulanıklaşırdı.
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
    public void Departman_kendi_isini_yapabilir(Department department, string permission)
    {
        Assert.True(Permissions.Has(department, permission));
    }

    [Fact]
    public void Kayitli_herkes_bildirim_gonderebilir()
    {
        // Kullanıcı kararı: bildirim göndermek bir birime ait iş değil,
        // herkesin iletişim hakkı. Yeni bir departman eklenip bu yetki
        // unutulursa bu test söyler.
        foreach (var d in Enum.GetValues<Department>())
            Assert.True(Permissions.Has(d, Permissions.NotificationsSend),
                        $"{d} bildirim gönderemiyor");
    }

    [Fact]
    public void Personel_yonetimi_yalnizca_yonetimde()
    {
        var owners = Enum.GetValues<Department>()
            .Where(d => Permissions.Has(d, Permissions.PersonnelManage));
        Assert.Equal(new[] { Department.Management }, owners);
    }

    [Fact]
    public void Bilinmeyen_yetki_reddedilir()
    {
        // Yazım hatası yüzünden bir kapının açık kalmasındansa kapalı
        // kalması iyidir.
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
        // Varsayılan tam yetki olsaydı, departmanı girilmeyi unutulan her
        // kayıt açık bir kapı olurdu.
        var person = new Technician();
        Assert.Equal(Department.FieldService, person.Department);
        Assert.False(Permissions.Has(person.Department, Permissions.PersonnelManage));
    }
}
