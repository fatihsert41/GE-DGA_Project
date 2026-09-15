using System.ComponentModel.DataAnnotations.Schema;
using System.Text.Json.Serialization;
using TransformerAI.Maintenance.Api.Services;

namespace TransformerAI.Maintenance.Api.Models;

/// <summary>Arızanın gerçekleştiği alt sistem — kök neden analizinin sınıfı. (Faz 12.5)</summary>
/// <remarks>
/// Serbest metin yerine sabit bir liste: "sargı", "Sargı arızası",
/// "winding" diye üç farklı yazılan aynı arıza, "bu arıza daha önce oldu
/// mu?" sorusunu cevapsız bırakırdı. Benzer analiz önerisi bu alana
/// dayanıyor.
///
/// <see cref="Undetermined"/> bilinçli olarak var: sebep bulunamadığında
/// en yakın kategoriyi seçmek, geçmişi yanlış bir örüntüyle doldurur.
/// (Faz 12.3'teki uzman etiketinde "belirlenemedi" seçeneği de aynı gerekçeyle.)
/// </remarks>
public enum FailureMode
{
    Insulation = 0,     // kağıt / pres tahtası yalıtımı
    Winding = 1,        // sargı (spir kısa devresi, deformasyon)
    Core = 2,           // nüve (topraklama, laminasyon)
    Bushing = 3,        // buşing
    TapChanger = 4,     // kademe değiştirici
    Cooling = 5,        // soğutma (fan, pompa, radyatör)
    Oil = 6,            // yağ (nem, kirlilik, bozunma)
    Protection = 7,     // koruma ve kontrol (röle, Buchholz, sensör)
    External = 8,       // dış etken (yıldırım, şebeke olayı, çevre)
    Undetermined = 9,   // belirlenemedi
}

/// <summary>Kapanmış bir iş emrinin kök neden analizi (RCA). (Faz 12.5)</summary>
/// <remarks>
/// <b>Neden iş emrine bağlı?</b> RCA "bir şey oldu, neden oldu, ne yaptık"
/// kaydıdır; bağlamı olmayan bir RCA denetlenemez. Hangi işin sonucunda
/// yazıldığı, o işi kimin yaptığı ve tamamlama notunda ne yazdığı RCA'nın
/// kanıtıdır.
///
/// <b>Neden bu veritabanında (Python'da değil)?</b> İş emirleri burada
/// duruyor. RCA'yı Python'a koymak, iki servisin birbirinin kaydına
/// işaret etmesi demekti — Faz 7'deki "ortak veritabanı yok" kuralı.
///
/// <b>Kayıt değiştirilemez.</b> Güncelleme uç noktası YOK: RCA bir denetim
/// kaydıdır. Sonradan "aslında sebep başkaymış" anlaşılırsa bu da bir
/// bilgidir ve yeni bir iş emriyle yeni bir analiz olarak kaydedilmeli.
/// </remarks>
public class RootCauseAnalysis
{
    /// <summary>RCA-0007 — iş emrinin sıra numarasından türetilir.</summary>
    /// <remarks>
    /// İş emri başına tek RCA olduğu için ayrı bir sayaç gerekmiyor; iş
    /// emrindeki yarış sorunu (Faz 7.5) burada yeniden yaşanmıyor.
    /// </remarks>
    public string Id { get; set; } = string.Empty;

    public string WorkOrderId { get; set; } = string.Empty;

    /// <summary>İlgili iş emri — navigation property.</summary>
    /// <remarks>JSON'a yazılmaz: uç noktalar iş emrini ayrıca döndürüyor,
    /// burada tekrar etmek cevabı şişirirdi.</remarks>
    [JsonIgnore]
    public WorkOrder? WorkOrder { get; set; }

    /// <summary>İş emrinden KOPYALANIR: benzer analiz sorgusu JOIN istemesin.</summary>
    public string TransformerId { get; set; } = string.Empty;

    public FailureMode FailureMode { get; set; }

    /// <summary>Arayüz için Türkçe ad. Veritabanına yazılmaz.</summary>
    [NotMapped]
    public string FailureModeLabel => RcaRules.Label(FailureMode);

    /// <summary>Bulgu — ne görüldü, ne ölçüldü.</summary>
    public string Finding { get; set; } = string.Empty;

    /// <summary>Kök neden — neden oldu.</summary>
    public string RootCause { get; set; } = string.Empty;

    /// <summary>Alınan önlem — ne yapıldı.</summary>
    public string CorrectiveAction { get; set; } = string.Empty;

    /// <summary>Tekrarı önleme — isteğe bağlı (ör. "numune aralığı 6 aya indirildi").</summary>
    public string? PreventiveAction { get; set; }

    public DateTime RecordedAt { get; set; } = DateTime.UtcNow;

    // Kaydeden kişi ANLIK GÖRÜNTÜ olarak yazılır (bildirimlerdeki gibi):
    // personel kaydı sonradan değişse de "bu analizi kim yazdı" cevaplanabilmeli.
    public string RecordedById { get; set; } = string.Empty;
    public string RecordedByName { get; set; } = string.Empty;
    public string RecordedByEmployeeNo { get; set; } = string.Empty;
}

/// <summary>RCA kaydetme isteği.</summary>
/// <remarks>
/// Alanlar bilinçli olarak <c>string?</c>: eksik ya da tanımsız bir arıza
/// türü, ASP.NET'in İngilizce bağlama hatası yerine
/// <see cref="RcaRules.Validate"/> içindeki Türkçe açıklamayla reddedilsin.
/// </remarks>
public record CreateRcaRequest(
    string? FailureMode,
    string? Finding,
    string? RootCause,
    string? CorrectiveAction,
    string? PreventiveAction = null);
