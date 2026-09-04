import {
  Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

// Horizontal bar of SHAP contributions; green pushes toward the prediction,
// red pushes away. Shows the top drivers of the model's decision.
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
          <XAxis type="number" stroke="#8ea0b8" fontSize={12} />
          <YAxis type="category" dataKey="name" stroke="#8ea0b8"
            fontSize={12} width={80} />
          <Tooltip
            contentStyle={{ background: '#1e2a3c', border: '1px solid #2a3a52',
              borderRadius: 8, color: '#e6edf6' }}
            formatter={(v, _n, p) => [`${v} (değer: ${p.payload.value})`, 'SHAP']} />
          <Bar dataKey="shap" radius={[0, 4, 4, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.shap >= 0 ? '#22c55e' : '#ef4444'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="note">
        Yeşil: tahmini <i>destekleyen</i> katkı · Kırmızı: <i>zayıflatan</i> katkı.
      </p>
    </div>
  )
}
