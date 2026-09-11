import { useCallback, useEffect, useState } from 'react'
import api from '../api'

/* Faz 7.7 — Bakım planlama ekranı.
 *
 * Bu bileşen İKİNCİ servise (.NET, :5080) konuşur. Filo ekranı Python
 * servisinden beslenir; burası iş emirlerini .NET'ten alır.
 *
 * Önemli davranış: .NET servisi kapalıysa bu ekran açıklayıcı bir mesaj
 * gösterir ama uygulamanın geri kalanı çalışmaya devam eder. Servislerin
 * birbirini düşürmemesi mimarinin amacıydı; arayüz de buna uymalı.
 */

const STATUS_TR = {
  Planned: 'Planlandı',
  InProgress: 'Devam ediyor',
  Done: 'Tamamlandı',
  Cancelled: 'İptal',
}

// Kural -> hangi ölçüm kaynağından geldiği. Aynı ekranda "gaz analizi
// böyle diyor" ile "sargı direnci böyle diyor" ayırt edilebilmeli:
// ikisi bağımsız kaynaklardır ve aynı anda aynı şeyi söylemeleri,
// tek kaynağın iki kez söylemesinden çok daha güçlü bir kanıttır.
const SOURCE = {
  'severe-fault': { label: 'DGA', cls: 'gas' },
  'high-risk': { label: 'DGA', cls: 'gas' },
  'low-confidence': { label: 'DGA', cls: 'gas' },
  'sampling-overdue': { label: 'Numune', cls: '' },
  'never-sampled': { label: 'Numune', cls: '' },
  'electrical-fault': { label: 'Elektriksel', cls: 'elec' },
  'electrical-data-suspect': { label: 'Elektriksel', cls: 'elec' },
  'no-electrical-baseline': { label: 'Elektriksel', cls: 'elec' },
  'paper-end-of-life': { label: 'Kağıt', cls: 'paper' },
  'health-critical': { label: 'Sağlık endeksi', cls: 'health' },
}

const KIND_TR = {
  Inspection: 'İnceleme',
  Sampling: 'Numune alma',
  Repair: 'Onarım',
  Replacement: 'Değişim',
  // Faz 9.1: elektriksel test yapılması/tekrarlanması. İncelemeden ayrı,
  // çünkü ekipman ve planlı kesinti gerektirir.
  Test: 'Elektriksel test',
}

// Durum -> rozet sınıfı. Risk rampasının renkleri KULLANILMIYOR: iş emri
// durumu bir tehlike seviyesi değil, iş akışı aşamasıdır.
const STATUS_CLASS = {
  Planned: 'wo-planned',
  InProgress: 'wo-progress',
  Done: 'wo-done',
  Cancelled: 'wo-cancelled',
}

const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('tr-TR',
    { day: 'numeric', month: 'short', year: '2-digit' }) : '—'

/** Son tarihi geçmiş mi? Geçtiyse görünür olmalı. */
const isOverdue = (order) =>
  order.dueDate
  && order.status !== 'Done'
  && order.status !== 'Cancelled'
  && new Date(order.dueDate) < new Date()

function StatTile({ label, value, hint, tone }) {
  return (
    <div className={`kpi${tone ? ` ${tone}` : ''}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {hint && <div className="kpi-hint">{hint}</div>}
    </div>
  )
}

/** Sistemin ürettiği öneriler — henüz iş emri değiller. */
function SuggestionPanel({ suggestions, onApply, applying }) {
  if (!suggestions) return null

  if (suggestions.count === 0) {
    return (
      <div className="panel">
        <h2>Öneriler</h2>
        <p className="empty">
          Açık iş emri gerektiren yeni durum yok.
        </p>
      </div>
    )
  }

  return (
    <div className="panel">
      <h2>
        Öneriler <span className="count-pill">{suggestions.count}</span>
      </h2>
      <p className="note" style={{ marginTop: 0 }}>
        Sistem filoya baktı ve şu işlerin açılmasını öneriyor. Zaten açık
        emri olan trafolar listede yok.
      </p>

      <table className="compare">
        <thead>
          <tr>
            <th>Trafo</th><th>Tür</th><th>Öncelik</th>
            <th>Son tarih</th><th>Gerekçe</th>
          </tr>
        </thead>
        <tbody>
          {suggestions.suggestions.map((s) => (
            <tr key={`${s.transformerId}-${s.kind}`}>
              <td><b>{s.transformerId}</b></td>
              <td>
                {KIND_TR[s.kind] || s.kind}
                {/* Önerinin hangi DUYUDAN geldiği. Faz 9.1'e kadar
                    hepsi gaz analizindendi; artık dört kaynak var ve
                    planlamacının hangisine baktığını bilmesi gerekir. */}
                <span className={`src-chip ${SOURCE[s.rule]?.cls || ''}`}>
                  {SOURCE[s.rule]?.label || 'DGA'}
                </span>
              </td>
              <td>{s.priority.toFixed(2)}</td>
              <td>{fmtDate(s.dueDate)}</td>
              <td className="muted" style={{ fontFamily: 'inherit' }}>
                {s.reason}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <button type="button" className="primary" onClick={onApply}
        disabled={applying}>
        {applying ? 'Uygulanıyor…' : `${suggestions.count} iş emrini oluştur`}
      </button>
    </div>
  )
}

function TechnicianTable({ technicians }) {
  if (!technicians?.items?.length) return null

  return (
    <div className="panel">
      <h2>Teknisyenler</h2>
      <table className="compare">
        <thead>
          <tr><th>Sicil</th><th>Ad</th><th>Uzmanlık</th><th>Yük</th></tr>
        </thead>
        <tbody>
          {technicians.items.map((t) => (
            <tr key={t.id}>
              <td className="num">{t.employeeNo}</td>
              <td><b>{t.name}</b></td>
              <td className="muted">{t.specialty}</td>
              <td>
                <span className={t.hasCapacity ? '' : 'over-limit'}>
                  {t.openOrders} / {t.maxOpenOrders}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="note">
        Otomatik atama bölge eşleşmesine (+10), uzmanlığa (+5) ve yüke bakar.
      </p>
    </div>
  )
}

function WorkOrderTable({ orders, onAssign, onStatus, busyId }) {
  if (!orders?.items?.length) {
    return (
      <div className="panel">
        <h2>İş Emirleri</h2>
        <p className="empty">Henüz iş emri yok.</p>
      </div>
    )
  }

  return (
    <div className="panel">
      <h2>İş Emirleri <span className="count-pill">{orders.count}</span></h2>
      <div className="table-scroll">
        <table className="compare wo-table">
          <thead>
            <tr>
              <th>No</th><th>Trafo</th><th>İş</th><th>Öncelik</th>
              <th>Son tarih</th><th>Teknisyen</th><th>Durum</th><th></th>
            </tr>
          </thead>
          <tbody>
            {orders.items.map((o) => (
              <tr key={o.id} className={isOverdue(o) ? 'row-overdue' : ''}>
                <td className="mono">{o.id}</td>
                <td><b>{o.transformerId}</b></td>
                <td>
                  <div>{o.title}</div>
                  <div className="muted" style={{ fontSize: '0.75rem' }}>
                    {KIND_TR[o.kind] || o.kind}
                  </div>
                </td>
                <td>{o.priority?.toFixed(2)}</td>
                <td>
                  {fmtDate(o.dueDate)}
                  {isOverdue(o) && <div className="over-limit">gecikti</div>}
                </td>
                <td>
                  {o.technician
                    ? o.technician.name
                    : <span className="muted">atanmadı</span>}
                </td>
                <td>
                  <span className={`wo-badge ${STATUS_CLASS[o.status]}`}>
                    {STATUS_TR[o.status] || o.status}
                  </span>
                </td>
                <td className="wo-actions">
                  {!o.technician && (
                    <button type="button" className="chip"
                      disabled={busyId === o.id}
                      onClick={() => onAssign(o.id)}>Ata</button>
                  )}
                  {o.status === 'Planned' && (
                    <button type="button" className="chip"
                      disabled={busyId === o.id}
                      onClick={() => onStatus(o.id, 'InProgress')}>Başlat</button>
                  )}
                  {o.status === 'InProgress' && (
                    <button type="button" className="chip"
                      disabled={busyId === o.id}
                      onClick={() => onStatus(o.id, 'Done')}>Bitir</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default function MaintenancePanel() {
  const [orders, setOrders] = useState(null)
  const [summary, setSummary] = useState(null)
  const [suggestions, setSuggestions] = useState(null)
  const [technicians, setTechnicians] = useState(null)
  const [error, setError] = useState(null)
  const [applying, setApplying] = useState(false)
  const [busyId, setBusyId] = useState(null)
  const [notice, setNotice] = useState(null)

  // useCallback: fonksiyonu her render'da yeniden yaratmamak için.
  // useEffect'in bağımlılık listesinde kullanıldığı için şart — yoksa
  // sonsuz döngüye girer.
  const load = useCallback(async () => {
    setError(null)
    try {
      // Promise.all: dört isteği PARALEL at, hepsi bitince devam et.
      // Sırayla atsaydık dört gidiş-dönüş süresi toplanırdı.
      const [o, s, sg, t] = await Promise.all([
        api.maintenance.workOrders(),
        api.maintenance.summary(),
        api.maintenance.suggestions().catch(() => null),
        api.maintenance.technicians(),
      ])
      setOrders(o); setSummary(s); setSuggestions(sg); setTechnicians(t)
    } catch (e) {
      setError(e?.response?.data?.title
               || e?.response?.data?.detail
               || e.message)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const handleApply = async () => {
    setApplying(true); setNotice(null)
    try {
      const res = await api.maintenance.applySuggestions()
      setNotice(`${res.created} iş emri oluşturuldu.`)
      await load()
    } catch (e) {
      setError(e?.response?.data?.title || e.message)
    } finally {
      setApplying(false)
    }
  }

  const handleAssign = async (id) => {
    setBusyId(id); setNotice(null)
    try {
      const res = await api.maintenance.assign(id)
      setNotice(res.warning
        ? `${res.workOrder.technician.name} atandı — ${res.warning}`
        : `${res.workOrder.technician.name} atandı (${res.reason}).`)
      await load()
    } catch (e) {
      setError(e?.response?.data?.title || e?.response?.data?.message || e.message)
    } finally {
      setBusyId(null)
    }
  }

  const handleStatus = async (id, status) => {
    setBusyId(id)
    try {
      await api.maintenance.setStatus(id, status)
      await load()
    } catch (e) {
      setError(e?.response?.data?.message || e.message)
    } finally {
      setBusyId(null)
    }
  }

  if (error && !orders) {
    return (
      <div className="panel">
        <h2>Bakım Planlama</h2>
        <p className="empty">
          Bakım servisine ulaşılamıyor: {String(error)}
        </p>
        <p className="note">
          .NET servisi çalışıyor mu? <code>cd maintenance/TransformerAI.Maintenance.Api;
          dotnet run --urls http://localhost:5080</code>
        </p>
      </div>
    )
  }

  if (!orders) {
    return <div className="panel"><p className="empty">Yükleniyor…</p></div>
  }

  const byStatus = summary?.byStatus || {}

  return (
    <div>
      <div className="panel">
        <h2>Bakım Planlama</h2>
        <div className="kpis">
          <StatTile label="Toplam iş emri" value={summary?.total ?? 0}
            hint="tüm zamanlar" />
          <StatTile label="Açık" value={summary?.open ?? 0}
            hint="planlandı + devam ediyor"
            tone={summary?.open ? 'alert' : ''} />
          <StatTile label="Devam eden" value={byStatus.InProgress ?? 0}
            hint="sahada" />
          <StatTile label="Tamamlanan" value={byStatus.Done ?? 0}
            hint="kapandı" />
        </div>
        {notice && <p className="note"><b>{notice}</b></p>}
        {error && <p className="note over-limit">Hata: {String(error)}</p>}
      </div>

      <div style={{ marginTop: 16 }}>
        <SuggestionPanel suggestions={suggestions} onApply={handleApply}
          applying={applying} />
      </div>

      <div style={{ marginTop: 16 }}>
        <WorkOrderTable orders={orders} onAssign={handleAssign}
          onStatus={handleStatus} busyId={busyId} />
      </div>

      <div style={{ marginTop: 16 }}>
        <TechnicianTable technicians={technicians} />
      </div>
    </div>
  )
}
