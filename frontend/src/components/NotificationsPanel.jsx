import { useCallback, useEffect, useState } from 'react'
import api from '../api'

/* Faz 9.2 — Gelen kutusu.
 *
 * Bildirim, iş emrinin EKİDİR: bağımsız bir mesajlaşma kutusu değil.
 * Her satır bir iş emrine bağlı ve "şunu yapman gerekiyor" diyor.
 * Bağlantısı olmayan bir uyarı kutusu, bir süre sonra kapatılan bir
 * uyarı kutusudur.
 *
 * Sıralama bilinçli: önce okunmamışlar, sonra öncelik, sonra tarih.
 * Salt tarihe göre sıralamak, acil bir bildirimi rutin olanların
 * altına gömerdi.
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
}

const fmtWhen = (iso) => {
  if (!iso) return '—'
  const d = new Date(iso)
  const mins = Math.round((Date.now() - d.getTime()) / 60000)
  if (mins < 1) return 'az önce'
  if (mins < 60) return `${mins} dk önce`
  if (mins < 1440) return `${Math.round(mins / 60)} saat önce`
  return d.toLocaleDateString('tr-TR',
    { day: 'numeric', month: 'short', year: 'numeric' })
}

function Item({ note, onRead, onOpenTransformer }) {
  const unread = note.status !== 'Read'
  // Konu satırı "TR-05 · Onarım · son tarih 14 Eylül 2026" biçiminde.
  const transformerId = note.subject.split('·')[0]?.trim()

  return (
    <li className={`note-item${unread ? ' unread' : ''}`}>
      <div className="note-head">
        <span className={`badge sm ${note.priority >= 2.5 ? 'high' : 'low'}`}>
          {note.priority.toFixed(2)}
        </span>
        <b className="note-subject">{note.subject}</b>
        <span className="note-when muted">{fmtWhen(note.createdAt)}</span>
      </div>

      <div className="note-meta muted">
        {TRIGGER_TR[note.trigger] || note.trigger}
        {' · '}{STATUS_TR[note.status] || note.status}
        {note.lastError && (
          <span className="over-limit"> · hata: {note.lastError}</span>
        )}
      </div>

      <pre className="note-body">{note.body}</pre>

      <div className="note-actions">
        {transformerId && (
          <button type="button" className="chip"
            onClick={() => onOpenTransformer(transformerId)}>
            {transformerId} detayı →
          </button>
        )}
        {unread && (
          <button type="button" className="link-like"
            onClick={() => onRead(note.id)}>okundu işaretle</button>
        )}
      </div>
    </li>
  )
}

export default function NotificationsPanel({ onOpenTransformer }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [unreadOnly, setUnreadOnly] = useState(false)

  const load = useCallback(() => {
    api.notifications(unreadOnly)
      .then(setData)
      .catch((e) => setError(e?.response?.data?.message || e.message))
  }, [unreadOnly])

  useEffect(() => { load() }, [load])

  const markRead = (id) => {
    api.markNotificationRead(id).then(load).catch(() => {})
  }

  if (error) {
    return (
      <div className="panel">
        <h2>Bildirimler</h2>
        <p className="empty">Bildirimler alınamadı: {error}</p>
        <p className="note">
          Bu ekran <b>.NET bakım servisinden</b> beslenir (:5080).
        </p>
      </div>
    )
  }
  if (!data) return <div className="panel"><p className="empty">Yükleniyor…</p></div>

  return (
    <div>
      <div className="panel">
        <div className="np-head">
          <h2>Gelen Kutusu
            {data.unread > 0 && (
              <span className="count-pill">{data.unread}</span>
            )}
          </h2>
          <div className="chips">
            <button type="button"
              className={`chip${unreadOnly ? '' : ' active'}`}
              onClick={() => setUnreadOnly(false)}>Tümü</button>
            <button type="button"
              className={`chip${unreadOnly ? ' active' : ''}`}
              onClick={() => setUnreadOnly(true)}>Okunmamış</button>
          </div>
        </div>

        <p className="note" style={{ marginTop: 0 }}>
          Her bildirim bir <b>iş emrine</b> bağlıdır ve ne yapılması
          gerektiğini söyler. Bildirimler önce veritabanına yazılır, sonra
          arka planda iletilir — böylece iletim başarısız olsa bile
          kaydolan iş kaybolmaz ve "kime ne zaman haber verildi" sorusu
          cevaplanabilir kalır.
        </p>

        {data.items.length === 0 ? (
          <p className="empty">
            {unreadOnly ? 'Okunmamış bildirim yok.' : 'Bildirim yok.'}
          </p>
        ) : (
          <ul className="note-list">
            {data.items.map((n) => (
              <Item key={n.id} note={n} onRead={markRead}
                onOpenTransformer={onOpenTransformer} />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
