namespace TransformerAI.Maintenance.Api.Models;

// Sistem Yönetimi: kullanıcı hesaplarının istek gövdeleri ve denetim kaydı.
//
// İstek alanları bilinçli olarak string? — eksik ya da tanımsız bir
// departman adı, ASP.NET'in İngilizce bağlama hatası yerine
// UserAdminRules içindeki Türkçe açıklamayla reddedilsin (RCA'daki gibi).

/// <summary>Yeni kullanıcı isteği. Parola YOK: geçici parolayı sistem üretir.</summary>
/// <remarks>
/// Admin'in parola yazmasına izin verseydik iki sorun olurdu: admin zayıf
/// bir parola seçebilirdi ("Demo12345") ve kullanıcının ilk parolasını
/// bilen biri olurdu. Sistem üretir, bir kez gösterir, kullanıcı ilk
/// girişte değiştirir.
/// </remarks>
public record CreateUserRequest(
    string? EmployeeNo,
    string? Name,
    string? Department,
    string? Role,
    string? Specialty = null,
    int? MaxOpenOrders = null);

/// <summary>Pasife alma isteği — gerekçe zorunlu.</summary>
public record DeactivateUserRequest(string? Reason);

/// <summary>Kullanıcının kendi parolasını değiştirmesi.</summary>
public record ChangePasswordRequest(string? CurrentPassword, string? NewPassword);

/// <summary>Kullanıcı hesabıyla ilgili bir olay — kim, kime, ne yaptı.</summary>
/// <remarks>
/// <b>Neden ayrı tablo?</b> "Bu hesabı kim açtı, parolasını kim sıfırladı,
/// neden pasife alındı?" soruları admin panelinin kendisini denetler.
/// Kullanıcı ekleyebilen biri, izi olmadan ekleyebilmemeli.
///
/// Kişiler ANLIK GÖRÜNTÜ olarak yazılır (sicil + ad): hesap sonradan
/// değişse de olayın kime ait olduğu okunabilmeli. Kayıt silinmez,
/// güncellenmez.
///
/// <c>Actor*</c> alanları boş olabilir: kilitlenme gibi olayları bir kişi
/// değil sistem üretir.
/// </remarks>
public class UserAuditEvent
{
    public long Id { get; set; }
    public DateTime At { get; set; }
    public string Action { get; set; } = string.Empty;

    public string TargetId { get; set; } = string.Empty;
    public string TargetEmployeeNo { get; set; } = string.Empty;
    public string TargetName { get; set; } = string.Empty;

    public string? ActorId { get; set; }
    public string? ActorEmployeeNo { get; set; }
    public string? ActorName { get; set; }

    public string? Detail { get; set; }
}

/// <summary>Denetim olayı türleri ve Türkçe adları.</summary>
public static class UserAuditActions
{
    public const string Created = "created";
    public const string PasswordReset = "password_reset";
    public const string PasswordChanged = "password_changed";
    public const string Unlocked = "unlocked";
    public const string Locked = "locked";
    public const string Deactivated = "deactivated";
    public const string Activated = "activated";
    public const string DepartmentChanged = "department_changed";

    public static readonly IReadOnlyDictionary<string, string> Labels =
        new Dictionary<string, string>
        {
            [Created] = "Hesap açıldı",
            [PasswordReset] = "Parola sıfırlandı",
            [PasswordChanged] = "Parola değiştirildi",
            [Unlocked] = "Kilit açıldı",
            [Locked] = "Hatalı denemeler nedeniyle kilitlendi",
            [Deactivated] = "Pasife alındı",
            [Activated] = "Yeniden etkinleştirildi",
            [DepartmentChanged] = "Departman değişti",
        };

    public static string Label(string action) =>
        Labels.TryGetValue(action, out var label) ? label : action;
}
