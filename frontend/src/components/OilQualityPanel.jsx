import { useCallback, useEffect, useState } from 'react'
import {
  CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import api from '../api'
import { axis, grid, tooltip, muted, SERIES } from '../theme'

/* Faz 8.4 — Yağ kalitesi ve kağıt yaşlanması ekranı.
 *
 * İki ayrı soru, iki ayrı bölüm:
 *   1. YAĞ nasıl?     → nem, delinme gerilimi, asitlik, arayüzey gerilimi
 *   2. KAĞIT nasıl?   → furan → DP → tüketilen ömür
 *
 * Bu ayrım ekranda da korunuyor, çünkü sonuçları farklı olabilir: yağı
 * "kabul" görünen bir trafonun kağıdı ömrünün %82'sini tüketmiş olabilir
 * (demo filodaki TR-09 tam olarak böyle).
 */

// Durum → rozet sınıfı. Sıralı bir şiddet olduğu için mevcut risk
// rampasını kullanıyoruz; yeni bir renk dizisi eklemek arayüzde ikinci bir
// "kötülük" dili yaratırdı.
const CONDITION_CLASS = {
  'iyi': 'low',
  'kabul': 'medium',
  'kötü': 'critical',
  'bilinmiyor': '',
}

const BAND_CLASS = {
  'sağlıklı': 'low',
  'orta': 'medium',
  'ileri': 'high',
  'ömür sonu': 'critical',
}

const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('tr-TR',
    { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

/** Kağıt ömrü göstergesi: tüketilen / kalan. */
function PaperLife({ paper }) {
  if (!paper?.available) {
    return (
      <div className="panel">
        <h2>Kağıt Yalıtım</h2>
        <p className="empty">
          Furan (2-FAL) ölçümü yok; kağıt yaşlanması hesaplanamıyor.
        </p>
        <p className="note">
          Furan analizi ayrıca istenen bir laboratuvar testidir. Kağıdın
          durumunu gösteren tek dolaylı yöntemdir: DP'yi doğrudan ölçmek
          için trafoyu açıp kağıt örneği almak gerekir.
        </p>
      </div>
    )
  }

  const consumed = paper.life_consumed_pct ?? 0
  const bandClass = BAND_CLASS[paper.band] || ''

  return (
    <div className="panel">
      <h2>
        Kağıt Yalıtım
        <span className={`badge sm ${bandClass}`}
          style={{ marginLeft: 10 }}>{paper.band}</span>
      </h2>

      <div className="paper-head">
        <div>
          <div className="kpi-label">Polimerizasyon derecesi (DP)</div>
          <div className="kpi-value">{paper.dp_estimate}</div>
          <div className="kpi-hint">
            yeni {paper.dp_new} · ömür sonu {paper.dp_end_of_life}
          </div>
        </div>
        <div>
          <div className="kpi-label">Tüketilen ömür</div>
          <div className={`kpi-value${consumed >= 75 ? ' danger' : ''}`}>
            %{consumed.toFixed(0)}
          </div>
          <div className="kpi-hint">{paper.model}</div>
        </div>
      </div>

      {/* Tüketilen/kalan çubuğu: renk sıralı şiddet rampasından. */}
      <div className="life-bar" role="img"
        aria-label={`Ömrünün yüzde ${consumed.toFixed(0)}'i tüketilmiş`}>
        <span className={bandClass} style={{ width: `${consumed}%` }} />
      </div>
      <div className="life-legend">
        <span>tüketilen %{consumed.toFixed(0)}</span>
        <span className="muted">kalan %{(100 - consumed).toFixed(0)}</span>
      </div>

      <p className="note">{paper.description}</p>

      {/* Güvenilirlik beyanı sonucun yanında durmalı: sayıyı gösterip
          kısıtını gizlemek, sayıyı olduğundan kesin göstermek olurdu. */}
      {paper.reliable === false && paper.warnings?.map((w) => (
        <div key={w} className="paper-warning">
          <b>Güvenilirlik uyarısı:</b> {w}
        </div>
      ))}
    </div>
  )
}

/** DP'nin zaman içindeki düşüşü. */
function DpTrend({ series }) {
  if (!series || series.length < 2) return null

  const data = series.map((p) => ({
    date: fmtDate(p.sampled_at),
    dp: p.dp,
  }))

  return (
    <div className="panel" style={{ marginTop: 16 }}>
      <h2>Kağıt Bozunması — Zaman Serisi</h2>
      <ResponsiveContainer width="100%" height={260}>
        <LineChart data={data} margin={{ left: 0, right: 16, top: 8, bottom: 8 }}>
          <CartesianGrid stroke={grid.stroke} vertical={false} />
          {/* Bant arka planları: DP'nin hangi bölgede olduğu bir bakışta
              görünsün. Değerler backend'deki DP_BANDS ile aynı. */}
          <ReferenceArea y1={700} y2={1200} fill="var(--low)" fillOpacity={0.07} />
          <ReferenceArea y1={450} y2={700} fill="var(--medium)" fillOpacity={0.07} />
          <ReferenceArea y1={250} y2={450} fill="var(--high)" fillOpacity={0.07} />
          <ReferenceArea y1={0} y2={250} fill="var(--critical)" fillOpacity={0.09} />
          <XAxis dataKey="date" stroke={axis.stroke} tick={axis.tick} />
          <YAxis stroke={axis.stroke} tick={axis.tick} domain={[0, 1200]}
            width={54} />
          <Tooltip {...tooltip} />
          <Line type="monotone" dataKey="dp" name="DP" stroke={SERIES[0]}
            strokeWidth={2} dot={{ r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
      <p className="note">
        Kağıt bozunması <b>geri dönüşsüzdür</b>: DP yalnızca düşer. Tek bir
        değerden çok, düşüş <b>hızı</b> bilgilendiricidir. Arka plan bantları
        sağlıklı / orta / ileri / ömür sonu bölgelerini gösterir.
      </p>
    </div>
  )
}

/** Yağ parametreleri tablosu. */
function OilParameters({ assessment }) {
  const params = (assessment?.parameters || [])
    .filter((p) => p.condition !== 'bilinmiyor')

  if (!params.length) {
    return <p className="empty">Bu testte ölçülmüş yağ parametresi yok.</p>
  }

  return (
    <>
      <div className="table-scroll">
        <table className="compare">
          <thead>
            <tr>
              <th>Parametre</th><th>Değer</th><th>İyi</th>
              <th>Kabul sınırı</th><th>Durum</th><th>Standart</th>
            </tr>
          </thead>
          <tbody>
            {params.map((p) => (
              <tr key={p.parameter}>
                <td>
                  <b>{p.label}</b>
                  <div className="muted" style={{ fontSize: '0.74rem' }}>
                    {p.meaning}
                  </div>
                </td>
                <td><b>{p.value}</b> <span className="unit">{p.unit}</span></td>
                <td className="muted">{p.good_limit}</td>
                <td className="muted">{p.acceptable_limit}</td>
                <td>
                  <span className={`badge sm ${CONDITION_CLASS[p.condition]}`}>
                    {p.condition}
                  </span>
                </td>
                <td className="muted" style={{ fontSize: '0.74rem' }}>
                  {p.standard}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note">
        Eşikler <b>gerilim sınıfına</b> göre değişir (bu trafo:{' '}
        {assessment.voltage_class}). Yüksek gerilimde aynı nem çok daha
        tehlikelidir. Genel durum <b>en kötü</b> parametreye göre belirlenir —
        ortalama almak üç iyinin bir kötüyü gizlemesine yol açardı.
      </p>
    </>
  )
}

/** Yeni yağ testi girişi. */
function OilTestForm({ transformerId, schema, onSaved, onCancel }) {
  const [values, setValues] = useState({})
  const [meta, setMeta] = useState({ lab: '', notes: '', sampled_at: '' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const set = (key) => (e) =>
    setValues((v) => ({ ...v, [key]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    const payload = {}
    for (const [k, v] of Object.entries(values)) {
      if (v !== '') payload[k] = Number(v)
    }
    if (!Object.keys(payload).length) {
      setError('En az bir ölçüm değeri girilmelidir.')
      return
    }
    for (const [k, v] of Object.entries(meta)) {
      if (v) payload[k] = v
    }

    setSaving(true); setError(null)
    try {
      await api.createOilTest(transformerId, payload)
      onSaved?.()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    } finally {
      setSaving(false)
    }
  }

  const params = Object.entries(schema?.parameters || {})

  return (
    <form className="panel np-form" onSubmit={submit}>
      <h2>Yeni Yağ Testi</h2>
      <p className="note" style={{ marginTop: 0 }}>
        Laboratuvarlar her zaman tüm parametreleri ölçmez; elindeki kadarını
        gir. Furan analizi ayrıca istenir ve kağıt yaşlanmasını hesaplamak
        için gereklidir.
      </p>

      {error && <div className="np-problems"><b>{String(error)}</b></div>}

      <div className="np-grid">
        {params.map(([key, spec]) => (
          <div className="field np-field" key={key}>
            <label>
              {spec.label}
              <span className="np-hint"> · {spec.unit}</span>
            </label>
            <input type="number" step="any" value={values[key] ?? ''}
              onChange={set(key)} />
          </div>
        ))}
        <div className="field np-field">
          <label>
            Furan 2-FAL<span className="np-hint"> · mg/L · kağıt yaşı</span>
          </label>
          <input type="number" step="any" value={values.furan_2fal_mgl ?? ''}
            onChange={set('furan_2fal_mgl')} />
        </div>
        <div className="field np-field">
          <label>Renk<span className="np-hint"> · ASTM D1500</span></label>
          <input type="number" step="0.5" min="0" max="8"
            value={values.color_astm ?? ''} onChange={set('color_astm')} />
        </div>
      </div>

      <div className="np-grid" style={{ marginTop: 14 }}>
        <div className="field np-field">
          <label>Numune tarihi</label>
          <input type="date" value={meta.sampled_at}
            onChange={(e) => setMeta({ ...meta, sampled_at: e.target.value })} />
        </div>
        <div className="field np-field">
          <label>Laboratuvar</label>
          <input value={meta.lab}
            onChange={(e) => setMeta({ ...meta, lab: e.target.value })} />
        </div>
        <div className="field np-field">
          <label>Not</label>
          <input value={meta.notes}
            onChange={(e) => setMeta({ ...meta, notes: e.target.value })} />
        </div>
      </div>

      <div className="np-actions">
        <button type="submit" className="primary" disabled={saving}>
          {saving ? 'Kaydediliyor…' : 'Testi kaydet'}
        </button>
        <button type="button" className="chip" onClick={onCancel}>Vazgeç</button>
      </div>
    </form>
  )
}

export default function OilQualityPanel({ id }) {
  const [data, setData] = useState(null)
  const [schema, setSchema] = useState(null)
  const [error, setError] = useState(null)
  const [adding, setAdding] = useState(false)

  const load = useCallback(() => {
    setError(null)
    api.oilTests(id)
      .then(setData)
      .catch((e) => setError(e?.response?.data?.detail || e.message))
  }, [id])

  useEffect(() => { load() }, [load])
  useEffect(() => { api.oilSchema().then(setSchema).catch(() => setSchema(null)) },
    [])

  if (error) {
    return <div className="panel"><p className="empty">Hata: {String(error)}</p></div>
  }
  if (!data) {
    return <div className="panel"><p className="empty">Yükleniyor…</p></div>
  }

  if (adding) {
    return (
      <OilTestForm transformerId={id} schema={schema}
        onCancel={() => setAdding(false)}
        onSaved={() => { setAdding(false); load() }} />
    )
  }

  if (!data.available) {
    return (
      <div className="panel">
        <div className="np-head">
          <h2>Yağ Kalitesi</h2>
          <button type="button" className="chip"
            onClick={() => setAdding(true)}>+ Test ekle</button>
        </div>
        <p className="empty">{data.message}</p>
      </div>
    )
  }

  const a = data.latest_assessment
  const test = a.test || {}

  return (
    <div>
      <div className="panel">
        <div className="np-head">
          <h2>
            Yağ Kalitesi
            <span className={`badge sm ${CONDITION_CLASS[a.overall]}`}
              style={{ marginLeft: 10 }}>{a.overall}</span>
          </h2>
          <span className="muted" style={{ fontSize: '0.8rem' }}>
            son test {fmtDate(test.sampled_at)}
            {test.lab ? ` · ${test.lab}` : ''} · toplam {data.n_tests} test
          </span>
          <button type="button" className="chip"
            onClick={() => setAdding(true)}>+ Test ekle</button>
        </div>

        <OilParameters assessment={a} />

        {a.problems?.length > 0 && (
          <p className="note over-limit">
            <b>Sınır dışı:</b> {a.problems.join(' · ')}
          </p>
        )}
      </div>

      <div style={{ marginTop: 16 }}>
        <PaperLife paper={a.paper} />
      </div>

      <DpTrend series={data.dp_series} />
    </div>
  )
}
