import { useEffect, useState } from 'react'
import api from '../api'
import { ASSET_CLASS_TR } from '../constants'

/* Faz 9.3 — Yönetici ekranı.
 *
 * TASARIM İLKESİ: bu ekran, aynı verinin daha büyük puntolu hâli
 * DEĞİLDİR. Farklı sorulara cevap verir.
 *
 *   Saha ekranı (Filo/Detay)        Yönetici ekranı (bu)
 *   ─────────────────────────────   ────────────────────────────
 *   "Bu trafo ne durumda?"          "Filomun sağlığı nereye gidiyor?"
 *   "TTR B fazı %1.4 düşük"         "3 varlık kritik, ikisi LPT"
 *   "Bu testi gir"                  "Hangi varlığa bütçe ayırayım?"
 *   Tek ünite, derin                Filo, agregat
 *
 * Dördüncü bölüm (iş yükü) genelde unutulur ve en çok o gerekir: bir
 * yönetici sadece varlığın durumunu değil, EKİBİNİN o duruma yetişip
 * yetişmediğini bilmek ister.
 *
 * Veri üç kaynaktan gelir: Python filo + sağlık + test kapsaması,
 * .NET iş emirleri + personel. Servislerden biri kapalıysa o bölüm
 * kendi hatasını gösterir, ekranın geri kalanı çalışmaya devam eder.
 */

const BAND_ORDER = ['critical', 'poor', 'fair', 'good', 'excellent']
const BAND_TR = {
  critical: 'Kritik', poor: 'Kötü', fair: 'Orta',
  good: 'İyi', excellent: 'Çok İyi',
}
const BAND_CLASS = {
  critical: 'critical', poor: 'high', fair: 'medium',
  good: 'low', excellent: 'low',
}

const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('tr-TR',
    { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

function Tile({ label, value, hint, tone }) {
  return (
    <div className={`kpi${tone ? ` ${tone}` : ''}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {hint && <div className="kpi-hint">{hint}</div>}
    </div>
  )
}

/** Varlık sınıfı × sağlık bandı matrisi.
 *
 *  Neden matris? Çünkü "3 varlık kritik" tek başına karar verdirmez.
 *  Kritik olanın LPT mi SPT mi olduğu, bütçenin nereye gideceğini
 *  belirler: risk = olasılık × SONUÇ. */
function HealthMatrix({ transformers, onSelect }) {
  const classes = ['LPT', 'MPT', 'SPT']
  const cell = (cls, band) =>
    transformers.filter((t) => t.asset_class === cls && t.health_band === band)

  return (
    <div className="panel">
      <h2>Varlık Sınıfı × Sağlık Bandı</h2>
      <div className="table-scroll">
        <table className="compare matrix">
          <thead>
            <tr>
              <th>Sınıf</th>
              {BAND_ORDER.map((b) => <th key={b}>{BAND_TR[b]}</th>)}
              <th>Toplam</th>
            </tr>
          </thead>
          <tbody>
            {classes.map((cls) => {
              const row = transformers.filter((t) => t.asset_class === cls)
              if (!row.length) return null
              return (
                <tr key={cls}>
                  <td>
                    <b>{cls}</b>
                    <div className="muted matrix-sub">
                      {ASSET_CLASS_TR[cls] || cls}
                    </div>
                  </td>
                  {BAND_ORDER.map((band) => {
                    const items = cell(cls, band)
                    return (
                      <td key={band} className="matrix-cell">
                        {items.length === 0
                          ? <span className="muted">—</span>
                          : (
                            <div className={`matrix-box ${BAND_CLASS[band]}`}>
                              <b>{items.length}</b>
                              <div className="matrix-ids">
                                {items.map((t) => (
                                  <button key={t.id} type="button"
                                    className="link-like"
                                    onClick={() => onSelect(t)}>{t.id}</button>
                                ))}
                              </div>
                            </div>
                          )}
                      </td>
                    )
                  })}
                  <td className="num"><b>{row.length}</b></td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <p className="note">
        "3 varlık kritik" tek başına karar verdirmez: kritik olanın LPT mi
        SPT mi olduğu, bütçenin nereye gideceğini belirler.
        <b> Risk = olasılık × sonuç</b> — sağlık endeksi olasılığı, varlık
        sınıfı sonucu verir.
      </p>
    </div>
  )
}

/** Yenileme adayları: durum, aciliyet değil. */
function RenewalList({ items, onSelect }) {
  const top = items.filter((i) => i.renewal_priority != null)
    .sort((a, b) => b.renewal_priority - a.renewal_priority).slice(0, 6)

  if (!top.length) return null

  return (
    <div className="panel">
      <h2>Yenileme Adayları</h2>
      <table className="compare">
        <thead>
          <tr>
            <th>Varlık</th><th>Sağlık</th><th>Çeken boyut</th>
            <th>Yenileme önceliği</th>
          </tr>
        </thead>
        <tbody>
          {top.map((i) => (
            <tr key={i.transformer_id}>
              <td>
                <button type="button" className="link-like"
                  onClick={() => onSelect({ id: i.transformer_id })}>
                  <b>{i.transformer_id}</b>
                </button>
                <span className="muted"> · {i.asset_class}</span>
              </td>
              <td>
                <span className={`badge sm ${BAND_CLASS[i.band] || ''}`}>
                  {i.score ?? '—'}
                </span>
              </td>
              <td className="muted">
                {i.critical_dimensions?.length
                  ? i.critical_dimensions.join(', ')
                  : '—'}
              </td>
              <td className="num"><b>{i.renewal_priority?.toFixed(3)}</b></td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="note">
        Bu liste <b>aciliyeti</b> değil <b>durumu</b> sıralar. Filo
        ekranındaki öncelik "bugün kime koşayım" sorusunu, bu liste "bu yıl
        hangi ünitenin bütçesini ayırayım" sorusunu cevaplar. Aynı trafo
        birinde üstte, diğerinde altta olabilir.
      </p>
    </div>
  )
}

/** İş yükü: ekip duruma yetişiyor mu? */
function Workload({ orders, personnel, today }) {
  const open = orders.filter((o) => o.status === 'Planned'
                                 || o.status === 'InProgress')
  const overdue = open.filter((o) => o.dueDate && o.dueDate < today)
  const unassigned = open.filter((o) => !o.technicianId)

  const byPerson = (personnel?.items || []).map((p) => ({
    ...p,
    mine: open.filter((o) => o.technicianId === p.id),
  })).sort((a, b) => b.mine.length - a.mine.length)

  return (
    <div className="panel">
      <h2>İş Yükü</h2>

      <div className="kpis">
        <Tile label="Açık iş emri" value={open.length} hint="planlı + sürüyor" />
        <Tile label="Süresi geçmiş" value={overdue.length}
          hint="son tarih aşıldı"
          tone={overdue.length ? 'danger' : ''} />
        <Tile label="Atanmamış" value={unassigned.length}
          hint="sahibi yok"
          tone={unassigned.length ? 'alert' : ''} />
      </div>

      {overdue.length > 0 && (
        <>
          <h3>Süresi Geçmiş İşler</h3>
          <table className="compare">
            <thead>
              <tr><th>No</th><th>Varlık</th><th>İş</th>
                <th>Son tarih</th><th>Sorumlu</th></tr>
            </thead>
            <tbody>
              {overdue.slice(0, 8).map((o) => (
                <tr key={o.id}>
                  <td className="num">{o.seq}</td>
                  <td><b>{o.transformerId}</b></td>
                  <td className="muted">{o.title}</td>
                  <td className="over-limit">{fmtDate(o.dueDate)}</td>
                  <td className="muted">
                    {o.technician?.name || 'atanmadı'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}

      <h3>Kişi Başına Yük</h3>
      <table className="compare">
        <thead>
          <tr><th>Sicil</th><th>Ad</th><th>Rol</th>
            <th>Açık iş</th><th>Kapasite</th></tr>
        </thead>
        <tbody>
          {byPerson.map((p) => {
            const full = p.mine.length >= p.maxOpenOrders
            return (
              <tr key={p.id}>
                <td className="num">{p.employeeNo}</td>
                <td>{p.name}</td>
                <td className="muted">{p.role}</td>
                <td className="num">
                  <span className={full ? 'over-limit' : ''}>
                    {p.mine.length}
                  </span>
                </td>
                <td className="muted num">/ {p.maxOpenOrders}</td>
              </tr>
            )
          })}
        </tbody>
      </table>

      <p className="note">
        Bir yönetici sadece varlığın durumunu değil, <b>ekibinin o duruma
        yetişip yetişmediğini</b> bilmek ister. Atanmamış bir iş, açılmış
        ama sahibi olmayan bir iştir; süresi geçmiş bir iş, planlanmış ama
        yapılmamış bir iştir. İkisi de varlık ekranında görünmez.
      </p>
    </div>
  )
}

export default function ManagerDashboard({ onSelect }) {
  const [fleet, setFleet] = useState(null)
  const [health, setHealth] = useState(null)
  const [electrical, setElectrical] = useState(null)
  const [orders, setOrders] = useState(null)
  const [personnel, setPersonnel] = useState(null)
  const [maintError, setMaintError] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.fleetOverview(), api.healthFleet(), api.electricalFleet()])
      .then(([f, h, e]) => { setFleet(f); setHealth(h); setElectrical(e) })
      .catch((err) => setError(err?.response?.data?.detail || err.message))

    // .NET ayrı ele alınıyor: kapalıysa yalnızca iş yükü bölümü
    // kaybolsun, varlık bölümleri çalışmaya devam etsin.
    Promise.all([api.maintenance.workOrders(), api.personnel()])
      .then(([o, p]) => { setOrders(o.items || o); setPersonnel(p) })
      .catch((err) => setMaintError(err?.response?.data?.message || err.message))
  }, [])

  if (error) {
    return <div className="panel"><b>Filo verisi alınamadı:</b> {error}</div>
  }
  if (!fleet || !health) {
    return <div className="panel"><p className="empty">Yükleniyor…</p></div>
  }

  const stats = health.stats || {}
  const dist = stats.band_distribution || {}
  const critical = (dist.critical || 0) + (dist.poor || 0)
  const today = new Date().toISOString().slice(0, 10)

  // Veri kapsaması: kaç varlığın kaç boyutu ölçülü?
  const fullCoverage = fleet.transformers.filter(
    (t) => t.health?.coverage?.level === 'full').length
  const neverTested = electrical?.never_tested?.length ?? 0

  return (
    <div>
      <div className="panel">
        <h2>Yönetim Özeti</h2>
        <p className="note" style={{ marginTop: 0 }}>
          Bu ekran filo geneline bakar. Tek bir trafonun ölçüm ayrıntısı
          için <b>Filo</b> sekmesindeki karta girin.
        </p>

        <div className="kpis">
          <Tile label="Filo sağlığı" value={stats.average ?? '—'}
            hint={`en kötü ${stats.worst ?? '—'}`} />
          <Tile label="Kötü veya kritik" value={critical}
            hint={`${fleet.summary.total} varlık içinde`}
            tone={critical ? 'danger' : ''} />
          <Tile label="Tam veri" value={`${fullCoverage}/${fleet.summary.total}`}
            hint="dört boyutu da ölçülü" />
          <Tile label="Elektriksel testsiz" value={neverTested}
            hint="temel çizgi yok"
            tone={neverTested ? 'alert' : ''} />
          <Tile label="Numunesi gecikmiş"
            value={fleet.summary.sampling_overdue ?? 0}
            hint="sınıfa göre aralık"
            tone={fleet.summary.sampling_overdue ? 'alert' : ''} />
        </div>

        <h3>Sağlık Bandı Dağılımı</h3>
        <div className="riskbar" role="img"
          aria-label={BAND_ORDER.map((b) => `${BAND_TR[b]}: ${dist[b] || 0}`)
            .join(', ')}>
          {BAND_ORDER.filter((b) => dist[b] > 0).map((b) => (
            <span key={b} className={BAND_CLASS[b]}
              style={{ width: `${(dist[b] / (stats.scored || 1)) * 100}%` }}
              title={`${BAND_TR[b]}: ${dist[b]}`} />
          ))}
        </div>
        <div className="risk-legend">
          {BAND_ORDER.map((b) => (
            <span key={b} className={dist[b] ? '' : 'off'}>
              <i className={`dot ${BAND_CLASS[b]}`} />
              {BAND_TR[b]} <b>{dist[b] || 0}</b>
            </span>
          ))}
          {stats.unknown > 0 && (
            <span><i className="dot" />Bilinmiyor <b>{stats.unknown}</b></span>
          )}
        </div>
      </div>

      <HealthMatrix transformers={fleet.transformers} onSelect={onSelect} />

      <RenewalList items={health.items || []} onSelect={onSelect} />

      {maintError ? (
        <div className="panel">
          <h2>İş Yükü</h2>
          <p className="empty">Bakım servisine ulaşılamıyor: {maintError}</p>
          <p className="note">
            İş emirleri <b>.NET servisinde</b> (:5080). Bu bölüm olmasa da
            yukarıdaki varlık değerlendirmeleri Python'dan geldiği için
            çalışmaya devam eder — servislerin ayrı olmasının somut
            karşılığı.
          </p>
        </div>
      ) : orders && personnel ? (
        <Workload orders={orders} personnel={personnel} today={today} />
      ) : (
        <div className="panel"><p className="empty">İş yükü yükleniyor…</p></div>
      )}
    </div>
  )
}
