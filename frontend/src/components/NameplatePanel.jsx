import { useCallback, useEffect, useState } from 'react'
import api from '../api'
import NameplateForm from './NameplateForm'

/* Faz 8.2 — Künye görüntüleme paneli.
 *
 * Trafo detay sayfasında "Künye" sekmesi olarak açılır. Görüntüleme ve
 * düzenleme aynı bileşende: kullanıcı "Düzenle"ye basınca form yerine geçer,
 * kaydedince geri döner. Ayrı sayfaya gitmek bağlamı kaybettirirdi.
 */

const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString('tr-TR',
    { day: 'numeric', month: 'long', year: 'numeric' }) : '—'

const val = (v, suffix = '') =>
  v === null || v === undefined || v === '' ? '—' : `${v}${suffix}`

function Row({ label, children, hint }) {
  return (
    <>
      <span className="k">{label}</span>
      <span>
        {children}
        {hint && <div className="np-rowhint">{hint}</div>}
      </span>
    </>
  )
}

export default function NameplatePanel({ id }) {
  const [record, setRecord] = useState(null)
  const [editing, setEditing] = useState(false)
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    setError(null)
    api.transformer(id)
      .then(setRecord)
      .catch((e) => setError(e?.response?.data?.detail || e.message))
  }, [id])

  useEffect(() => { load() }, [load])

  if (error) {
    return <div className="panel"><p className="empty">Künye alınamadı: {error}</p></div>
  }
  if (!record) {
    return <div className="panel"><p className="empty">Yükleniyor…</p></div>
  }

  if (editing) {
    return (
      <NameplateForm mode="edit" transformer={record}
        onCancel={() => setEditing(false)}
        onSaved={() => { setEditing(false); load() }} />
    )
  }

  const np = record.nameplate || {}
  const d = record.derived || {}

  // Künyenin ne kadarı dolu? Eksik veri sessizce durmasın — sonraki
  // modüller (termal model, sarım oranı) eksik alanlarda çalışamaz.
  const total = Object.keys(np).length
  const filled = Object.values(np).filter(
    (v) => v !== null && v !== undefined && v !== '').length
  const completeness = Math.round((filled / total) * 100)

  return (
    <div className="panel">
      <div className="np-head">
        <h2>Künye</h2>
        <span className={`np-completeness${completeness < 60 ? ' low' : ''}`}>
          %{completeness} dolu ({filled}/{total})
        </span>
        <button type="button" className="chip" onClick={() => setEditing(true)}>
          Düzenle
        </button>
      </div>

      <div className="np-view">
        <div>
          <h3>Kimlik</h3>
          <div className="kv">
            <Row label="Üretici">{val(np.manufacturer)}</Row>
            <Row label="Seri no">{val(np.serial_no)}</Row>
            <Row label="Üretim yılı">{val(np.year_made)}</Row>
            <Row label="Devreye alma">{fmtDate(np.commissioned_at)}</Row>
            <Row label="Yaş">
              {d.age_years !== null && d.age_years !== undefined
                ? <b>{d.age_years} yıl</b> : '—'}
            </Row>
          </div>
        </div>

        <div>
          <h3>Güç ve gerilim</h3>
          <div className="kv">
            <Row label="Varlık sınıfı">
              <b>{record.asset_class}</b>
            </Row>
            <Row label="Anma gücü">{val(record.mva, ' MVA')}</Row>
            <Row label="Gerilim">
              {np.hv_kv && np.lv_kv ? `${np.hv_kv} / ${np.lv_kv} kV` : '—'}
            </Row>
            <Row label="Bağlantı grubu">{val(np.vector_group)}</Row>
            <Row label="Beklenen sarım oranı"
              hint="sarım oranı (TTR) testinin referans değeri">
              {d.rated_turns_ratio
                ? <b className="mono">{d.rated_turns_ratio}</b> : '—'}
            </Row>
          </div>
        </div>

        <div>
          <h3>Tasarım</h3>
          <div className="kv">
            <Row label="Soğutma">
              {np.cooling ? `${np.cooling}` : '—'}
              {d.cooling_label && <div className="np-rowhint">{d.cooling_label}</div>}
            </Row>
            <Row label="Yağ hacmi">
              {np.oil_volume_l ? `${np.oil_volume_l.toLocaleString('tr-TR')} L` : '—'}
            </Row>
            <Row label="Sargı">{val(np.winding_material)}</Row>
            <Row label="Yalıtım">{val(d.insulation_label)}</Row>
          </div>
        </div>

        <div>
          <h3>Kademe değiştirici</h3>
          <div className="kv">
            <Row label="Tip">{val(d.tap_changer_label)}</Row>
            <Row label="Aralık">
              {np.tap_min !== null && np.tap_max !== null
                ? `${np.tap_min} … +${np.tap_max}` : '—'}
            </Row>
            <Row label="Adım">{val(np.tap_step_percent, ' %')}</Row>
          </div>
        </div>
      </div>

      {np.notes && <p className="note"><b>Not:</b> {np.notes}</p>}

      {completeness < 100 && (
        <p className="note">
          Eksik alanlar sonraki tanı modüllerini sınırlar: termal model
          soğutma tipini, sarım oranı testi bağlantı grubunu, kağıt yaşlanma
          hesabı devreye alma tarihini ister.
        </p>
      )}
    </div>
  )
}
