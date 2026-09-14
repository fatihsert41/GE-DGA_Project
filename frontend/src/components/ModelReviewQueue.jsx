import { useCallback, useEffect, useState } from 'react'
import api, { session } from '../api'
import { can } from '../permissions'

/* Faz 12.3 — MH02 Model İnceleme Kuyruğu (uzman etiketi).
 *
 * Model bir DGA tanısından emin olmadığında vaka buraya düşer. Mühendis
 * gazlara, klasik yöntemlerin oylarına ve modelin olasılıklarına bakıp
 * GERÇEK arıza tipini seçer. Bu karar iki iş görür:
 *
 *   1. Bugün: filo kartındaki tanı uzman kararına döner; bakım
 *      planlayıcısı doğru iş emrini üretir.
 *   2. Yarın: etiketli gerçek veri olur (Faz 6.9: modele en büyük katkı
 *      daha çok gerçek veriden gelir).
 *
 * ⚠ Modelin cevabı formda ÖNCEDEN SEÇİLİ DEĞİL. Gösteriliyor ama mühendis
 * kendisi seçiyor. Önceden seçili bir cevap insanı ona doğru çeker
 * ("otomasyon yanlılığı") ve etiketler modelin kopyasına dönüşür — o
 * zaman veri seti modele yeni hiçbir şey öğretmez.
 */

const FOLDERS = [
  { id: 'pending', label: 'İnceleme Bekleyen' },
  { id: 'labeled', label: 'Etiketlenen' },
  { id: 'all', label: 'Tümü' },
]

const GAS_ORDER = ['H2', 'CH4', 'C2H6', 'C2H4', 'C2H2', 'CO', 'CO2']

const pct = (v) => (v == null ? '—' : `%${Math.round(v * 100)}`)

const fmtDate = (iso) => (iso
  ? new Date(iso).toLocaleDateString('tr-TR',
    { day: '2-digit', month: '2-digit', year: 'numeric' })
  : '—')

function StatsStrip({ stats }) {
  if (!stats) return null
  return (
    <div className="kpis" style={{ marginBottom: 10 }}>
      <div className="kpi">
        <div className="kpi-label">İnceleme bekleyen</div>
        <div className="kpi-value">{stats.pending}</div>
        <div className="kpi-hint">güven &lt; {pct(stats.threshold)}</div>
      </div>
      <div className="kpi">
        <div className="kpi-label">Etiketlenen</div>
        <div className="kpi-value">{stats.labeled}</div>
        <div className="kpi-hint">{stats.undetermined} belirlenemedi</div>
      </div>
      <div className="kpi">
        <div className="kpi-label">Model–uzman uyumu</div>
        <div className="kpi-value">{pct(stats.agreement_rate)}</div>
        <div className="kpi-hint">aynı alt tip</div>
      </div>
      <div className="kpi">
        <div className="kpi-label">Aile uyumu</div>
        <div className="kpi-value">{pct(stats.family_agreement_rate)}</div>
        <div className="kpi-hint">Normal / Termal / Deşarj</div>
      </div>
      <div className={`kpi${stats.severe_missed_by_model ? ' danger' : ''}`}>
        <div className="kpi-label">Modelin kaçırdığı ciddi arıza</div>
        <div className="kpi-value">{stats.severe_missed_by_model}</div>
        <div className="kpi-hint">uzman D2/T3 dedi</div>
      </div>
    </div>
  )
}

function LabelForm({ detail, onDone }) {
  const me = session.user()
  const [label, setLabel] = useState(null)       // bilinçli olarak BOŞ başlar
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  if (detail.expert_label) {
    return (
      <div className="mail-meta" style={{ marginTop: 10 }}>
        <span className="k">Uzman kararı</span>
        <span><b>{detail.expert_label_tr}</b>
          {detail.agrees ? <span className="muted"> · modelle aynı</span>
            : <span className="muted"> · modelden farklı</span>}</span>
        <span className="k">Karar veren</span>
        <span>{detail.labeled_by_name}
          <span className="muted"> · sicil {detail.labeled_by_id}</span></span>
        {detail.note && (<><span className="k">Gerekçe</span><span>{detail.note}</span></>)}
      </div>
    )
  }

  if (!can('engineering.review_model')) {
    return <p className="note">Tanı kararı <b>Mühendislik</b> departmanının yetkisindedir.</p>
  }

  if (detail.recorded_by_id && detail.recorded_by_id === me?.employeeNo) {
    return (
      <div className="np-problems" style={{ marginTop: 10 }}>
        <b>Dört göz ilkesi:</b> Bu ölçümü siz kaydettiniz. Tanıyı başka bir
        mühendis etiketlemeli.
      </div>
    )
  }

  const min = detail.note_min_length || 10
  const noteRequired = label != null && label !== detail.model_prediction
  const ready = label != null && (!noteRequired || note.trim().length >= min)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      await api.modelReviewLabel(detail.measurement_id,
        { label, note: note.trim() || null })
      onDone(detail.labels.find((l) => l.value === label)?.label)
    } catch (err) {
      const d = err?.response?.data?.detail
      setError(typeof d === 'string' ? d : err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="review-form" onSubmit={submit}>
      {error && <div className="np-problems"><b>{error}</b></div>}

      <div className="msg-label" style={{ textAlign: 'left', marginBottom: 4 }}>
        Gerçek arıza tipi nedir?
      </div>
      <div className="label-grid" role="radiogroup" aria-label="Uzman tanısı">
        {detail.labels.map((l) => (
          <label key={l.value} className={label === l.value ? 'active' : ''}>
            <input type="radio" name="expert-label" value={l.value}
              checked={label === l.value} onChange={() => setLabel(l.value)} />
            <b>{l.value === 'undetermined' ? '?' : l.value}</b>
            <span className="muted">{l.label}</span>
          </label>
        ))}
      </div>
      <p className="note" style={{ marginTop: 4 }}>
        Modelin cevabı bilerek önceden seçilmedi: seçili gelen cevap kararı
        ona doğru çeker ve etiketler modelin kopyasına döner.
      </p>

      <div className="field np-field">
        <label htmlFor="label-note">
          Gerekçe
          <span className="np-hint">
            {noteRequired
              ? ` · modelden farklı karar: zorunlu, en az ${min} karakter (${note.trim().length})`
              : ' · isteğe bağlı'}
          </span>
        </label>
        <textarea id="label-note" rows={3} maxLength={500} value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="ör. C2H4/C2H6 oranı yüksek, Duval T3 bölgesinde; CO düşük, kağıt dahil değil." />
      </div>

      <div className="msg-actions">
        <button type="submit" className="erp-tb primary-tb" disabled={busy || !ready}>
          {busy ? 'Kaydediliyor…' : 'Tanıyı kaydet'}
        </button>
        <span className="note">Karar bir kez verilir ve adınızla kayda geçer.</span>
      </div>
    </form>
  )
}

function Detail({ measurementId, onDone, onOpenTransformer }) {
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    if (measurementId == null) return
    setDetail(null); setError(null)
    api.modelReviewDetail(measurementId)
      .then(setDetail)
      .catch((e) => setError(e?.response?.data?.detail || e.message))
  }, [measurementId])

  if (measurementId == null) {
    return (
      <div className="panel mail-preview">
        <h2>Vaka Ayrıntısı</h2>
        <p className="empty">İncelemek için listeden bir ölçüm seçin.</p>
      </div>
    )
  }
  if (error) return <div className="panel"><p className="empty">Hata: {String(error)}</p></div>
  if (!detail) return <div className="panel"><p className="empty">Yükleniyor…</p></div>

  const current = detail.current_model
  const topProbs = current?.probabilities
    ? Object.entries(current.probabilities).sort((a, b) => b[1] - a[1]).slice(0, 3)
    : []
  const votes = detail.classical?.votes || []

  return (
    <div className="panel mail-preview">
      <h2>Vaka Ayrıntısı</h2>
      <div className="mail-subject">
        {detail.transformer_id} · ölçüm {fmtDate(detail.sampled_at)}
        {detail.is_latest && <span className="me-chip">son ölçüm</span>}
      </div>

      <div className="review-columns">
        <div>
          <h3>Gaz değerleri (ppm)</h3>
          <table className="compare">
            <thead><tr>{GAS_ORDER.map((g) => <th key={g}>{g}</th>)}</tr></thead>
            <tbody>
              <tr>{GAS_ORDER.map((g) => <td key={g} className="num">{detail.gases?.[g] ?? '—'}</td>)}</tr>
            </tbody>
          </table>

          <h3>Klasik yöntemler</h3>
          <div className="mail-meta">
            <span className="k">Uzlaşı</span>
            <span><b>{detail.classical.prediction}</b>
              <span className="muted"> · oy oranı {pct(detail.classical.confidence)}</span></span>
            <span className="k">Oylar</span>
            <span>{votes.length ? votes.join(' · ') : 'yöntemler karar veremedi'}</span>
            <span className="k">IEEE risk</span>
            <span>{detail.risk?.level_tr || detail.risk?.level || '—'}</span>
          </div>
        </div>

        <div>
          <h3>Model</h3>
          <div className="mail-meta">
            <span className="k">Kayıttaki tanı</span>
            <span><b>{detail.model_prediction}</b>
              <span className="muted"> · güven {pct(detail.confidence)}</span></span>
            <span className="k">Eşik</span>
            <span>{pct(detail.threshold)}
              {detail.low_confidence && <span className="muted"> · altında, model kararsız</span>}
            </span>
            {current && (
              <>
                <span className="k">Güncel model</span>
                <span>{topProbs.map(([cls, p]) => `${cls} ${pct(p)}`).join(' · ')}</span>
              </>
            )}
            <span className="k">Ölçümü giren</span>
            <span>{detail.recorded_by_name || <span className="muted">kayıt yok (eski ölçüm)</span>}</span>
          </div>
          {current && current.prediction !== detail.model_prediction && (
            <p className="note">
              Güncel model bu ölçüme <b>{current.prediction}</b> diyor; kayıttaki
              tanı daha eski bir model sürümünden gelmiş olabilir.
            </p>
          )}
        </div>
      </div>

      <div className="mail-actions">
        <button type="button" className="erp-tb"
          onClick={() => onOpenTransformer(detail.transformer_id)}>
          {detail.transformer_id} kartını aç
        </button>
      </div>

      <LabelForm key={detail.measurement_id} detail={detail} onDone={onDone} />
    </div>
  )
}

export default function ModelReviewQueue({ onOpenTransformer }) {
  const [folder, setFolder] = useState('pending')
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [selected, setSelected] = useState(null)
  const [notice, setNotice] = useState(null)

  const load = useCallback(() => {
    setError(null)
    api.modelReviewQueue(folder)
      .then(setData)
      .catch((e) => setError(e?.response?.data?.detail || e.message))
  }, [folder])

  useEffect(() => { setData(null); load() }, [load])

  const items = data?.items || []
  const stats = data?.stats

  const onDone = (labelText) => {
    const item = items.find((i) => i.measurement_id === selected)
    setNotice(`${item?.transformer_id} ölçümü "${labelText}" olarak etiketlendi.`)
    setSelected(null)
    load()
  }

  return (
    <div className="mail">
      <aside className="mail-folders" aria-label="İnceleme klasörleri">
        <ul>
          {FOLDERS.map((f) => {
            const n = f.id === 'pending' ? stats?.pending
              : f.id === 'labeled' ? stats?.labeled
                : (stats ? stats.pending + stats.labeled : null)
            return (
              <li key={f.id}>
                <button type="button" className={folder === f.id ? 'active' : ''}
                  aria-current={folder === f.id ? 'true' : undefined}
                  onClick={() => { setFolder(f.id); setSelected(null); setNotice(null) }}>
                  <span>{f.label}</span>
                  {n != null && (
                    <span className={`mail-n${f.id === 'pending' && n > 0 ? ' hot' : ''}`}>{n}</span>
                  )}
                </button>
              </li>
            )
          })}
        </ul>

        {/* Veri seti indirme: uzman kararları eğitim/değerlendirme verisi. */}
        <a className="erp-tb dataset-link" href="/api/model-reviews/dataset?format=csv">
          Veri setini indir (CSV)
        </a>

        <p className="note">
          Model güveni eşiğin altında kalan DGA ölçümleri buraya düşer.
          Mühendisin seçtiği tanı filo kartındaki tanının yerine geçer ve
          etiketli gerçek veri olarak saklanır. "Belirlenemedi" kararı veri
          setine girmez.
        </p>
      </aside>

      <section className="mail-main">
        {notice && <div className="hi-note" style={{ marginBottom: 10 }}><b>{notice}</b></div>}

        <StatsStrip stats={stats} />

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
                    <th style={{ width: 95 }}>Ölçüm</th>
                    <th>Model tanısı</th>
                    <th style={{ width: 60 }}>Güven</th>
                    <th>Uzman kararı</th>
                    <th style={{ width: 90 }}></th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((i) => (
                    <tr key={i.measurement_id} tabIndex={0}
                      aria-selected={i.measurement_id === selected}
                      className={i.measurement_id === selected ? 'selected' : ''}
                      onClick={() => setSelected(i.measurement_id)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault(); setSelected(i.measurement_id)
                        }
                      }}>
                      <td><b>{i.transformer_id}</b> <span className="muted">{i.asset_class}</span></td>
                      <td className="num">{fmtDate(i.sampled_at)}</td>
                      <td>{i.model_prediction} <span className="muted">{i.model_prediction_tr}</span></td>
                      <td className="num">{pct(i.confidence)}</td>
                      <td>{i.expert_label_tr
                        ? <b>{i.expert_label_tr}</b>
                        : <span className="muted">bekliyor</span>}</td>
                      <td>{i.is_latest && <span className="me-chip">son ölçüm</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <Detail measurementId={selected} onDone={onDone}
          onOpenTransformer={onOpenTransformer} />
      </section>
    </div>
  )
}
