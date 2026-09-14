import { useCallback, useEffect, useState } from 'react'
import api from '../api'
import { can } from '../permissions'

/* Faz 9.0d — Personel kayıtları. Faz 10: departmanlar ve yetkiler.
 *
 * Bu ekran tamamen .NET servisinden beslenir (:5080). Python kapalı olsa
 * bile çalışır — servislerin ayrı olmasının somut karşılığı.
 *
 * Dört farklı şeyi bir arada gösteriyor ve bunlar karıştırılmamalı:
 *   DEPARTMAN → sistemde NE YAPABİLİR (yetkiler buna bağlı)
 *   ROL       → kurumdaki kıdemi
 *   UZMANLIK  → sahada hangi işi yapabilir (otomatik atama buna bakar)
 *   KAPASİTE  → aynı anda kaç açık iş üstlenebilir
 */

const ROLE_TR = {
  Technician: 'Teknisyen',
  Engineer: 'Mühendis',
  Supervisor: 'Süpervizör',
}

const SPECIALTY_TR = {
  General: 'Genel',
  Electrical: 'Elektriksel',
  Thermal: 'Termal',
  Sampling: 'Numune',
}

const ROLE_CLASS = {
  Supervisor: 'critical',
  Engineer: 'medium',
  Technician: 'low',
}

/** Departman → yetki tablosu. Veri .NET'teki katalogdan geliyor. */
function PermissionMatrix({ catalog, items }) {
  if (!catalog) return null
  const label = (key) => catalog.permissions.find((p) => p.key === key)?.label || key

  return (
    <div className="panel">
      <h2>Departmanlar ve Yetkiler</h2>
      <div className="table-scroll">
        <table className="compare perm-matrix">
          <thead>
            <tr><th>Departman</th><th>Personel</th><th>Yetkiler</th></tr>
          </thead>
          <tbody>
            {catalog.departments.map((d) => (
              <tr key={d.code}>
                <td>
                  <b>{d.name}</b>
                  <div className="muted" style={{ fontSize: '0.76rem' }}>
                    {d.description}
                  </div>
                </td>
                <td className="num">
                  {items.filter((p) => p.department === d.code).length}
                </td>
                <td>
                  <div className="perm-tags">
                    {d.fullAccess
                      ? <span className="perm-tag full">Tam yetki — her ekran ve her işlem</span>
                      : d.permissions.map((p) => (
                        <span key={p} className="perm-tag">{label(p)}</span>
                      ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note">
        Yetki <b>kişiye değil departmana</b> bağlıdır ve işlem bazlıdır:
        "Testler ekranı" diye bir yetki yok, "yağ testi kaydetme" diye bir
        yetki var. Her test türünü tek bir departman girer, böylece her
        ölçümün sorumlu birimi bellidir. Yönetim her yere girebilir.
      </p>
    </div>
  )
}

export default function PersonnelPanel({ currentUser }) {
  const [data, setData] = useState(null)
  const [catalog, setCatalog] = useState(null)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [busyId, setBusyId] = useState(null)

  const canManage = can('personnel.manage')

  const load = useCallback(() => {
    api.personnel()
      .then(setData)
      .catch((e) => setError(e?.response?.data?.message || e.message))
  }, [])

  useEffect(() => {
    load()
    api.departments().then(setCatalog).catch(() => setCatalog(null))
  }, [load])

  const changeDepartment = async (person, department) => {
    if (department === person.department) return
    const target = catalog?.departments.find((d) => d.code === department)
    // Onay şart: departman değişince kişinin yapabildikleri anında değişir.
    const ok = window.confirm(
      `${person.name} → ${target?.name || department}\n\n`
      + 'Kişinin yetkileri bu departmanın yetkileriyle değişecek. Devam edilsin mi?')
    if (!ok) return

    setBusyId(person.id); setNotice(null); setError(null)
    try {
      const res = await api.changeDepartment(person.id, department)
      setNotice(`${res.name} artık ${res.departmentName} departmanında. ${res.note}`)
      load()
    } catch (e) {
      setError(e?.response?.data?.message || e.message)
    } finally {
      setBusyId(null)
    }
  }

  if (error && !data) {
    return (
      <div className="panel">
        <h2>Personel</h2>
        <p className="empty">Personel kayıtları alınamadı: {error}</p>
        <p className="note">
          Bu ekran <b>.NET bakım servisinden</b> beslenir (:5080). Servis
          kapalıysa buradaki veriler gelmez — ama ölçüm ve analiz ekranları
          Python'dan beslendiği için çalışmaya devam eder.
        </p>
      </div>
    )
  }
  if (!data) return <div className="panel"><p className="empty">Yükleniyor…</p></div>

  const items = data.items || []
  const loaded = items.filter((p) => p.openOrders >= p.maxOpenOrders).length
  const departments = catalog?.departments || []

  return (
    <div>
      <div className="panel">
        <h2>Personel Kayıtları</h2>
        <p className="note" style={{ marginTop: 0 }}>
          Bu kayıtlar <b>.NET bakım servisinde</b> tutulur (:5080) —
          ölçümler ve analizler Python'da (:8000). İki servisin ayrı
          veritabanı kullanması bilinçlidir; ortak veritabanı,
          mikroservis mimarisinin en yaygın hatasıdır.
        </p>

        <div className="kpis">
          <div className="kpi">
            <div className="kpi-label">Personel</div>
            <div className="kpi-value">{items.length}</div>
            <div className="kpi-hint">kayıtlı</div>
          </div>
          <div className="kpi">
            <div className="kpi-label">Departman</div>
            <div className="kpi-value">{departments.length || '—'}</div>
            <div className="kpi-hint">birim</div>
          </div>
          <div className={`kpi${loaded ? ' alert' : ''}`}>
            <div className="kpi-label">Kapasitesi dolu</div>
            <div className="kpi-value">{loaded}</div>
            <div className="kpi-hint">yeni iş alamaz</div>
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Kayıtlar</h2>
        {notice && <div className="hi-note"><b>{notice}</b></div>}
        {error && <div className="np-problems"><b>{String(error)}</b></div>}

        <div className="table-scroll">
          <table className="compare">
            <thead>
              <tr>
                <th>Sicil</th><th>Ad</th><th>Departman</th><th>Rol</th>
                <th>Uzmanlık</th><th>Yük</th><th>Durum</th>
              </tr>
            </thead>
            <tbody>
              {items.map((p) => {
                const isMe = currentUser?.employeeNo === p.employeeNo
                const full = p.openOrders >= p.maxOpenOrders
                return (
                  <tr key={p.id} className={isMe ? 'selected' : ''}>
                    <td className="num"><b>{p.employeeNo}</b></td>
                    <td>
                      {p.name}
                      {isMe && <span className="me-chip">siz</span>}
                    </td>
                    <td>
                      {/* Yönetim departmanı buradan değiştirir; diğerleri
                          yalnızca görür. */}
                      {canManage && departments.length ? (
                        <select className="dept-select" value={p.department}
                          disabled={busyId === p.id}
                          aria-label={`${p.name} departmanı`}
                          onChange={(e) => changeDepartment(p, e.target.value)}>
                          {departments.map((d) => (
                            <option key={d.code} value={d.code}>{d.name}</option>
                          ))}
                        </select>
                      ) : (
                        p.departmentName || '—'
                      )}
                    </td>
                    <td>
                      <span className={`badge sm ${ROLE_CLASS[p.role] || ''}`}>
                        {ROLE_TR[p.role] || p.role}
                      </span>
                    </td>
                    <td className="muted">
                      {SPECIALTY_TR[p.specialty] || p.specialty}
                    </td>
                    <td className="num">
                      <span className={full ? 'over-limit' : ''}>
                        {p.openOrders}
                      </span>
                      <span className="muted"> / {p.maxOpenOrders}</span>
                    </td>
                    <td className="muted">
                      {p.isActive ? 'Aktif' : 'Pasif'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        <p className="note">
          <b>Departman</b> sistemde ne yapabileceğini, <b>rol</b> kıdemini,
          <b> uzmanlık</b> sahada hangi işi yapabileceğini söyler. Otomatik
          atama uzmanlığa, ekran ve işlem yetkileri departmana bakar.
          {canManage && (
            <> Sistemde en az bir aktif Yönetim personeli kalmak zorundadır;
              aksi hâlde kimse yetki yönetimi yapamazdı.</>
          )}
        </p>
      </div>

      <PermissionMatrix catalog={catalog} items={items} />

      <div className="panel">
        <h2>Kimlik ve İzlenebilirlik</h2>
        <p className="note" style={{ marginTop: 0 }}>
          Sisteme sicil numarası ve PIN ile girilir. Girilen her ölçüm,
          yağ testi ve elektriksel test <b>kimin kaydettiği</b> bilgisiyle
          saklanır; hatalı bir kaydı geçersiz işaretleyen kişi de kayda
          geçer.
        </p>
        <div className="tmeta">
          <span className="k">PIN saklama</span>
          <span>PBKDF2 · 100.000 tur · kişiye özel tuz
            <span className="muted"> (düz metin saklanmaz)</span></span>
          <span className="k">Hatalı deneme</span>
          <span>5 denemeden sonra 15 dakika kilit</span>
          <span className="k">Oturum</span>
          <span>İmzalı belirteç · 9 saat · çıkışta anında iptal</span>
          <span className="k">Yetki</span>
          <span>Departmana bağlı · her istekte sunucuda kontrol
            <span className="muted"> — yetkisiz istek 403 alır</span></span>
          <span className="k">Servisler arası</span>
          <span>Python belirteci ve yetki listesini imzasından doğrular
            <span className="muted"> — .NET'e sormaz, bu yüzden .NET
              kapalıyken de ölçüm girilebilir</span></span>
        </div>
        <div className="hi-note warn" style={{ marginTop: 14 }}>
          <b>Bu bir tam güvenlik katmanı değildir.</b> HTTPS/TLS yok (demo
          yerel ağda çalışıyor; gerçek kurulumda şart), çok faktörlü
          doğrulama ve parola politikası yok. Departmanı değiştirilen
          kişinin ölçüm servisindeki yetkileri yeniden giriş yapana kadar
          eski kalır. Dört haneli PIN güçlü bir parola değildir — amaç
          güvenlikten çok <b>izlenebilirliktir</b>.
        </div>
      </div>
    </div>
  )
}
