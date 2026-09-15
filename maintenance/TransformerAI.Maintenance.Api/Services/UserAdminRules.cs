using System.Security.Cryptography;
using System.Text.RegularExpressions;
using TransformerAI.Maintenance.Api.Models;

namespace TransformerAI.Maintenance.Api.Services;

/// <summary>Kullanıcı yönetimi kuralları. (Sistem Yönetimi)</summary>
/// <remarks>
/// SAF bir sınıf: veritabanı ve HTTP bilmez. Uç nokta personel listesini
/// verir, bu sınıf "izin var mı?" cevabını üretir.
///
/// <b>En önemli tehlike: yetki yükseltme (privilege escalation).</b>
/// Kullanıcı yönetebilen biri kendi hesabına dokunabilseydi, kendini
/// Yönetim departmanına taşıyıp her yetkiyi alırdı. Bu yüzden admin
/// KENDİ hesabının departmanını değiştiremez ve kendini pasife alamaz.
///
/// <b>İkinci tehlike: kilitlenme.</b> Son aktif Sistem Yöneticisi ya da son
/// aktif Yönetim personeli pasife alınır veya taşınırsa, sistemi ancak
/// veritabanına elle müdahale kurtarır.
/// </remarks>
public static partial class UserAdminRules
{
    public const int NameMin = 3;
    public const int NameMax = 100;
    public const int MaxOpenOrdersLimit = 10;
    public const int ReasonMin = 10;
    public const int TemporaryPasswordLength = 12;

    /// <summary>Geçici parola alfabesi — karıştırılan karakterler YOK.</summary>
    /// <remarks>
    /// 0/O, 1/l/I yok: geçici parola admin tarafından kullanıcıya SÖZLÜ ya
    /// da yazılı iletilir. "Bu sıfır mı O mu?" sorusu, yanlış denemeyle
    /// hesabın kilitlenmesine yol açar.
    /// </remarks>
    private const string TemporaryAlphabet =
        "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghjkmnpqrstuvwxyz23456789";

    [GeneratedRegex(@"^\d{5,10}$")]
    private static partial Regex EmployeeNoPattern();

    [GeneratedRegex(@"^TK-(\d+)$")]
    private static partial Regex IdPattern();

    // --- Yeni kullanıcı ---------------------------------------------------------

    /// <summary>İsteği doğrular; geçerliyse kaydedilmeye hazır (kimliksiz) bir taslak döner.</summary>
    /// <remarks>Sicil benzersizliği burada DEĞİL: onu veritabanı bilir (benzersiz indeks).</remarks>
    public static (Technician? Draft, IReadOnlyList<string> Problems) ValidateCreate(CreateUserRequest request)
    {
        var problems = new List<string>();

        var employeeNo = request.EmployeeNo?.Trim() ?? "";
        if (!EmployeeNoPattern().IsMatch(employeeNo))
            problems.Add("Sicil numarası 5–10 haneli, yalnızca rakamdan oluşmalı.");

        var name = request.Name?.Trim() ?? "";
        if (name.Length < NameMin || name.Length > NameMax)
            problems.Add($"Ad soyad {NameMin}–{NameMax} karakter olmalı.");

        var department = ParseEnum<Department>(request.Department, "Departman", problems, required: true);
        var role = ParseEnum<PersonnelRole>(request.Role, "Rol", problems, required: true);
        var specialty = ParseEnum<Specialty>(request.Specialty, "Uzmanlık", problems, required: false)
                        ?? Specialty.General;

        var maxOpen = request.MaxOpenOrders ?? 3;
        if (maxOpen < 0 || maxOpen > MaxOpenOrdersLimit)
            problems.Add($"Açık iş kapasitesi 0–{MaxOpenOrdersLimit} arasında olmalı.");

        if (problems.Count > 0)
            return (null, problems);

        return (new Technician
        {
            EmployeeNo = employeeNo,
            Name = name,
            Department = department!.Value,
            Role = role!.Value,
            Specialty = specialty,
            MaxOpenOrders = maxOpen,
            IsActive = true,
        }, problems);
    }

    /// <summary>Sıradaki iç kimlik: TK-09, TK-10...</summary>
    /// <remarks>
    /// Sayı üzerinde en büyük alınır, metin üzerinde değil — iş emri
    /// numarasındaki "WO-9999 &gt; WO-10001" dersiyle aynı. Yarışı bu
    /// metot ÇÖZMEZ; birincil anahtar ikinci kaydı reddeder, uç nokta
    /// yeniden dener.
    /// </remarks>
    public static string NextId(IEnumerable<string> existingIds)
    {
        var max = 0;
        foreach (var id in existingIds)
        {
            var m = IdPattern().Match(id);
            if (m.Success && int.TryParse(m.Groups[1].Value, out var n) && n > max)
                max = n;
        }
        return $"TK-{max + 1:D2}";
    }

    /// <summary>Kriptografik rastgele geçici parola.</summary>
    public static string GenerateTemporaryPassword()
    {
        while (true)
        {
            var chars = RandomNumberGenerator.GetItems<char>(TemporaryAlphabet, TemporaryPasswordLength);
            var candidate = new string(chars);
            // En az bir harf ve bir rakam: sözlü iletilirken "hepsi harf mi?"
            // karışıklığı olmasın. (Güvenlik için değil — 12 karakter zaten yeterli.)
            if (candidate.Any(char.IsDigit) && candidate.Any(char.IsLetter))
                return candidate;
        }
    }

    // --- Hesap üzerindeki işlemler ---------------------------------------------

    /// <summary>Pasife alınabilir mi? Sorun varsa (HTTP kodu, mesaj).</summary>
    public static (int Status, string Message)? CanDeactivate(
        string actorId, Technician target, IReadOnlyList<Technician> all, string? reason)
    {
        if (target.Id == actorId)
            return (409, "Kendi hesabınızı pasife alamazsınız. Başka bir Sistem Yöneticisi yapmalı.");

        if (!target.IsActive)
            return (409, $"{target.Name} zaten pasif.");

        if (IsLastActiveIn(Department.SystemAdmin, target, all))
            return (409, "Son aktif Sistem Yöneticisi pasife alınamaz; aksi hâlde kimse kullanıcı yönetemez.");

        if (IsLastActiveIn(Department.Management, target, all))
            return (409, "Son aktif Yönetim personeli pasife alınamaz.");

        if (string.IsNullOrWhiteSpace(reason) || reason.Trim().Length < ReasonMin)
            return (400, $"Pasife alma gerekçesi zorunludur (en az {ReasonMin} karakter).");

        return null;
    }

    /// <summary>Departman değiştirilebilir mi?</summary>
    public static (int Status, string Message)? CanChangeDepartment(
        string actorId, Technician target, Department newDepartment, IReadOnlyList<Technician> all)
    {
        if (!Enum.IsDefined(newDepartment))
            return (400, "Geçersiz departman.");

        // Yetki yükseltme koruması: kişi kendi yetkisini değiştiremez.
        if (target.Id == actorId)
            return (403, "Kendi departmanınızı değiştiremezsiniz: kişi kendi yetkisini "
                         + "genişletememeli. Başka bir yetkili yapmalı.");

        if (target.Department == newDepartment)
            return null;

        if (IsLastActiveIn(Department.SystemAdmin, target, all))
            return (409, "Sistemde en az bir aktif Sistem Yöneticisi kalmalı. "
                         + "Önce başka birini Sistem Yönetimi departmanına atayın.");

        if (IsLastActiveIn(Department.Management, target, all))
            return (409, "Sistemde en az bir aktif Yönetim personeli kalmalı. "
                         + "Önce başka birini Yönetim departmanına atayın.");

        return null;
    }

    /// <summary>Parola sıfırlanabilir mi?</summary>
    public static (int Status, string Message)? CanResetPassword(string actorId, Technician target)
    {
        if (target.Id == actorId)
            return (409, "Kendi parolanızı buradan sıfırlayamazsınız; \"Parolamı değiştir\" kullanın.");
        if (!target.IsActive)
            return (409, "Pasif hesabın parolası sıfırlanmaz; önce hesabı etkinleştirin.");
        return null;
    }

    private static bool IsLastActiveIn(Department department, Technician target,
                                       IReadOnlyList<Technician> all) =>
        target.IsActive
        && target.Department == department
        && !all.Any(t => t.Id != target.Id && t.IsActive && t.Department == department);

    private static T? ParseEnum<T>(string? raw, string label, List<string> problems, bool required)
        where T : struct, Enum
    {
        var value = raw?.Trim();
        if (string.IsNullOrEmpty(value))
        {
            if (required) problems.Add($"{label} seçilmelidir.");
            return null;
        }

        // Yalnızca harf: Enum.TryParse "3" ve "A, B" girdilerini de kabul
        // ediyor (RCA fazında bulunan tuzak).
        if (value.All(char.IsLetter)
            && Enum.TryParse<T>(value, ignoreCase: false, out var parsed)
            && Enum.IsDefined(parsed))
            return parsed;

        problems.Add($"Bilinmeyen {label.ToLowerInvariant()}: {value}");
        return null;
    }
}
