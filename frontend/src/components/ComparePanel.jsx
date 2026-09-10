import { useEffect, useState } from 'react'
import {
  Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import api from '../api'
import { axis, tooltip, SERIES } from '../theme'

/* Dürüstlük paneli (Faz 6.5).
 *
 * Bir modelin kendi ürettiği veride aldığı skoru "doğruluk" diye sunmak
 * en yaygın yanıltma biçimlerinden biri. Bu panel iki sayıyı yan yana
 * koyar: sentetik test verisi ve bağımsız gerçek trafo ölçümleri. */
function RealityCheck() {
  const [data, setData] = useState(null)

  useEffect(() => { api.realityCheck().then(setData).catch(() => setData(null)) }, [])
  if (!data) return null

  const syn = data.synthetic
  const real = data.real

  return (
    <div className="reality">
      <h3>Gerçeklik Kontrolü</h3>

      <div className="reality-pair">
        <div className="reality-card">
          <div className="reality-tag">Sentetik test verisi</div>
          <div className="reality-num">
            {syn ? `%${Math.round(syn.accuracy * 100)}` : '—'}
          </div>
          <div className="reality-sub">
            {syn ? `${syn.model} · ${syn.n_test} numune` : 'model eğitilmedi'}
          </div>
        </div>

        <div className="reality-card">
          <div className="reality-tag">Bağımsız gerçek ölçümler</div>
          <div className="reality-num">
            {real ? `%${Math.round(real.seven_class.accuracy * 100)}` : '—'}
          </div>
          <div className="reality-sub">
            {real ? `${real.n_test} numune · 5 gaz (CO/CO₂ yok)`
              : 'değerlendirme yapılmadı'}
          </div>
        </div>
      </div>

      {real && (
        <>
          <p className="note">
            Yedi sınıflı tam isabet iki hatayı aynı sayar: "T1 yerine T2"
            (aynı bakım kararı) ile "ark yerine normal" (felaket). Emniyet
            açısından anlamlı ölçütler:
          </p>
          <div className="kv">
            <span className="k">Arıza yakalama</span>
            <span><b>%{(real.fault_recall * 100).toFixed(1)}</b></span>
            <span className="k">Yanlış alarm</span>
            <span>%{(real.false_alarm_rate * 100).toFixed(1)}</span>
            <span className="k">Arıza ailesi doğruluğu</span>
            <span><b>%{(real.family_accuracy * 100).toFixed(1)}</b></span>
            <span className="k">Ciddi arıza (ark / {'>'}700 °C)</span>
            <span>{real.severe.n} vakanın {real.severe.declared_normal}'ine
              "Normal" dendi</span>
          </div>
          <p className="note">
            Kaynak: {real.n_test} bağımsız gerçek ölçüm · {real.generated_at}
          </p>
        </>
      )}
    </div>
  )
}

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
          <XAxis dataKey="name" stroke={axis.stroke} tick={axis.tick}
            angle={-20} textAnchor="end" height={50} />
          <YAxis stroke={axis.stroke} tick={axis.tick} domain={[0, 100]}
            unit="%" />
          <Tooltip {...tooltip}
            cursor={{ fill: 'rgba(28,26,23,0.05)' }}
            formatter={(v) => [`%${v}`, 'Doğruluk']} />
          <Bar dataKey="acc" radius={[2, 2, 0, 0]} maxBarSize={46}>
            {data.map((d, i) => (
              <Cell key={i} fill={d.type === 'ML' ? SERIES[0] : SERIES[3]} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <p className="note">
        Mavi: ML modelleri · Turkuaz: klasik konsensüs. En iyi model:{' '}
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
      <RealityCheck />
    </div>
  )
}
