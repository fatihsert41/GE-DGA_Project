import { useEffect, useState } from 'react'
import api from '../api'
import { RISK_ORDER, RISK_TR } from '../constants'

const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('tr-TR',
    { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

function StatTile({ label, value, hint, tone }) {
  return (
    <div className={`kpi${tone ? ` ${tone}` : ''}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {hint && <div className="kpi-hint">{hint}</div>}
    </div>
  )
}

/** Part-to-whole composition of the fleet by risk level.
 *  Colour never carries the meaning alone: every segment is repeated as a
 *  labelled legend entry below the bar. */
function RiskComposition({ distribution, total }) {
  if (!total) return null
  const present = RISK_ORDER.filter((lvl) => distribution[lvl] > 0)

  return (
    <div className="risk-composition">
      <div className="riskbar" role="img"
        aria-label={present.map((l) => `${RISK_TR[l]}: ${distribution[l]}`).join(', ')}>
        {present.map((lvl) => (
          <span key={lvl} className={lvl}
            style={{ width: `${(distribution[lvl] / total) * 100}%` }}
            title={`${RISK_TR[lvl]}: ${distribution[lvl]} trafo`} />
        ))}
      </div>
      <div className="risk-legend">
        {RISK_ORDER.map((lvl) => (
          <span key={lvl} className={distribution[lvl] ? '' : 'off'}>
            <i className={`dot ${lvl}`} />
            {RISK_TR[lvl]} <b>{distribution[lvl]}</b>
          </span>
        ))}
      </div>
    </div>
  )
}

function TransformerCard({ t, onSelect }) {
  if (!t.has_data) {
    return (
      <div className="tcard">
        <div className="tcard-head">
          <div><div className="tid">{t.id}</div>
            <div className="tname">{t.name}</div></div>
        </div>
        <p className="empty" style={{ padding: '18px 0' }}>Henüz ölçüm yok</p>
      </div>
    )
  }

  // Gerçek <button>: klavyeyle gezinme ve ekran okuyucu desteği bedava gelir.
  return (
    <button type="button" className={`tcard clickable ${t.risk_level}`}
      onClick={() => onSelect(t)}
      aria-label={`${t.id} ${t.name} detayını aç`}>
      <div className="tcard-head">
        <div>
          <div className="tid">{t.id}</div>
          <div className="tname">{t.name}</div>
        </div>
        <span className={`badge sm ${t.risk_level}`}>{t.risk_level_tr}</span>
      </div>

      <div className="tverdict">{t.prediction}
        <span className="group-tag"> · {t.prediction_group}</span></div>
      <div className="tname">{t.prediction_label}</div>

      <div className="tmeta">
        <span className="k">Güven</span><span>%{Math.round(t.confidence * 100)}</span>
        <span className="k">TDCG</span><span>{t.tdcg} ppm</span>
        <span className="k">Konum</span><span>{t.location || '—'}</span>
        <span className="k">Son ölçüm</span><span>{fmtDate(t.last_sampled_at)}</span>
        <span className="k">Geçmiş</span><span>{t.measurement_count} ölçüm</span>
      </div>
      <span className="tcard-go">Detay →</span>
    </button>
  )
}

export default function FleetOverview({ onSelect }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.fleetOverview()
      .then(setData)
      .catch((e) => setError(e?.response?.data?.detail || e.message))
  }, [])

  if (error) return <div className="panel"><b>Filo verisi alınamadı:</b> {error}</div>
  if (!data) return <div className="panel"><p className="empty">Filo yükleniyor…</p></div>

  const { summary, transformers } = data
  const critical = summary.risk_distribution.critical || 0

  return (
    <div>
      <div className="panel">
        <h2>Filo Genel Durumu</h2>

        <div className="kpis">
          <StatTile label="Trafo" value={summary.total}
            hint={`${summary.with_data} tanesi ölçümlü`} />
          <StatTile label="Toplam ölçüm" value={summary.total_measurements}
            hint="tüm geçmiş" />
          <StatTile label="Dikkat gerektiren" value={summary.needs_attention}
            hint="yüksek + kritik" tone={summary.needs_attention ? 'alert' : ''} />
          <StatTile label="Kritik" value={critical}
            hint="acil değerlendirme" tone={critical ? 'danger' : ''} />
        </div>

        <h3>Risk Dağılımı</h3>
        <RiskComposition distribution={summary.risk_distribution}
          total={summary.with_data} />

        {summary.attention_ids.length > 0 && (
          <p className="note">
            Öncelikli: <b>{summary.attention_ids.join(', ')}</b>
          </p>
        )}
      </div>

      <div className="fleet-grid">
        {transformers.map((t) => (
          <TransformerCard key={t.id} t={t} onSelect={onSelect} />
        ))}
      </div>
    </div>
  )
}
