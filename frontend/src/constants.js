export const GASES = ['H2', 'CH4', 'C2H6', 'C2H4', 'C2H2', 'CO', 'CO2']

export const GAS_LABELS = {
  H2: 'Hidrojen (H₂)',
  CH4: 'Metan (CH₄)',
  C2H6: 'Etan (C₂H₆)',
  C2H4: 'Etilen (C₂H₄)',
  C2H2: 'Asetilen (C₂H₂)',
  CO: 'Karbonmonoksit (CO)',
  CO2: 'Karbondioksit (CO₂)',
}

export const FAULT_LABELS = {
  Normal: 'Normal (arıza yok)',
  PD: 'Kısmi Deşarj',
  D1: 'Düşük Enerjili Deşarj',
  D2: 'Yüksek Enerjili Deşarj (Ark)',
  T1: 'Termal Arıza (< 300 °C)',
  T2: 'Termal Arıza (300-700 °C)',
  T3: 'Termal Arıza (> 700 °C)',
}

// Illustrative readings for quick demoing (typical of each fault type).
export const PRESETS = {
  Normal: { H2: 15, CH4: 10, C2H6: 8, C2H4: 6, C2H2: 0.3, CO: 250, CO2: 2000 },
  'Kısmi Deşarj': { H2: 420, CH4: 65, C2H6: 15, C2H4: 8, C2H2: 1, CO: 300, CO2: 2500 },
  'Ark (D2)': { H2: 280, CH4: 120, C2H6: 40, C2H4: 220, C2H2: 240, CO: 500, CO2: 3200 },
  'Termal T3': { H2: 120, CH4: 200, C2H6: 70, C2H4: 520, C2H2: 4, CO: 450, CO2: 3300 },
}

// Risk seviyesi -> Türkçe etiket. Backend'deki core/risk.py::RISK_LEVELS_TR
// ile aynı tutulmalı.
export const RISK_TR = {
  low: 'Düşük', medium: 'Orta', high: 'Yüksek', critical: 'Kritik',
}

// Şiddet sırası: en kötü önce. Risk çubuğunun segment sırası da budur.
export const RISK_ORDER = ['critical', 'high', 'medium', 'low']
