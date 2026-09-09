import { useEffect, useState } from 'react'
import {
  CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
  Legend,
} from 'recharts'
import api from '../api'
import { axis, grid, tooltip, muted, SERIES } from '../theme'

const CLASSES = ['T1', 'T2', 'T3', 'D1', 'D2', 'PD']
// Kategorik seriler sabit sırada atanır: bir gaz her zaman aynı rengi alır.
const PLOT_GASES = [
  { key: 'H2', color: SERIES[0] },
  { key: 'CH4', color: SERIES[1] },
  { key: 'C2H4', color: SERIES[2] },
  { key: 'C2H2', color: SERIES[3] },
]

const STATUS_CLASS = { stable: 'low', watch: 'medium', critical_soon: 'critical' }

export default function TrendPanel() {
  const [cls, setCls] = useState('T2')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)

  const load = (c) => {
    setLoading(true)
    api.trendDemo(c, 24, 6)
      .then(setData)
      .finally(() => setLoading(false))
  }
  useEffect(() => { load(cls) }, []) // eslint-disable-line

  const onChange = (e) => { setCls(e.target.value); load(e.target.value) }

  const series = (data?.series || []).map((r) => ({
    month: r.month, H2: r.H2, CH4: r.CH4, C2H4: r.C2H4, C2H2: r.C2H2,
  }))

  return (
    <div>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <h3 style={{ margin: 0 }}>Trafo Yaşlanma Senaryosu (demo)</h3>
        <div className="row">
          <span className="muted" style={{ fontSize: '0.8rem' }}>Hedef arıza:</span>
          <select value={cls} onChange={onChange}>
            {CLASSES.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>
      </div>

      {data && (
        <div className="row" style={{ margin: '12px 0' }}>
          <span className={`badge ${STATUS_CLASS[data.status] || 'medium'}`}>
            {data.message}
          </span>
          {data.months_to_critical != null && (
            <span className="muted" style={{ fontSize: '0.85rem' }}>
              Tahmini kritik süre: <b>~{data.months_to_critical} ay</b>
              {data.driver_gas ? ` (${data.driver_gas})` : ''}
            </span>
          )}
        </div>
      )}

      {loading ? <p className="empty">Yükleniyor…</p> : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={series} margin={{ left: 0, right: 20, top: 8 }}>
            <CartesianGrid stroke={grid.stroke} vertical={false} />
            <XAxis dataKey="month" stroke={axis.stroke} tick={axis.tick}
              label={{ value: 'AY', position: 'insideBottom', offset: -2,
                fill: muted, fontSize: 10, letterSpacing: '0.1em' }} />
            <YAxis stroke={axis.stroke} tick={axis.tick} unit=" ppm" width={68} />
            <Tooltip {...tooltip} />
            <Legend wrapperStyle={{ fontSize: 11, fontFamily: 'JetBrains Mono, monospace' }} />
            {PLOT_GASES.map((g) => (
              <Line key={g.key} type="monotone" dataKey={g.key}
                stroke={g.color} dot={false} strokeWidth={2} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      )}
      <p className="note">
        Doğrusal regresyon her gazın IEEE eşiğine ne zaman ulaşacağını kestirir;
        en erken aşımı yapan gaz "kritik süre"yi belirler.
      </p>
    </div>
  )
}
