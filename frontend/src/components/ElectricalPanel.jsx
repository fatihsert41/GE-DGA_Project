import { useCallback, useEffect, useState } from 'react'
import {
  CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from 'recharts'
import api from '../api'
import { axis, grid, tooltip, muted, SERIES } from '../theme'

/* Faz 8.6 — Elektriksel testler ekranı.
 *
 * Bu ekranın diğerlerinden farkı: burada gösterilen her şey trafo
 * ENERJİSİZKEN ölçülür. Yani veri seyrektir ve "test yok" bir istisna
 * değil, normal durumdur — ekran bunu kusur gibi değil, bilgi gibi
 * göstermeli.
 *
 * Dört bölüm, dört bağımsız soru:
 *   TTR      → sargıda spir kaybı var mı?          (DGA göremez)
 *   Direnç   → bağlantı/kademe kontağı sağlam mı?  (DGA göremez)
 *   PI       → yalıtım kuru mu?
 *   tan δ    → yalıtım genel olarak ne durumda?
 */

const CONDITION_CLASS = {
  'iyi': 'low',
  'kabul': 'medium',
  'kötü': 'critical',
  'bilinmiyor': '',
}

const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('tr-TR',
    { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

const Badge = ({ condition }) => (
  <span className={`badge sm ${CONDITION_CLASS[condition] || ''}`}>
    {condition || 'bilinmiyor'}
  </span>
)

/** Bölüm başlığı: hüküm + hangi standarda göre. */
function SectionHead({ title, condition, standard, meaning }) {
  return (
    <div className="el-head">
      <div>
        <h2>{title} {condition && <Badge condition={condition} />}</h2>
        {meaning && <p className="note el-meaning">{meaning}</p>}
      </div>
      {standard && <span className="el-standard">{standard}</span>}
    </div>
  )
}

/* --- 1) Sarım oranı ---------------------------------------------------- */

function TurnsRatio({ section }) {
  if (!section?.available) {
    return (
      <div className="panel">
        <SectionHead title="Sarım Oranı (TTR)" />
        <p className="empty">{section?.reason || 'Ölçüm yok.'}</p>
      </div>
    )
  }

  return (
    <div className="panel">
      <SectionHead title="Sarım Oranı (TTR)" condition={section.overall}
        standard={section.standard}
        meaning="Kısa devre olmuş spiri yakalar. Yağa iz bırakması için önce
                 ısınıp gaz üretmesi gerekir; TTR aynı gün görür." />

      <div className="el-expected">
        <span className="k">Beklenen oran</span>
        <b className="num">{section.expected}</b>
        {section.tap != null && (
          <span className="muted"> · kademe {section.tap > 0 ? '+' : ''}
            {section.tap}</span>
        )}
        <span className="muted"> · tolerans ±%{section.tolerance_pct}</span>
      </div>

      <table className="compare">
        <thead>
          <tr><th>Faz</th><th>Ölçülen</th><th>Sapma</th><th>Durum</th></tr>
        </thead>
        <tbody>
          {section.phases.map((p) => (
            <tr key={p.phase}>
              <td><b>{p.phase}</b></td>
              <td className="num">{p.measured ?? '—'}</td>
              <td className={p.condition === 'kötü' ? 'over-limit num' : 'num'}>
                {p.deviation_pct == null ? '—'
                  : `${p.deviation_pct > 0 ? '+' : ''}%${p.deviation_pct}`}
              </td>
              <td><Badge condition={p.condition} /></td>
            </tr>
          ))}
        </tbody>
      </table>

      {/* Asıl tanı burada: sapmanın DESENİ, büyüklüğünden çok şey söyler. */}
      {section.note && (
        <div className="el-note warn"><b>Yorum.</b> {section.note}</div>
      )}

      {section.spread_pct != null && (
        <p className="note">
          Fazlar arası yayılım <b>%{section.spread_pct}</b>. Üç faz birlikte
          kaymışsa sebep genellikle kademe pozisyonudur; tek faz ayrışmışsa
          o sargıda fiziksel bir sorun vardır. Aynı sapma, iki farklı
          sonuç — biri kağıt hatası, diğeri devreden çıkarma sebebi.
        </p>
      )}
    </div>
  )
}

/* --- 2) Sargı direnci -------------------------------------------------- */

function WindingResistance({ section, series }) {
  if (!section?.available) {
    return (
      <div className="panel">
        <SectionHead title="Sargı Direnci" />
        <p className="empty">{section?.reason || 'Ölçüm yok.'}</p>
      </div>
    )
  }

  const chart = (series || []).map((s, i) => ({
    i, date: fmtDate(s.tested_at), imbalance: s.imbalance_pct,
  }))

  return (
    <div className="panel">
      <SectionHead title="Sargı Direnci" condition={section.condition}
        standard={section.standard} meaning={section.meaning} />

      <div className="el-metric">
        <div>
          <div className="k">Fazlar arası dengesizlik</div>
          <b className={`el-big ${CONDITION_CLASS[section.condition]}`}>
            %{section.imbalance_pct}
          </b>
          <div className="muted">sınır %{section.limit_pct} · en çok sapan
            faz {section.worst_phase}</div>
        </div>
        <div>
          <div className="k">Ortalama direnç</div>
          <b className="el-big">{section.mean_ohm}</b>
          <div className="muted">Ω
            {section.temp_c != null &&
              ` · ${section.temp_c} °C ölçümden ${section.reference_temp_c} °C'ye düzeltildi`}
          </div>
        </div>
      </div>

      <table className="compare">
        <thead>
          <tr><th>Faz</th><th>Ölçülen (Ω)</th>
            <th>Düzeltilmiş (Ω)</th></tr>
        </thead>
        <tbody>
          {Object.keys(section.corrected).map((ph) => (
            <tr key={ph}>
              <td><b>{ph}</b></td>
              <td className="num">{section.measured[ph]}</td>
              <td className="num">{section.corrected[ph]}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <p className="note">
        Ölçüt <b>mutlak ohm değil, dengesizlik</b>: mutlak direnç tasarıma
        ve sıcaklığa bağlıdır ve künyede yazmaz — ama üç faz aynı trafoda,
        aynı koşuldadır, yani birbirlerinin doğal referansıdır.
        Sıcaklık düzeltmesi {section.winding_material === 'Al'
          ? 'alüminyum (225)' : 'bakır (234.5)'} sabitiyle yapıldı.
      </p>

      {chart.length > 1 && (
        <>
          <h3>Dengesizliğin Seyri</h3>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={chart}
              margin={{ left: 0, right: 16, top: 8, bottom: 8 }}>
              <CartesianGrid stroke={grid.stroke} vertical={false} />
              <XAxis dataKey="date" stroke={axis.stroke} tick={axis.tick} />
              <YAxis stroke={axis.stroke} tick={axis.tick} unit="%" width={50} />
              <Tooltip {...tooltip} />
              <ReferenceLine y={section.limit_pct} stroke={muted}
                strokeDasharray="4 4"
                label={{ value: `sınır %${section.limit_pct}`, position: 'right',
                  fill: muted, fontSize: 11 }} />
              <Line type="monotone" dataKey="imbalance" name="dengesizlik"
                stroke={SERIES[0]} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
          <p className="note">
            Tek ölçüm sınırın altında olsa bile <b>eğilim</b> uyarı
            verebilir: %1.8 tek başına iyidir, ama iki yılda %0.4'ten
            %1.8'e çıkmışsa gelişen bir sorun vardır.
          </p>
        </>
      )}
    </div>
  )
}

/* --- 3) Yalıtım direnci / PI ------------------------------------------- */

function Insulation({ section }) {
  if (!section?.available) {
    return (
      <div className="panel">
        <SectionHead title="Yalıtım Direnci / PI" />
        <p className="empty">{section?.reason || 'Ölçüm yok.'}</p>
      </div>
    )
  }

  return (
    <div className="panel">
      <SectionHead title="Yalıtım Direnci / PI" condition={section.condition}
        standard={section.standard}
        meaning="Kuru ve temiz yalıtımda direnç zamanla YÜKSELİR
                 (polarizasyon); nemli veya kirli yalıtımda sabit kalır." />

      <div className="el-metric">
        <div>
          <div className="k">Polarizasyon indeksi</div>
          <b className={`el-big ${CONDITION_CLASS[section.condition]}`}>
            {section.pi ?? '—'}
          </b>
          <div className="muted">R(10 dk) ÷ R(1 dk)</div>
        </div>
        <div>
          <div className="k">1 dakika direnci</div>
          <b className="el-big">{section.ir_1min_mohm}</b>
          <div className="muted">MΩ
            {section.temp_c != null &&
              ` · 20 °C'ye düzeltilmiş ${section.ir_1min_corrected}`}
          </div>
        </div>
      </div>

      <p className="note">
        {section.description || section.note}
      </p>

      {/* Tuzak vakası: sistemin en sağlam trafoyu suçlamasını engelleyen
          kural. Sessizce uygulamak yerine GÖRÜNÜR yapıyoruz. */}
      {(section.warnings || []).map((w) => (
        <div key={w} className="el-note warn"><b>Hüküm düzeltildi.</b> {w}</div>
      ))}

      <p className="note">
        PI'ın sahada sevilmesinin sebebi <b>oran</b> olmasıdır: mutlak
        değere ve sıcaklığa görece duyarsızdır, yani farklı günlerde
        farklı koşullarda alınmış ölçümler karşılaştırılabilir.
      </p>
    </div>
  )
}

/* --- 4) tan δ ---------------------------------------------------------- */

function TanDelta({ section }) {
  if (!section?.available) {
    return (
      <div className="panel">
        <SectionHead title="Kayıp Faktörü (tan δ)" />
        <p className="empty">{section?.reason || 'Ölçüm yok.'}</p>
      </div>
    )
  }

  const pct = Math.min(100, (section.tan_delta_pct /
    (section.acceptable_limit * 2)) * 100)

  return (
    <div className="panel">
      <SectionHead title="Kayıp Faktörü (tan δ)" condition={section.condition}
        standard={section.standard} meaning={section.meaning} />

      <div className="el-metric">
        <div>
          <div className="k">tan δ</div>
          <b className={`el-big ${CONDITION_CLASS[section.condition]}`}>
            %{section.tan_delta_pct}
          </b>
          <div className="muted">
            iyi ≤ %{section.good_limit} · kabul ≤ %{section.acceptable_limit}
          </div>
        </div>
      </div>

      <div className="life-bar" role="img"
        aria-label={`tan delta yüzde ${section.tan_delta_pct}`}>
        <span className={CONDITION_CLASS[section.condition]}
          style={{ width: `${pct}%` }} />
      </div>

      {(section.warnings || []).map((w) => (
        <div key={w} className="el-note warn"><b>Sınır.</b> {w}</div>
      ))}

      <p className="note">
        DGA noktasal bir arızayı gösterir; tan δ ise <b>yalıtımın
        bütününün</b> durumunu. Bu yüzden ikisi rakip değil, tamamlayıcıdır.
      </p>
    </div>
  )
}

/* --- Veri giriş formu -------------------------------------------------- */

/** Sahada girilen sayının beklenen değere göre sapmasını ANINDA gösterir.
 *  Teknisyen ölçtüğü değeri yazarken hedefi görmeli; kaydettikten sonra
 *  "meğer yanlışmış" demek, sahaya ikinci kez gitmek demektir. */
function LiveDeviation({ value, expected, tolerance }) {
  if (!value || !expected) return null
  const dev = ((Number(value) - expected) / expected) * 100
  if (!Number.isFinite(dev)) return null
  const cls = Math.abs(dev) <= tolerance ? 'low'
    : Math.abs(dev) <= tolerance * 2 ? 'medium' : 'critical'
  return (
    <span className={`el-live ${cls}`}>
      {dev > 0 ? '+' : ''}%{dev.toFixed(2)}
    </span>
  )
}

function ElectricalTestForm({ transformerId, schema, onSaved, onCancel }) {
  const [values, setValues] = useState({})
  const [meta, setMeta] = useState({ tested_by: '', notes: '', tested_at: '' })
  const [expected, setExpected] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const tap = values.tap_position

  // Kademe değiştikçe beklenen oran yeniden hesaplanır — formun kalbi bu.
  useEffect(() => {
    api.expectedRatio(transformerId, tap === '' || tap == null ? null : tap)
      .then(setExpected)
      .catch(() => setExpected(null))
  }, [transformerId, tap])

  const set = (key) => (e) =>
    setValues((v) => ({ ...v, [key]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    const payload = {}
    for (const [k, v] of Object.entries(values)) {
      if (v !== '' && v != null) payload[k] = Number(v)
    }
    for (const [k, v] of Object.entries(meta)) {
      if (v) payload[k] = v
    }

    setSaving(true); setError(null)
    try {
      await api.createElectricalTest(transformerId, payload)
      onSaved?.()
    } catch (err) {
      setError(err?.response?.data?.detail || err.message)
    } finally {
      setSaving(false)
    }
  }

  const exp = expected?.expected_at_tap ?? expected?.rated_turns_ratio
  const tol = expected?.tolerance_pct ?? 0.5

  return (
    <form className="panel np-form" onSubmit={submit}>
      <h2>Yeni Elektriksel Test</h2>
      <p className="note" style={{ marginTop: 0 }}>
        Dört testin dördü birden nadiren yapılır; elindeki kadarını gir.
        Sarım oranı girerken <b>kademe pozisyonunu</b> da ver — beklenen
        oran kademeye göre kayar.
      </p>

      {error && <div className="np-problems"><b>{String(error)}</b></div>}

      {/* --- TTR --- */}
      <h3>Sarım Oranı (TTR)</h3>
      <div className="np-grid">
        <div className="field np-field">
          <label>Kademe pozisyonu
            {expected?.tap_min != null && (
              <span className="np-hint"> · {expected.tap_min}…
                {expected.tap_max}</span>)}
          </label>
          <input type="number" step="1" value={values.tap_position ?? ''}
            onChange={set('tap_position')} />
        </div>
        {['a', 'b', 'c'].map((ph) => (
          <div className="field np-field" key={ph}>
            <label>
              {ph.toUpperCase()} fazı
              <LiveDeviation value={values[`ttr_${ph}`]} expected={exp}
                tolerance={tol} />
            </label>
            <input type="number" step="any" value={values[`ttr_${ph}`] ?? ''}
              onChange={set(`ttr_${ph}`)} />
          </div>
        ))}
      </div>

      {exp ? (
        <p className="note el-target">
          Beklenen oran: <b className="num">{exp.toFixed(4)}</b>
          {expected?.vector_group && <> · bağlantı grubu {expected.vector_group}</>}
          {' '}· tolerans ±%{tol}. Değeri yazdıkça sapma yanında görünür.
        </p>
      ) : (
        <p className="note el-target warn">
          Künyede gerilim/bağlantı grubu eksik olduğu için beklenen oran
          hesaplanamıyor. Önce <b>Künye</b> sekmesini doldurun.
        </p>
      )}

      {/* --- Sargı direnci --- */}
      <h3>Sargı Direnci</h3>
      <div className="np-grid">
        {['a', 'b', 'c'].map((ph) => (
          <div className="field np-field" key={ph}>
            <label>{ph.toUpperCase()} fazı<span className="np-hint"> · Ω</span></label>
            <input type="number" step="any" value={values[`rw_${ph}_ohm`] ?? ''}
              onChange={set(`rw_${ph}_ohm`)} />
          </div>
        ))}
        <div className="field np-field">
          <label>Sargı sıcaklığı<span className="np-hint"> · °C · düzeltme için</span></label>
          <input type="number" step="any" value={values.winding_temp_c ?? ''}
            onChange={set('winding_temp_c')} />
        </div>
      </div>

      {/* --- Yalıtım --- */}
      <h3>Yalıtım Direnci</h3>
      <div className="np-grid">
        <div className="field np-field">
          <label>1 dakika<span className="np-hint"> · MΩ</span></label>
          <input type="number" step="any" value={values.ir_1min_mohm ?? ''}
            onChange={set('ir_1min_mohm')} />
        </div>
        <div className="field np-field">
          <label>10 dakika<span className="np-hint"> · MΩ · PI için</span></label>
          <input type="number" step="any" value={values.ir_10min_mohm ?? ''}
            onChange={set('ir_10min_mohm')} />
        </div>
        <div className="field np-field">
          <label>Sıcaklık<span className="np-hint"> · °C</span></label>
          <input type="number" step="any" value={values.insulation_temp_c ?? ''}
            onChange={set('insulation_temp_c')} />
        </div>
      </div>

      {/* --- tan δ --- */}
      <h3>Kayıp Faktörü</h3>
      <div className="np-grid">
        <div className="field np-field">
          <label>tan δ<span className="np-hint"> · %</span></label>
          <input type="number" step="any" value={values.tan_delta_pct ?? ''}
            onChange={set('tan_delta_pct')} />
        </div>
        <div className="field np-field">
          <label>Sıcaklık<span className="np-hint"> · °C · 20 °C tercih edilir</span></label>
          <input type="number" step="any" value={values.tan_delta_temp_c ?? ''}
            onChange={set('tan_delta_temp_c')} />
        </div>
      </div>

      <div className="np-grid" style={{ marginTop: 14 }}>
        <div className="field np-field">
          <label>Test tarihi</label>
          <input type="date" value={meta.tested_at}
            onChange={(e) => setMeta({ ...meta, tested_at: e.target.value })} />
        </div>
        <div className="field np-field">
          <label>Test eden</label>
          <input value={meta.tested_by}
            onChange={(e) => setMeta({ ...meta, tested_by: e.target.value })} />
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

/* --- Panel ------------------------------------------------------------- */

export default function ElectricalPanel({ id }) {
  const [data, setData] = useState(null)
  const [schema, setSchema] = useState(null)
  const [error, setError] = useState(null)
  const [adding, setAdding] = useState(false)

  const load = useCallback(() => {
    setError(null)
    api.electricalTests(id)
      .then(setData)
      .catch((e) => setError(e?.response?.data?.detail || e.message))
  }, [id])

  useEffect(() => { setData(null); load() }, [id, load])
  useEffect(() => {
    api.electricalSchema().then(setSchema).catch(() => setSchema(null))
  }, [])

  if (error) return <div className="panel"><p className="empty">Hata: {error}</p></div>

  if (adding) {
    return (
      <ElectricalTestForm transformerId={id} schema={schema}
        onSaved={() => { setAdding(false); load() }}
        onCancel={() => setAdding(false)} />
    )
  }

  if (!data) return <div className="panel"><p className="empty">Yükleniyor…</p></div>

  const addButton = (
    <button type="button" className="chip" onClick={() => setAdding(true)}>
      + Test gir
    </button>
  )

  if (!data.available) {
    return (
      <div className="panel">
        <div className="np-head">
          <h2>Elektriksel Testler</h2>
          {addButton}
        </div>
        <p className="empty">{data.message}</p>
        <p className="note">
          Bu bir eksiklik işareti değil, olağan durum olabilir: elektriksel
          testler trafo <b>enerjisizken</b> yapılır, yani planlı kesinti
          gerektirir. Tipik olarak devreye alma ve büyük bakımlarda alınır.
          Yine de hiç temel çizgi ölçümü olmaması, ileride bir sapmayı
          neye göre değerlendireceğimizi belirsiz bırakır.
        </p>
      </div>
    )
  }

  const a = data.latest_assessment
  const s = a.sections
  const ctx = a.context
  const latest = data.tests[data.tests.length - 1]

  return (
    <div>
      <div className="panel">
        <div className="np-head">
          <h2>Elektriksel Testler {' '}
            <Badge condition={a.overall} />
          </h2>
          {addButton}
        </div>

        <div className="tmeta">
          <span className="k">Son test</span>
          <span>{fmtDate(latest.tested_at)}
            {latest.tested_by && <span className="muted"> · {latest.tested_by}</span>}
          </span>
          <span className="k">Geçmiş</span><span>{data.n_tests} test</span>
          <span className="k">Anma sarım oranı</span>
          <span className="num">{ctx.rated_turns_ratio ?? '—'}</span>
          <span className="k">Sargı malzemesi</span>
          <span>{ctx.winding_material === 'Al' ? 'Alüminyum' : 'Bakır'}</span>
        </div>

        {a.problems.length > 0 && (
          <div className="np-problems">
            <b>Bulgular</b>
            <ul>{a.problems.map((p) => <li key={p}>{p}</li>)}</ul>
          </div>
        )}

        <p className="note">
          Genel hüküm <b>en kötü bölüme</b> göre verilir, ortalamaya göre
          değil: bir bölümün kötü olması trafoyu riske atmaya yeter,
          diğerlerinin iyiliği bunu telafi etmez.
        </p>
      </div>

      <TurnsRatio section={s.turns_ratio} />
      <WindingResistance section={s.winding_resistance}
        series={data.imbalance_series} />
      <Insulation section={s.insulation} />
      <TanDelta section={s.tan_delta} />
    </div>
  )
}
