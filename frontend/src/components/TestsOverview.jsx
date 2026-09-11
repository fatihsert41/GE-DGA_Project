import { useEffect, useState } from 'react'
import api from '../api'

/* Faz 8.6 — Filo geneli test durumu.
 *
 * NEDEN AYRI BİR EKRAN?
 * Trafo detayındaki sekmeler "bu trafo ne durumda?" sorusunu cevaplıyor.
 * Ama bakım planlamacısının bir sorusu daha var: **"nerede eksiğim?"**
 *
 * Bu ekran onu cevaplıyor. En önemli sütunu bulgular değil, BOŞLUKLAR:
 * hiç test edilmemiş varlıklar, eksik bırakılmış bölümler. Bir arıza
 * bulgusu zaten görünürdür; görünmeyen şey, hiç bakılmamış olandır.
 */

const CONDITION_CLASS = {
  'iyi': 'low', 'kabul': 'medium', 'kötü': 'critical', 'bilinmiyor': '',
}

const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('tr-TR',
    { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

const daysSince = (iso) => {
  if (!iso) return null
  const d = Math.floor((Date.now() - new Date(iso).getTime()) / 86400000)
  return Number.isFinite(d) ? d : null
}

const Badge = ({ condition }) => (
  <span className={`badge sm ${CONDITION_CLASS[condition] || ''}`}>
    {condition || 'bilinmiyor'}
  </span>
)

function Tile({ label, value, hint, tone }) {
  return (
    <div className={`kpi${tone ? ` ${tone}` : ''}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {hint && <div className="kpi-hint">{hint}</div>}
    </div>
  )
}

/** Tek bir test türünün filo geneli tablosu. */
function TestTable({ rows, onSelect, dateKey, extraLabel, extraKey }) {
  if (!rows.length) {
    return <p className="empty">Bu türde kayıt yok.</p>
  }
  return (
    <table className="compare">
      <thead>
        <tr>
          <th>Trafo</th><th>Son test</th><th>Yaş</th>
          <th>Hüküm</th>{extraLabel && <th>{extraLabel}</th>}<th>Bulgu</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => {
          const age = daysSince(r[dateKey])
          return (
            <tr key={r.transformer_id}>
              <td>
                <button type="button" className="link-like"
                  onClick={() => onSelect?.(r.transformer_id)}>
                  <b>{r.transformer_id}</b>
                </button>
              </td>
              <td>{fmtDate(r[dateKey])}</td>
              <td className="muted num">
                {age == null ? '—'
                  : age > 730 ? <b className="over-limit">{Math.round(age / 365)} yıl</b>
                    : age > 365 ? `${Math.round(age / 365)} yıl`
                      : `${Math.round(age / 30)} ay`}
              </td>
              <td><Badge condition={r.overall} /></td>
              {extraLabel && <td className="muted">{r[extraKey] ?? '—'}</td>}
              <td className="muted el-finding">
                {r.problems?.length ? r.problems[0] : 'bulgu yok'}
              </td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

export default function TestsOverview({ onSelect }) {
  const [electrical, setElectrical] = useState(null)
  const [oil, setOil] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([api.electricalFleet(), api.oilFleet()])
      .then(([e, o]) => { setElectrical(e); setOil(o) })
      .catch((err) => setError(err?.response?.data?.detail || err.message))
  }, [])

  if (error) {
    return <div className="panel"><b>Test verisi alınamadı:</b> {error}</div>
  }
  if (!electrical || !oil) {
    return <div className="panel"><p className="empty">Yükleniyor…</p></div>
  }

  const elCounts = electrical.condition_counts || {}
  const oilCounts = oil.condition_counts || {}
  const neverTested = electrical.never_tested || []

  return (
    <div>
      <div className="panel">
        <h2>Filo Geneli Test Durumu</h2>
        <p className="note" style={{ marginTop: 0 }}>
          Bu ekran "hangi trafo bozuk?" sorusundan çok <b>"nerede
          eksiğim?"</b> sorusunu cevaplar. Bir arıza bulgusu zaten
          görünürdür; asıl risk, hiç bakılmamış olandır.
        </p>

        <div className="kpis">
          <Tile label="Elektriksel test" value={electrical.tested}
            hint="test edilmiş varlık" />
          <Tile label="Hiç test edilmemiş" value={neverTested.length}
            hint="temel çizgi yok"
            tone={neverTested.length ? 'alert' : ''} />
          <Tile label="Elektriksel bulgu" value={elCounts['kötü'] || 0}
            hint="hüküm: kötü"
            tone={elCounts['kötü'] ? 'danger' : ''} />
          <Tile label="Yağ testi" value={oil.tested}
            hint="test edilmiş varlık" />
          <Tile label="Yağ bulgusu" value={oilCounts['kötü'] || 0}
            hint="hüküm: kötü"
            tone={oilCounts['kötü'] ? 'danger' : ''} />
        </div>
      </div>

      {neverTested.length > 0 && (
        <div className="panel">
          <h2>Elektriksel Testi Hiç Yapılmamış Varlıklar
            <span className="count-pill">{neverTested.length}</span>
          </h2>
          <div className="chips">
            {neverTested.map((id) => (
              <button key={id} type="button" className="chip"
                onClick={() => onSelect?.(id)}>{id}</button>
            ))}
          </div>
          <p className="note">
            Bu bir kusur değil, bir <b>boşluk</b>: elektriksel testler
            trafo enerjisizken yapılır, yani planlı kesinti gerektirir ve
            seyrek alınır. Ama hiç <b>temel çizgi</b> ölçümü yoksa,
            ileride bulunan bir sapmayı neye göre değerlendireceğimiz
            belirsiz kalır — "hep böyleydi" ile "yeni gelişti" arasındaki
            farkı ancak geçmiş söyler.
          </p>
        </div>
      )}

      <div className="panel">
        <h2>Elektriksel Testler</h2>
        <TestTable rows={electrical.items} onSelect={onSelect}
          dateKey="tested_at" extraLabel="Bölüm"
          extraKey="sections_measured" />
        <p className="note">
          "Bölüm" sütunu dört testten kaçının yapıldığını gösterir
          (TTR · sargı direnci · yalıtım direnci/PI · tan δ). Dördü birden
          nadiren yapılır; eksik bölüm hüküm verilmeyen alandır.
        </p>
      </div>

      <div className="panel">
        <h2>Yağ Kalitesi Testleri</h2>
        <TestTable rows={oil.items} onSelect={onSelect}
          dateKey="sampled_at" extraLabel="Kağıt DP"
          extraKey="dp_estimate" />
      </div>

      {oil.most_aged_paper?.length > 0 && (
        <div className="panel">
          <h2>En Yaşlı Kağıtlar</h2>
          <table className="compare">
            <thead>
              <tr><th>Trafo</th><th>DP</th><th>Bant</th>
                <th>Tüketilen ömür</th></tr>
            </thead>
            <tbody>
              {oil.most_aged_paper.map((r) => (
                <tr key={r.transformer_id}>
                  <td>
                    <button type="button" className="link-like"
                      onClick={() => onSelect?.(r.transformer_id)}>
                      <b>{r.transformer_id}</b>
                    </button>
                  </td>
                  <td className="num">{r.dp_estimate}</td>
                  <td>{r.paper_band}</td>
                  <td className="num">%{Math.round(r.life_consumed_pct)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="note">
            Kağıt bozunması geri dönüşsüzdür: yağ değiştirilebilir, kağıt
            değiştirilemez. Bu liste bakım değil, <b>yenileme</b>{' '}
            planlamasının girdisidir.
          </p>
        </div>
      )}
    </div>
  )
}
