import { useCallback, useEffect, useState } from 'react'
import api from '../api'
import MessageComposer, { SentMessages } from './MessageComposer'

/* Faz 11 — Bildirimler modülü (BL01).
 *
 * Kullanıcı isteği: gelen bildirimler ve bildirim gönderme TEK ekranda.
 * Düzen kurumsal e-posta istemcilerinden alındı:
 *
 *   klasörler (sol) → liste (tablo) → önizleme (alt)
 *
 * İki tür bildirim aynı listede durur:
 *   İş emri bildirimi → sistem üretir, bir iş emrine bağlıdır.
 *   Mesaj             → bir personel elle gönderir; gönderen bellidir.
 *
 * Kayıtlı HER personel bildirim gönderebilir (kullanıcı kararı, 14 Eyl).
 * Açılan bildirim okunmuş sayılır — e-posta istemcilerindeki gibi. Ayrı
 * bir "okundu işaretle" tıklaması istemek, okunan bildirimlerin okunmamış
 * görünmesine ve menüdeki sayının boşuna şişmesine yol açıyordu.
 */

const STATUS_TR = {
  Pending: 'kuyrukta',
  Sent: 'iletildi',
  Failed: 'iletilemedi',
  Read: 'okundu',
}

const TRIGGER_TR = {
  'work-order-created': 'Yeni iş emri',
  'work-order-escalated': 'Aciliyet yükseldi',
  message: 'Mesaj',
}

const priorityClass = (p) => (p >= 4 ? 'critical' : p >= 2.5 ? 'high' : 'low')
const priorityText = (n) => (n.trigger === 'message'
  ? (n.priority >= 4 ? 'Acil' : n.priority >= 2.5 ? 'Yüksek' : 'Normal')
  : n.priority.toFixed(2))

const fmtDateTime = (iso) => (iso
  ? new Date(iso).toLocaleString('tr-TR', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
  : '—')

// İlgili trafo: mesajda açıkça verilir; iş emri bildiriminde konu satırının
// başında durur ("TR-05 · Onarım · son tarih 14 Eylül 2026").
const transformerOf = (n) => n.transformerId
  || (n.trigger !== 'message' ? n.subject.split('·')[0]?.trim() : null)

function InboxGrid({ items, selectedId, onOpen }) {
  if (!items.length) return <p className="empty">Bu klasörde kayıt yok.</p>

  return (
    <div className="table-scroll">
      <table className="compare mail-grid">
        <thead>
          <tr>
            <th aria-label="Okunma durumu" style={{ width: 22 }} />
            <th style={{ width: 80 }}>Öncelik</th>
            <th>Konu</th>
            <th>Tür / Gönderen</th>
            <th style={{ width: 130 }}>Tarih</th>
            <th style={{ width: 80 }}>Durum</th>
          </tr>
        </thead>
        <tbody>
          {items.map((n) => {
            const unread = n.status !== 'Read'
            const isSelected = n.id === selectedId
            return (
              <tr key={n.id} tabIndex={0} aria-selected={isSelected}
                className={[unread ? 'unread' : '', isSelected ? 'selected' : '']
                  .filter(Boolean).join(' ')}
                onClick={() => onOpen(n)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onOpen(n) }
                }}>
                <td>{unread && <span className="mail-dot" title="okunmadı" />}</td>
                <td>
                  <span className={`badge sm ${priorityClass(n.priority)}`}>
                    {priorityText(n)}
                  </span>
                </td>
                <td>{n.subject}</td>
                <td>
                  {n.trigger === 'message'
                    ? (n.senderName || 'Personel')
                    : (TRIGGER_TR[n.trigger] || n.trigger)}
                </td>
                <td className="num">{fmtDateTime(n.createdAt)}</td>
                <td>{STATUS_TR[n.status] || n.status}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function Preview({ note, onOpenTransformer }) {
  if (!note) {
    return (
      <div className="panel mail-preview">
        <h2>Bildirim Ayrıntısı</h2>
        <p className="empty">Okumak için listeden bir bildirim seçin.</p>
      </div>
    )
  }

  const tr = transformerOf(note)
  const isMessage = note.trigger === 'message'

  return (
    <div className="panel mail-preview">
      <h2>Bildirim Ayrıntısı</h2>
      <div className="mail-subject">{note.subject}</div>

      <div className="mail-meta">
        <span className="k">Tür</span>
        <span>{TRIGGER_TR[note.trigger] || note.trigger}</span>
        {isMessage && (
          <>
            <span className="k">Gönderen</span>
            <span>{note.senderName}
              <span className="muted"> · sicil {note.senderEmployeeNo}</span></span>
          </>
        )}
        <span className="k">Öncelik</span>
        <span>{priorityText(note)}</span>
        <span className="k">Tarih</span>
        <span>{fmtDateTime(note.createdAt)}</span>
        <span className="k">Durum</span>
        <span>{STATUS_TR[note.status] || note.status}
          {note.readAt && <span className="muted"> · {fmtDateTime(note.readAt)}</span>}
        </span>
        {tr && (<><span className="k">İlgili trafo</span><span>{tr}</span></>)}
        {note.lastError && (
          <><span className="k">İletim hatası</span>
            <span className="over-limit">{note.lastError}</span></>
        )}
      </div>

      <pre className="note-body">{note.body}</pre>

      {tr && (
        <div className="mail-actions">
          <button type="button" className="erp-tb" onClick={() => onOpenTransformer(tr)}>
            {tr} kartını aç
          </button>
        </div>
      )}
    </div>
  )
}

export default function NotificationsPanel({ onOpenTransformer, onChange }) {
  const [folder, setFolder] = useState('inbox')     // inbox | unread | sent | compose
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [sentVersion, setSentVersion] = useState(0)
  const [notice, setNotice] = useState(null)

  const load = useCallback(() => {
    setError(null)
    api.notifications(false)
      .then(setData)
      .catch((e) => setError(e?.response?.data?.message || e.message))
  }, [])

  useEffect(() => { load() }, [load])

  const open = (note) => {
    setSelectedId(note.id)
    if (note.status !== 'Read') {
      api.markNotificationRead(note.id)
        .then(() => { load(); onChange?.() })
        .catch(() => {})
    }
  }

  const go = (id) => { setFolder(id); setNotice(null) }

  const items = data?.items || []
  const unreadCount = data?.unread ?? 0
  const shown = folder === 'unread' ? items.filter((n) => n.status !== 'Read') : items
  // Önizleme TÜM listeden bulunur: "Okunmamış" klasöründe açılan bildirim
  // okununca listeden düşer ama önizlemesi ekranda kalmalı.
  const current = items.find((n) => n.id === selectedId) || null

  const folders = [
    { id: 'inbox', label: 'Gelen Kutusu', n: items.length },
    { id: 'unread', label: 'Okunmamış', n: unreadCount, hot: unreadCount > 0 },
    { id: 'sent', label: 'Gönderilenler' },
  ]

  return (
    <div className="mail">
      <aside className="mail-folders" aria-label="Bildirim klasörleri">
        <button type="button" className="erp-tb primary-tb"
          onClick={() => go('compose')}>Yeni Bildirim</button>

        <ul>
          {folders.map((f) => (
            <li key={f.id}>
              <button type="button" className={folder === f.id ? 'active' : ''}
                aria-current={folder === f.id ? 'true' : undefined}
                onClick={() => go(f.id)}>
                <span>{f.label}</span>
                {f.n != null && (
                  <span className={`mail-n${f.hot ? ' hot' : ''}`}>{f.n}</span>
                )}
              </button>
            </li>
          ))}
        </ul>

        <p className="note">
          Kayıtlı her personel bildirim gönderebilir. Bildirimler önce
          veritabanına yazılır, sonra iletilir; kimin okuduğu
          Gönderilenler klasöründe görünür.
        </p>
      </aside>

      <section className="mail-main">
        {notice && <div className="hi-note" style={{ marginBottom: 10 }}><b>{notice}</b></div>}

        {folder === 'compose' && (
          <MessageComposer
            onCancel={() => go('inbox')}
            onSent={(res) => {
              setSentVersion((v) => v + 1)
              setFolder('sent')
              setNotice(`Bildirim ${res.sent} kişiye gönderildi: `
                + res.recipients.map((r) => r.name).join(', ') + '.')
            }} />
        )}

        {folder === 'sent' && <SentMessages key={sentVersion} />}

        {(folder === 'inbox' || folder === 'unread') && (
          <>
            <div className="panel">
              <div className="np-head">
                <h2>{folder === 'unread' ? 'Okunmamış' : 'Gelen Kutusu'}</h2>
                <span className="muted" style={{ fontSize: '0.8rem' }}>
                  {shown.length} kayıt
                </span>
              </div>
              {error ? (
                <>
                  <p className="empty">Bildirimler alınamadı: {error}</p>
                  <p className="note">Bu modül <b>bakım servisinden</b> beslenir (:5080).</p>
                </>
              ) : !data ? (
                <p className="empty">Yükleniyor…</p>
              ) : (
                <InboxGrid items={shown} selectedId={selectedId} onOpen={open} />
              )}
            </div>

            <Preview note={current} onOpenTransformer={onOpenTransformer} />
          </>
        )}
      </section>
    </div>
  )
}
