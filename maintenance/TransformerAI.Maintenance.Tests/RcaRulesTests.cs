using TransformerAI.Maintenance.Api.Models;
using TransformerAI.Maintenance.Api.Services;

namespace TransformerAI.Maintenance.Tests;

/// <summary>Kök neden analizi kuralları. (Faz 12.5)</summary>
/// <remarks>
/// Hepsi saf: veritabanı yok. <c>RcaRules</c> girdiyi parametre olarak
/// aldığı için "iş emri kritik mi, RCA yazılabilir mi, geçmişte benzeri
/// var mı" soruları tek tek sınanabiliyor.
/// </remarks>
public class RcaRulesTests
{
    private static WorkOrder Order(WorkOrderKind kind = WorkOrderKind.Inspection,
                                   WorkOrderStatus status = WorkOrderStatus.Done,
                                   double priority = 1.0,
                                   string transformerId = "TR-01")
    {
        var o = TestData.Order(transformerId, kind, status);
        o.Priority = priority;
        return o;
    }

    private static RootCauseAnalysis Rca(string workOrderId, string transformerId,
                                         FailureMode mode, int daysAgo = 0)
        => new()
        {
            Id = $"RCA-{workOrderId}",
            WorkOrderId = workOrderId,
            TransformerId = transformerId,
            FailureMode = mode,
            Finding = "test bulgusu",
            RootCause = "test nedeni",
            CorrectiveAction = "test önlemi",
            RecordedAt = new DateTime(2026, 9, 1, 0, 0, 0, DateTimeKind.Utc).AddDays(-daysAgo),
        };

    private const string LongText = "Yeterince uzun ve açıklayıcı bir metin.";

    // --- 1. Gerekli mi? ------------------------------------------------------

    [Fact]
    public void Rutin_dusuk_oncelikli_is_RCA_gerektirmez()
    {
        // Her kapanan işe RCA istemek kuyruğu şişirir, analizi anlamsızlaştırır.
        var routine = Order(WorkOrderKind.Sampling, priority: 1.0);
        Assert.False(RcaRules.IsRequired(routine));
        Assert.Empty(RcaRules.RequiredBecause(routine));
    }

    [Theory]
    [InlineData(2.5, true)]    // eşik dahil
    [InlineData(2.49, false)]
    [InlineData(4.0, true)]
    public void Kritik_oncelik_esigi(double priority, bool required)
    {
        Assert.Equal(required, RcaRules.IsRequired(Order(priority: priority)));
    }

    [Theory]
    [InlineData(WorkOrderKind.Repair)]
    [InlineData(WorkOrderKind.Replacement)]
    public void Onarim_ve_degisim_dusuk_oncelikte_de_RCA_gerektirir(WorkOrderKind kind)
    {
        // Onarım yapıldıysa arıza gerçekleşmiştir; önceliği ne olursa olsun.
        Assert.True(RcaRules.IsRequired(Order(kind, priority: 0.5)));
    }

    [Fact]
    public void Gerekce_metni_sunucu_kulturunden_bagimsiz()
    {
        // Linux/Docker'da kültür Invariant: "2.80" yazılırdı. Metin tr-TR sabit.
        var previous = System.Globalization.CultureInfo.CurrentCulture;
        System.Globalization.CultureInfo.CurrentCulture = System.Globalization.CultureInfo.InvariantCulture;
        try
        {
            var reason = Assert.Single(RcaRules.RequiredBecause(Order(priority: 2.8)));
            Assert.Contains("2,80", reason);
            Assert.Contains("2,5", reason);
        }
        finally
        {
            System.Globalization.CultureInfo.CurrentCulture = previous;
        }
    }

    [Fact]
    public void Iki_sebep_birden_varsa_ikisi_de_gosterilir()
    {
        var reasons = RcaRules.RequiredBecause(Order(WorkOrderKind.Repair, priority: 3.2));
        Assert.Equal(2, reasons.Count);
    }

    // --- 2. Yazılabilir mi? --------------------------------------------------

    [Fact]
    public void Olmayan_is_emrine_404()
    {
        Assert.Equal(404, RcaRules.CanRecord(null, alreadyRecorded: false)!.Value.Status);
    }

    [Theory]
    [InlineData(WorkOrderStatus.Planned)]
    [InlineData(WorkOrderStatus.InProgress)]
    [InlineData(WorkOrderStatus.Cancelled)]
    public void Yalnizca_tamamlanmis_ise_yazilir(WorkOrderStatus status)
    {
        var block = RcaRules.CanRecord(Order(status: status), alreadyRecorded: false);
        Assert.NotNull(block);
        Assert.Equal(409, block!.Value.Status);
    }

    [Fact]
    public void Ikinci_RCA_yazilamaz()
    {
        // Kayıt değiştirilemez: denetim izi korunmalı.
        var block = RcaRules.CanRecord(Order(), alreadyRecorded: true);
        Assert.Equal(409, block!.Value.Status);
    }

    [Fact]
    public void Tamamlanmis_ve_kaydi_olmayan_ise_yazilabilir()
    {
        Assert.Null(RcaRules.CanRecord(Order(), alreadyRecorded: false));
    }

    // --- Doğrulama -------------------------------------------------------------

    [Fact]
    public void Bos_istek_dort_sorun_uretir()
    {
        var (mode, problems) = RcaRules.Validate(new CreateRcaRequest(null, null, null, null));
        Assert.Null(mode);
        Assert.Equal(4, problems.Count);   // arıza türü + bulgu + kök neden + önlem
    }

    [Fact]
    public void Gecerli_istek_kabul_edilir_ve_tur_cozulur()
    {
        var (mode, problems) = RcaRules.Validate(
            new CreateRcaRequest("TapChanger", LongText, LongText, LongText));
        Assert.Empty(problems);
        Assert.Equal(FailureMode.TapChanger, mode);
    }

    [Fact]
    public void Kisa_metin_reddedilir()
    {
        // "Arıza giderildi" tekrarlayan arızada kimseye yol göstermez.
        var (_, problems) = RcaRules.Validate(
            new CreateRcaRequest("Winding", "Arıza giderildi", LongText, LongText));
        Assert.Single(problems);
        Assert.Contains("Bulgu", problems[0]);
    }

    [Theory]
    [InlineData("Sargi")]            // Türkçe ad değil, kod bekleniyor
    [InlineData("3")]                // sayı kabul edilmez
    [InlineData("Winding, Core")]    // TryParse bunu sessizce Bushing yapardı
    [InlineData("99")]
    public void Tanimsiz_ariza_turu_reddedilir(string raw)
    {
        var (mode, problems) = RcaRules.Validate(
            new CreateRcaRequest(raw, LongText, LongText, LongText));
        Assert.Null(mode);
        Assert.Single(problems);
    }

    [Fact]
    public void Tekrari_onleme_istege_bagli_ama_sinirli()
    {
        var ok = RcaRules.Validate(new CreateRcaRequest("Oil", LongText, LongText, LongText, null));
        Assert.Empty(ok.Problems);

        var tooLong = new string('x', RcaRules.TextMax + 1);
        var bad = RcaRules.Validate(new CreateRcaRequest("Oil", LongText, LongText, LongText, tooLong));
        Assert.Single(bad.Problems);
    }

    // --- 3. Benzer geçmiş analizler -------------------------------------------

    [Fact]
    public void Benzerlik_sirasi_tur_ve_trafo_ikisi_birden_en_ustte()
    {
        var past = new[]
        {
            Rca("WO-1", "TR-02", FailureMode.TapChanger),   // yalnızca tür  → 3
            Rca("WO-2", "TR-01", FailureMode.Cooling),      // yalnızca trafo → 2
            Rca("WO-3", "TR-01", FailureMode.TapChanger),   // ikisi birden  → 5
            Rca("WO-4", "TR-09", FailureMode.Oil),          // ilgisiz → dışarıda
        };

        var similar = RcaRules.Similar("TR-01", FailureMode.TapChanger, past);

        Assert.Equal(new[] { "WO-3", "WO-1", "WO-2" },
                     similar.Select(s => s.Rca.WorkOrderId).ToArray());
        Assert.Equal(2, similar[0].Why.Count);
    }

    [Fact]
    public void Tur_secilmeden_yalnizca_ayni_trafo_eslesir()
    {
        var past = new[]
        {
            Rca("WO-1", "TR-02", FailureMode.TapChanger),
            Rca("WO-2", "TR-01", FailureMode.Cooling),
        };
        var similar = RcaRules.Similar("TR-01", mode: null, past);
        Assert.Equal("WO-2", Assert.Single(similar).Rca.WorkOrderId);
    }

    [Fact]
    public void Belirlenemedi_tur_eslesmesi_sayilmaz()
    {
        // Sebebi bilinmeyen iki olay birbirine benzemez, sadece ikisi de bilinmiyordur.
        var past = new[] { Rca("WO-1", "TR-02", FailureMode.Undetermined) };
        Assert.Empty(RcaRules.Similar("TR-01", FailureMode.Undetermined, past));
    }

    [Fact]
    public void Kendi_analizi_benzer_gosterilmez()
    {
        var past = new[] { Rca("WO-7", "TR-01", FailureMode.Winding) };
        Assert.Empty(RcaRules.Similar("TR-01", FailureMode.Winding, past, excludeWorkOrderId: "WO-7"));
    }

    [Fact]
    public void Esit_benzerlikte_yeni_olan_ustte_ve_liste_sinirli()
    {
        var past = Enumerable.Range(1, 8)
            .Select(i => Rca($"WO-{i}", "TR-05", FailureMode.Bushing, daysAgo: i))
            .ToArray();

        var similar = RcaRules.Similar("TR-01", FailureMode.Bushing, past);

        Assert.Equal(RcaRules.SimilarLimit, similar.Count);
        Assert.Equal("WO-1", similar[0].Rca.WorkOrderId);   // en yeni (1 gün önce)
    }

    [Fact]
    public void Her_ariza_turunun_turkce_adi_var()
    {
        foreach (var mode in Enum.GetValues<FailureMode>())
            Assert.NotEqual(mode.ToString(), RcaRules.Label(mode));
    }
}
