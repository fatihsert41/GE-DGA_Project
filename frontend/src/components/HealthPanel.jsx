import { useEffect, useState } from 'react'
import api from '../api'

/* Faz 8.5 — Sağlık Endeksi paneli.
 *
 * Tek bir sayı göstermek KOLAY olurdu ama işe yaramazdı: bakımcı "85 puan"
 * gördüğünde ne yapacağını bilemez. Bu yüzden ekran skoru değil, skorun
 * NASIL oluştuğunu anlatır — her boyutun puanı, ağırlığı ve katkısı ayrı
 * satırda, altta da formülün kendisi.
 *
 * Tüm veri tek istekten gelir: GET /transformers/{id}/health
 */

const BAND_CLASS = {
  excellent: 'low',
  good: 'low',
  fair: 'medium',
  poor: 'high',
  critical: 'critical',
}

const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('tr-TR',
    { day: 'numeric', month: 'short', year: 'numeric' }) : '—'

/** Skoru bir kadranda değil, yatay ölçekte gösteriyoruz: bant sınırları
 *  ölçeğin üstünde işaretli olduğu için "85 iyi mi kötü mü?" sorusu
 *  açıklama okumadan cevaplanıyor. */
function ScoreGauge({ score, band, bandTr }) {
  return (
    <div className="hi-gauge">
      <div className="hi-score">
        <b className={`hi-number ${BAND_CLASS[band] || 'medium'}`}>{score}</b>
        <span className="hi-outof">/ 100</span>
        <span className={`badge ${BAND_CLASS[band] || 'medium'}`}>{bandTr}</span>
      </div>
      <div className="hi-scale" role="img"
        aria-label={`Sağlık endeksi ${score} / 100`}>
        <span className="hi-fill" style={{ width: `${Math.max(0, Math.min(100, score))}%` }} />
        {[30, 50, 70, 85].map((tick) => (
          <span key={tick} className="hi-tick" style={{ left: `${tick}%` }} />
        ))}
      </div>
      <div className="hi-scale-legend">
        <span>0 · Kritik</span><span>30 · Kötü</span><span>50 · Orta</span>
        <span>70 · İyi</span><span>85 · Çok İyi</span>
      </div>
    </div>
  )
}

/** Boyut dökümü: skorun aritmetiği satır satır. */
function DimensionTable({ dimensions, weightSum, weightedSum, rawScore }) {
  return (
    <table className="compare hi-table">
      <thead>
        <tr>
          <th>Boyut</th><th>Ölçüm</th><th>Puan</th>
          <th>Ağırlık</th><th>Katkı</th>
        </tr>
      </thead>
      <tbody>
        {dimensions.map((d) => (
          <tr key={d.key} className={d.available ? '' : 'hi-missing'}>
            <td>
              <b>{d.label}</b>
              <div className="muted hi-source">{d.source}</div>
            </td>
            <td>{d.available
              ? d.detail
              : <span className="muted">ölçüm yok — {d.reason}</span>}</td>
            <td>{d.available ? d.score : '—'}</td>
            <td className="muted">×{d.weight}</td>
            <td>{d.available ? d.contribution : '—'}</td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <td colSpan={3}><b>Toplam</b></td>
          <td className="muted">{weightSum}</td>
          <td><b>{weightedSum}</b></td>
        </tr>
        <tr>
          <td colSpan={5} className="hi-formula">
            {weightedSum} ÷ {weightSum} = <b>{rawScore}</b>
            <span className="muted"> · ağırlıklı ortalama</span>
          </td>
        </tr>
      </tfoot>
    </table>
  )
}

export default function HealthPanel({ id }) {
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setData(null); setError(null)
    api.transformerHealth(id)
      .then(setData)
      .catch((e) => setError(e?.response?.data?.detail || e.message))
  }, [id])

  if (error) return <div className="panel"><p className="empty">Hata: {error}</p></div>
  if (!data) return <div className="panel"><p className="empty">Yükleniyor…</p></div>

  const h = data.health
  const s = data.sources

  if (!h.available) {
    return (
      <div className="panel">
        <h2>Sağlık Endeksi</h2>
        <p className="empty">{h.message}</p>
      </div>
    )
  }

  return (
    <div>
      <div className="panel">
        <h2>Sağlık Endeksi</h2>
        <ScoreGauge score={h.score} band={h.band} bandTr={h.band_tr} />
        <p className="hi-action">{h.action}</p>

        {/* Tek sayı hikâyeyi gizler; skoru en çok aşağı çeken boyut
            skorun HEMEN yanında dursun. */}
        <div className="hi-weakest">
          <span className="k">Skoru çeken boyut</span>
          <b>{h.weakest.label}</b>
          <span className="muted"> · {h.weakest.detail} · {h.weakest.score} puan</span>
        </div>

        {h.capped && (
          <div className="hi-note warn">
            <b>Tavan uygulandı.</b> Ağırlıklı ortalama {h.raw_score} çıktı,
            ancak <b>{h.critical_dimensions.join(', ')}</b> boyutu en kötü
            seviyesinde olduğu için skor {h.cap} ile sınırlandı. Gerekçe:
            iyi durumdaki boyutların kritik bir boyutu gizlemesine izin
            verilmemeli.
          </div>
        )}

        {h.coverage.level !== 'full' && (
          <div className="hi-note">
            <b>Eksik veri.</b> {h.coverage.note} Skor {h.coverage.measured}/
            {h.coverage.total} boyuta dayanıyor (ağırlığın %
            {Math.round(h.coverage.weight_ratio * 100)}'i). Eksik boyut
            "sağlıklı" sayılmadı, ortalamadan çıkarıldı.
          </div>
        )}

        {h.warnings?.filter((w) => !w.startsWith('Skor eksik')).map((w) => (
          <div key={w} className="hi-note warn">{w}</div>
        ))}
      </div>

      <div className="panel">
        <h2>Skor Nasıl Oluştu?</h2>
        <DimensionTable dimensions={h.dimensions} weightSum={h.weight_sum}
          weightedSum={h.weighted_sum} rawScore={h.raw_score} />
        <p className="note">
          Ağırlıklar boyutun önemini yansıtır: <b>DGA</b> en ağır çünkü
          aktif, gelişmekte olan arızayı gösteren tek boyut o.
          <b> Kağıt</b> ikinci çünkü bozunması geri dönüşsüz — trafonun ömrü
          kağıdın ömrüdür. <b>Yağ</b> en hafif çünkü kötü yağ ciddidir ama
          yağ filtrelenebilir, hatta değiştirilebilir.
        </p>
      </div>

      <div className="panel">
        <h2>Skorun Dayandığı Ölçümler</h2>
        <div className="tmeta hi-sources">
          <span className="k">Son DGA</span>
          <span>{fmtDate(s.dga_sampled_at)}
            {s.dga_prediction && <span className="muted"> · {s.dga_prediction}</span>}
          </span>
          <span className="k">Son yağ testi</span>
          <span>{fmtDate(s.oil_sampled_at)}</span>
          <span className="k">Geçmiş</span>
          <span>{s.measurement_count} DGA · {s.oil_test_count} yağ testi</span>
          {h.renewal_priority != null && (
            <>
              <span className="k">Yenileme önceliği</span>
              <span title={`(100 − ${h.score}) ÷ 100 × varlık ağırlığı ${h.asset_weight}`}>
                <b>{h.renewal_priority.toFixed(3)}</b>
                <span className="muted"> · {data.asset_class}</span>
              </span>
            </>
          )}
        </div>
        <p className="note">
          Filo listesindeki <b>öncelik</b> ACİLİYETİ ölçer (bugün kime
          koşayım — DGA kondisyonu × varlık ağırlığı). Buradaki
          <b> yenileme önceliği</b> ise DURUMU ölçer (bu yıl hangi ünitenin
          bütçesini ayırayım). Aynı trafo birinde üstte, diğerinde altta
          olabilir; ikisi farklı sorulara cevap verir.
        </p>
      </div>
    </div>
  )
}
