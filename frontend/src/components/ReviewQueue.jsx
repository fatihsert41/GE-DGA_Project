import { useCallback, useEffect, useState } from 'react'
import api, { session } from '../api'
import { can } from '../permissions'

/* Faz 12.2 — MH01 Test Onay Kuyruğu.
 *
 * Sınır dışı çıkan (genel hükmü "kötü") yağ, elektriksel ve buşing/kademe
 * testleri burada mühendis kararını bekler. Üç karar var:
 *
 *   Onayla          → ölçüm doğru, sonuç geçerli
 *   Tekrar ölçülsün → sonuç hesapta KALIR ama doğrulanmamış işaretli
 *   Reddet          → ölçüm hatalı; hükme ve sağlık endeksine girmez,
 *                     kayıt silinmez
 *
 * Dört göz: testi giren kişi kendi testine karar veremez. Sunucu da aynı
 * kuralı uyguluyor; burada düğmeyi hiç göstermiyoruz ki kullanıcı
 * boşuna gerekçe yazıp ret mesajıyla karşılaşmasın.
 */

const FOLDERS = [
  { id: 'pending', label: 'Onay Bekleyen', hot: true },
  { id: 'retest', label: 'Tekrar Ölçüm İstenen' },
  { id: 'approved', label: 'Onaylanan' },
  { id: 'rejected', label: 'Reddedilen' },
  { id: 'all', label: 'Tümü' },
]

const DECISIONS = [
  { value: 'approve', label: 'Onayla',
    hint: 'Ölçüm doğru; sonuç geçerli sayılır.' },
  { value: 'retest', label: 'Tekrar ölçülsün',
    hint: 'Sonuç şüpheli. Hesapta kalır ama "doğrulanmamış" işaretli kalır.' },
  { value: 'reject', label: 'Reddet',
    hint: 'Ölçüm hatalı. Hükme ve sağlık endeksine girmez; kayıt silinmez.' },
]

const STATUS_CLASS = {
  pending: 'high', retest: 'medium', approved: 'low', rejected: 'critical',
}

const NOTE_MIN = 10

const fmtDateTime = (iso) => (iso
  ? new Date(iso).toLocaleString('tr-TR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
  : '—')

const fmtDate = (iso) => (iso
  ? new Date(iso).toLocaleDateString('tr-TR',
    { day: '2-digit', month: '2-digit', year: 'numeric' })
  : '—')

function DecisionForm({ item, onDone }) {
  const me = session.user()
  const [decision, setDecision] = useState('approve')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  // Karar verilmiş kayıt: kararın kendisi gösterilir.
  if (item.review_status !== 'pending') {
    return (
      <div className="mail-meta" style={{ marginTop: 10 }}>
        <span className="k">Karar</span>
        <span><b>{item.review_status_label}</b></span>
        {item.reviewed_by_name && (
          <>
            <span className="k">Karar veren</span>
            <span>{item.reviewed_by_name}
              <span className="muted"> · sicil {item.reviewed_by_id}</span></span>
          </>
        )}
        {item.reviewed_at && (
          <><span className="k">Karar tarihi</span><span>{fmtDateTime(item.reviewed_at)}</span></>
        )}
        {item.review_note && (
          <><span className="k">Gerekçe</span><span>{item.review_note}</span></>
        )}
      </div>
    )
  }

  if (!can('engineering.approve')) {
    return (
      <p className="note">
        Onay kararı <b>Mühendislik</b> departmanının yetkisindedir.
      </p>
    )
  }

  if (item.recorded_by_id && item.recorded_by_id === me?.employeeNo) {
    return (
      <div className="np-problems" style={{ marginTop: 10 }}>
        <b>Dört göz ilkesi:</b> Bu testi siz girdiniz. Kararı başka bir
        mühendis vermeli — ölçen ile onaylayan aynı kişi olamaz.
      </div>
    )
  }

  const noteRequired = decision !== 'approve'
  const noteOk = !noteRequired || note.trim().length >= NOTE_MIN

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      await api.reviewDecision(item.kind, item.test_id,
        { decision, note: note.trim() || null })
      onDone(DECISIONS.find((d) => d.value === decision)?.label)
    } catch (err) {
      const detail = err?.response?.data?.detail
      setError(typeof detail === 'string' ? detail : err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="review-form" onSubmit={submit}>
      {error && <div className="np-problems"><b>{error}</b></div>}

      <fieldset className="review-decisions">
        <legend className="msg-label">Karar</legend>
        {DECISIONS.map((d) => (
          <label key={d.value} className={decision === d.value ? 'active' : ''}>
            <input type="radio" name="decision" value={d.value}
              checked={decision === d.value}
              onChange={() => setDecision(d.value)} />
            <span>
              <b>{d.label}</b>
              <span className="muted"> — {d.hint}</span>
            </span>
          </label>
        ))}
      </fieldset>

      <div className="field np-field">
        <label htmlFor="review-note">
          Gerekçe
          <span className="np-hint">
            {noteRequired
              ? ` · zorunlu, en az ${NOTE_MIN} karakter (${note.trim().length})`
              : ' · isteğe bağlı'}
          </span>
        </label>
        <textarea id="review-note" rows={3} maxLength={500} value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={noteRequired
            ? 'ör. Numune kabı nemliydi; ölçüm tekrar alınmalı.'
            : 'ör. Değerler önceki testle tutarlı.'} />
      </div>

      <div className="msg-actions">
        <button type="submit" className="erp-tb primary-tb" disabled={busy || !noteOk}>
          {busy ? 'Kaydediliyor…' : 'Kararı kaydet'}
        </button>
        <span className="note">
          Karar bir kez verilir ve karar verenin adıyla kayda geçer.
        </span>
      </div>
    </form>
  )
}

function Detail({ item, onDone, onOpenTransformer }) {
  if (!item) {
    return (
      <div className="panel mail-preview">
        <h2>Test Ayrıntısı</h2>
        <p className="empty">Değerlendirmek için listeden bir test seçin.</p>
      </div>
    )
  }

  return (
    <div className="panel mail-preview">
      <h2>Test Ayrıntısı</h2>
      <div className="mail-subject">
        {item.transformer_id} · {item.kind_label}
      </div>

      <div className="mail-meta">
        <span className="k">Trafo</span>
        <span>{item.transformer_name}
          <span className="muted"> · {item.asset_class}</span></span>
        <span className="k">Test tarihi</span>
        <span>{fmtDate(item.tested_at)}</span>
        <span className="k">Genel hüküm</span>
        <span><b>{item.overall}</b></span>
        <span className="k">Kaydı giren</span>
        <span>{item.recorded_by_name || '—'}
          {item.recorded_by_id && <span className="muted"> · sicil {item.recorded_by_id}</span>}
        </span>
        <span className="k">Durum</span>
        <span>{item.review_status_label}
          {item.review_status === 'pending' && item.waiting_days != null && (
            <span className="muted"> · {item.waiting_days} gündür bekliyor</span>
          )}
        </span>
      </div>

      {item.problems?.length > 0 && (
        <div className="np-problems" style={{ marginTop: 10 }}>
          <b>Sınır dışı bulgular</b>
          <ul>{item.problems.map((p) => <li key={p}>{p}</li>)}</ul>
        </div>
      )}

      <div className="mail-actions">
        <button type="button" className="erp-tb"
          onClick={() => onOpenTransformer(item.transformer_id)}>
          {item.transformer_id} kartını aç
        </button>
      </div>

      <DecisionForm key={`${item.kind}-${item.test_id}`} item={item} onDone={onDone} />
    </div>
  )
}

export default function ReviewQueue({ onOpenTransformer }) {
  const [folder, setFolder] = useState('pending')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [selectedKey, setSelectedKey] = useState(null)
  const [notice, setNotice] = useState(null)

  const load = useCallback(() => {
    setError(null)
    api.reviewQueue(folder)
      .then(setData)
      .catch((e) => setError(e?.response?.data?.detail || e.message))
  }, [folder])

  useEffect(() => { setData(null); load() }, [load])

  const keyOf = (i) => `${i.kind}-${i.test_id}`
  const items = data?.items || []
  const current = items.find((i) => keyOf(i) === selectedKey) || null
  const counts = data?.counts || {}

  const onDone = (label) => {
    setNotice(`${current?.transformer_id} · ${current?.kind_label}: "${label}" kararı kaydedildi.`)
    setSelectedKey(null)
    load()
  }

  return (
    <div className="mail">
      <aside className="mail-folders" aria-label="Onay klasörleri">
        <ul>
          {FOLDERS.map((f) => {
            const n = f.id === 'all'
              ? ['pending', 'retest', 'approved', 'rejected']
                .reduce((sum, s) => sum + (counts[s] || 0), 0)
              : (counts[f.id] || 0)
            return (
              <li key={f.id}>
                <button type="button" className={folder === f.id ? 'active' : ''}
                  aria-current={folder === f.id ? 'true' : undefined}
                  onClick={() => { setFolder(f.id); setSelectedKey(null); setNotice(null) }}>
                  <span>{f.label}</span>
                  <span className={`mail-n${f.hot && n > 0 ? ' hot' : ''}`}>{n}</span>
                </button>
              </li>
            )
          })}
        </ul>
        <p className="note">
          Genel hükmü <b>kötü</b> çıkan yağ, elektriksel ve buşing/kademe
          testleri buraya düşer. Onay bekleyen sonuç sağlık endeksine
          <b> doğrulanmamış</b> işaretiyle girer.
        </p>
      </aside>

      <section className="mail-main">
        {notice && <div className="hi-note" style={{ marginBottom: 10 }}><b>{notice}</b></div>}

        <div className="panel">
          <div className="np-head">
            <h2>{FOLDERS.find((f) => f.id === folder)?.label}</h2>
            <span className="muted" style={{ fontSize: '0.8rem' }}>{items.length} kayıt</span>
          </div>

          {error ? (
            <p className="empty">Kuyruk alınamadı: {String(error)}</p>
          ) : !data ? (
            <p className="empty">Yükleniyor…</p>
          ) : items.length === 0 ? (
            <p className="empty">Bu klasörde kayıt yok.</p>
          ) : (
            <div className="table-scroll">
              <table className="compare mail-grid">
                <thead>
                  <tr>
                    <th>Trafo</th>
                    <th>Test türü</th>
                    <th style={{ width: 95 }}>Test tarihi</th>
                    <th>Bulgu</th>
                    <th>Giren</th>
                    <th style={{ width: 60 }}>Bekleme</th>
                    <th style={{ width: 130 }}>Durum</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((i) => {
                    const k = keyOf(i)
                    return (
                      <tr key={k} tabIndex={0} aria-selected={k === selectedKey}
                        className={k === selectedKey ? 'selected' : ''}
                        onClick={() => setSelectedKey(k)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' || e.key === ' ') {
                            e.preventDefault(); setSelectedKey(k)
                          }
                        }}>
                        <td><b>{i.transformer_id}</b> <span className="muted">{i.asset_class}</span></td>
                        <td>{i.kind_label}</td>
                        <td className="num">{fmtDate(i.tested_at)}</td>
                        <td>{i.problems?.[0] || i.overall}
                          {i.problems?.length > 1 && (
                            <span className="muted"> +{i.problems.length - 1}</span>
                          )}
                        </td>
                        <td>{i.recorded_by_name || '—'}</td>
                        <td className="num">
                          {i.review_status === 'pending' && i.waiting_days != null
                            ? `${i.waiting_days} gün` : '—'}
                        </td>
                        <td>
                          <span className={`badge sm ${STATUS_CLASS[i.review_status] || ''}`}>
                            {i.review_status_label}
                          </span>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <Detail item={current} onDone={onDone} onOpenTransformer={onOpenTransformer} />
      </section>
    </div>
  )
}
