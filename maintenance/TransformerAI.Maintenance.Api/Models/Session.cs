using System.Text.Json.Serialization;

namespace TransformerAI.Maintenance.Api.Models;

/// <summary>Açık bir oturum. (Faz 9.0b)</summary>
/// <remarks>
/// <b>Neden her istekte parola göndermiyoruz?</b> Çünkü parola ne kadar çok
/// dolaşırsa o kadar çok yerde sızabilir: günlük dosyaları, tarayıcı
/// geçmişi, ara sunucular. Bir kez doğrulanır, karşılığında süreli bir
/// <b>belirteç</b> (token) verilir.
///
/// <b>Neden sunucuda saklıyoruz (JWT değil)?</b> JWT kendi kendini
/// doğrular ve sunucuda kayıt tutmaz — hızlıdır ama <i>iptal edilemez</i>.
/// Bir personel işten ayrıldığında ya da belirteç çalındığında JWT'yi
/// süresi dolana kadar durduramazsın. Sunucuda tutulan oturum tek satır
/// silinerek anında iptal edilir. Sistem Yönetimi bunu kullanıyor:
/// parola sıfırlama ve pasife alma, kişinin bütün oturumlarını kapatır.
///
/// Belirtecin kendisi de veritabanında <b>özetlenerek</b> saklanır —
/// parolada olduğu gibi. Veritabanı sızarsa açık belirteçlerle kimse
/// kimliğe bürünememeli.
/// </remarks>
public class Session
{
    /// <summary>Belirtecin ÖZETİ. Belirtecin kendisi saklanmaz.</summary>
    public string TokenHash { get; set; } = string.Empty;

    public string TechnicianId { get; set; } = string.Empty;

    /// <summary>Oturumu açan personel.</summary>
    [JsonIgnore]
    public Technician? Technician { get; set; }

    public DateTime CreatedAt { get; set; }

    /// <summary>Bu andan sonra belirteç geçersizdir.</summary>
    public DateTime ExpiresAt { get; set; }

    /// <summary>Son kullanım — "kimse kullanmıyorsa kapat" için.</summary>
    public DateTime LastSeenAt { get; set; }
}

/// <summary>Giriş isteği: sicil numarası + parola.</summary>
/// <remarks>Alanlar <c>string?</c>: eksik alan 400 bağlama hatası değil,
/// "sicil veya parola hatalı" cevabı alsın.</remarks>
public record LoginRequest(string? EmployeeNo, string? Password);

/// <summary>Giriş sonucu — arayüzün ihtiyaç duyduğu her şey.</summary>
/// <remarks>
/// <c>Token</c> YALNIZCA burada, bir kez döner. Sunucu onu özetleyip
/// saklar, bir daha okuyamaz — kaybedilirse yeniden giriş gerekir.
///
/// <c>MustChangePassword</c> true ise <c>Permissions</c> BOŞTUR ve oturum
/// kısa ömürlüdür: bu oturumla yapılabilecek tek iş parola değiştirmek.
/// </remarks>
public record LoginResponse(
    string Token,
    DateTime ExpiresAt,
    string EmployeeNo,
    string Name,
    string Role,
    string Specialty,
    // Faz 10: arayüz hangi ekranı/düğmeyi göstereceğini buradan bilir.
    // Sunucu yine de her istekte ayrıca kontrol eder — arayüzde gizlemek
    // tek başına yetki sayılmaz.
    string Department,
    string DepartmentName,
    IReadOnlyList<string> Permissions,
    bool MustChangePassword = false);

/// <summary>Personelin departmanını değiştirme isteği. (Faz 10)</summary>
public record ChangeDepartmentRequest(Department Department);

/// <summary>Giriş reddi — sebebiyle birlikte.</summary>
/// <remarks>
/// ⚠ Güvenlik dengesi: "sicil yok" ile "parola yanlış" ayrı ayrı söylenirse
/// saldırgan hangi sicillerin var olduğunu öğrenir (kullanıcı sayımı).
/// Bu yüzden ikisi de aynı mesajı döndürür. Kilitlenme ise AYRI bildirilir,
/// çünkü kullanıcının bunu bilmesi gerekir — yoksa doğru parolayı girip
/// reddedildiğinde ne olduğunu anlamaz ve destek arar.
/// </remarks>
public record LoginFailure(string Message, DateTime? LockedUntil = null);
