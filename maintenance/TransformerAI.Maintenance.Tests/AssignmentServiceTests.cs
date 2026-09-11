using TransformerAI.Maintenance.Api.Models;
using TransformerAI.Maintenance.Api.Services;
using static TransformerAI.Maintenance.Tests.TestData;

namespace TransformerAI.Maintenance.Tests;

/// <summary>Teknisyen seçim mantığının testleri.</summary>
public class AssignmentServiceTests
{
    private readonly AssignmentService _assigner = new();

    [Theory]
    [InlineData(WorkOrderKind.Sampling, "Deşarj", Specialty.Sampling)]
    [InlineData(WorkOrderKind.Inspection, "Deşarj", Specialty.Electrical)]
    [InlineData(WorkOrderKind.Inspection, "Termal", Specialty.Thermal)]
    [InlineData(WorkOrderKind.Inspection, "Normal", Specialty.General)]
    [InlineData(WorkOrderKind.Inspection, null, Specialty.General)]
    public void GerekenUzmanlik_TurVeAileyeGoreBelirlenir(
        WorkOrderKind kind, string? family, Specialty expected)
    {
        // Numune alma her zaman numune uzmanı ister — arıza ailesi ne olursa olsun.
        Assert.Equal(expected, AssignmentService.RequiredSpecialty(kind, family));
    }

    [Fact]
    public void Uzman_genelciden_once_gelir()
    {
        // Uzmanlık +5, genel uzmanlık +1.
        //
        // ⚠ Burada eskiden "bölge eşleşmesi +10 uzmanlıktan ağır basar"
        // testi vardı. Bölge kuralı kaldırıldı: bu kurulumdaki personelin
        // tamamı aynı bölgede olduğu için kural ayrım üretmiyor, üstelik
        // trafo konumları farklı olduğundan bazı varlıkları sessizce
        // kayırıyordu. Çok bölgeli bir işletmede geri gelmesi gerekir.
        var genelci = Load(Tech("TK-Y", Specialty.General), 0);
        var uzman = Load(Tech("TK-U", Specialty.Electrical), 0);

        var result = _assigner.Choose([genelci, uzman],
                                      WorkOrderKind.Inspection,
                                      "İstanbul-Avrupa", "Deşarj");

        Assert.NotNull(result);
        Assert.Equal("TK-U", result!.Technician.Id);
    }

    [Fact]
    public void AyniBolgede_UzmanGenelciyeTercihEdilir()
    {
        var genel = Load(Tech("TK-G", Specialty.General), 0);
        var uzman = Load(Tech("TK-E", Specialty.Electrical), 0);

        var result = _assigner.Choose([genel, uzman],
                                      WorkOrderKind.Inspection,
                                      "Kocaeli", "Deşarj");

        Assert.Equal("TK-E", result!.Technician.Id);
        Assert.Contains("uzmanlık eşleşti", result.Reason);
    }

    [Fact]
    public void PuanEsitse_YukuAzOlanKazanir()
    {
        // İşin dağılmasını sağlayan kural.
        var yuklu = Load(Tech("TK-1", Specialty.Electrical), 2);
        var bos = Load(Tech("TK-2", Specialty.Electrical), 0);

        var result = _assigner.Choose([yuklu, bos],
                                      WorkOrderKind.Inspection,
                                      "Bursa", "Deşarj");

        Assert.Equal("TK-2", result!.Technician.Id);
    }

    [Fact]
    public void KapasitesiDolanlar_AdayDegildir()
    {
        var dolu = Load(Tech("TK-1", Specialty.Electrical, maxOpen: 2), 2);
        var uzakBos = Load(Tech("TK-2", Specialty.General), 0);

        var result = _assigner.Choose([dolu, uzakBos],
                                      WorkOrderKind.Inspection,
                                      "İstanbul-Avrupa", "Deşarj");

        // Bölge eşleşmesi olmasa bile kapasitesi olan seçilir.
        Assert.Equal("TK-2", result!.Technician.Id);
    }

    [Fact]
    public void PasifTeknisyen_AdayDegildir()
    {
        var pasif = Load(Tech("TK-1", Specialty.Electrical,
                              active: false), 0);
        var aktif = Load(Tech("TK-2", Specialty.General), 0);

        var result = _assigner.Choose([pasif, aktif],
                                      WorkOrderKind.Inspection,
                                      "İstanbul-Avrupa", "Deşarj");

        Assert.Equal("TK-2", result!.Technician.Id);
    }

    [Fact]
    public void HerkesDoluysa_NullDoner()
    {
        // Uç nokta bunu 409 Conflict'e çevirir. Sessizce yanlış kişiye
        // atamak yerine "uygun kimse yok" demek doğrusu.
        var dolu1 = Load(Tech("TK-1", Specialty.Electrical, maxOpen: 1), 1);
        var dolu2 = Load(Tech("TK-2", Specialty.General, maxOpen: 1), 1);

        var result = _assigner.Choose([dolu1, dolu2],
                                      WorkOrderKind.Inspection,
                                      "İstanbul-Avrupa", "Deşarj");

        Assert.Null(result);
    }

    [Fact]
    public void AdayYoksa_NullDoner()
    {
        Assert.Null(_assigner.Choose([], WorkOrderKind.Inspection,
                                     "İstanbul-Avrupa", "Deşarj"));
    }

    [Fact]
    public void SecimDeterministiktir()
    {
        // Her şey eşitse aynı girdi aynı çıktıyı vermeli; yoksa arayüzde
        // atama her yenilemede değişiyormuş gibi görünür.
        var a = Load(Tech("TK-B", Specialty.General), 0);
        var b = Load(Tech("TK-A", Specialty.General), 0);

        var ilk = _assigner.Choose([a, b], WorkOrderKind.Inspection,
                                   "Bursa", "Normal");
        var ikinci = _assigner.Choose([b, a], WorkOrderKind.Inspection,
                                      "Bursa", "Normal");

        Assert.Equal(ilk!.Technician.Id, ikinci!.Technician.Id);
        Assert.Equal("TK-A", ilk.Technician.Id);   // id'ye göre alfabetik
    }
}
