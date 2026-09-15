import { useCallback, useEffect, useState } from 'react'
import api from '../api'
import { can } from '../permissions'

/* Faz 12.5 — MH04 Kök Neden Analizi (RCA).
 *
 * Kapanan KRİTİK iş emri (öncelik ≥ 2.5 ya da onarım/değişim) buraya düşer.
 * Mühendis üç soruyu cevaplar:
 *
 *   Bulgu         → ne görüldü, ne ölçüldü
 *   Kök neden     → neden oldu
 *   Alınan önlem  → ne yapıldı (+ isteğe bağlı: tekrarı nasıl önlenecek)
 *
 * Form, YAZMADAN ÖNCE geçmişe bakar: aynı arıza türünde ya da aynı trafoda
 * daha önce yazılmış analizler formun üstünde durur. "Bu arıza daha önce
 * oldu mu, o zaman ne yapmıştık?" sorusu, yeni analizin en değerli girdisi.
 *
 * Kayıt değiştirilemez (sunucuda güncelleme uç noktası yok): RCA bir denetim
 * kaydıdır.
 */

const FOLDERS = [
  { id: 'pending', label: 'Analiz Bekleyen', hot: true },
  { id: 'recorded', label: 'Kayıtlı Analizler' },
]

const KIND_TR = {
  Inspection: 'İnceleme', Sampling: 'Numune', Repair: 'Onarım',
  Replacement: 'Değişim', Test: 'Test',
}

const fmtDate = (iso) => (iso
  ? new Date(iso).toLocaleDateString('tr-TR',
    { day: '2-digit', month: '2-digit', year: 'numeric' })
  : '—')

const fmtDateTime = (iso) => (iso
  ? new Date(iso).toLocaleString('tr-TR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
  : '—')

/** .NET hata cevabı: { message, problems? }. */
const errorOf = (err) => {
  const data = err?.response?.data
  return {
    message: data?.message || data?.title || err.message,
    problems: Array.isArray(data?.problems) ? data.problems : [],
  }
}

function SimilarList({ items }) {
  if (!items?.length) {
    return (
      <p className="note">
        Benzer geçmiş analiz yok: bu trafoda ve bu arıza türünde ilk kayıt olacak.
      </p>
    )
  }
  return (
    <div className="hi-note warn" style={{ marginTop: 10 }}>
      <b>Geçmiş analizler — aynı arıza tekrarlıyor olabilir</b>
      <ul className="rca-similar">
        {items.map((s) => (
          <li key={s.rca.id}>
            <div>
              <b>{s.rca.id}</b> · {s.rca.transformerId} · {s.rca.failureModeLabel}
              <span className="muted"> · {fmtDate(s.rca.recordedAt)} · {s.why.join(', ')}</span>
            </div>
            <div><span className="k">Kök neden:</span> {s.rca.rootCause}</div>
            <div><span className="k">Alınan önlem:</span> {s.rca.correctiveAction}</div>
          </li>
        ))}
      </ul>
    </div>
  )
}

function RcaView({ rca }) {
  return (
    <div className="mail-meta" style={{ marginTop: 10 }}>
      <span className="k">Analiz</span><span><b>{rca.id}</b></span>
      <span className="k">Arıza türü</span><span>{rca.failureModeLabel}</span>
      <span className="k">Bulgu</span><span>{rca.finding}</span>
      <span className="k">Kök neden</span><span>{rca.rootCause}</span>
      <span className="k">Alınan önlem</span><span>{rca.correctiveAction}</span>
      {rca.preventiveAction && (
        <><span className="k">Tekrarı önleme</span><span>{rca.preventiveAction}</span></>
      )}
      <span className="k">Kaydeden</span>
      <span>{rca.recordedByName}
        <span className="muted"> · sicil {rca.recordedByEmployeeNo} · {fmtDateTime(rca.recordedAt)}</span>
      </span>
    </div>
  )
}

function TextField({ id, label, hint, value, onChange, min, required, placeholder }) {
  const n = value.trim().length
  return (
    <div className="field np-field">
      <label htmlFor={id}>
        {label}
        <span className="np-hint">
          {required ? ` · zorunlu, en az ${min} karakter (${n})` : ` · isteğe bağlı${hint ? ` — ${hint}` : ''}`}
        </span>
      </label>
      <textarea id={id} rows={3} maxLength={2000} value={value}
        onChange={(e) => onChange(e.target.value)} placeholder={placeholder} />
    </div>
  )
}

function RcaForm({ order, schema, onDone }) {
  const [mode, setMode] = useState('')
  const [finding, setFinding] = useState('')
  const [rootCause, setRootCause] = useState('')
  const [corrective, setCorrective] = useState('')
  const [preventive, setPreventive] = useState('')
  const [similar, setSimilar] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  // Arıza türü seçildikçe benzerler yeniden sorulur: tür, trafodan ağır basar.
  useEffect(() => {
    api.maintenance.rcaSimilar({
      transformerId: order.transformerId,
      failureMode: mode || undefined,
      excludeWorkOrderId: order.id,
    })
      .then((d) => setSimilar(d.items || []))
      .catch(() => setSimilar([]))
  }, [order.id, order.transformerId, mode])

  if (!can('engineering.rca')) {
    return (
      <>
        <SimilarList items={similar} />
        <p className="note">Kök neden analizini <b>Mühendislik</b> yazar.</p>
      </>
    )
  }

  const min = schema?.textMin ?? 20
  const ready = mode && [finding, rootCause, corrective].every((t) => t.trim().length >= min)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      await api.maintenance.createRca(order.id, {
        failureMode: mode,
        finding: finding.trim(),
        rootCause: rootCause.trim(),
        correctiveAction: corrective.trim(),
        preventiveAction: preventive.trim() || null,
      })
      onDone(`${order.id}: kök neden analizi kaydedildi.`)
    } catch (err) {
      setError(errorOf(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <SimilarList items={similar} />

      <form className="review-form" onSubmit={submit}>
        {error && (
          <div className="np-problems">
            <b>{error.message}</b>
            {error.problems.length > 0 && (
              <ul>{error.problems.map((p) => <li key={p}>{p}</li>)}</ul>
            )}
          </div>
        )}

        <div className="field np-field">
          <label htmlFor="rca-mode">Arıza türü<span className="np-hint"> · zorunlu</span></label>
          <select id="rca-mode" value={mode} onChange={(e) => setMode(e.target.value)}>
            <option value="">Seçin…</option>
            {(schema?.failureModes || []).map((m) => (
              <option key={m.code} value={m.code}>{m.label}</option>
            ))}
          </select>
        </div>

        <TextField id="rca-finding" label="Bulgu — ne görüldü" required min={min}
          value={finding} onChange={setFinding}
          placeholder="ör. Kademe değiştirici kontaklarında erime izi; sargı direnci dengesizliği %4.1." />
        <TextField id="rca-cause" label="Kök neden — neden oldu" required min={min}
          value={rootCause} onChange={setRootCause}
          placeholder="ör. 58.000 işletmede revizyon yapılmamış; kontak basıncı düşmüş." />
        <TextField id="rca-action" label="Alınan önlem — ne yapıldı" required min={min}
          value={corrective} onChange={setCorrective}
          placeholder="ör. Kontak takımı değiştirildi, direnç ölçümü tekrarlandı: dengesizlik %0.6." />
        <TextField id="rca-prevent" label="Tekrarı önleme" hint="filoya yayılacak ders"
          min={min} value={preventive} onChange={setPreventive}
          placeholder="ör. OLTC revizyon uyarısı 40.000 işletmeye çekildi." />

        <div className="msg-actions">
          <button type="submit" className="erp-tb primary-tb" disabled={busy || !ready}>
            {busy ? 'Kaydediliyor…' : 'Analizi kaydet'}
          </button>
          <span className="note">
            Kayıt <b>değiştirilemez</b> ve adınızla kayda geçer.
          </span>
        </div>
      </form>
    </>
  )
}

function Detail({ workOrderId, schema, onDone }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (!workOrderId) return
    setData(null); setError(null)
    api.maintenance.workOrderRca(workOrderId)
      .then(setData)
      .catch((e) => setError(errorOf(e).message))
  }, [workOrderId])

  if (!workOrderId) {
    return (
      <div className="panel mail-preview">
        <h2>İş Emri ve Analiz</h2>
        <p className="empty">Listeden bir iş emri seçin.</p>
      </div>
    )
  }
  if (error) return <div className="panel mail-preview"><p className="empty">{error}</p></div>
  if (!data) return <div className="panel mail-preview"><p className="empty">Yükleniyor…</p></div>

  const o = data.workOrder
  return (
    <div className="panel mail-preview">
      <h2>İş Emri ve Analiz</h2>
      <div className="mail-subject">{o.id} · {o.transformerId} · {o.title}</div>

      <div className="mail-meta">
        <span className="k">İş türü</span><span>{KIND_TR[o.kind] || o.kind}</span>
        <span className="k">Öncelik</span><span className="num">{o.priority?.toFixed(2)}</span>
        <span className="k">Açılma sebebi</span><span>{o.reason || '—'}</span>
        <span className="k">Yürüten</span><span>{o.technician?.name || '—'}</span>
        <span className="k">Tamamlandı</span><span>{fmtDateTime(o.completedAt)}</span>
        <span className="k">Tamamlama notu</span><span>{o.completionNote || '—'}</span>
        {data.requiredBecause?.length > 0 && (
          <>
            <span className="k">Neden analiz</span>
            <span>{data.requiredBecause.join(' ')}</span>
          </>
        )}
      </div>

      {data.rca
        ? (<><RcaView rca={data.rca} /><SimilarList items={data.similar} /></>)
        : <RcaForm key={o.id} order={o} schema={schema} onDone={onDone} />}
    </div>
  )
}

export default function RcaQueue() {
  const [folder, setFolder] = useState('pending')
  const [pending, setPending] = useState(null)
  const [recorded, setRecorded] = useState(null)
  const [schema, setSchema] = useState(null)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [notice, setNotice] = useState(null)

  // İki klasörün sayısı da görünsün diye ikisi birlikte yüklenir.
  const load = useCallback(() => {
    setError(null)
    Promise.all([api.maintenance.rcaPending(), api.maintenance.rcaList()])
      .then(([p, r]) => { setPending(p); setRecorded(r) })
      .catch((e) => setError(errorOf(e).message))
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    api.maintenance.rcaSchema().then(setSchema).catch(() => setSchema(null))
  }, [])

  const counts = { pending: pending?.count ?? 0, recorded: recorded?.count ?? 0 }
  const loading = !pending || !recorded

  const onDone = (msg) => {
    setNotice(msg)
    setSelected(null)
    load()
  }

  const selectable = (id) => ({
    tabIndex: 0,
    'aria-selected': id === selected,
    className: id === selected ? 'selected' : '',
    onClick: () => setSelected(id),
    onKeyDown: (e) => {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelected(id) }
    },
  })

  return (
    <div className="mail">
      <aside className="mail-folders" aria-label="Kök neden analizi klasörleri">
        <ul>
          {FOLDERS.map((f) => (
            <li key={f.id}>
              <button type="button" className={folder === f.id ? 'active' : ''}
                aria-current={folder === f.id ? 'true' : undefined}
                onClick={() => { setFolder(f.id); setSelected(null); setNotice(null) }}>
                <span>{f.label}</span>
                <span className={`mail-n${f.hot && counts[f.id] > 0 ? ' hot' : ''}`}>{counts[f.id]}</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="note">
          Tamamlanan <b>kritik</b> iş emirleri (öncelik ≥ {schema?.criticalPriority ?? 2.5})
          ve <b>onarım/değişim</b> işleri kök neden analizi bekler. Rutin işler
          buraya düşmez.
        </p>
      </aside>

      <section className="mail-main">
        {notice && <div className="hi-note" style={{ marginBottom: 10 }}><b>{notice}</b></div>}

        <div className="panel">
          <div className="np-head">
            <h2>{FOLDERS.find((f) => f.id === folder)?.label}</h2>
            <span className="muted" style={{ fontSize: '0.8rem' }}>{counts[folder]} kayıt</span>
          </div>

          {error ? (
            <p className="empty">Bakım servisine ulaşılamadı: {String(error)}</p>
          ) : loading ? (
            <p className="empty">Yükleniyor…</p>
          ) : folder === 'pending' ? (
            pending.items.length === 0 ? (
              <p className="empty">Analiz bekleyen kritik iş yok.</p>
            ) : (
              <div className="table-scroll">
                <table className="compare mail-grid">
                  <thead>
                    <tr>
                      <th>İş emri</th><th>Trafo</th><th>İş</th>
                      <th style={{ width: 70 }}>Öncelik</th>
                      <th style={{ width: 95 }}>Tamamlandı</th>
                      <th style={{ width: 70 }}>Bekleme</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pending.items.map(({ workOrder: o, waitingDays }) => (
                      <tr key={o.id} {...selectable(o.id)}>
                        <td className="mono">{o.id}</td>
                        <td><b>{o.transformerId}</b></td>
                        <td>{o.title}<div className="muted" style={{ fontSize: '0.75rem' }}>{KIND_TR[o.kind] || o.kind}</div></td>
                        <td className="num">{o.priority?.toFixed(2)}</td>
                        <td className="num">{fmtDate(o.completedAt)}</td>
                        <td className="num">{waitingDays != null ? `${waitingDays} gün` : '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          ) : recorded.items.length === 0 ? (
            <p className="empty">Henüz kayıtlı kök neden analizi yok.</p>
          ) : (
            <div className="table-scroll">
              <table className="compare mail-grid">
                <thead>
                  <tr>
                    <th>Analiz</th><th>İş emri</th><th>Trafo</th><th>Arıza türü</th>
                    <th>Kaydeden</th><th style={{ width: 95 }}>Tarih</th>
                  </tr>
                </thead>
                <tbody>
                  {recorded.items.map((r) => (
                    <tr key={r.id} {...selectable(r.workOrderId)}>
                      <td className="mono">{r.id}</td>
                      <td className="mono">{r.workOrderId}</td>
                      <td><b>{r.transformerId}</b></td>
                      <td>{r.failureModeLabel}</td>
                      <td>{r.recordedByName}</td>
                      <td className="num">{fmtDate(r.recordedAt)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <Detail key={selected || 'none'} workOrderId={selected} schema={schema} onDone={onDone} />
      </section>
    </div>
  )
}
