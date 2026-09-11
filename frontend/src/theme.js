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
// Faz 9.7: nötr yüzeyler soğuk griye çevrildi (kurumsal görünüm).
// Risk rampası ve seri paleti DEĞİŞMEDİ — renk körlüğü doğrulamasından
// geçmişlerdi; görsel moda için doğrulanmış bir paleti bozmak yanlış olur.
export const ink = '#16191d'
export const inkSoft = '#3d454e'
export const muted = '#6b757f'
export const rule = '#d3d8de'
export const surface = '#ffffff'
export const paper = '#eceef1'

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
    boxShadow: '0 2px 10px rgba(22,25,29,0.12)',
  },
  labelStyle: { color: muted },
}
