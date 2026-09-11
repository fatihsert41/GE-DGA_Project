import { useCallback, useEffect, useState } from 'react'
import api from '../api'

/* Faz 9.5 — Fiziksel saha gözlemi.
 *
 * Bu ekranın diğerlerinden farkı: HİÇBİR CİHAZ GEREKTİRMİYOR. Teknisyen
 * zaten sahada, gözü zaten orada. Endüstriyel sağlık endeksi
 * modellerinin gerçek bileşenlerinden biri ve bizde eksikti.
 *
 * Gözün gördüğünü cihaz göremez:
 *   yağ kaçağı        → DGA göremez (üstelik yağ azalınca gaz derişimi
 *                       ARTMIŞ görünür)
 *   tıkalı radyatör   → DGA ancak termal arıza gazı çıkınca görür
 *   doymuş silikajel  → yağ testinde aylar sonra
 *   arızalı koruma    → hiçbir kimyasal ölçüme yansımaz
 */

const RATING_CLASS = {
  'iyi': 'low',
  'dikkat': 'medium',
  'kötü': 'critical',
  'bakılmadı': '',
}

const OVERALL_CLASS = { 'iyi': 'low', 'kabul': 'medium', 'kötü': 'critical' }

// Kötüleşme karşılaştırması için sıra. "bakılmadı" (-1) kıyaslamaya
// girmez: bakılmamış bir madde iyileşmiş de kötüleşmiş de sayılamaz.
const RANK = { 'iyi': 0, 'dikkat': 1, 'kötü': 2, 'bakılmadı': -1 }

const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('tr-TR',
    { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

function Form({ transformerId, schema, onSaved, onCancel }) {
  const [values, setValues] = useState({})
  const [notes, setNotes] = useState('')
  const [when, setWhen] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const set = (code, rating) => setValues((v) => ({ ...v, [code]: rating }))

  const submit = (e) => {
    e.preventDefault()
    const checked = Object.entries(values)
      .filter(([, v]) => v && v !== 'bakılmadı')
    if (!checked.length) {
      setError('En az bir maddeyi işaretleyin.')
      return
    }
    setBusy(true); setError(null)
    api.createInspection(transformerId, {
      observations: values,
      notes: notes.trim() || null,
      inspected_at: when || null,
    })
      .then(onSaved)
      .catch((err) => setError(err?.response?.data?.detail || err.message))
      .finally(() => setBusy(false))
  }

  if (!schema) {
    return <div className="panel"><p className="empty">Yükleniyor…</p></div>
  }

  return (
    <form className="panel np-form" onSubmit={submit}>
      <h2>Yeni Saha Gözlemi</h2>
      <p className="note" style={{ marginTop: 0 }}>
        Bakmadığınız maddeyi <b>boş bırakın</b>. Boş bırakmak "sorun yok"
        demek değildir; bakmadığınıza "iyi" demek veriyi bozar ve sonraki
        turda neyin gerçekten kontrol edildiği bilinemez.
      </p>

      {error && <div className="np-problems"><b>{String(error)}</b></div>}

      {schema.groups.map((g) => (
        <div key={g.name} className="insp-group">
          <h3>{g.name}</h3>
          {g.items.map((item) => (
            <div key={item.code} className="insp-row">
              <div className="insp-item">
                <b>{item.label}</b>
                {item.critical && (
                  <span className="crit-chip" title="Tek başına iş emri açar">
                    kritik
                  </span>
                )}
                <div className="muted insp-hint">{item.what_to_look}</div>
              </div>
              <div className="insp-choices">
                {schema.ratings.map((r) => (
                  <button key={r.code} type="button"
                    className={`insp-choice${values[item.code] === r.code ? ' on' : ''} ${RATING_CLASS[r.code]}`}
                    onClick={() => set(item.code, r.code)}>
                    {r.label}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      ))}

      <div className="np-grid" style={{ marginTop: 16 }}>
        <div className="field np-field">
          <label>Gözlem tarihi</label>
          <input type="date" value={when}
            onChange={(e) => setWhen(e.target.value)} />
        </div>
        <div className="field np-field">
          <label>Not</label>
          <input value={notes} onChange={(e) => setNotes(e.target.value)}
            placeholder="ör. radyatör 3 ve 4 kirli, fan 2 çalışmıyor" />
        </div>
      </div>

      <div className="np-actions">
        <button type="submit" className="btn-add" disabled={busy}>
          {busy ? 'Kaydediliyor…' : 'Gözlemi kaydet'}
        </button>
        <button type="button" className="chip" onClick={onCancel}>Vazgeç</button>
      </div>
    </form>
  )
}

export default function InspectionPanel({ id }) {
  const [data, setData] = useState(null)
  const [schema, setSchema] = useState(null)
  const [error, setError] = useState(null)
  const [adding, setAdding] = useState(false)

  const load = useCallback(() => {
    api.inspections(id)
      .then(setData)
      .catch((e) => setError(e?.response?.data?.detail || e.message))
  }, [id])

  useEffect(() => { setData(null); load() }, [id, load])
  useEffect(() => {
    api.physicalSchema().then(setSchema).catch(() => setSchema(null))
  }, [])

  if (error) return <div className="panel"><p className="empty">Hata: {error}</p></div>

  if (adding) {
    return <Form transformerId={id} schema={schema}
      onSaved={() => { setAdding(false); load() }}
      onCancel={() => setAdding(false)} />
  }

  if (!data) return <div className="panel"><p className="empty">Yükleniyor…</p></div>

  const addButton = (
    <button type="button" className="btn-add" onClick={() => setAdding(true)}>
      + Yeni saha gözlemi
    </button>
  )

  if (!data.available) {
    return (
      <div className="panel">
        <div className="np-head"><h2>Saha Gözlemi</h2>{addButton}</div>
        <p className="empty">{data.message}</p>
        <p className="note">
          Bu boyut hiçbir cihaz gerektirmez — teknisyen zaten sahada.
          Buna rağmen boş kalması, en ucuz bilgi kaynağının
          kullanılmadığı anlamına gelir.
        </p>
      </div>
    )
  }

  const latest = data.latest
  const previous = data.inspections.length > 1
    ? data.inspections[data.inspections.length - 2] : null

  // Önceki tura göre kötüleşen maddeler: bir bulgunun ne zaman ortaya
  // çıktığı, bulgunun kendisi kadar bilgi taşır. "Korozyon üç turdur
  // var" ile "bu tur çıktı" farklı şeylerdir.
  const worsened = previous
    ? latest.items.filter((it) => {
      const before = previous.items.find((p) => p.code === it.code)
      return before && RANK[before.rating] >= 0
             && RANK[it.rating] > RANK[before.rating]
    })
    : []

  return (
    <div>
      <div className="panel">
        <div className="np-head">
          <h2>Saha Gözlemi{' '}
            <span className={`badge sm ${OVERALL_CLASS[latest.overall] || ''}`}>
              {latest.overall}
            </span>
          </h2>
          {addButton}
        </div>

        <div className="tmeta">
          <span className="k">Son gözlem</span>
          <span>{fmtDate(latest.inspected_at)}
            {latest.recorded_by_name && (
              <span className="muted"> · {latest.recorded_by_name}</span>)}
          </span>
          <span className="k">Kapsama</span>
          <span>{latest.checked_count}/{latest.total_count} madde
            <span className="muted"> (%{latest.coverage_pct})</span></span>
          <span className="k">Geçmiş</span>
          <span>{data.n_inspections} tur</span>
        </div>

        {latest.critical_findings.length > 0 && (
          <div className="np-problems">
            <b>Kritik bulgular — iş emri açar</b>
            <ul>{latest.critical_findings.map((f) => <li key={f}>{f}</li>)}</ul>
          </div>
        )}

        {worsened.length > 0 && (
          <div className="el-note warn">
            <b>Önceki tura göre kötüleşen:</b>{' '}
            {worsened.map((w) => w.label).join(', ')}. Bir bulgunun ne
            zaman ortaya çıktığı, bulgunun kendisi kadar bilgi taşır.
          </div>
        )}

        {latest.notes && <p className="note"><b>Not:</b> {latest.notes}</p>}
      </div>

      <div className="panel">
        <h2>Kontrol Listesi</h2>
        <div className="table-scroll">
          <table className="compare">
            <thead>
              <tr><th>Madde</th><th>Grup</th><th>Sonuç</th>
                <th>Neden önemli</th></tr>
            </thead>
            <tbody>
              {latest.items.map((it) => (
                <tr key={it.code}
                  className={it.rating === 'bakılmadı' ? 'hi-missing' : ''}>
                  <td>
                    <b>{it.label}</b>
                    {it.critical && <span className="crit-chip">kritik</span>}
                  </td>
                  <td className="muted">{it.group}</td>
                  <td>
                    <span className={`badge sm ${RATING_CLASS[it.rating]}`}>
                      {it.rating_label}
                    </span>
                  </td>
                  <td className="muted insp-why">{it.meaning}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note">
          <b>Kritik</b> maddelerden biri "müdahale gerekli" ise genel hüküm
          tek başına kötüye döner ve iş emri açılır. Kritik olmayan
          bulgular (boya, gürültü) üç tanesi birikince anlam kazanır —
          boyanın dökülmesi ile koruma rölesinin çalışmaması aynı şey
          değildir.
        </p>
      </div>
    </div>
  )
}
