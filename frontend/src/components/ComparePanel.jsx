import {
  Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

function MethodTable({ compare }) {
  if (!compare) return <p className="empty">Karşılaştırma için bir analiz çalıştırın.</p>
  const c = compare.classical
  const rows = [
    ['Duval Üçgeni', c.duval.zone, 'classical'],
    ['Rogers Oranı', c.rogers.fault, 'classical'],
    ['IEC 60599', c.iec.fault, 'classical'],
    ['Key Gas', c.key_gas.fault, 'classical'],
    ['ML Modeli', compare.ml ? compare.ml.prediction : '—', 'ml'],
  ]
  return (
    <table className="compare">
      <thead><tr><th>Yöntem</th><th>Tahmin</th><th>Tür</th></tr></thead>
      <tbody>
        {rows.map(([m, f, t]) => (
          <tr key={m}>
            <td>{m}</td><td><b>{f}</b></td>
            <td className={t === 'ml' ? 'tag-ml' : 'tag-classical'}>
              {t === 'ml' ? 'ML' : 'Klasik'}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function LeaderboardChart({ leaderboard }) {
  if (!leaderboard || !leaderboard.available) {
    return <p className="note">Model eğitilmemiş: <code>python -m app.ml.train</code></p>
  }
  const data = leaderboard.leaderboard.map((r) => ({
    name: r.model, acc: Math.round((r.accuracy || 0) * 1000) / 10, type: r.type,
  }))
  return (
    <div>
      <h3>Doğruluk Karşılaştırması (aynı test seti)</h3>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ left: 0, right: 20, top: 8, bottom: 30 }}>
          <XAxis dataKey="name" stroke="#8ea0b8" fontSize={11}
            angle={-20} textAnchor="end" height={50} />
          <YAxis stroke="#8ea0b8" fontSize={12} domain={[0, 100]}
            unit="%" />
          <Tooltip
            contentStyle={{ background: '#1e2a3c', border: '1px solid #2a3a52',
              borderRadius: 8, color: '#e6edf6' }}
            formatter={(v) => [`%${v}`, 'Doğruluk']} />
          <Bar dataKey="acc" radius={[4, 4, 0, 0]}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.type === 'ML' ? '#2f81f7' : '#14b8a6'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="note">
        Mavi: ML modelleri · Yeşil: klasik konsensüs. En iyi model:{' '}
        <b>{leaderboard.best_model}</b>.
      </p>
    </div>
  )
}

export default function ComparePanel({ compare, leaderboard }) {
  return (
    <div>
      <h3>Bu Ölçüm İçin Yöntemler</h3>
      <MethodTable compare={compare} />
      <LeaderboardChart leaderboard={leaderboard} />
    </div>
  )
}
