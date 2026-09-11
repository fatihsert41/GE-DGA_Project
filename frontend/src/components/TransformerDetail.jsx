import { useEffect, useState } from 'react'
import {
  CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import api from '../api'
import { axis, grid, tooltip, muted, SERIES } from '../theme'
import { RISK_TR } from '../constants'
import NameplatePanel from './NameplatePanel'
import OilQualityPanel from './OilQualityPanel'
import HealthPanel from './HealthPanel'
import ElectricalPanel from './ElectricalPanel'
import LifecyclePanel from './LifecyclePanel'

/* Faz 5.4 — tek trafonun detayı.
 *
 * Tamamı TEK istekten beslenir: GET /trend/{id} hem ölçüm geçmişini hem de
 * gaz başına doğrusal trendi ve öngörü noktalarını döndürür.
 */

// Grafikte gösterilen gazlar. Yedisini birden çizmek okunmaz olurdu;
// tanı açısından en ayırt edici dördü seçildi, kalanlar tabloda.
const PLOT_GASES = [
  { key: 'H2', color: SERIES[0] },
  { key: 'CH4', color: SERIES[1] },
  { key: 'C2H4', color: SERIES[2] },
  { key: 'C2H2', color: SERIES[3] },
]

const STATUS_TR = {
  stable: { label: 'Kararlı', cls: 'low' },
  watch: { label: 'İzlemede', cls: 'medium' },
  critical_soon: { label: 'Yakında Kritik', cls: 'critical' },
}

const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('tr-TR',
    { day: 'numeric', month: 'short', year: '2-digit' }) : '—'

/** Ölçülen geçmiş + öngörü, tek bir seriye birleştirilir.
 *  Öngörü noktaları ayrı anahtarlarda (ör. H2_f) tutulur; böylece grafikte
 *  kesikli çizgiyle ayrı çizilebilir — kesikli çizgi "tahmin" demektir. */
function buildSeries(measurements, perGas, horizon) {
  const rows = measurements.map((m, i) => {
    const row = { month: i, tip: 'ölçüm' }
    PLOT_GASES.forEach((g) => { row[g.key] = m.gases[g.key] })
    return row
  })

  const lastIdx = measurements.length - 1
  // Kesikli çizginin ölçülen eğriye yapışması için köprü noktası.
  if (rows.length) {
    PLOT_GASES.forEach((g) => { rows[lastIdx][`${g.key}_f`] = rows[lastIdx][g.key] })
  }

  for (let k = 0; k < horizon; k += 1) {
    const row = { month: lastIdx + k + 1, tip: 'öngörü' }
    PLOT_GASES.forEach((g) => {
      const f = perGas?.[g.key]?.forecast?.[k]
      if (f) row[`${g.key}_f`] = Math.max(0, f.value)
    })
    rows.push(row)
  }
  return rows
}

function TrendVerdict({ trend }) {
  const st = STATUS_TR[trend.status] || STATUS_TR.stable
  return (
    <div className={`verdict-band ${st.cls}`}>
      <span className={`badge ${st.cls}`}>{st.label}</span>
      <span className="verdict-msg">{trend.message}</span>
      {trend.months_to_critical != null && (
        <span className="verdict-eta">
          <b>{trend.months_to_critical}</b> ay
          <span className="muted"> · sürükleyen gaz {trend.driver_gas}</span>
        </span>
      )}
    </div>
  )
}

/** Gaz başına trend tablosu — yedi gazın tamamı, en acil olan üstte. */
function GasTrendTable({ perGas }) {
  const rows = Object.entries(perGas)
    .map(([gas, d]) => ({ gas, ...d }))
    .sort((a, b) => {
      const A = a.months_to_limit, B = b.months_to_limit
      if (A == null && B == null) return 0
      if (A == null) return 1          // eşiğe gitmeyenler en sona
      if (B == null) return -1
      return A - B
    })

  return (
    <table className="compare">
      <thead>
        <tr>
          <th>Gaz</th><th>Güncel</th><th>IEEE eşiği</th>
          <th>Eğim</th><th>R²</th><th>Kalan süre</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const over = r.current >= r.limit
          return (
            <tr key={r.gas}>
              <td><b>{r.gas}</b></td>
              <td className={over ? 'over-limit' : ''}>{r.current}</td>
              <td className="muted">{r.limit}</td>
              <td>{r.slope > 0 ? '+' : ''}{r.slope} <span className="unit">ppm/ay</span></td>
              <td className="muted">{r.r2}</td>
              <td>
                {r.months_to_limit == null
                  ? <span className="muted">artış yok</span>
                  : r.months_to_limit === 0
                    ? <b className="over-limit">aşıldı</b>
                    : <>{r.months_to_limit} ay</>}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

function HistoryTable({ measurements }) {
  const rows = [...measurements].reverse()   // en yeni ölçüm en üstte
  return (
    <table className="compare">
      <thead>
        <tr><th>Tarih</th><th>Tanı</th><th>Güven</th><th>Risk</th></tr>
      </thead>
      <tbody>
        {rows.map((m) => (
          <tr key={m.id}>
            <td>{fmtDate(m.sampled_at)}</td>
            <td><b>{m.prediction}</b></td>
            <td>%{Math.round((m.confidence || 0) * 100)}</td>
            <td>
              <span className={`badge sm ${m.risk_level}`}>
                {RISK_TR[m.risk_level] || m.risk_level}
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

export default function TransformerDetail({ id, meta, onBack }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  // Ölçüm/trend görünümü ile künye görünümü arasında geçiş.
  const [tab, setTab] = useState('measurements')

  useEffect(() => {
    setData(null); setError(null)
    api.transformerTrend(id, 6)
      .then(setData)
      .catch((e) => setError(e?.response?.data?.detail || e.message))
  }, [id])

  const header = (
    <div className="detail-head">
      <button type="button" className="link-back" onClick={onBack}>
        ← Filo
      </button>
      <div>
        <h2 className="detail-title">{id}
          <span className="detail-name">{meta?.name}</span>
        </h2>
        <div className="muted" style={{ fontSize: '0.82rem' }}>
          {meta?.location} · {meta?.measurement_count} ölçüm
        </div>
      </div>
      {meta?.risk_level && (
        <span className={`badge ${meta.risk_level}`}>{meta.risk_level_tr}</span>
      )}
    </div>
  )

  const tabs = (
    <div className="tabs detail-tabs">
      <button type="button" className={tab === 'measurements' ? 'active' : ''}
        onClick={() => setTab('measurements')}>Ölçümler ve Trend</button>
      <button type="button" className={tab === 'oil' ? 'active' : ''}
        onClick={() => setTab('oil')}>Yağ Kalitesi</button>
      <button type="button" className={tab === 'electrical' ? 'active' : ''}
        onClick={() => setTab('electrical')}>Elektriksel</button>
      <button type="button" className={tab === 'health' ? 'active' : ''}
        onClick={() => setTab('health')}>Sağlık Endeksi</button>
      <button type="button" className={tab === 'nameplate' ? 'active' : ''}
        onClick={() => setTab('nameplate')}>Künye</button>
      <button type="button" className={tab === 'lifecycle' ? 'active' : ''}
        onClick={() => setTab('lifecycle')}>Yaşam Döngüsü</button>
    </div>
  )

  // Künye sekmesi ölçüm verisinden bağımsızdır: hiç ölçümü olmayan yeni
  // bir trafonun künyesi de görüntülenebilmeli.
  if (tab === 'nameplate') {
    return (
      <div>
        <div className="panel">{header}{tabs}</div>
        <div style={{ marginTop: 16 }}><NameplatePanel id={id} /></div>
      </div>
    )
  }

  // Yaşam döngüsü ölçümden tamamen bağımsız: henüz hiç ölçümü olmayan
  // bir fabrika ünitesinin de durumu vardır.
  if (tab === 'lifecycle') {
    return (
      <div>
        <div className="panel">{header}{tabs}</div>
        <div style={{ marginTop: 16 }}><LifecyclePanel id={id} /></div>
      </div>
    )
  }

  // Elektriksel testler trafo ENERJİSİZKEN yapılır; DGA'dan tamamen
  // bağımsızdır, o yüzden ölçüm verisi beklemeden açılabilir.
  if (tab === 'electrical') {
    return (
      <div>
        <div className="panel">{header}{tabs}</div>
        <div style={{ marginTop: 16 }}><ElectricalPanel id={id} /></div>
      </div>
    )
  }

  // Sağlık endeksi üç boyutu birleştirir; eksik boyutları da kendisi
  // bildirdiği için ölçüm olmadan da açılabilir.
  if (tab === 'health') {
    return (
      <div>
        <div className="panel">{header}{tabs}</div>
        <div style={{ marginTop: 16 }}><HealthPanel id={id} /></div>
      </div>
    )
  }

  // Yağ kalitesi de DGA ölçümünden bağımsızdır: DGA'sı olmayan bir trafonun
  // yağ testi olabilir (ya da tam tersi).
  if (tab === 'oil') {
    return (
      <div>
        <div className="panel">{header}{tabs}</div>
        <div style={{ marginTop: 16 }}><OilQualityPanel id={id} /></div>
      </div>
    )
  }

  if (error) {
    return <div className="panel">{header}{tabs}<p className="empty">Hata: {error}</p></div>
  }
  if (!data) {
    return <div className="panel">{header}{tabs}<p className="empty">Yükleniyor…</p></div>
  }

  const measurements = data.measurements || []
  const perGas = data.per_gas || {}
  const series = buildSeries(measurements, perGas, 6)
  const lastIdx = measurements.length - 1

  return (
    <div>
      <div className="panel">
        {header}
        {tabs}
        <TrendVerdict trend={data} />

        <h3>Gaz Geçmişi ve 6 Aylık Öngörü</h3>
        <ResponsiveContainer width="100%" height={320}>
          <LineChart data={series} margin={{ left: 0, right: 16, top: 8, bottom: 18 }}>
            <CartesianGrid stroke={grid.stroke} vertical={false} />
            <XAxis dataKey="month" stroke={axis.stroke} tick={axis.tick}
              label={{ value: 'ölçüm sırası (ay)', position: 'insideBottom',
                offset: -10, fill: muted, fontSize: 11 }} />
            <YAxis stroke={axis.stroke} tick={axis.tick} unit=" ppm" width={70} />
            <Tooltip {...tooltip} />
            <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
            {/* Ölçülen ile öngörülen bölgeyi ayıran dikey işaret. */}
            <ReferenceLine x={lastIdx} stroke={muted}
              label={{ value: 'bugün', position: 'top', fill: muted, fontSize: 11 }} />
            {PLOT_GASES.map((g) => (
              <Line key={g.key} type="monotone" dataKey={g.key} name={g.key}
                stroke={g.color} strokeWidth={2} dot={false} />
            ))}
            {/* Öngörü: aynı renk, kesikli — kesiklilik "bu ölçüm değil" demek. */}
            {PLOT_GASES.map((g) => (
              <Line key={`${g.key}_f`} dataKey={`${g.key}_f`} legendType="none"
                stroke={g.color} strokeWidth={2} strokeDasharray="5 4"
                dot={false} connectNulls />
            ))}
          </LineChart>
        </ResponsiveContainer>
        <p className="note">
          Düz çizgi: ölçülen değerler · Kesikli: doğrusal regresyon öngörüsü.
          Öngörü mevcut eğilimin sürmesi varsayımına dayanır.
        </p>
      </div>

      <div className="detail-cols">
        <div className="panel">
          <h2>Gaz Bazında Trend</h2>
          <GasTrendTable perGas={perGas} />
          <p className="note">
            R² eğrinin doğrusala ne kadar uyduğunu gösterir (1 = kusursuz uyum);
            düşük R² varsa kalan süre tahminine temkinli yaklaş.
          </p>
        </div>

        <div className="panel">
          <h2>Ölçüm Geçmişi</h2>
          <HistoryTable measurements={measurements} />
        </div>
      </div>
    </div>
  )
}
