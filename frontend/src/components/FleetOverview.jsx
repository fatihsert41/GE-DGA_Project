import { useEffect, useMemo, useState } from 'react'
import api from '../api'
import { ASSET_CLASSES, ASSET_CLASS_TR, fold, RISK_ORDER, RISK_TR }
  from '../constants'

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
          <div className="tid">
            {t.id}
            <span className={`class-tag ${t.asset_class}`}
              title={`${ASSET_CLASS_TR[t.asset_class] || t.asset_class}`
                + (t.mva ? ` · ${t.mva} MVA` : '')}>
              {t.asset_class}
            </span>
          </div>
          <div className="tname">{t.name}</div>
        </div>
        <span className={`badge sm ${t.risk_level}`}>{t.risk_level_tr}</span>
      </div>

      {t.needs_review && (
        <span className="review-chip" title="Model bu tanıdan emin değil">
          Uzman incelemesi
        </span>
      )}

      <div className="tverdict">{t.prediction}
        <span className="group-tag"> · {t.prediction_group}</span></div>
      <div className="tname">{t.prediction_label}</div>

      <div className="tmeta">
        <span className="k">Güven</span><span>%{Math.round(t.confidence * 100)}</span>
        <span className="k">TDCG</span><span>{t.tdcg} ppm</span>
        <span className="k">Konum</span><span>{t.location || '—'}</span>
        <span className="k">Son ölçüm</span><span>{fmtDate(t.last_sampled_at)}</span>
        <span className="k">Geçmiş</span><span>{t.measurement_count} ölçüm</span>
        <span className="k">Öncelik</span>
        <span title={`kondisyon ${t.risk_condition} × ağırlık ${t.asset_weight}`}>
          <b>{t.priority?.toFixed(2)}</b>
        </span>
      </div>

      {t.sampling_overdue && (
        <span className="overdue-chip">
          Numune gecikti · {Math.round(t.days_since_sample / 30)} ay
          {' '}(aralık {t.sampling_months} ay)
        </span>
      )}
      <span className="tcard-go">Detay →</span>
    </button>
  )
}

/** Dikkat gerektiren varlıklar: kartları taramaya gerek kalmadan
 *  "önce şuna bak" listesi. Zaten riske göre sıralı geldiği için
 *  ilk sıradaki en acil olandır. */
function AlarmList({ items, onSelect }) {
  if (!items.length) {
    return (
      <div className="panel alarm-panel">
        <h2>Alarmlar</h2>
        <p className="empty">Yüksek veya kritik seviyede varlık yok.</p>
      </div>
    )
  }
  return (
    <div className="panel alarm-panel">
      <h2>Alarmlar <span className="count-pill">{items.length}</span></h2>
      <ul className="alarm-list">
        {items.map((t) => (
          <li key={t.id}>
            <button type="button" onClick={() => onSelect(t)}>
              <span className={`alarm-mark ${t.risk_level}`} aria-hidden="true" />
              <span className="alarm-id">{t.id}</span>
              <span className="alarm-name">{t.name}</span>
              <span className="alarm-fault">{t.prediction}</span>
              <span className={`badge sm ${t.risk_level}`}>{t.risk_level_tr}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}

/** Filtre satırı: kartların hemen üstünde tek sıra. */
function FilterBar({ query, onQuery, level, onLevel, cls, onClass,
                    counts, classCounts, shown, total }) {
  const chips = [{ key: 'all', label: 'Tümü', n: total }].concat(
    RISK_ORDER.map((lvl) => ({ key: lvl, label: RISK_TR[lvl], n: counts[lvl] || 0 })))

  return (
    <div className="filter-bar">
      <input type="search" className="search" value={query}
        onChange={(e) => onQuery(e.target.value)}
        placeholder="Trafo ara — kod, ad veya konum" />

      <div className="chips">
        {chips.map((c) => (
          <button key={c.key} type="button"
            className={`chip${level === c.key ? ' active' : ''}`}
            disabled={c.n === 0 && c.key !== 'all'}
            onClick={() => onLevel(c.key)}>
            {c.label} <span className="chip-n">{c.n}</span>
          </button>
        ))}
      </div>

      <div className="chips">
        {['all', ...ASSET_CLASSES].map((c) => (
          <button key={c} type="button"
            className={`chip alt${cls === c ? ' active' : ''}`}
            disabled={c !== 'all' && !(classCounts[c] > 0)}
            onClick={() => onClass(c)}>
            {c === 'all' ? 'Tüm sınıflar' : c}
            <span className="chip-n">
              {c === 'all' ? total : (classCounts[c] || 0)}
            </span>
          </button>
        ))}
      </div>

      <span className="shown-count">{shown} / {total}</span>
    </div>
  )
}

export default function FleetOverview({ onSelect }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [query, setQuery] = useState('')
  const [level, setLevel] = useState('all')
  const [cls, setCls] = useState('all')

  // Filo 8 varlık: filtreleme istemcide yapılır, API'ye tekrar gitmeye gerek yok.
  // useMemo, her tuş vuruşunda listeyi baştan süzmemek için sonucu önbelleğe alır.
  const visible = useMemo(() => {
    if (!data) return []
    const q = fold(query.trim())
    return data.transformers.filter((t) => {
      if (level !== 'all' && t.risk_level !== level) return false
      if (cls !== 'all' && t.asset_class !== cls) return false
      if (!q) return true
      return [t.id, t.name, t.location, t.prediction]
        .filter(Boolean)
        .some((f) => fold(f).includes(q))
    })
  }, [data, query, level, cls])

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
          <StatTile label="Uzman incelemesi" value={summary.needs_review ?? 0}
            hint="model kararsız" />
          <StatTile label="Numune gecikti" value={summary.sampling_overdue ?? 0}
            hint="sınıfa göre aralık" tone={summary.sampling_overdue ? 'alert' : ''} />
        </div>

        <h3>Risk Dağılımı</h3>
        <RiskComposition distribution={summary.risk_distribution}
          total={summary.with_data} />

      </div>

      <AlarmList onSelect={onSelect}
        items={transformers.filter(
          (t) => t.risk_level === 'critical' || t.risk_level === 'high')} />

      <FilterBar query={query} onQuery={setQuery}
        level={level} onLevel={setLevel}
        cls={cls} onClass={setCls}
        counts={summary.risk_distribution}
        classCounts={summary.class_distribution || {}}
        shown={visible.length} total={transformers.length} />

      {visible.length === 0 ? (
        <div className="panel">
          <p className="empty">Bu ölçütlere uyan trafo yok.</p>
        </div>
      ) : (
        <div className="fleet-grid">
          {visible.map((t) => (
            <TransformerCard key={t.id} t={t} onSelect={onSelect} />
          ))}
        </div>
      )}
    </div>
  )
}
