import { useCallback, useEffect, useState } from 'react'
import api from '../api'

/* Faz 9.6 — Trafo şeması.
 *
 * Faz 9'un başındaki analizde bu ekran ERTELENMİŞTİ, gerekçesiyle:
 * "bileşen verisi yoksa şema boş bir çizim olur." Faz 9.4 (buşing,
 * kademe) ve 9.5 (saha gözlemi) tamamlandıktan sonra her parçanın
 * arkasında gerçek bir ölçüm var — şema artık veri gösteriyor.
 *
 * İKİ KURAL:
 *
 * 1. Renk TEK BAŞINA anlam taşımaz. Her parçanın yanında durumu yazılı,
 *    altta da tam bir liste var. Renk körlüğü olan biri için şema
 *    bilgi kaybı olmamalı.
 *
 * 2. Her parça TIKLANABİLİR ve ölçümüne götürür. Tıklanamayan bir
 *    şema dekordur; "burası kırmızı" demek yetmez, "neden kırmızı"
 *    sorusunun cevabına ulaşılabilmeli.
 */

const COND_FILL = {
  'iyi': 'var(--low)',
  'kabul': 'var(--medium)',
  'kötü': 'var(--critical)',
  'bilinmiyor': 'var(--surface-2)',
  'yok': 'var(--surface-2)',
}

const COND_TEXT = {
  'iyi': '#241a08',
  'kabul': '#1c1205',
  'kötü': '#fffdf8',
  'bilinmiyor': 'var(--muted)',
  'yok': 'var(--muted)',
}

const COND_CLASS = {
  'iyi': 'low', 'kabul': 'medium', 'kötü': 'critical',
  'bilinmiyor': '', 'yok': '',
}

export default function SchematicPanel({ id, onOpenTab }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [focus, setFocus] = useState(null)

  const load = useCallback(() => {
    api.schematic(id)
      .then(setData)
      .catch((e) => setError(e?.response?.data?.detail || e.message))
  }, [id])

  useEffect(() => { setData(null); setFocus(null); load() }, [id, load])

  if (error) return <div className="panel"><p className="empty">Hata: {error}</p></div>
  if (!data) return <div className="panel"><p className="empty">Yükleniyor…</p></div>

  const part = (code) => data.parts.find((p) => p.code === code)
  const fill = (code) => COND_FILL[part(code)?.condition] || COND_FILL.bilinmiyor
  const stroke = (code) =>
    focus === code ? 'var(--ink)' : 'var(--rule-strong)'
  const width = (code) => (focus === code ? 2.5 : 1.2)

  /** Tıklanabilir parça sarmalayıcısı. */
  const Part = ({ code, children }) => {
    const p = part(code)
    if (!p) return null
    return (
      <g className="sch-part" role="button" tabIndex={0}
        aria-label={`${p.label}: ${p.condition}`}
        onMouseEnter={() => setFocus(code)}
        onMouseLeave={() => setFocus(null)}
        onFocus={() => setFocus(code)}
        onBlur={() => setFocus(null)}
        onClick={() => onOpenTab?.(p.tab)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault(); onOpenTab?.(p.tab)
          }
        }}>
        <title>{`${p.label} — ${p.condition}\n${p.source}: ${p.detail || ''}`}</title>
        {children}
      </g>
    )
  }

  const label = (x, y, text, code, anchor = 'middle') => (
    <text x={x} y={y} textAnchor={anchor} className="sch-label"
      fill={code && part(code)?.condition === 'kötü'
        ? COND_TEXT['kötü'] : 'var(--ink)'}>
      {text}
    </text>
  )

  return (
    <div>
      <div className="panel">
        <h2>Trafo Şeması</h2>
        <p className="note" style={{ marginTop: 0 }}>
          Her parçanın rengi bir <b>ölçümden</b> gelir. Üzerine gelince
          kaynağı görünür, tıklayınca o ölçümün sekmesi açılır —
          "burası kırmızı" demek yetmez, <b>neden</b> kırmızı olduğuna
          ulaşılabilmeli.
        </p>

        <div className="sch-wrap">
          <svg viewBox="0 0 620 400" className="sch-svg"
            role="img" aria-label="Trafo şeması">

            {/* --- Buşingler (YG tarafı) ------------------------------ */}
            {[['bushing_a', 150, 'A'], ['bushing_b', 250, 'B'],
              ['bushing_c', 350, 'C']].map(([code, x, ph]) => (
              <Part code={code} key={code}>
                {/* Porselen etekler */}
                {[0, 1, 2].map((i) => (
                  <ellipse key={i} cx={x} cy={70 + i * 18} rx={22 - i * 2}
                    ry={6} fill={fill(code)} stroke={stroke(code)}
                    strokeWidth={width(code)} />
                ))}
                <rect x={x - 6} y={40} width={12} height={30}
                  fill={fill(code)} stroke={stroke(code)}
                  strokeWidth={width(code)} />
                {label(x, 34, ph, code)}
              </Part>
            ))}

            {/* --- Konservatör + nem alıcı ----------------------------- */}
            <Part code="conservator">
              <rect x={440} y={52} width={110} height={34} rx={17}
                fill={fill('conservator')} stroke={stroke('conservator')}
                strokeWidth={width('conservator')} />
              <rect x={486} y={86} width={10} height={26}
                fill={fill('conservator')} stroke={stroke('conservator')}
                strokeWidth={width('conservator')} />
              {label(495, 44, 'Konservatör')}
            </Part>

            {/* --- Koruma (Buchholz) ---------------------------------- */}
            <Part code="protection">
              <circle cx={412} cy={104} r={15}
                fill={fill('protection')} stroke={stroke('protection')}
                strokeWidth={width('protection')} />
              {label(412, 138, 'Koruma')}
            </Part>

            {/* --- Tank ------------------------------------------------ */}
            <Part code="tank">
              <rect x={120} y={120} width={300} height={200} rx={8}
                fill={fill('tank')} stroke={stroke('tank')}
                strokeWidth={width('tank')} opacity={0.35} />
            </Part>

            {/* --- Yağ (tank dolgusu) --------------------------------- */}
            <Part code="oil">
              <rect x={132} y={150} width={276} height={158} rx={5}
                fill={fill('oil')} stroke={stroke('oil')}
                strokeWidth={width('oil')} opacity={0.55} />
              {label(390, 316, 'Yağ', 'oil', 'end')}
            </Part>

            {/* --- Sargılar (aktif kısım) ----------------------------- */}
            <Part code="windings">
              {[178, 250, 322].map((x) => (
                <rect key={x} x={x - 24} y={168} width={48} height={110}
                  rx={4} fill={fill('windings')} stroke={stroke('windings')}
                  strokeWidth={width('windings')} />
              ))}
              {label(250, 160, 'Sargılar', 'windings')}
            </Part>

            {/* --- Kağıt yalıtım (sargı çevresi) ---------------------- */}
            <Part code="paper">
              {[178, 250, 322].map((x) => (
                <rect key={x} x={x - 30} y={162} width={60} height={122}
                  rx={6} fill="none" stroke={fill('paper')}
                  strokeWidth={focus === 'paper' ? 6 : 4} />
              ))}
              {label(250, 298, 'Kağıt yalıtım', 'paper')}
            </Part>

            {/* --- Kademe değiştirici --------------------------------- */}
            <Part code="oltc">
              <rect x={424} y={180} width={62} height={90} rx={6}
                fill={fill('oltc')} stroke={stroke('oltc')}
                strokeWidth={width('oltc')} />
              {label(455, 172, 'Kademe')}
            </Part>

            {/* --- Radyatörler ---------------------------------------- */}
            <Part code="cooling">
              {[0, 1, 2, 3, 4].map((i) => (
                <rect key={i} x={50 + i * 13} y={170} width={9} height={120}
                  rx={3} fill={fill('cooling')} stroke={stroke('cooling')}
                  strokeWidth={width('cooling')} />
              ))}
              {label(82, 162, 'Radyatör')}
              {/* Fan */}
              <circle cx={82} cy={306} r={13} fill={fill('cooling')}
                stroke={stroke('cooling')} strokeWidth={width('cooling')} />
              {label(82, 334, 'Fan')}
            </Part>

            {/* Zemin çizgisi */}
            <line x1={40} y1={348} x2={580} y2={348}
              stroke="var(--rule-strong)" strokeWidth={2} />
          </svg>
        </div>

        {/* Renk tek başına anlam taşımasın: açık lejant. */}
        <div className="risk-legend sch-legend">
          {['iyi', 'kabul', 'kötü', 'bilinmiyor'].map((c) => (
            <span key={c}>
              <i className={`dot ${COND_CLASS[c]}`}
                style={c === 'bilinmiyor'
                  ? { background: 'var(--surface-2)',
                      border: '1px solid var(--rule-strong)' }
                  : undefined} />
              {c === 'bilinmiyor' ? 'ölçüm yok' : c}
            </span>
          ))}
        </div>

        {data.summary.bad > 0 && (
          <div className="np-problems" style={{ marginTop: 14 }}>
            <b>Sorunlu parçalar</b>
            <ul>{data.summary.bad_parts.map((p) => <li key={p}>{p}</li>)}</ul>
          </div>
        )}
      </div>

      <div className="panel">
        <h2>Parça Durumları</h2>
        <div className="table-scroll">
          <table className="compare">
            <thead>
              <tr><th>Parça</th><th>Durum</th><th>Kaynak</th><th>Ayrıntı</th></tr>
            </thead>
            <tbody>
              {data.parts.map((p) => (
                <tr key={p.code}
                  className={focus === p.code ? 'selected' : ''}
                  onMouseEnter={() => setFocus(p.code)}
                  onMouseLeave={() => setFocus(null)}>
                  <td>
                    <button type="button" className="link-like"
                      onClick={() => onOpenTab?.(p.tab)}>
                      <b>{p.label}</b>
                    </button>
                  </td>
                  <td>
                    <span className={`badge sm ${COND_CLASS[p.condition] || ''}`}>
                      {p.condition}
                    </span>
                  </td>
                  <td className="muted">{p.source}</td>
                  <td className="muted insp-why">{p.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="note">
          Şema <b>ölçüm üretmez</b>, ölçümleri bir araya getirir. Her
          satırın kaynağı ayrı bir sekmede ölçülüyor: buşingler bileşen
          testinde, sargılar gaz analizinde, radyatör ve koruma saha
          gözleminde. Şemanın değeri, bunların hepsini aynı anda tek
          bakışta göstermesi.
        </p>
      </div>
    </div>
  )
}
