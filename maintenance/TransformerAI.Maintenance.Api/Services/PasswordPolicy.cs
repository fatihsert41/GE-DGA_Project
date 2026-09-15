using System.Globalization;

namespace TransformerAI.Maintenance.Api.Services;

/// <summary>Parola kuralları. (Sistem Yönetimi)</summary>
/// <remarks>
/// <b>Neden "büyük harf + rakam + sembol zorunlu" YOK?</b>
///
/// Karmaşıklık kuralları sezgisel olarak güvenli görünür ama insanlar
/// onlara tahmin edilebilir kalıplarla uyar: "parola" → "Parola1!".
/// Saldırganların sözlükleri tam olarak bu dönüşümleri dener. ABD'nin
/// NIST SP 800-63B rehberi bu yüzden karmaşıklık kurallarını
/// ÖNERMİYOR; önerdiği şey:
///
/// <list type="bullet">
/// <item><b>Uzunluk</b> — her ek karakter olasılık uzayını katlar.</item>
/// <item><b>Bilinen kötü parolaları reddetmek</b> — yaygın liste, kişinin
/// kendi bilgisi (sicil, ad).</item>
/// <item>Periyodik zorunlu değiştirme YOK — insanlar "Parola1" →
/// "Parola2" yapar. Değiştirme yalnızca şüphe ya da sıfırlama sonrası.</item>
/// </list>
///
/// Bu sınıf saftır: doğrudan test edilir, veritabanı bilmez.
/// </remarks>
public static class PasswordPolicy
{
    public const int MinLength = 10;

    /// <summary>Üst sınır: PBKDF2 çok uzun girdide yavaşlar (hizmet dışı bırakma).</summary>
    public const int MaxLength = 128;

    /// <summary>En az kaç FARKLI karakter — "aaaaaaaaaa" gibi tekrarları reddeder.</summary>
    private const int MinDistinctChars = 4;

    /// <summary>Addan kontrol edilecek parçanın en az uzunluğu.</summary>
    /// <remarks>
    /// 3 olsaydı "Can" adı "Vulcanize2026" parolasını reddederdi. Yanlış
    /// ret kullanıcıyı sistemi aşmaya iter; 4 makul bir denge.
    /// </remarks>
    private const int MinNamePartLength = 4;

    /// <summary>Kısa bir yaygın parola listesi.</summary>
    /// <remarks>
    /// Gerçek sistemde bu, sızıntılardan derlenmiş milyonlarca kayıtlık bir
    /// listedir (ör. "Have I Been Pwned"). Demo için alana özgü ve en bilinen
    /// örnekler yeterli; mekanizmanın varlığı önemli.
    /// </remarks>
    private static readonly HashSet<string> Common = new(StringComparer.OrdinalIgnoreCase)
    {
        "1234567890", "0123456789", "12345678910", "1111111111",
        "qwertyuiop", "abcdefghij", "password123", "password1234",
        "parola1234", "parola12345", "sifre12345", "şifre12345",
        "trafo12345", "transformer", "transformer1", "gevernova1",
        "gevernova123", "yonetici123", "admin12345", "administrator",
    };

    private static readonly CompareInfo Turkish =
        CultureInfo.GetCultureInfo("tr-TR").CompareInfo;

    /// <summary>Parolanın sorunları; boşsa kabul edilir.</summary>
    public static IReadOnlyList<string> Check(string? password, string employeeNo, string name)
    {
        var problems = new List<string>();

        if (string.IsNullOrEmpty(password))
        {
            problems.Add("Parola boş olamaz.");
            return problems;
        }

        if (password.Length < MinLength)
            problems.Add($"Parola en az {MinLength} karakter olmalı (şu an {password.Length}).");

        if (password.Length > MaxLength)
            problems.Add($"Parola en fazla {MaxLength} karakter olabilir.");

        if (!string.IsNullOrWhiteSpace(employeeNo) && password.Contains(employeeNo.Trim()))
            problems.Add("Parola sicil numaranızı içeremez: sicil herkesin bildiği bir bilgi.");

        // Ad kontrolü Türkçe büyük/küçük harf kurallarıyla: "İ"/"i" ve "I"/"ı".
        foreach (var part in (name ?? "").Split(' ', StringSplitOptions.RemoveEmptyEntries))
        {
            if (part.Length >= MinNamePartLength
                && Turkish.IndexOf(password, part, CompareOptions.IgnoreCase) >= 0)
            {
                problems.Add("Parola adınızı ya da soyadınızı içeremez.");
                break;
            }
        }

        if (password.Distinct().Count() < MinDistinctChars)
            problems.Add("Parola çok tekrarlı (ör. \"aaaaaaaaaa\").");

        if (Common.Contains(password))
            problems.Add("Bu parola çok yaygın; saldırganların ilk denediği listede.");

        return problems;
    }
}
