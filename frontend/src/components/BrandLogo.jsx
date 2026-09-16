import { useState } from 'react'

/* Kurumsal logo yuvası (GE Vernova).
 *
 * Logo dosyaları depoya konmadı: kurumsal marka varlıkları projenin
 * kaynak kodu değildir ve lisansı ayrıdır. Bu yüzden bileşen dosyayı
 * `frontend/public/brand/` altından ARAR; dosya yoksa `onError` ile
 * yazı işaretine (wordmark) düşer. Böylece arayüz logo olmadan da
 * bozulmadan çalışır — demoyu logo dosyasına bağımlı yapmıyoruz.
 *
 * variant="mark"  → yuvarlak amblem (küçük alanlar: başlık çubuğu)
 * variant="lockup"→ yatay "GE VERNOVA" kilidi (giriş ekranı)
 */
export default function BrandLogo({ variant = 'mark', className = '' }) {
  const [failed, setFailed] = useState(false)
  const src = variant === 'lockup' ? '/brand/ge-vernova.png' : '/brand/ge-mark.png'

  if (failed) {
    return (
      <span className={`brand-fallback brand-fallback-${variant} ${className}`} aria-label="GE Vernova">
        <b>GE</b>{variant === 'lockup' && <i>VERNOVA</i>}
      </span>
    )
  }

  return (
    <img src={src} alt="GE Vernova" className={`brand-img brand-img-${variant} ${className}`}
      onError={() => setFailed(true)} />
  )
}
