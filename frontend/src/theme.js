/**
 * Grafiklerin (Recharts / SVG) okuduğu tasarım belirteçleri.
 *
 * CSS değişkenleri JS'ten okunamadığı için renkler burada bir kez tanımlanır;
 * index.css'teki :root değerleriyle AYNI tutulmalıdır.
 *
 * Paletler dataviz doğrulayıcısından geçirildi (açık zemin):
 *  - SEVERITY: tek hüzmeli sıralı rampa (kehribar→pas), monoton açıklık.
 *  - SERIES:   kategorik palet; renk körlüğünde komşu ayrımı ΔE >= 9.
 */
export const ink = '#1c1a17'
export const inkSoft = '#4a453d'
export const muted = '#7a736a'
export const rule = '#d8d2c6'
export const surface = '#fffdf8'
export const paper = '#f5f2ea'

/** Risk seviyesi -> renk. Sıralı veri olduğu için tek hüzmeli rampa. */
export const SEVERITY = {
  low: '#cda760',
  medium: '#c08a35',
  high: '#a05c1c',
  critical: '#78380f',
}

/** Kategorik seriler (gaz eğrileri, model çubukları). Sabit sırada atanır. */
export const SERIES = ['#1b6ca8', '#4f7a1f', '#8b4a9c', '#0d8a7a']

/** SHAP: katkının yönü — pozitif/negatif. */
export const POSITIVE = '#4f7a1f'
export const NEGATIVE = '#a03828'

/** Recharts eksen/ızgara/ipucu ortak ayarları. */
export const axis = { stroke: rule, tick: { fill: muted, fontSize: 11 } }
export const grid = { stroke: rule, strokeDasharray: '0' }
export const tooltip = {
  contentStyle: {
    background: surface,
    border: `1px solid ${rule}`,
    borderRadius: 2,
    color: ink,
    fontSize: 12,
    fontFamily: "'JetBrains Mono', monospace",
    boxShadow: '0 2px 10px rgba(28,26,23,0.10)',
  },
  labelStyle: { color: muted },
}
