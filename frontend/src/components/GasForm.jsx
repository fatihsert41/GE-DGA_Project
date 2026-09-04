import { useState } from 'react'
import { GASES, GAS_LABELS, PRESETS } from '../constants'

const empty = () => GASES.reduce((o, g) => ({ ...o, [g]: '' }), {})

export default function GasForm({ onSubmit, loading }) {
  const [values, setValues] = useState(PRESETS['Ark (D2)'])
  const [tid, setTid] = useState('TR-01')

  const setGas = (g, v) => setValues((s) => ({ ...s, [g]: v }))
  const applyPreset = (p) => setValues(PRESETS[p])

  const submit = (e) => {
    e.preventDefault()
    const gases = GASES.reduce(
      (o, g) => ({ ...o, [g]: parseFloat(values[g]) || 0 }), {})
    onSubmit({ gases, transformer_id: tid || null,
      transformer_name: tid || null, persist: !!tid })
  }

  return (
    <form className="panel" onSubmit={submit}>
      <h2>Yağ Analiz Sonuçları (ppm)</h2>

      <div className="presets">
        {Object.keys(PRESETS).map((p) => (
          <button type="button" key={p} onClick={() => applyPreset(p)}>{p}</button>
        ))}
        <button type="button" onClick={() => setValues(empty())}>Temizle</button>
      </div>

      <div className="gas-grid">
        {GASES.map((g) => (
          <div className="field" key={g}>
            <label>{GAS_LABELS[g]}</label>
            <input type="number" step="any" min="0" value={values[g]}
              onChange={(e) => setGas(g, e.target.value)} placeholder="0" />
          </div>
        ))}
      </div>

      <h3>Trafo</h3>
      <div className="field">
        <label>Trafo ID (kayıt ve trend için)</label>
        <input value={tid} onChange={(e) => setTid(e.target.value)}
          placeholder="Örn: TR-01" />
      </div>

      <button className="primary" type="submit" disabled={loading}>
        {loading ? 'Analiz ediliyor…' : 'Analiz Et'}
      </button>
      <p className="note">
        Değerler ppm cinsindendir. Hazır örneklerle hızlıca deneyebilirsiniz.
      </p>
    </form>
  )
}
