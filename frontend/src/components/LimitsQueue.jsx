import { useCallback, useEffect, useState } from 'react'
import api, { session } from '../api'
import { can } from '../permissions'

/* Faz 12.4 — MH03 Varlığa Özel Eşik.
 *
 * "TR-07 eski tasarım, nem sınırı 20 değil 25 ppm" gibi istisnalar burada
 * KAYIT olarak yaşar: gerekçesi, süresi, öneren ve onaylayan kişisiyle.
 *
 *   Öner        → onay bekler, UYGULANMAZ
 *   Onayla      → başka bir mühendis; geçerlilik aralığındaki testlere uygulanır
 *   Reddet      → standart eşik geçerli kalır (gerekçe zorunlu)
 *   Geri çek    → standart eşik hemen geri gelir (dört göz gerekmez)
 *
 * Onay ekranında "bu istisna neyi değiştirir?" sorusunun cevabı (son testin
 * iki hükmü) kararın HEMEN üstünde durur: etkisini görmeden gevşetme
 * onaylanmamalı. Kurallar sunucuda da uygulanıyor; burada sadece kullanıcı
 * boşuna form doldurup ret mesajıyla karşılaşmasın diye tekrar gösteriliyor.
 */

const FOLDERS = [
  { id: 'pending', label: 'Onay Bekleyen', hot: true, statuses: ['pending'] },
  { id: 'active', label: 'Yürürlükte', statuses: ['active'] },
  { id: 'closed', label: 'Kapanan', statuses: ['rejected', 'revoked', 'expired'] },
  { id: 'all', label: 'Tümü',
    statuses: ['pending', 'active', 'rejected', 'revoked', 'expired'] },
]

const STATUS_CLASS = {
  pending: 'high', active: 'medium', rejected: '', revoked: '', expired: '',
}

// Gevşetme dikkat ister; sıkılaştırma korumacıdır.
const DIRECTION_CLASS = { loosen: 'high', mixed: 'medium', tighten: 'low' }

const DAY_MS = 24 * 60 * 60 * 1000
const isoDay = (offsetDays = 0) =>
  new Date(Date.now() + offsetDays * DAY_MS).toISOString().slice(0, 10)

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

const errorText = (err) => {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (detail?.message) return detail.message
  return err.message
}

/** "≤" düşük olanın iyi olduğu parametrede, "≥" yüksek olanın iyi olduğunda. */
const cmp = (direction) => (direction === 'higher_better' ? '≥' : '≤')

function LimitPair({ good, acceptable, direction, unit }) {
  const c = cmp(direction)
  return (
    <span className="num">
      iyi {c} {good} · kabul {c} {acceptable}
      {unit && <span className="muted"> {unit}</span>}
    </span>
  )
}

function ImpactBox({ impact, unit }) {
  if (!impact) {
    return (
      <p className="note">
        Bu trafonun geçerli bir yağ testi yok; istisnanın etkisi henüz
        görülemiyor.
      </p>
    )
  }
  return (
    <div className={`hi-note${impact.changes_verdict ? ' warn' : ''}`}
      style={{ marginTop: 10 }}>
      <b>Son test bu sınırlarla değerlendirilseydi</b>
      <span className="muted"> ({fmtDate(impact.sampled_at)})</span>
      <div>
        Ölçülen: <b className="num">{impact.value ?? '—'}</b> {unit} →
        standart eşikle <b>{impact.condition_standard}</b>, istisnayla
        <b> {impact.condition_override}</b>
      </div>
      <div>
        Genel hüküm: <b>{impact.overall_standard}</b> →
        <b> {impact.overall_override}</b>
        {impact.changes_verdict ? ' — hüküm DEĞİŞİYOR' : ' — hüküm değişmiyor'}
      </div>
    </div>
  )
}

function DecisionForm({ item, noteMin, onDone }) {
  const me = session.user()
  const [decision, setDecision] = useState('approve')
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  if (!can('engineering.limits')) {
    return <p className="note">İstisna kararı <b>Mühendislik</b> yetkisindedir.</p>
  }

  if (item.proposed_by_id && item.proposed_by_id === me?.employeeNo) {
    return (
      <div className="np-problems" style={{ marginTop: 10 }}>
        <b>Dört göz ilkesi:</b> Bu istisnayı siz önerdiniz. Kararı başka bir
        mühendis vermeli — eşik gevşetmek o trafonun gelecekteki bütün
        testlerini etkiler.
      </div>
    )
  }

  const noteOk = decision === 'approve' || note.trim().length >= noteMin

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      await api.limitDecision(item.id, { decision, note: note.trim() || null })
      onDone(decision === 'approve' ? 'Onaylandı' : 'Reddedildi')
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="review-form" onSubmit={submit}>
      {error && <div className="np-problems"><b>{error}</b></div>}
      <fieldset className="review-decisions">
        <legend className="msg-label">Karar</legend>
        {[
          { value: 'approve', label: 'Onayla',
            hint: 'Geçerlilik aralığındaki testlere uygulanır.' },
          { value: 'reject', label: 'Reddet',
            hint: 'Standart eşik geçerli kalır. Gerekçe zorunlu.' },
        ].map((d) => (
          <label key={d.value} className={decision === d.value ? 'active' : ''}>
            <input type="radio" name="limit-decision" value={d.value}
              checked={decision === d.value}
              onChange={() => setDecision(d.value)} />
            <span><b>{d.label}</b><span className="muted"> — {d.hint}</span></span>
          </label>
        ))}
      </fieldset>

      <div className="field np-field">
        <label htmlFor="limit-note">
          Gerekçe
          <span className="np-hint">
            {decision === 'reject'
              ? ` · zorunlu, en az ${noteMin} karakter (${note.trim().length})`
              : ' · isteğe bağlı'}
          </span>
        </label>
        <textarea id="limit-note" rows={3} maxLength={500} value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder={decision === 'reject'
            ? 'ör. Nem yüksekliği tasarımdan değil, conta kaçağından.'
            : 'ör. Konservatör tipi künyeyle doğrulandı.'} />
      </div>

      <div className="msg-actions">
        <button type="submit" className="erp-tb primary-tb" disabled={busy || !noteOk}>
          {busy ? 'Kaydediliyor…' : 'Kararı kaydet'}
        </button>
        <span className="note">Karar bir kez verilir ve adınızla kayda geçer.</span>
      </div>
    </form>
  )
}

function RevokeForm({ item, noteMin, onDone }) {
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  if (!can('engineering.limits')) return null

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      await api.revokeLimit(item.id, { note: note.trim() })
      onDone('Geri çekildi')
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="review-form" onSubmit={submit}>
      {error && <div className="np-problems"><b>{error}</b></div>}
      <div className="field np-field">
        <label htmlFor="revoke-note">
          Geri çekme gerekçesi
          <span className="np-hint">
            {` · zorunlu, en az ${noteMin} karakter (${note.trim().length})`}
          </span>
        </label>
        <textarea id="revoke-note" rows={2} maxLength={500} value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="ör. Konservatör yenilendi; standart eşik geçerli." />
      </div>
      <div className="msg-actions">
        <button type="submit" className="erp-tb"
          disabled={busy || note.trim().length < noteMin}>
          {busy ? 'Kaydediliyor…' : 'İstisnayı geri çek'}
        </button>
        <span className="note">
          Standart eşik hemen geri gelir. Dört göz gerekmez: standarda dönmek
          korumacıdır.
        </span>
      </div>
    </form>
  )
}

function Detail({ item, schema, onDone, onOpenTransformer }) {
  if (!item) {
    return (
      <div className="panel mail-preview">
        <h2>İstisna Ayrıntısı</h2>
        <p className="empty">İncelemek için listeden bir istisna seçin.</p>
      </div>
    )
  }

  const param = schema?.parameters?.[item.parameter] || {}
  const noteMin = schema?.note_min_length ?? 10

  return (
    <div className="panel mail-preview">
      <h2>İstisna Ayrıntısı</h2>
      <div className="mail-subject">
        {item.transformer_id} · {item.parameter_label}
      </div>

      <div className="mail-meta">
        <span className="k">Trafo</span>
        <span>{item.transformer_name || '—'}
          <span className="muted"> · {item.voltage_class}</span></span>
        <span className="k">Standart</span>
        <LimitPair good={item.standard_good_limit} acceptable={item.standard_acceptable_limit}
          direction={param.direction} unit={item.unit} />
        <span className="k">İstisna</span>
        <span>
          <b><LimitPair good={item.good_limit} acceptable={item.acceptable_limit}
            direction={param.direction} unit={item.unit} /></b>{' '}
          <span className={`badge sm ${DIRECTION_CLASS[item.change_direction] || ''}`}>
            {item.change_direction_label}
          </span>
        </span>
        <span className="k">Geçerlilik</span>
        <span className="num">{fmtDate(item.valid_from)} – {fmtDate(item.valid_until)}
          {item.days_left != null && <span className="muted"> · {item.days_left} gün kaldı</span>}
        </span>
        <span className="k">Öneren</span>
        <span>{item.proposed_by_name || '—'}
          {item.proposed_by_id && <span className="muted"> · sicil {item.proposed_by_id}</span>}
          <span className="muted"> · {fmtDateTime(item.proposed_at)}</span>
        </span>
        {item.decided_by_name && (
          <>
            <span className="k">Karar veren</span>
            <span>{item.decided_by_name}
              <span className="muted"> · sicil {item.decided_by_id} · {fmtDateTime(item.decided_at)}</span>
            </span>
          </>
        )}
        {item.decision_note && (
          <><span className="k">Karar notu</span><span>{item.decision_note}</span></>
        )}
        {item.revoked_by_name && (
          <>
            <span className="k">Geri çeken</span>
            <span>{item.revoked_by_name}
              <span className="muted"> · {fmtDateTime(item.revoked_at)}</span></span>
            <span className="k">Gerekçe</span><span>{item.revoke_note}</span>
          </>
        )}
        <span className="k">Durum</span>
        <span>
          <span className={`badge sm ${STATUS_CLASS[item.status] || ''}`}>{item.status_label}</span>
        </span>
      </div>

      <div className="hi-note" style={{ marginTop: 10 }}>
        <b>İstisna gerekçesi</b>
        <div>{item.reason}</div>
      </div>

      <ImpactBox impact={item.impact} unit={item.unit} />

      <div className="mail-actions">
        <button type="button" className="erp-tb"
          onClick={() => onOpenTransformer(item.transformer_id)}>
          {item.transformer_id} kartını aç
        </button>
      </div>

      {item.status === 'pending' && (
        <DecisionForm key={`d-${item.id}`} item={item} noteMin={noteMin} onDone={onDone} />
      )}
      {item.status === 'active' && (
        <RevokeForm key={`r-${item.id}`} item={item} noteMin={noteMin} onDone={onDone} />
      )}
    </div>
  )
}

function ProposalForm({ schema, onDone, onCancel }) {
  const [transformers, setTransformers] = useState([])
  const [tid, setTid] = useState('')
  const [context, setContext] = useState(null)
  const [parameter, setParameter] = useState('water_ppm')
  const [good, setGood] = useState('')
  const [acceptable, setAcceptable] = useState('')
  const [validUntil, setValidUntil] = useState(isoDay(180))
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.fleetOverview()
      .then((d) => setTransformers(d.transformers || []))
      .catch(() => setTransformers([]))
  }, [])

  useEffect(() => {
    setContext(null)
    if (!tid) return
    api.transformerLimits(tid).then(setContext).catch(() => setContext(null))
  }, [tid])

  const params = schema?.parameters || {}
  const spec = params[parameter] || {}
  const std = context?.standard_limits?.[parameter]
  const maxDev = schema?.max_deviation_pct ?? 50
  const reasonMin = schema?.reason_min_length ?? 20
  const openHere = (context?.history || []).find(
    (i) => i.parameter === parameter && ['pending', 'active'].includes(i.status))

  // Canlı sapma: sunucu da denetliyor, bu yalnızca yazarken uyarır.
  const deviation = (value, base) => {
    const v = Number(value)
    if (value === '' || !base || Number.isNaN(v)) return null
    return Math.round((Math.abs(v - base) / base) * 100)
  }
  const devGood = deviation(good, std?.good)
  const devAcc = deviation(acceptable, std?.acceptable)

  const ready = tid && good !== '' && acceptable !== '' && validUntil
    && reason.trim().length >= reasonMin && !openHere

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      await api.proposeLimit(tid, {
        parameter,
        good_limit: Number(good),
        acceptable_limit: Number(acceptable),
        valid_until: validUntil,
        reason: reason.trim(),
      })
      onDone(`${tid} · ${spec.label}: istisna önerildi, onay bekliyor.`)
    } catch (err) {
      setError(errorText(err))
    } finally {
      setBusy(false)
    }
  }

  const devHint = (dev) => (dev == null ? null : (
    <span className={dev > maxDev ? 'np-bad' : 'muted'}>
      {' '}· standarttan %{dev}{dev > maxDev ? ` (en fazla %${maxDev})` : ''}
    </span>
  ))

  return (
    <div className="panel">
      <div className="np-head">
        <h2>Yeni İstisna Önerisi</h2>
        <button type="button" className="erp-tb" onClick={onCancel}>Vazgeç</button>
      </div>

      <form className="review-form" onSubmit={submit}>
        {error && <div className="np-problems"><b>{error}</b></div>}

        <div className="np-grid">
          <div className="field np-field">
            <label htmlFor="lim-tid">Trafo</label>
            <select id="lim-tid" value={tid} onChange={(e) => setTid(e.target.value)}>
              <option value="">Seçin…</option>
              {transformers.map((t) => (
                <option key={t.id} value={t.id}>{t.id} · {t.name}</option>
              ))}
            </select>
          </div>
          <div className="field np-field">
            <label htmlFor="lim-param">Parametre</label>
            <select id="lim-param" value={parameter}
              onChange={(e) => { setParameter(e.target.value); setGood(''); setAcceptable('') }}>
              {Object.entries(params).map(([key, p]) => (
                <option key={key} value={key}>{p.label} ({p.unit})</option>
              ))}
            </select>
          </div>
        </div>

        {std && (
          <p className="note">
            Standart ({context.voltage_class}):{' '}
            <LimitPair good={std.good} acceptable={std.acceptable}
              direction={spec.direction} unit={spec.unit} />
            {' '}— {spec.direction === 'higher_better'
              ? 'yüksek değer iyidir; sınırı düşürmek gevşetmedir.'
              : 'düşük değer iyidir; sınırı yükseltmek gevşetmedir.'}
          </p>
        )}

        {openHere && (
          <div className="np-problems">
            Bu trafoda bu parametre için zaten <b>{openHere.status_label.toLowerCase()}</b> bir
            istisna var. Yeni öneri için önce onu sonuçlandırın ya da geri çekin.
          </div>
        )}

        <div className="np-grid">
          <div className="field np-field">
            <label htmlFor="lim-good">İyi sınırı ({spec.unit}){devHint(devGood)}</label>
            <input id="lim-good" type="number" step="any" min="0" value={good}
              onChange={(e) => setGood(e.target.value)} />
          </div>
          <div className="field np-field">
            <label htmlFor="lim-acc">Kabul sınırı ({spec.unit}){devHint(devAcc)}</label>
            <input id="lim-acc" type="number" step="any" min="0" value={acceptable}
              onChange={(e) => setAcceptable(e.target.value)} />
          </div>
          <div className="field np-field">
            <label htmlFor="lim-until">
              Bitiş tarihi
              <span className="np-hint"> · en fazla {schema?.max_duration_days ?? 365} gün</span>
            </label>
            <input id="lim-until" type="date" value={validUntil}
              min={isoDay(0)} max={isoDay(schema?.max_duration_days ?? 365)}
              onChange={(e) => setValidUntil(e.target.value)} />
          </div>
        </div>

        <div className="field np-field">
          <label htmlFor="lim-reason">
            Gerekçe
            <span className="np-hint">
              {` · zorunlu, en az ${reasonMin} karakter (${reason.trim().length})`}
            </span>
          </label>
          <textarea id="lim-reason" rows={3} maxLength={500} value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="ör. Serbest solunumlu eski konservatör tasarımı; nem tarihsel olarak 20 ppm üstünde, BDV kararlı." />
        </div>

        <div className="msg-actions">
          <button type="submit" className="erp-tb primary-tb" disabled={busy || !ready}>
            {busy ? 'Gönderiliyor…' : 'Öneriyi gönder'}
          </button>
          <span className="note">
            Öneri, başka bir mühendis onaylayana kadar <b>uygulanmaz</b>.
            Geçerlilik bugün başlar.
          </span>
        </div>
      </form>

      {schema?.not_overridable && (
        <details className="note" style={{ marginTop: 12 }}>
          <summary>Neden yalnızca yağ kalitesi eşikleri?</summary>
          <ul>
            {Object.entries(schema.not_overridable).map(([k, why]) => (
              <li key={k}>{why}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}

export default function LimitsQueue({ onOpenTransformer }) {
  const [folder, setFolder] = useState('pending')
  const [data, setData] = useState(null)
  const [schema, setSchema] = useState(null)
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const [notice, setNotice] = useState(null)
  const [proposing, setProposing] = useState(false)

  const load = useCallback(() => {
    setError(null)
    api.limitsQueue(folder)
      .then(setData)
      .catch((e) => setError(errorText(e)))
  }, [folder])

  useEffect(() => { setData(null); load() }, [load])
  useEffect(() => { api.limitsSchema().then(setSchema).catch(() => setSchema(null)) }, [])

  const items = data?.items || []
  const current = items.find((i) => i.id === selectedId) || null
  const counts = data?.counts || {}

  const onDone = (label) => {
    setNotice(`${current?.transformer_id} · ${current?.parameter_label}: "${label}" kaydedildi.`)
    setSelectedId(null)
    load()
  }

  return (
    <div className="mail">
      <aside className="mail-folders" aria-label="İstisna klasörleri">
        <ul>
          {FOLDERS.map((f) => {
            const n = f.statuses.reduce((sum, s) => sum + (counts[s] || 0), 0)
            return (
              <li key={f.id}>
                <button type="button" className={folder === f.id ? 'active' : ''}
                  aria-current={folder === f.id ? 'true' : undefined}
                  onClick={() => { setFolder(f.id); setSelectedId(null); setNotice(null) }}>
                  <span>{f.label}</span>
                  <span className={`mail-n${f.hot && n > 0 ? ' hot' : ''}`}>{n}</span>
                </button>
              </li>
            )
          })}
        </ul>
        <p className="note">
          Varlığa özel eşik, standart yağ kalitesi sınırının <b>tek bir trafo</b>
          {' '}için, <b>süreli</b> ve <b>gerekçeli</b> olarak değiştirilmesidir.
          Yürürlükteki istisna, değerlendirmede standart hükümle birlikte
          gösterilir — sessiz eşik değişikliği yoktur.
        </p>
      </aside>

      <section className="mail-main">
        {notice && <div className="hi-note" style={{ marginBottom: 10 }}><b>{notice}</b></div>}

        {proposing ? (
          <ProposalForm schema={schema}
            onCancel={() => setProposing(false)}
            onDone={(msg) => {
              setProposing(false); setNotice(msg)
              if (folder === 'pending') load(); else setFolder('pending')
            }} />
        ) : (
          <>
            <div className="panel">
              <div className="np-head">
                <h2>{FOLDERS.find((f) => f.id === folder)?.label}</h2>
                <span className="muted" style={{ fontSize: '0.8rem' }}>{items.length} kayıt</span>
                {can('engineering.limits') && (
                  <button type="button" className="erp-tb primary-tb"
                    onClick={() => { setProposing(true); setNotice(null) }}>
                    + Yeni istisna
                  </button>
                )}
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
                        <th>Parametre</th>
                        <th>Standart → İstisna</th>
                        <th>Yön</th>
                        <th style={{ width: 95 }}>Bitiş</th>
                        <th>Öneren</th>
                        <th style={{ width: 120 }}>Durum</th>
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((i) => (
                        <tr key={i.id} tabIndex={0} aria-selected={i.id === selectedId}
                          className={i.id === selectedId ? 'selected' : ''}
                          onClick={() => setSelectedId(i.id)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter' || e.key === ' ') {
                              e.preventDefault(); setSelectedId(i.id)
                            }
                          }}>
                          <td><b>{i.transformer_id}</b></td>
                          <td>{i.parameter_label}</td>
                          <td className="num">
                            {i.standard_acceptable_limit} → <b>{i.acceptable_limit}</b>
                            <span className="muted"> {i.unit} (kabul)</span>
                          </td>
                          <td>
                            <span className={`badge sm ${DIRECTION_CLASS[i.change_direction] || ''}`}>
                              {i.change_direction_label}
                            </span>
                          </td>
                          <td className="num">{fmtDate(i.valid_until)}</td>
                          <td>{i.proposed_by_name || '—'}</td>
                          <td>
                            <span className={`badge sm ${STATUS_CLASS[i.status] || ''}`}>
                              {i.status_label}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            <Detail item={current} schema={schema} onDone={onDone}
              onOpenTransformer={onOpenTransformer} />
          </>
        )}
      </section>
    </div>
  )
}
