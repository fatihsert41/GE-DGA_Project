import { useCallback, useEffect, useState } from 'react'
import api from '../api'

/* Faz 9.35 — Varlık yaşam döngüsü.
 *
 * Sisteme şimdiye kadar "işletmedeki trafo" gözüyle bakılıyordu. Ama
 * GE Vernova bu üniteleri üretip satıyor: bir trafonun hayatı fabrikada
 * başlıyor ve sahaya varması aylar sürüyor.
 *
 * Bunu modellememenin bedeli somuttu: fabrikada sevkiyat bekleyen bir
 * ünite "numunesi gecikmiş" sayılıyor ve numune alma iş emri
 * üretiliyordu — henüz enerjilenmemiş bir trafo için.
 */

const PHASE_CLASS = {
  factory: 'medium',
  transit: 'medium',
  field: 'low',
  retired: '',
}

const fmtWhen = (iso) =>
  iso ? new Date(iso).toLocaleDateString('tr-TR',
    { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

/** Yaşam döngüsü şeridi: varlık hangi aşamada? */
function Track({ states, current }) {
  const currentOrder = states.findIndex((s) => s.code === current.code)
  // Hurda ve hizmet dışı, doğrusal akışın parçası değil; şeritte
  // göstermek yanıltıcı olurdu.
  const flow = states.filter((s) => s.phase !== 'retired')

  return (
    <ol className="lc-track">
      {flow.map((s, i) => {
        const idx = states.findIndex((x) => x.code === s.code)
        const state = idx < currentOrder ? 'done'
          : idx === currentOrder ? 'now' : 'todo'
        return (
          <li key={s.code} className={`lc-step ${state}`}>
            <span className="lc-dot" aria-hidden="true" />
            <span className="lc-label">{s.label_tr}</span>
          </li>
        )
      })}
    </ol>
  )
}

export default function LifecyclePanel({ id }) {
  const [data, setData] = useState(null)
  const [schema, setSchema] = useState(null)
  const [error, setError] = useState(null)
  const [target, setTarget] = useState('')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    api.lifecycle(id)
      .then((d) => { setData(d); setTarget(''); setNote('') })
      .catch((e) => setError(e?.response?.data?.detail || e.message))
  }, [id])

  useEffect(() => { setData(null); setError(null); load() }, [id, load])
  useEffect(() => {
    api.lifecycleSchema().then(setSchema).catch(() => setSchema(null))
  }, [])

  const submit = (e) => {
    e.preventDefault()
    if (!target) return
    setBusy(true); setError(null)
    api.changeLifecycle(id, target, note.trim() || null)
      .then(load)
      .catch((err) => setError(err?.response?.data?.detail || err.message))
      .finally(() => setBusy(false))
  }

  if (!data) {
    return (
      <div className="panel">
        <p className="empty">{error || 'Yükleniyor…'}</p>
      </div>
    )
  }

  const cur = data.current

  return (
    <div>
      <div className="panel">
        <h2>Yaşam Döngüsü</h2>

        <div className="lc-current">
          <span className={`badge ${PHASE_CLASS[cur.phase] || ''}`}>
            {cur.label_tr}
          </span>
          <span className="muted">{cur.phase_tr}</span>
          <span className="muted lc-since">
            · {fmtWhen(data.changed_at)} tarihinden beri
          </span>
        </div>

        <p className="note">{cur.description}</p>

        {/* Kuralların gerçekten neye baktığını göstermek: durum değil,
            izlenip izlenmediği. */}
        <div className={`lc-monitor ${cur.monitored ? 'on' : 'off'}`}>
          {cur.monitored ? (
            <>
              <b>Periyodik izlemede.</b> Numune alma takvimi işliyor;
              gecikme olursa iş emri üretilir.
            </>
          ) : (
            <>
              <b>Periyodik izleme dışında.</b> {cur.phase_note} Bu yüzden
              numune takvimi işlemez ve bu varlık "numunesi gecikmiş"
              sayılmaz.
            </>
          )}
        </div>

        {schema && <Track states={schema.states} current={cur} />}
      </div>

      <div className="panel">
        <h2>Durum Değiştir</h2>

        {error && <div className="np-problems"><b>{String(error)}</b></div>}

        {cur.next_states.length === 0 ? (
          <p className="empty">
            Bu uç durumdan çıkış yok ({cur.label_tr}).
          </p>
        ) : (
          <form onSubmit={submit}>
            <div className="np-grid">
              <div className="field np-field">
                <label>Yeni durum</label>
                <select value={target} onChange={(e) => setTarget(e.target.value)}>
                  <option value="">— seçin —</option>
                  {cur.next_states.map((s) => (
                    <option key={s.code} value={s.code}>{s.label_tr}</option>
                  ))}
                </select>
              </div>
              <div className="field np-field">
                <label>Açıklama<span className="np-hint"> · isteğe bağlı</span></label>
                <input value={note} onChange={(e) => setNote(e.target.value)}
                  placeholder="ör. vinç planlandı, 3 Ekim" />
              </div>
            </div>
            <div className="np-actions">
              <button type="submit" className="btn-add" disabled={busy || !target}>
                {busy ? 'Kaydediliyor…' : 'Durumu güncelle'}
              </button>
            </div>
          </form>
        )}

        <p className="note">
          Yalnızca <b>izinli geçişler</b> listeleniyor: "Devrede"
          durumundan "Üretimde"ye dönülemez. Geçersiz geçişi engellemek,
          yanlış veriyi sonradan düzeltmekten ucuzdur. Her geçiş kim
          tarafından, ne zaman yapıldığıyla birlikte kaydedilir.
        </p>
      </div>

      {data.events.length > 0 && (
        <div className="panel">
          <h2>Durum Geçmişi</h2>
          <table className="compare">
            <thead>
              <tr><th>Tarih</th><th>Geçiş</th><th>Açıklama</th><th>Kim</th></tr>
            </thead>
            <tbody>
              {[...data.events].reverse().map((e) => (
                <tr key={e.id}>
                  <td>{fmtWhen(e.changed_at)}</td>
                  <td>
                    <span className="muted">{e.from_label || '—'}</span>
                    {' → '}<b>{e.to_label}</b>
                  </td>
                  <td className="muted">{e.note || '—'}</td>
                  <td className="muted">
                    {e.changed_by_name || 'kimliksiz'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="note">
            Geçmiş silinmez: "bu ünite ne zaman devreye alındı, ne zaman
            hizmet dışı kaldı" varlık yönetiminin temel sorularındandır.
          </p>
        </div>
      )}
    </div>
  )
}
