using System.Text.Json.Serialization;

namespace TransformerAI.Maintenance.Api.Models;

/// <summary>Açık bir oturum. (Faz 9.0b)</summary>
/// <remarks>
/// <b>Neden her istekte PIN göndermiyoruz?</b> Çünkü PIN ne kadar çok
/// dolaşırsa o kadar çok yerde sızabilir: günlük dosyaları, tarayıcı
/// geçmişi, ara sunucular. Bir kez doğrulanır, karşılığında süreli bir
/// <b>belirteç</b> (token) verilir.
///
/// <b>Neden sunucuda saklıyoruz (JWT değil)?</b> JWT kendi kendini
/// doğrular ve sunucuda kayıt tutmaz — hızlıdır ama <i>iptal edilemez</i>.
/// Bir personel işten ayrıldığında ya da belirteç çalındığında JWT'yi
/// süresi dolana kadar durduramazsın. Sunucuda tutulan oturum tek satır
/// silinerek anında iptal edilir. Bu projede kullanıcı sayısı küçük,
/// yani JWT'nin ölçeklenme avantajına ihtiyaç yok; iptal edilebilirlik
/// ise doğrudan güvenlik kazancı.
///
/// Belirtecin kendisi de veritabanında <b>özetlenerek</b> saklanır —
/// PIN'de olduğu gibi. Veritabanı sızarsa açık belirteçlerle kimse
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

/// <summary>Giriş isteği: sicil numarası + PIN.</summary>
public record LoginRequest(string EmployeeNo, string Pin);

/// <summary>Giriş sonucu — arayüzün ihtiyaç duyduğu her şey.</summary>
/// <remarks>
/// <c>Token</c> YALNIZCA burada, bir kez döner. Sunucu onu özetleyip
/// saklar, bir daha okuyamaz — kaybedilirse yeniden giriş gerekir.
/// </remarks>
public record LoginResponse(
    string Token,
    DateTime ExpiresAt,
    string EmployeeNo,
    string Name,
    string Role,
    string Specialty);

/// <summary>Giriş reddi — sebebiyle birlikte.</summary>
/// <remarks>
/// ⚠ Güvenlik dengesi: "sicil yok" ile "PIN yanlış" ayrı ayrı söylenirse
/// saldırgan hangi sicillerin var olduğunu öğrenir (kullanıcı sayımı).
/// Bu yüzden ikisi de aynı mesajı döndürür. Kilitlenme ise AYRI bildirilir,
/// çünkü kullanıcının bunu bilmesi gerekir — yoksa doğru PIN'i girip
/// reddedildiğinde ne olduğunu anlamaz ve destek arar.
/// </remarks>
public record LoginFailure(string Message, DateTime? LockedUntil = null);
