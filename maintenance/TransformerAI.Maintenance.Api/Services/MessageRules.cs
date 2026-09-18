using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Services;

/// <summary>Elle gönderilen bildirimin kurallları: doğrulama ve alıcılar.
/// (Faz 10)</summary>
/// <remarks>
/// <c>NotificationPlanner</c> gibi SAF bir sınıf: veritabanı ve HTTP
/// bilmez. "Departmana gönder" dendiğinde kimin alacağı gibi kurallar
/// burada durduğu için doğrudan test edilebiliyor.
///
/// <b>Neden alıcı listesi sunucuda çözülüyor?</b> Arayüz "Yağ Laboratuvarı"
/// seçildiğinde kişileri kendisi sayıp gönderebilirdi. Ama o anda
/// departmana yeni katılan ya da pasife alınan biri olabilir; gerçeği
/// bilen tek yer sunucudur.
/// </remarks>
public static class MessageRules
{
    public const int SubjectMax = 200;
    public const int BodyMax = 2000;

    /// <summary>Tek mesajla ulaşılabilecek en fazla kişi.</summary>
    /// <remarks>Yanlışlıkla "herkese" tıklanıp yüzlerce kişiye gitmesin;
    /// bu kurulumda personel az olduğu için sınır cömert.</remarks>
    public const int MaxRecipients = 200;

    /// <summary>Öncelik seçimi → gelen kutusu sıralama değeri.</summary>
    /// <remarks>
    /// İş emri bildirimleriyle AYNI ölçek kullanılıyor (öncelik 2.5 üstü
    /// "yüksek" görünüyor). Ayrı bir ölçek olsaydı gelen kutusunda acil
    /// bir mesaj rutin bir iş emrinin altına düşebilirdi.
    /// </remarks>
    public static double PriorityValue(string? priority) => priority switch
    {
        "urgent" => 4.0,
        "high" => 2.5,
        _ => 1.0,
    };

    /// <summary>Mesajı doğrular ve alıcıları çözer.</summary>
    /// <returns>Alıcılar (tekrarsız, aktif, gönderen hariç) ve sorunlar.
    /// Sorun listesi boş değilse mesaj GÖNDERİLMEMELİ.</returns>
    public static (IReadOnlyList<Technician> Recipients, IReadOnlyList<string> Problems)
        Resolve(SendMessageRequest request, IReadOnlyList<Technician> personnel,
                string senderId)
    {
        var problems = new List<string>();

        if (string.IsNullOrWhiteSpace(request.Subject)) 
            problems.Add("Konu boş olamaz.");
        else if (request.Subject.Trim().Length > SubjectMax)
            problems.Add($"Konu en fazla {SubjectMax} karakter olabilir.");

        if (string.IsNullOrWhiteSpace(request.Body))
            problems.Add("Mesaj metni boş olamaz.");
        else if (request.Body.Length > BodyMax)
            problems.Add($"Mesaj en fazla {BodyMax} karakter olabilir.");

        var chosen = new Dictionary<string, Technician>();
        void Add(Technician t)
        {
            // Pasif personele gönderilmez: işten ayrılmış birinin gelen
            // kutusu okunmaz ve "haber verildi" sanılır.
            if (!t.IsActive) return;
            // Gönderen kendine gönderemez; departmanını seçtiğinde de
            // kendi mesajı kendi gelen kutusuna düşmesin.
            if (t.Id == senderId) return;
            chosen[t.Id] = t;   // sözlük: aynı kişi iki yoldan seçilse de TEK kayıt
        }

        if (request.AllPersonnel)
            foreach (var t in personnel) Add(t);

        foreach (var code in request.Departments ?? new List<string>())
        {
            if (!Enum.TryParse<Department>(code, ignoreCase: false, out var dept)
                || !Enum.IsDefined(dept))
            {
                problems.Add($"Bilinmeyen departman: {code}");
                continue;
            }
            foreach (var t in personnel.Where(p => p.Department == dept)) Add(t);
        }

        foreach (var id in request.RecipientIds ?? new List<string>())
        {
            var person = personnel.FirstOrDefault(p => p.Id == id);
            if (person is null)
            {
                problems.Add($"Personel bulunamadı: {id}");
                continue;
            }
            if (!person.IsActive)
            {
                problems.Add($"{person.Name} pasif durumda; bildirim alamaz.");
                continue;
            }
            Add(person);
        }

        if (chosen.Count == 0 && problems.Count == 0)
            problems.Add("En az bir alıcı seçilmelidir (kişi, departman veya tüm personel).");

        if (chosen.Count > MaxRecipients)
            problems.Add($"Tek mesaj en fazla {MaxRecipients} kişiye gönderilebilir.");

        var recipients = chosen.Values.OrderBy(t => t.EmployeeNo).ToList();
        return (recipients, problems);
    }
}
