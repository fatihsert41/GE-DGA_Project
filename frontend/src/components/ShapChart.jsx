import {
  Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { axis, tooltip, POSITIVE, NEGATIVE } from '../theme'

// Horizontal bar of SHAP contributions; olive pushes toward the prediction,
// brick pushes away. Shows the top drivers of the model's decision.
export default function ShapChart({ explanation }) {
  if (!explanation) {
    return <p className="empty">Açıklama için önce bir analiz çalıştırın.</p>
  }
  const data = explanation.contributions
    .slice(0, 8)
    .map((c) => ({ name: c.feature, shap: c.shap, value: c.value }))
    .reverse()

  return (
    <div>
      <p className="muted" style={{ fontSize: '0.85rem' }}>
        Tahmin: <b>{explanation.prediction}</b> — bu karara en çok katkı yapan
        büyüklükler ({explanation.model_name} / SHAP):
      </p>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={data} layout="vertical"
          margin={{ left: 20, right: 20, top: 8, bottom: 8 }}>
          <XAxis type="number" stroke={axis.stroke} tick={axis.tick} />
          <YAxis type="category" dataKey="name" stroke={axis.stroke}
            tick={axis.tick} width={80} />
          <Tooltip {...tooltip}
            cursor={{ fill: 'rgba(28,26,23,0.05)' }}
            formatter={(v, _n, p) => [`${v} (değer: ${p.payload.value})`, 'SHAP']} />
          <Bar dataKey="shap" radius={[0, 2, 2, 0]} barSize={14}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.shap >= 0 ? POSITIVE : NEGATIVE} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="note">
        Zeytin yeşili: tahmini <i>destekleyen</i> katkı · Kiremit: <i>zayıflatan</i> katkı.
      </p>
    </div>
  )
}
