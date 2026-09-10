using TransformerAI.Maintenance.Api.Models;
using TransformerAI.Maintenance.Api.Services;
using static TransformerAI.Maintenance.Tests.TestData;

namespace TransformerAI.Maintenance.Tests;

/// <summary>Teknisyen seçim mantığının testleri.</summary>
public class AssignmentServiceTests
{
    private readonly AssignmentService _assigner = new();

    [Theory]
    [InlineData("İstanbul-Avrupa", "Marmara")]
    [InlineData("İstanbul-Anadolu", "Marmara")]
    [InlineData("Kocaeli", "Marmara")]
    [InlineData("İzmir", "Ege")]
    [InlineData("Ankara", "İç Anadolu")]
    [InlineData("Mersin", "Akdeniz")]
    public void KonumdanBolge_DogruCikarilir(string location, string expected)
    {
        Assert.Equal(expected, AssignmentService.RegionOf(location));
    }

    [Theory]
    [InlineData(null)]
    [InlineData("")]
    [InlineData("Bilinmeyen Şehir")]
    public void TaninmayanKonum_NullDoner(string? location)
    {
        // Bilinmeyen konum hata FIRLATMAMALI: atama bölge puanı olmadan
        // yine de yapılabilmeli.
        Assert.Null(AssignmentService.RegionOf(location));
    }

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
    public void BolgeEslesmesi_UzmanliktanDahaAgirBasar()
    {
        // Bölge +10, uzmanlık +5. Yol süresi en pahalı kalem olduğu için
        // uzak bir uzman yerine yakın bir genelci tercih edilir.
        var uzakUzman = Load(Tech("TK-U", "Ege", Specialty.Electrical), 0);
        var yakinGenel = Load(Tech("TK-Y", "Marmara", Specialty.General), 0);

        var result = _assigner.Choose([uzakUzman, yakinGenel],
                                      WorkOrderKind.Inspection,
                                      "İstanbul-Avrupa", "Deşarj");

        Assert.NotNull(result);
        Assert.Equal("TK-Y", result.Technician.Id);
    }

    [Fact]
    public void AyniBolgede_UzmanGenelciyeTercihEdilir()
    {
        var genel = Load(Tech("TK-G", "Marmara", Specialty.General), 0);
        var uzman = Load(Tech("TK-E", "Marmara", Specialty.Electrical), 0);

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
        var yuklu = Load(Tech("TK-1", "Marmara", Specialty.Electrical), 2);
        var bos = Load(Tech("TK-2", "Marmara", Specialty.Electrical), 0);

        var result = _assigner.Choose([yuklu, bos],
                                      WorkOrderKind.Inspection,
                                      "Bursa", "Deşarj");

        Assert.Equal("TK-2", result!.Technician.Id);
    }

    [Fact]
    public void KapasitesiDolanlar_AdayDegildir()
    {
        var dolu = Load(Tech("TK-1", "Marmara", Specialty.Electrical, maxOpen: 2), 2);
        var uzakBos = Load(Tech("TK-2", "Ege", Specialty.General), 0);

        var result = _assigner.Choose([dolu, uzakBos],
                                      WorkOrderKind.Inspection,
                                      "İstanbul-Avrupa", "Deşarj");

        // Bölge eşleşmesi olmasa bile kapasitesi olan seçilir.
        Assert.Equal("TK-2", result!.Technician.Id);
    }

    [Fact]
    public void PasifTeknisyen_AdayDegildir()
    {
        var pasif = Load(Tech("TK-1", "Marmara", Specialty.Electrical,
                              active: false), 0);
        var aktif = Load(Tech("TK-2", "Ege", Specialty.General), 0);

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
        var dolu1 = Load(Tech("TK-1", "Marmara", Specialty.Electrical, maxOpen: 1), 1);
        var dolu2 = Load(Tech("TK-2", "Ege", Specialty.General, maxOpen: 1), 1);

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
        var a = Load(Tech("TK-B", "Marmara", Specialty.General), 0);
        var b = Load(Tech("TK-A", "Marmara", Specialty.General), 0);

        var ilk = _assigner.Choose([a, b], WorkOrderKind.Inspection,
                                   "Bursa", "Normal");
        var ikinci = _assigner.Choose([b, a], WorkOrderKind.Inspection,
                                      "Bursa", "Normal");

        Assert.Equal(ilk!.Technician.Id, ikinci!.Technician.Id);
        Assert.Equal("TK-A", ilk.Technician.Id);   // id'ye göre alfabetik
    }
}
