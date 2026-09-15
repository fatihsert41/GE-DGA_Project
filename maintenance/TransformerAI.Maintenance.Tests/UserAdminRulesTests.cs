using TransformerAI.Maintenance.Api.Models;
using TransformerAI.Maintenance.Api.Services;

namespace TransformerAI.Maintenance.Tests;

/// <summary>Kullanıcı yönetimi ve parola kuralları. (Sistem Yönetimi)</summary>
/// <remarks>
/// Buradaki en önemli testler "engeller" yönündekiler: yetki yükseltme ve
/// kilitlenme. İkisi de hiçbir ekranda hata vermeden sistemi bozar.
/// </remarks>
public class UserAdminRulesTests
{
    private static Technician P(string id, Department dept, bool active = true,
                                string employeeNo = "10000", string name = "Test Kişi")
        => new()
        {
            Id = id, EmployeeNo = employeeNo, Name = name,
            Department = dept, IsActive = active,
        };

    private static CreateUserRequest Valid(string? department = "OilLaboratory",
                                           string? role = "Technician",
                                           string? employeeNo = "10960",
                                           string? name = "Ayşe Kara",
                                           string? specialty = null,
                                           int? maxOpen = null)
        => new(employeeNo, name, department, role, specialty, maxOpen);

    // --- Yeni kullanıcı --------------------------------------------------------

    [Fact]
    public void Gecerli_istek_taslak_uretir()
    {
        var (draft, problems) = UserAdminRules.ValidateCreate(Valid(specialty: "Sampling", maxOpen: 4));
        Assert.Empty(problems);
        Assert.NotNull(draft);
        Assert.Equal("10960", draft!.EmployeeNo);
        Assert.Equal(Department.OilLaboratory, draft.Department);
        Assert.Equal(Specialty.Sampling, draft.Specialty);
        Assert.Equal(4, draft.MaxOpenOrders);
        Assert.True(draft.IsActive);
        // Taslakta parola YOK: geçici parolayı uç nokta üretir ve özetler.
        Assert.Equal("", draft.PasswordHash);
    }

    [Fact]
    public void Uzmanlik_ve_kapasite_verilmezse_varsayilan()
    {
        var (draft, _) = UserAdminRules.ValidateCreate(Valid());
        Assert.Equal(Specialty.General, draft!.Specialty);
        Assert.Equal(3, draft.MaxOpenOrders);
    }

    [Theory]
    [InlineData("1234")]          // kısa
    [InlineData("12345678901")]   // uzun
    [InlineData("10A60")]         // harf
    [InlineData("")]
    [InlineData(null)]
    public void Gecersiz_sicil_reddedilir(string? employeeNo)
    {
        var (draft, problems) = UserAdminRules.ValidateCreate(Valid(employeeNo: employeeNo));
        Assert.Null(draft);
        Assert.Contains(problems, p => p.Contains("Sicil"));
    }

    [Theory]
    [InlineData("Muhasebe")]       // olmayan departman
    [InlineData("6")]              // sayı
    [InlineData("SystemAdmin, Management")]
    [InlineData(null)]
    public void Gecersiz_departman_reddedilir(string? department)
    {
        var (draft, problems) = UserAdminRules.ValidateCreate(Valid(department: department));
        Assert.Null(draft);
        Assert.Single(problems);
    }

    [Fact]
    public void Bos_istek_tum_sorunlari_birlikte_soyler()
    {
        // Kullanıcı formu bir kez düzeltsin, beş kez değil.
        var (_, problems) = UserAdminRules.ValidateCreate(new CreateUserRequest(null, null, null, null));
        Assert.Equal(4, problems.Count);   // sicil + ad + departman + rol
    }

    [Theory]
    [InlineData(-1)]
    [InlineData(11)]
    public void Kapasite_sinir_disi_reddedilir(int maxOpen)
    {
        var (_, problems) = UserAdminRules.ValidateCreate(Valid(maxOpen: maxOpen));
        Assert.Single(problems);
    }

    [Fact]
    public void Siradaki_kimlik_sayiya_gore_hesaplanir()
    {
        // Metin sıralamasında "TK-9" > "TK-10" olurdu.
        Assert.Equal("TK-11", UserAdminRules.NextId(new[] { "TK-01", "TK-9", "TK-10" }));
        Assert.Equal("TK-01", UserAdminRules.NextId(Array.Empty<string>()));
        Assert.Equal("TK-03", UserAdminRules.NextId(new[] { "TK-02", "bozuk", "XX-99" }));
    }

    [Fact]
    public void Gecici_parola_rastgele_karisik_karakter_icermez()
    {
        var passwords = Enumerable.Range(0, 200).Select(_ => UserAdminRules.GenerateTemporaryPassword()).ToList();

        Assert.All(passwords, p =>
        {
            Assert.Equal(UserAdminRules.TemporaryPasswordLength, p.Length);
            Assert.Contains(p, char.IsDigit);
            Assert.Contains(p, char.IsLetter);
            // Sözlü iletilirken karışan karakterler yok.
            Assert.DoesNotContain(p, c => "0O1lI".Contains(c));
        });
        Assert.Equal(passwords.Count, passwords.Distinct().Count());
    }

    // --- Yetki yükseltme ve kilitlenme ------------------------------------------

    private static readonly Technician Admin = P("TK-09", Department.SystemAdmin);
    private static readonly Technician Admin2 = P("TK-10", Department.SystemAdmin);
    private static readonly Technician Manager = P("TK-04", Department.Management);
    private static readonly Technician Manager2 = P("TK-11", Department.Management);
    private static readonly Technician Lab = P("TK-03", Department.OilLaboratory);

    [Fact]
    public void Admin_kendi_departmanini_degistiremez()
    {
        // Değiştirebilseydi kendini Yönetim'e taşıyıp her yetkiyi alırdı.
        var all = new[] { Admin, Admin2, Manager };
        var block = UserAdminRules.CanChangeDepartment(Admin.Id, Admin, Department.Management, all);
        Assert.Equal(403, block!.Value.Status);
    }

    [Fact]
    public void Son_sistem_yoneticisi_tasinamaz()
    {
        var all = new[] { Admin, Manager, Lab };
        var block = UserAdminRules.CanChangeDepartment(Manager.Id, Admin, Department.OilLaboratory, all);
        Assert.Equal(409, block!.Value.Status);

        // İkinci admin varsa taşınabilir.
        Assert.Null(UserAdminRules.CanChangeDepartment(
            Manager.Id, Admin, Department.OilLaboratory, new[] { Admin, Admin2, Manager }));
    }

    [Fact]
    public void Son_yonetim_personeli_tasinamaz()
    {
        var all = new[] { Admin, Manager, Lab };
        Assert.Equal(409, UserAdminRules.CanChangeDepartment(
            Admin.Id, Manager, Department.FieldService, all)!.Value.Status);
        Assert.Null(UserAdminRules.CanChangeDepartment(
            Admin.Id, Manager, Department.FieldService, new[] { Admin, Manager, Manager2 }));
    }

    [Fact]
    public void Pasif_yonetici_son_yonetici_sayilmaz()
    {
        // Pasif bir yönetici sistemi yönetemez; "son aktif" hesabında sayılmamalı.
        var inactiveAdmin = P("TK-12", Department.SystemAdmin, active: false);
        var all = new[] { Admin, inactiveAdmin, Manager };
        Assert.Equal(409, UserAdminRules.CanChangeDepartment(
            Manager.Id, Admin, Department.FieldService, all)!.Value.Status);
    }

    [Fact]
    public void Admin_kendini_pasife_alamaz()
    {
        var all = new[] { Admin, Admin2, Manager };
        Assert.Equal(409, UserAdminRules.CanDeactivate(
            Admin.Id, Admin, all, "Yeterince uzun bir gerekçe.")!.Value.Status);
    }

    [Fact]
    public void Pasife_alma_gerekce_ister_ve_son_yoneticiyi_korur()
    {
        var all = new[] { Admin, Admin2, Manager, Lab };
        Assert.Equal(400, UserAdminRules.CanDeactivate(Admin.Id, Lab, all, "ayrıldı")!.Value.Status);
        Assert.Null(UserAdminRules.CanDeactivate(Admin.Id, Lab, all, "İşten ayrıldı, 15.09.2026."));

        // Son aktif Yönetim personeli:
        Assert.Equal(409, UserAdminRules.CanDeactivate(
            Admin.Id, Manager, all, "İşten ayrıldı, 15.09.2026.")!.Value.Status);
    }

    [Fact]
    public void Zaten_pasif_hesap_tekrar_pasife_alinmaz()
    {
        var gone = P("TK-13", Department.FieldService, active: false);
        Assert.Equal(409, UserAdminRules.CanDeactivate(
            Admin.Id, gone, new[] { Admin, gone }, "Yeterince uzun gerekçe.")!.Value.Status);
    }

    [Fact]
    public void Parola_sifirlama_kurallari()
    {
        Assert.Equal(409, UserAdminRules.CanResetPassword(Admin.Id, Admin)!.Value.Status);
        Assert.Equal(409, UserAdminRules.CanResetPassword(
            Admin.Id, P("TK-14", Department.FieldService, active: false))!.Value.Status);
        Assert.Null(UserAdminRules.CanResetPassword(Admin.Id, Lab));
    }

    // --- Parola politikası ---------------------------------------------------------

    [Fact]
    public void Uzun_ve_ozgun_parola_kabul_edilir()
    {
        Assert.Empty(PasswordPolicy.Check("Kademe-Revizyon-2026", "10247", "Ahmet Yılmaz"));
        // Karmaşıklık kuralı YOK: yalnızca küçük harfli uzun bir cümle geçerli.
        Assert.Empty(PasswordPolicy.Check("trafo yağı temiz çıktı", "10247", "Ahmet Yılmaz"));
    }

    [Fact]
    public void Kisa_parola_reddedilir()
    {
        var problems = PasswordPolicy.Check("Kisa1!", "10247", "Ahmet Yılmaz");
        Assert.Contains(problems, p => p.Contains("en az"));
    }

    [Fact]
    public void Sicil_iceren_parola_reddedilir()
    {
        Assert.Contains(PasswordPolicy.Check("ahmet-10247-xy", "10247", "Can Er"),
                        p => p.Contains("sicil"));
    }

    [Fact]
    public void Ad_iceren_parola_turkce_harf_kurallariyla_reddedilir()
    {
        // "YILMAZ" büyük harfle yazılsa da "Yılmaz"ı içerir (ı/I eşleşmesi).
        Assert.Contains(PasswordPolicy.Check("YILMAZ-guclu-parola", "10247", "Ahmet Yılmaz"),
                        p => p.Contains("adınızı"));
    }

    [Fact]
    public void Kisa_ad_parcasi_yanlis_ret_uretmez()
    {
        // "Can" 3 harf: "Vulcanize2026" parolasını reddetmemeli.
        Assert.Empty(PasswordPolicy.Check("Vulcanize2026", "10921", "Can Er"));
    }

    [Theory]
    [InlineData("aaaaaaaaaaaa")]
    [InlineData("1234567890")]
    [InlineData("Transformer1")]
    public void Tekrarli_ve_yaygin_parolalar_reddedilir(string password)
    {
        Assert.NotEmpty(PasswordPolicy.Check(password, "10247", "Ahmet Yılmaz"));
    }
}
