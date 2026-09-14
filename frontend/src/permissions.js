import { session } from './api'

/* Faz 10 — Arayüzde yetki kontrolü.
 *
 * Yetki listesi GİRİŞ cevabından geliyor ve oturumla birlikte saklanıyor.
 * Hangi departmanın hangi yetkiye sahip olduğu burada YAZILI DEĞİL:
 * harita yalnızca .NET'te (Models/Department.cs). Arayüz sadece "bu
 * kullanıcının listesinde bu yetki var mı?" diye bakar.
 *
 * ⚠ Bu bir GÜVENLİK sınırı DEĞİLDİR. Düğmeyi gizlemek, isteği atmayı
 * engellemez. Asıl kontrol sunucuda: yetkisiz istek 403 ile reddedilir.
 * Arayüzdeki kontrolün amacı kullanıcıyı işe yaramayacak bir düğmeye
 * bastırıp hata mesajıyla karşılamamak.
 */

/** Oturumdaki kullanıcı bu işlemi yapabilir mi? */
export const can = (permission, user = session.user()) =>
  Array.isArray(user?.permissions) && user.permissions.includes(permission)

/** Listedeki yetkilerden en az biri var mı? (ör. bakım ekranı: planlama VEYA yürütme) */
export const canAny = (permissions, user = session.user()) =>
  [].concat(permissions).some((p) => can(p, user))
