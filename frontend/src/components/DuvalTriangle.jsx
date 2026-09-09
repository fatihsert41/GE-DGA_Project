// Duval Triangle 1 rendered as SVG. The backend returns the sample's
import { muted, ink, rule, surface, SERIES } from '../theme'
// barycentric point in a unit triangle (CH4 at origin, C2H4 right, C2H2 top);
// we map it into SVG space and mark it. Zone labels sit at their regions.
const W = 360
const H = 320
const PAD = 30

// Unit-triangle vertices used by the backend (x in [0,1], y in [0,0.866]).
const toSvg = (x, y) => {
  const px = PAD + x * (W - 2 * PAD)
  const py = H - PAD - y * (W - 2 * PAD) // scale by width, flip vertical
  return [px, py]
}

const V_CH4 = toSvg(0, 0)
const V_C2H4 = toSvg(1, 0)
const V_C2H2 = toSvg(0.5, Math.sqrt(3) / 2)

// Approximate label anchor points (barycentric-ish) for each zone.
const ZONE_LABELS = [
  { z: 'PD', x: 0.5, y: 0.78 },
  { z: 'D2', x: 0.62, y: 0.42 },
  { z: 'D1', x: 0.34, y: 0.30 },
  { z: 'T3', x: 0.80, y: 0.08 },
  { z: 'T2', x: 0.55, y: 0.06 },
  { z: 'T1', x: 0.20, y: 0.06 },
]

export default function DuvalTriangle({ duval }) {
  if (!duval || !duval.applicable) {
    return <p className="empty">Duval üçgeni için geçerli gaz verisi gerekli.</p>
  }
  const pt = toSvg(duval.point.x, duval.point.y)
  const pct = duval.percentages

  return (
    <div>
      <p className="muted" style={{ fontSize: '0.85rem' }}>
        Duval Üçgeni 1 bölgesi: <b>{duval.zone}</b>
      </p>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: 380 }}>
        <polygon
          points={`${V_CH4.join(',')} ${V_C2H4.join(',')} ${V_C2H2.join(',')}`}
          fill={surface} stroke={rule} strokeWidth="1" />
        {ZONE_LABELS.map((l) => {
          const [lx, ly] = toSvg(l.x, l.y)
          return (
            <text key={l.z} x={lx} y={ly} fill={muted} fontSize="12"
              textAnchor="middle"
              fontWeight={l.z === duval.zone ? 700 : 400}
              opacity={l.z === duval.zone ? 1 : 0.6}>{l.z}</text>
          )
        })}
        {/* sample point */}
        <circle cx={pt[0]} cy={pt[1]} r="6" fill={SERIES[0]}
          stroke={surface} strokeWidth="2" />
        {/* axis labels */}
        <text x={V_CH4[0] - 6} y={V_CH4[1] + 16} fill={ink} fontSize="11"
          textAnchor="middle">CH₄</text>
        <text x={V_C2H4[0] + 6} y={V_C2H4[1] + 16} fill={ink} fontSize="11"
          textAnchor="middle">C₂H₄</text>
        <text x={V_C2H2[0]} y={V_C2H2[1] - 8} fill={ink} fontSize="11"
          textAnchor="middle">C₂H₂</text>
      </svg>
      <div className="kv">
        <span className="k">%CH₄</span><span>{pct.CH4.toFixed(1)}</span>
        <span className="k">%C₂H₄</span><span>{pct.C2H4.toFixed(1)}</span>
        <span className="k">%C₂H₂</span><span>{pct.C2H2.toFixed(1)}</span>
      </div>
    </div>
  )
}
