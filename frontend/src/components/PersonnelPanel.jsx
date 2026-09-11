import { useEffect, useState } from 'react'
import api from '../api'

/* Faz 9.0d — Personel kayıtları.
 *
 * Kullanıcı sorusu: ".NET'teki kayıtları nerede görüntüleyebiliyorum?"
 * Cevap şimdiye kadar "sadece iş emirleri ve yük tablosu" idi; personel
 * kaydının kendisi hiçbir yerde görünmüyordu.
 *
 * Bu ekran tamamen .NET servisinden beslenir (:5080). Python kapalı olsa
 * bile çalışır — servislerin ayrı olmasının somut karşılığı.
 *
 * Üç farklı şeyi bir arada gösteriyor ve bunlar karıştırılmamalı:
 *   ROL       → sistemde ne görür, neyi onaylar
 *   UZMANLIK  → sahada hangi işi yapabilir
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

export default function PersonnelPanel({ currentUser }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.personnel()
      .then(setData)
      .catch((e) => setError(e?.response?.data?.message || e.message))
  }, [])

  if (error) {
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
  const byRole = items.reduce((acc, p) => {
    acc[p.role] = (acc[p.role] || 0) + 1
    return acc
  }, {})
  const loaded = items.filter((p) => p.openOrders >= p.maxOpenOrders).length

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
          {['Supervisor', 'Engineer', 'Technician'].map((r) => (
            <div className="kpi" key={r}>
              <div className="kpi-label">{ROLE_TR[r]}</div>
              <div className="kpi-value">{byRole[r] || 0}</div>
              <div className="kpi-hint">rol dağılımı</div>
            </div>
          ))}
          <div className={`kpi${loaded ? ' alert' : ''}`}>
            <div className="kpi-label">Kapasitesi dolu</div>
            <div className="kpi-value">{loaded}</div>
            <div className="kpi-hint">yeni iş alamaz</div>
          </div>
        </div>
      </div>

      <div className="panel">
        <h2>Kayıtlar</h2>
        <table className="compare">
          <thead>
            <tr>
              <th>Sicil</th><th>Ad</th><th>Rol</th><th>Uzmanlık</th>
              <th>Bölge</th><th>Yük</th><th>Durum</th>
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
                    <span className={`badge sm ${ROLE_CLASS[p.role] || ''}`}>
                      {ROLE_TR[p.role] || p.role}
                    </span>
                  </td>
                  <td className="muted">
                    {SPECIALTY_TR[p.specialty] || p.specialty}
                  </td>
                  <td className="muted">{p.region}</td>
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

        <p className="note">
          <b>Rol</b> ile <b>uzmanlık</b> farklı sorulara cevap verir: rol
          "sistemde ne görür, neyi onaylar", uzmanlık "sahada hangi işi
          yapabilir". Bir teknisyen termal uzmanı olabilir ama süpervizör
          olmayabilir. Otomatik atama uzmanlığa bakar; ekran yetkileri
          role bakar.
        </p>
      </div>

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
          <span className="k">Servisler arası</span>
          <span>Python belirteci imzasından doğrular
            <span className="muted"> — .NET'e sormaz, bu yüzden .NET
              kapalıyken de ölçüm girilebilir</span></span>
        </div>
        <div className="hi-note warn" style={{ marginTop: 14 }}>
          <b>Bu bir tam güvenlik katmanı değildir.</b> HTTPS/TLS yok (demo
          yerel ağda çalışıyor; gerçek kurulumda şart), çok faktörlü
          doğrulama ve parola politikası yok. Dört haneli PIN güçlü bir
          parola değildir — buradaki önlemler onu sicilinizi bilen birine
          karşı korur, sistemi elinde tutan birine karşı değil. Amaç
          güvenlikten çok <b>izlenebilirliktir</b>.
        </div>
      </div>
    </div>
  )
}
