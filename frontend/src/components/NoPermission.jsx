import { useEffect, useState } from 'react'
import api, { session } from '../api'

/* Faz 10 — "Yetkiniz yok" gösterimi.
 *
 * İki biçimi var:
 *   compact → bir düğmenin YERİNE geçen tek satır ("Yağ testi kaydetme
 *             yetkisi yok"). Kullanıcı düğmenin neden olmadığını görür.
 *   tam     → bir ekranın yerine geçen panel.
 *
 * "Yetkiniz yok" tek başına kullanıcıyı çıkmazda bırakır. Bu yüzden her
 * iki biçim de işi KİMİN yapabileceğini söylüyor. Bilgi .NET'teki
 * katalogdan geliyor (GET /departments); burada tekrar yazılmıyor.
 */

export default function NoPermission({ permission, screen, compact = false }) {
  const [catalog, setCatalog] = useState(null)

  useEffect(() => {
    api.departments().then(setCatalog).catch(() => setCatalog(null))
  }, [])

  const wanted = [].concat(permission)
  const labels = wanted.map(
    (p) => catalog?.permissions?.find((x) => x.key === p)?.label || p)
  const owners = (catalog?.departments || [])
    .filter((d) => wanted.some((p) => d.permissions.includes(p)))
    .map((d) => d.name)
  const user = session.user()

  if (compact) {
    return (
      <span className="perm-locked"
        title={owners.length ? `Bu işlemi yapabilen: ${owners.join(', ')}` : undefined}>
        <span className="perm-lock" aria-hidden="true" />
        {labels.join(' / ')} yetkiniz yok
      </span>
    )
  }

  return (
    <div className="panel perm-denied">
      <h2>Erişim yetkiniz yok</h2>
      <p>
        <b>{screen || 'Bu ekran'}</b>, departmanınızın yetkileri arasında
        değil.
      </p>

      <div className="tmeta">
        <span className="k">Departmanınız</span>
        <span><b>{user?.departmentName || '—'}</b></span>
        <span className="k">Gerekli yetki</span>
        <span>{labels.join(' veya ')}</span>
        <span className="k">Bu yetkiye sahip</span>
        <span>{owners.length ? owners.join(', ') : '—'}</span>
      </div>

      <p className="note">
        Sistemde yetki kişiye değil <b>departmana</b> bağlıdır: yağ
        laboratuvarı yağ testini, elektriksel test ekibi elektriksel testi
        girer. Böylece her kaydın sorumlu birimi bellidir. Departmanınızın
        değişmesi gerekiyorsa Yönetim ile görüşün.
      </p>
    </div>
  )
}
