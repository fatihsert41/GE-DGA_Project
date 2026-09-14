import { Fragment, useCallback, useEffect, useMemo, useState } from 'react'
import api, { session } from '../api'

/* Faz 10/11 — Bildirim yazma ve gönderilenler.
 *
 * Artık ayrı bir ekran değil; Bildirimler modülünün (BL01) iki klasörü:
 *   default export  MessageComposer → "Yeni Bildirim" formu
 *   named export    SentMessages    → "Gönderilenler" listesi
 *
 * Alıcı üç yoldan seçilir ve BİRLEŞTİRİLİR: tek tek kişiler, bütün bir
 * departman ya da tüm personel. Aynı kişi iki yoldan seçilse de tek
 * bildirim alır. Ekrandaki kişi sayısı yalnızca ÖNİZLEMEDİR; gerçek alıcı
 * listesini sunucu çıkarır (o anda departmana biri eklenmiş ya da pasife
 * alınmış olabilir).
 */

const PRIORITIES = [
  { value: 'normal', label: 'Normal' },
  { value: 'high', label: 'Yüksek' },
  { value: 'urgent', label: 'Acil' },
]

const priorityLabel = (p) => (p >= 4 ? 'Acil' : p >= 2.5 ? 'Yüksek' : 'Normal')
const priorityClass = (p) => (p >= 4 ? 'critical' : p >= 2.5 ? 'high' : 'low')

const STATUS_TR = {
  Pending: 'kuyrukta',
  Sent: 'iletildi',
  Failed: 'iletilemedi',
  Read: 'okundu',
}

const fmtDateTime = (iso) => (iso
  ? new Date(iso).toLocaleString('tr-TR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
  : '—')

const SUBJECT_MAX = 200
const BODY_MAX = 2000

function RecipientPicker({ groups, meNo, all, onAll, depts, onDept, ids, onId }) {
  return (
    <div className="msg-recipients">
      <label className="msg-all">
        <input type="checkbox" checked={all}
          onChange={(e) => onAll(e.target.checked)} />
        <b>Tüm personel</b>
      </label>

      {groups.map((g) => {
        const deptOn = all || depts.has(g.code)
        return (
          <fieldset key={g.code} className="msg-dept" disabled={all}>
            <legend className="msg-dept-head">
              <label>
                <input type="checkbox" checked={deptOn}
                  onChange={() => onDept(g.code)} />
                <b>{g.name}</b>
                <span className="muted"> · departmanın tamamı</span>
              </label>
            </legend>

            {g.members.length === 0 ? (
              <p className="empty msg-empty">Bu departmanda personel yok.</p>
            ) : (
              <ul className="msg-people">
                {g.members.map((p) => {
                  const isMe = p.employeeNo === meNo
                  const inactive = !p.isActive
                  return (
                    <li key={p.id}>
                      <label className={isMe || inactive ? 'msg-off' : ''}>
                        <input type="checkbox"
                          disabled={isMe || inactive || deptOn}
                          checked={!isMe && !inactive && (deptOn || ids.has(p.id))}
                          onChange={() => onId(p.id)} />
                        {p.name}
                        <span className="muted num"> {p.employeeNo}</span>
                        {isMe && <span className="me-chip">siz</span>}
                        {inactive && <span className="muted"> · pasif</span>}
                      </label>
                    </li>
                  )
                })}
              </ul>
            )}
          </fieldset>
        )
      })}
    </div>
  )
}

/** "Gönderilenler" klasörü — kimin okuduğuyla birlikte. */
export function SentMessages() {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(null)

  useEffect(() => {
    api.sentMessages()
      .then(setData)
      .catch((e) => setError(e?.response?.data?.message || e.message))
  }, [])

  return (
    <div className="panel">
      <div className="np-head">
        <h2>Gönderilenler</h2>
        {data && (
          <span className="muted" style={{ fontSize: '0.8rem' }}>
            {data.items?.length ?? 0} mesaj
          </span>
        )}
      </div>

      {error ? (
        <p className="empty">Gönderilen mesajlar alınamadı: {error}</p>
      ) : !data ? (
        <p className="empty">Yükleniyor…</p>
      ) : !data.items?.length ? (
        <p className="empty">Henüz bildirim göndermediniz.</p>
      ) : (
        <div className="table-scroll">
          <table className="compare mail-grid">
            <thead>
              <tr>
                <th style={{ width: 130 }}>Tarih</th>
                <th>Konu</th>
                <th style={{ width: 80 }}>Öncelik</th>
                <th style={{ width: 60 }}>Alıcı</th>
                <th style={{ width: 70 }}>Okuyan</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((m) => {
                const isOpen = open === m.messageId
                return (
                  // Özet + ayrıntı iki satır. Kısa <></> yazımı `key`
                  // alamaz; listede anahtar şart.
                  <Fragment key={m.messageId}>
                    <tr tabIndex={0} aria-expanded={isOpen}
                      className={isOpen ? 'selected' : ''}
                      onClick={() => setOpen(isOpen ? null : m.messageId)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault(); setOpen(isOpen ? null : m.messageId)
                        }
                      }}>
                      <td className="num">{fmtDateTime(m.createdAt)}</td>
                      <td>
                        {m.subject}
                        {m.transformerId && <span className="muted"> · {m.transformerId}</span>}
                      </td>
                      <td>
                        <span className={`badge sm ${priorityClass(m.priority)}`}>
                          {priorityLabel(m.priority)}
                        </span>
                      </td>
                      <td className="num">{m.recipientCount}</td>
                      <td className="num">{m.readCount} / {m.recipientCount}</td>
                    </tr>
                    {isOpen && (
                      <tr className="msg-detail">
                        <td colSpan={5}>
                          <pre className="note-body">{m.body}</pre>
                          <div className="msg-status-list">
                            {m.recipients.map((r) => (
                              <span key={r.employeeNo}
                                className={`msg-status ${r.status === 'Read' ? 'read' : ''}`}>
                                {r.name}
                                <span className="muted"> · {STATUS_TR[r.status] || r.status}
                                  {r.readAt ? ` ${fmtDateTime(r.readAt)}` : ''}</span>
                              </span>
                            ))}
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

/** "Yeni Bildirim" formu. */
export default function MessageComposer({ onSent, onCancel }) {
  const me = session.user()

  const [people, setPeople] = useState(null)
  const [catalog, setCatalog] = useState(null)
  const [error, setError] = useState(null)
  const [problems, setProblems] = useState([])
  const [busy, setBusy] = useState(false)

  const [all, setAll] = useState(false)
  const [depts, setDepts] = useState(() => new Set())
  const [ids, setIds] = useState(() => new Set())
  const [subject, setSubject] = useState('')
  const [body, setBody] = useState('')
  const [priority, setPriority] = useState('normal')
  const [transformerId, setTransformerId] = useState('')

  useEffect(() => {
    Promise.all([api.personnel(), api.departments()])
      .then(([p, c]) => { setPeople(p.items || []); setCatalog(c) })
      .catch((e) => setError(e?.response?.data?.message || e.message))
  }, [])

  // Set'i yerinde değiştirmek React'e "değişti" demez; her seferinde YENİ
  // bir Set üretiyoruz ki ekran yeniden çizilsin.
  const toggle = useCallback((setter) => (key) => setter((prev) => {
    const next = new Set(prev)
    if (next.has(key)) next.delete(key); else next.add(key)
    return next
  }), [])

  const groups = useMemo(() => (catalog?.departments || []).map((d) => ({
    ...d,
    members: (people || []).filter((p) => p.department === d.code),
  })), [catalog, people])

  // Önizleme — sunucudaki MessageRules.Resolve ile aynı mantık.
  const preview = useMemo(() => {
    const chosen = new Map()
    for (const p of people || []) {
      if (!p.isActive || p.employeeNo === me?.employeeNo) continue
      if (all || depts.has(p.department) || ids.has(p.id)) chosen.set(p.id, p)
    }
    return [...chosen.values()]
  }, [people, all, depts, ids, me?.employeeNo])

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setProblems([]); setError(null)
    try {
      const res = await api.sendMessage({
        subject,
        body,
        recipientIds: [...ids],
        departments: [...depts],
        allPersonnel: all,
        priority,
        transformerId: transformerId.trim() || null,
      })
      onSent?.(res)
    } catch (err) {
      const data = err?.response?.data
      if (data?.problems?.length) setProblems(data.problems)
      else setError(data?.message || err.message)
    } finally {
      setBusy(false)
    }
  }

  if (error && !people) {
    return (
      <div className="panel">
        <h2>Yeni Bildirim</h2>
        <p className="empty">Personel listesi alınamadı: {error}</p>
      </div>
    )
  }
  if (!people || !catalog) {
    return <div className="panel"><p className="empty">Yükleniyor…</p></div>
  }

  const ready = subject.trim() && body.trim() && preview.length > 0

  return (
    <form className="panel msg-form" onSubmit={submit}>
      <h2>Yeni Bildirim</h2>

      {error && <div className="np-problems"><b>{String(error)}</b></div>}
      {problems.length > 0 && (
        <div className="np-problems">
          <b>Bildirim gönderilemedi</b>
          <ul>{problems.map((p) => <li key={p}>{p}</li>)}</ul>
        </div>
      )}

      <div className="msg-grid">
        {/* ERP formu: etiket solda, alan sağda. */}
        <div className="msg-form-grid">
          <span className="msg-label">Gönderen</span>
          <div className="msg-static">
            {me?.name} <span className="muted">· {me?.employeeNo} · {me?.departmentName}</span>
          </div>

          <label className="msg-label" htmlFor="msg-subject">Konu</label>
          <input id="msg-subject" value={subject} maxLength={SUBJECT_MAX}
            onChange={(e) => setSubject(e.target.value)}
            placeholder="ör. TR-05 yarın enerjisiz — elektriksel test planı" />

          <label className="msg-label" htmlFor="msg-priority">Öncelik</label>
          <select id="msg-priority" value={priority}
            onChange={(e) => setPriority(e.target.value)}>
            {PRIORITIES.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>

          <label className="msg-label" htmlFor="msg-tr">İlgili trafo</label>
          <input id="msg-tr" value={transformerId} maxLength={20}
            onChange={(e) => setTransformerId(e.target.value)}
            placeholder="isteğe bağlı, ör. TR-05" />

          <label className="msg-label msg-label-top" htmlFor="msg-body">Mesaj</label>
          <textarea id="msg-body" rows={10} value={body} maxLength={BODY_MAX}
            onChange={(e) => setBody(e.target.value)}
            placeholder="Ne yapılması gerektiğini kısa ve açık yazın." />

          <span />
          <span className="np-hint">
            Konu {subject.length}/{SUBJECT_MAX} · Mesaj {body.length}/{BODY_MAX}
          </span>
        </div>

        <div>
          <div className="msg-to-head">
            <b>Alıcılar</b>
            <span className={`msg-count${preview.length ? '' : ' none'}`}>
              {preview.length} kişi
            </span>
          </div>
          <RecipientPicker groups={groups} meNo={me?.employeeNo}
            all={all} onAll={setAll}
            depts={depts} onDept={toggle(setDepts)}
            ids={ids} onId={toggle(setIds)} />
        </div>
      </div>

      <div className="msg-actions">
        <button type="submit" className="erp-tb primary-tb" disabled={busy || !ready}>
          {busy ? 'Gönderiliyor…'
            : preview.length ? `Gönder (${preview.length} kişi)` : 'Alıcı seçin'}
        </button>
        {onCancel && (
          <button type="button" className="erp-tb" onClick={onCancel}>Vazgeç</button>
        )}
        <span className="note">
          Kendinize ve pasif personele bildirim gönderilmez. Aynı kişi iki
          yoldan seçilse de tek bildirim alır.
        </span>
      </div>
    </form>
  )
}
