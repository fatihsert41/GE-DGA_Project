namespace TransformerAI.Maintenance.Api.Models;

/// <summary>Personelin çalıştığı birim. (Faz 10)</summary>
/// <remarks>
/// <b>Rol ile departman farklı sorulara cevap verir.</b>
/// <list type="bullet">
/// <item><c>PersonnelRole</c> (Teknisyen / Mühendis / Süpervizör) KIDEMİ
/// anlatır: kişinin kurumdaki seviyesi.</item>
/// <item><c>Department</c> BİRİMİ anlatır ve sistemde <b>ne
/// yapabileceğini</b> belirler.</item>
/// </list>
/// Yağ laboratuvarındaki kıdemli bir mühendis elektriksel test
/// giremez; saha bakımdaki bir teknisyen iş emri planlayamaz. Yetkiyi
/// role bağlasaydık "Mühendis" diye her mühendise her testi açmış
/// olurduk.
///
/// Değerler veritabanına METİN olarak yazılır (bkz. DbContext): enum'a
/// ortadan yeni birim eklenirse eski kayıtların anlamı kaymasın.
/// </remarks>
public enum Department
{
    /// <summary>Yönetim — tam yetki.</summary>
    Management = 0,

    /// <summary>Yağ laboratuvarı — DGA ve yağ kalitesi numuneleri.</summary>
    OilLaboratory = 1,

    /// <summary>Elektriksel test — TTR, sargı, yalıtım, buşing, kademe.</summary>
    ElectricalTesting = 2,

    /// <summary>Bakım planlama — iş emirleri ve ekip koordinasyonu.</summary>
    MaintenancePlanning = 3,

    /// <summary>Saha bakım — atanan işi yürütür, saha gözlemi yapar.</summary>
    FieldService = 4,
}

/// <summary>Bir yetkinin tanımı — arayüzde gösterilecek adıyla.</summary>
public record PermissionInfo(string Key, string Label, string Group);

/// <summary>Bir departmanın tanımı ve verdiği yetkiler.</summary>
public record DepartmentInfo(
    string Code,
    string Name,
    string Description,
    bool FullAccess,
    IReadOnlyList<string> Permissions);

/// <summary>Yetki anahtarları ve departman → yetki haritası. (Faz 10)</summary>
/// <remarks>
/// <b>TEK DOĞRULUK KAYNAĞI BURASI.</b> Harita üç yerde kullanılıyor ama
/// yalnızca burada tanımlı:
/// <list type="number">
/// <item>.NET uç noktaları doğrudan buna bakar.</item>
/// <item>Giriş belirtecine kişinin yetkileri YAZILIR; Python servisi
/// yetkiyi belirteçten okur, .NET'e sormaz. (Faz 7 kuralı korunuyor:
/// Python .NET'i bilmez.)</item>
/// <item>Arayüz yetki listesini giriş cevabından ve
/// <c>GET /departments</c> uç noktasından alır.</item>
/// </list>
/// Haritayı Python'da veya arayüzde tekrar yazmak, bir gün birinin
/// değişip diğerinin değişmemesiyle "ekranda düğme var ama sunucu
/// reddediyor" türü hatalar üretirdi.
///
/// <b>Yetkiler işlem bazlıdır, ekran bazlı değil.</b> "Testler ekranı"
/// yerine "yağ testi kaydetme" yetkisi var. Aynı ekranda birden çok
/// departmanın işi olabiliyor (trafo detayında hem yağ hem elektriksel
/// test sekmesi var); ekran bazlı yetki bu ayrımı yapamazdı.
/// </remarks>
public static class Permissions
{
    // --- Ekranlar ---------------------------------------------------------
    public const string ManagerView = "manager.view";
    public const string AnalysisRun = "analysis.run";

    // --- Personel ---------------------------------------------------------
    public const string PersonnelView = "personnel.view";
    public const string PersonnelManage = "personnel.manage";

    // --- Test girişi: HER TEST TÜRÜ AYRI YETKİ ---------------------------
    public const string TestsDga = "tests.dga";
    public const string TestsOil = "tests.oil";
    public const string TestsElectrical = "tests.electrical";
    public const string TestsComponents = "tests.components";
    public const string TestsInspection = "tests.inspection";

    // --- Varlık kaydı -----------------------------------------------------
    public const string AssetsEdit = "assets.edit";

    // --- İş emirleri ------------------------------------------------------
    // Planlamak ile yürütmek ayrı: planlamacı işi açar ve atar, saha
    // personeli yalnızca KENDİSİNE atanan işi başlatıp bitirir.
    public const string WorkOrdersPlan = "workorders.plan";
    public const string WorkOrdersExecute = "workorders.execute";

    // --- Bildirim ---------------------------------------------------------
    public const string NotificationsSend = "notifications.send";

    /// <summary>Tüm yetkiler, arayüzde gösterilecek adlarıyla.</summary>
    public static readonly IReadOnlyList<PermissionInfo> Catalog = new List<PermissionInfo>
    {
        new(ManagerView, "Yönetim ekranı", "Ekranlar"),
        new(AnalysisRun, "Numune analizi (tanı)", "Ekranlar"),
        new(PersonnelView, "Personel kayıtlarını görme", "Personel"),
        new(PersonnelManage, "Personelin departmanını değiştirme", "Personel"),
        new(TestsDga, "DGA ölçümü kaydetme", "Test girişi"),
        new(TestsOil, "Yağ kalitesi testi kaydetme", "Test girişi"),
        new(TestsElectrical, "Elektriksel test kaydetme / geçersiz işaretleme", "Test girişi"),
        new(TestsComponents, "Buşing ve kademe testi kaydetme", "Test girişi"),
        new(TestsInspection, "Fiziksel saha gözlemi kaydetme", "Test girişi"),
        new(AssetsEdit, "Trafo kaydı, künye ve yaşam döngüsü", "Varlık"),
        new(WorkOrdersPlan, "İş emri açma, öneri uygulama, atama", "İş emirleri"),
        new(WorkOrdersExecute, "İş emrini başlatma / bitirme", "İş emirleri"),
        new(NotificationsSend, "Personele bildirim gönderme", "Bildirim"),
    };

    private static readonly IReadOnlyList<string> All =
        Catalog.Select(p => p.Key).ToList();

    /// <summary>Departman → yetki haritası.</summary>
    private static readonly IReadOnlyDictionary<Department, IReadOnlyList<string>> Map =
        new Dictionary<Department, IReadOnlyList<string>>
        {
            // Yönetim her yere girip çıkar. Listeyi elle yazmak yerine
            // katalogdan türetiyoruz: yeni bir yetki eklendiğinde yönetime
            // vermeyi unutmak mümkün olmasın.
            [Department.Management] = All,

            // Bildirim göndermek HERKESİN temel yetkisi (kullanıcı kararı,
            // 14 Eyl): laboratuvar "numune hazır", saha "trafoda yağ kaçağı
            // gördüm" diyebilmeli. Anahtar yine de ayrı duruyor: ileride
            // bir birim için kısıtlamak gerekirse tek satır değişir,
            // uç noktalar ve arayüz aynı kalır.
            [Department.OilLaboratory] = new[]
            {
                AnalysisRun, TestsDga, TestsOil, NotificationsSend,
            },

            [Department.ElectricalTesting] = new[]
            {
                TestsElectrical, TestsComponents, NotificationsSend,
            },

            // Planlamacı ekibi koordine eder: iş açar, atar ve kimin ne
            // kadar yükü olduğunu görmek için personel listesine bakar.
            // Test GİREMEZ.
            [Department.MaintenancePlanning] = new[]
            {
                WorkOrdersPlan, WorkOrdersExecute, NotificationsSend,
                PersonnelView,
            },

            [Department.FieldService] = new[]
            {
                WorkOrdersExecute, TestsInspection, NotificationsSend,
            },
        };

    /// <summary>Departmanın yetkileri.</summary>
    public static IReadOnlyList<string> For(Department department) =>
        Map.TryGetValue(department, out var list) ? list : Array.Empty<string>();

    /// <summary>Departman bu yetkiye sahip mi?</summary>
    /// <remarks>Bilinmeyen yetki anahtarı her zaman REDDEDİLİR: yazım
    /// hatası yüzünden bir kapının açık kalmasındansa kapalı kalması
    /// iyidir.</remarks>
    public static bool Has(Department department, string permission) =>
        For(department).Contains(permission);

    public static string Label(string permission) =>
        Catalog.FirstOrDefault(p => p.Key == permission)?.Label ?? permission;
}

/// <summary>Departmanların Türkçe adları ve açıklamaları.</summary>
public static class DepartmentCatalog
{
    private static readonly IReadOnlyDictionary<Department, (string Name, string Description)> Texts =
        new Dictionary<Department, (string, string)>
        {
            [Department.Management] = ("Yönetim",
                "Tam yetki: bütün ekranlar, bütün test girişleri, personel yönetimi."),
            [Department.OilLaboratory] = ("Yağ Laboratuvarı",
                "DGA ve yağ kalitesi numunelerini analiz eder ve kaydeder."),
            [Department.ElectricalTesting] = ("Elektriksel Test",
                "TTR, sargı direnci, yalıtım, buşing ve kademe testlerini yapar."),
            [Department.MaintenancePlanning] = ("Bakım Planlama",
                "İş emirlerini açar, atar, ekibi koordine eder ve bilgilendirir."),
            [Department.FieldService] = ("Saha Bakım",
                "Atanan işleri sahada yürütür, fiziksel gözlem turu yapar."),
        };

    public static string Name(Department d) =>
        Texts.TryGetValue(d, out var t) ? t.Name : d.ToString();

    public static DepartmentInfo Info(Department d) => new(
        d.ToString(),
        Name(d),
        Texts.TryGetValue(d, out var t) ? t.Description : "",
        FullAccess: d == Department.Management,
        Permissions.For(d));

    public static IReadOnlyList<DepartmentInfo> All() =>
        Enum.GetValues<Department>().Select(Info).ToList();

    /// <summary>Bu yetkiyi veren departmanların adları — ret mesajı için.</summary>
    /// <remarks>"Yetkiniz yok" tek başına yardımcı olmaz; kullanıcı işi
    /// KİME yönlendireceğini bilmeli.</remarks>
    public static IReadOnlyList<string> WithPermission(string permission) =>
        Enum.GetValues<Department>()
            .Where(d => Permissions.Has(d, permission))
            .Select(Name)
            .ToList();
}
