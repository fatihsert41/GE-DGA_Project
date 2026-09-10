import { FAULT_LABELS } from '../constants'

/* Uzman incelemesi şeridi (Faz 6.5).
 * Sistem sadece tahmin etmiyor; ne zaman kendi kararına güvenmediğini de
 * söylüyor. Eşik gerçek veriyle ölçüldü: güven 0.90'ın altındaki
 * tahminlerin doğruluğu %54, üstündekilerin %91. */
function ReviewBanner({ review }) {
  if (!review) return null
  if (!review.needed && !review.severe) return null

  const severeOnly = review.severe && !review.needed
  return (
    <div className={`review-band ${severeOnly ? 'severe' : 'unsure'}`}>
      <span className="review-title">
        {severeOnly ? 'Ciddi arıza sınıfı' : 'Uzman incelemesi öneriliyor'}
      </span>
      <ul>
        {review.severe && (
          <li>Yüksek enerjili ark veya {'>'}700 °C ısınma — doğrulanmalı.</li>
        )}
        {review.reasons.map((r) => <li key={r}>{r}</li>)}
      </ul>
    </div>
  )
}

export default function DiagnosisResult({ result }) {
  if (!result) return null
  const risk = result.risk || {}
  const conf = Math.round((result.confidence || 0) * 100)

  return (
    <div className="panel">
      <h2>Tanı Sonucu</h2>
      <ReviewBanner review={result.review} />
      <div className="result-head">
        <div>
          {/* Aile önce: bakım kararı bu seviyede verilir, alt tip ikincil. */}
          <div className="family-line">{result.prediction_family}</div>
          <div className="big-verdict">
            {FAULT_LABELS[result.prediction] || result.prediction}
          </div>
          <div className="group-tag">Grup: {result.prediction_group}</div>
        </div>
        <span className={`badge ${risk.level}`}>
          Risk: {risk.level_tr} (Kondisyon {risk.condition})
        </span>
        <span className={`agree ${result.agreement ? 'yes' : 'no'}`}>
          {result.source === 'ml'
            ? (result.agreement ? 'ML ↔ Klasik uyumlu' : 'ML ↔ Klasik farklı')
            : 'Klasik yöntem (model eğitilmemiş)'}
        </span>
      </div>

      <div className="kv">
        <span className="k">Model güveni</span><span>%{conf}</span>
        <span className="k">Kaynak</span>
        <span>{result.source === 'ml' ? result.ml?.model_name : 'Klasik konsensüs'}</span>
        <span className="k">Klasik tahmin</span>
        <span>{FAULT_LABELS[result.classical?.prediction] || result.classical?.prediction}
          {' '}(oy: {result.classical?.votes?.join(', ')})</span>
        <span className="k">TDCG</span>
        <span>{Math.round(risk.tdcg || 0)} ppm</span>
        <span className="k">Eşiği aşan gazlar</span>
        <span>{risk.exceeded_gases?.length ? risk.exceeded_gases.join(', ') : '—'}</span>
        <span className="k">Önerilen aksiyon</span><span>{risk.action}</span>
      </div>
    </div>
  )
}
