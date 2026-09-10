import { useEffect, useMemo, useState } from 'react'
import api from '../api'

/* Faz 8.2 — Trafo künyesi giriş formu.
 *
 * İki kipte çalışır:
 *   mode="create" → yeni trafo (id, ad, konum da istenir)
 *   mode="edit"   → mevcut trafonun künyesi (kimlik alanları kilitli)
 *
 * Tasarım ilkeleri:
 *  1. Alanlar ANLAMLI GRUPLARA bölünür. 20 alanı tek sütunda alt alta
 *     dizmek formu doldurulamaz yapar.
 *  2. Her alanın BİRİMİ etiketinde yazar (kV, MVA, litre, °C). Birimi
 *     tahmin ettirmek veri girişindeki en yaygın hata kaynağıdır.
 *  3. Türetilen değerler CANLI gösterilir: gerilim ve bağlantı grubunu
 *     girerken beklenen sarım oranı anında hesaplanır. Kullanıcı yanlış
 *     bağlantı grubu seçtiğini oracıkta anlar.
 *  4. Doğrulama hem burada hem sunucuda. Buradaki hızlı geri bildirim
 *     içindir; GÜVENİLİR olan sunucudaki (istemci kodu atlanabilir).
 */

// Bağlantı grubunun faz-faz oranına etkisi. Backend'deki
// core/nameplate.VECTOR_GROUPS ile aynı mantık; burada yalnızca canlı
// önizleme için var, karar sunucuda verilir.
const phaseFactor = (schema, vg) =>
  schema?.vector_groups?.[vg]?.phase_factor ?? 1

function Field({ label, hint, error, children }) {
  return (
    <div className="field np-field">
      <label>
        {label}
        {hint && <span className="np-hint"> · {hint}</span>}
      </label>
      {children}
      {error && <div className="np-error">{error}</div>}
    </div>
  )
}

function Section({ title, children }) {
  return (
    <section className="np-section">
      <h3>{title}</h3>
      <div className="np-grid">{children}</div>
    </section>
  )
}

const EMPTY = {
  id: '', name: '', location: '', asset_class: 'MPT', mva: '',
  manufacturer: '', serial_no: '', year_made: '', commissioned_at: '',
  hv_kv: '', lv_kv: '', vector_group: '', cooling: '',
  oil_volume_l: '', winding_material: '', insulation_type: '',
  tap_changer_type: '', tap_min: '', tap_max: '', tap_step_percent: '',
  rated_hotspot_c: '', rated_top_oil_c: '', notes: '',
}

/** Boş dizeleri at, sayısal alanları sayıya çevir. */
function toPayload(form, fields) {
  const numeric = new Set(['mva', 'year_made', 'hv_kv', 'lv_kv',
    'oil_volume_l', 'tap_min', 'tap_max', 'tap_step_percent',
    'rated_hotspot_c', 'rated_top_oil_c'])

  const out = {}
  for (const key of fields) {
    const v = form[key]
    if (v === '' || v === null || v === undefined) continue
    out[key] = numeric.has(key) ? Number(v) : v
  }
  return out
}

/** Sunucudaki kurallarla aynı hızlı kontroller. */
function validate(form, mode) {
  const errors = {}
  if (mode === 'create') {
    if (!form.id.trim()) errors.id = 'Zorunlu'
    else if (!/^[A-Za-z0-9-]{2,20}$/.test(form.id.trim())) {
      errors.id = 'Harf, rakam ve tire; 2-20 karakter'
    }
    if (!form.name.trim()) errors.name = 'Zorunlu'
  }

  const hv = Number(form.hv_kv)
  const lv = Number(form.lv_kv)
  if (form.hv_kv && form.lv_kv && hv <= lv) {
    errors.hv_kv = 'YG gerilimi AG geriliminden büyük olmalı'
  }

  if (form.tap_min !== '' && form.tap_max !== ''
      && Number(form.tap_min) > Number(form.tap_max)) {
    errors.tap_min = 'Alt kademe üst kademeden büyük olamaz'
  }

  const year = Number(form.year_made)
  if (form.year_made && (year < 1900 || year > new Date().getFullYear() + 1)) {
    errors.year_made = 'Makul bir yıl girin'
  }

  for (const [key, label] of [['mva', 'Güç'], ['oil_volume_l', 'Yağ hacmi']]) {
    if (form[key] !== '' && Number(form[key]) <= 0) {
      errors[key] = `${label} pozitif olmalı`
    }
  }
  return errors
}

export default function NameplateForm({ mode = 'edit', transformer, onSaved,
                                        onCancel }) {
  const [schema, setSchema] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [errors, setErrors] = useState({})
  const [serverProblems, setServerProblems] = useState([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.nameplateSchema().then(setSchema).catch(() => setSchema(null))
  }, [])

  // Mevcut kaydı forma doldur. null değerler boş dizeye çevrilir; yoksa
  // React "controlled input" uyarısı verir ve alanlar salt okunur davranır.
  useEffect(() => {
    if (!transformer) return
    const np = transformer.nameplate || {}
    setForm({
      ...EMPTY,
      id: transformer.id ?? '',
      name: transformer.name ?? '',
      location: transformer.location ?? '',
      asset_class: transformer.asset_class ?? 'MPT',
      mva: transformer.mva ?? '',
      ...Object.fromEntries(
        Object.entries(np).map(([k, v]) => [k, v ?? ''])),
    })
  }, [transformer])

  const set = (key) => (e) => {
    const value = e.target.value
    setForm((f) => ({ ...f, [key]: value }))
    setServerProblems([])
  }

  // Canlı türetilmiş değerler — kullanıcı yazarken hesaplanır.
  const derived = useMemo(() => {
    const hv = Number(form.hv_kv)
    const lv = Number(form.lv_kv)
    const ratio = hv > 0 && lv > 0
      ? (hv / lv) * phaseFactor(schema, form.vector_group)
      : null

    let age = null
    if (form.commissioned_at) {
      const d = new Date(form.commissioned_at)
      if (!Number.isNaN(d.getTime())) {
        age = ((Date.now() - d.getTime()) / (365.25 * 24 * 3600 * 1000))
      }
    } else if (form.year_made) {
      age = new Date().getFullYear() - Number(form.year_made)
    }

    return { ratio, age }
  }, [form.hv_kv, form.lv_kv, form.vector_group, form.commissioned_at,
      form.year_made, schema])

  const handleSubmit = async (e) => {
    e.preventDefault()
    const errs = validate(form, mode)
    setErrors(errs)
    if (Object.keys(errs).length) return

    setSaving(true); setServerProblems([])
    try {
      const npFields = toPayload(form, schema?.fields || [])
      if (mode === 'create') {
        await api.createTransformer({
          id: form.id.trim(),
          name: form.name.trim(),
          location: form.location.trim(),
          asset_class: form.asset_class,
          mva: form.mva === '' ? null : Number(form.mva),
          nameplate: npFields,
        })
      } else {
        await api.updateNameplate(transformer.id, npFields)
      }
      onSaved?.()
    } catch (err) {
      // Sunucu doğrulaması sorun LİSTESİ döndürür; hepsini gösteriyoruz.
      const detail = err?.response?.data?.detail
      setServerProblems(detail?.problems
        || [detail || err.message || 'Kayıt başarısız'])
    } finally {
      setSaving(false)
    }
  }

  if (!schema) {
    return <div className="panel"><p className="empty">Form yükleniyor…</p></div>
  }

  const opts = (obj) => Object.entries(obj || {})

  return (
    <form className="panel np-form" onSubmit={handleSubmit}>
      <h2>{mode === 'create' ? 'Yeni Trafo Kaydı' : 'Künye Düzenle'}</h2>

      {serverProblems.length > 0 && (
        <div className="np-problems">
          <b>Kayıt yapılamadı:</b>
          <ul>{serverProblems.map((p) => <li key={p}>{p}</li>)}</ul>
        </div>
      )}

      <Section title="Kimlik">
        <Field label="Trafo kodu" error={errors.id}
          hint={mode === 'edit' ? 'değiştirilemez' : 'ör. TR-10'}>
          <input value={form.id} onChange={set('id')}
            disabled={mode === 'edit'} placeholder="TR-10" />
        </Field>
        <Field label="Ad" error={errors.name}>
          <input value={form.name} onChange={set('name')}
            disabled={mode === 'edit'} placeholder="Ana Merkez Trafosu" />
        </Field>
        <Field label="Konum">
          <input value={form.location} onChange={set('location')}
            disabled={mode === 'edit'} placeholder="İstanbul-Avrupa" />
        </Field>
        <Field label="Üretici">
          <input value={form.manufacturer} onChange={set('manufacturer')} />
        </Field>
        <Field label="Seri no">
          <input value={form.serial_no} onChange={set('serial_no')} />
        </Field>
        <Field label="Üretim yılı" error={errors.year_made}>
          <input type="number" value={form.year_made}
            onChange={set('year_made')} placeholder="2015" />
        </Field>
        <Field label="Devreye alma" hint="yaş hesabında kullanılır">
          <input type="date" value={form.commissioned_at}
            onChange={set('commissioned_at')} />
        </Field>
      </Section>

      <Section title="Güç ve gerilim">
        <Field label="Varlık sınıfı" hint="öncelik ağırlığını belirler">
          <select value={form.asset_class} onChange={set('asset_class')}
            disabled={mode === 'edit'}>
            {opts(schema.asset_classes).map(([code, v]) => (
              <option key={code} value={code}>
                {code} — {v.name_tr}{v.active ? '' : ' (hat kapandı)'}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Anma gücü (MVA)" error={errors.mva}>
          <input type="number" step="0.1" value={form.mva}
            onChange={set('mva')} disabled={mode === 'edit'} />
        </Field>
        <Field label="YG gerilimi (kV)" error={errors.hv_kv}>
          <input type="number" step="0.1" value={form.hv_kv}
            onChange={set('hv_kv')} placeholder="154" />
        </Field>
        <Field label="AG gerilimi (kV)">
          <input type="number" step="0.1" value={form.lv_kv}
            onChange={set('lv_kv')} placeholder="34.5" />
        </Field>
        <Field label="Bağlantı grubu" hint="sarım oranını etkiler">
          <select value={form.vector_group} onChange={set('vector_group')}>
            <option value="">— seçiniz —</option>
            {opts(schema.vector_groups).map(([code, v]) => (
              <option key={code} value={code}>
                {code} (×{v.phase_factor})
              </option>
            ))}
          </select>
        </Field>
      </Section>

      {(derived.ratio || derived.age !== null) && (
        <div className="np-derived">
          <span className="np-derived-title">Hesaplanan</span>
          {derived.ratio && (
            <span>
              Beklenen sarım oranı <b>{derived.ratio.toFixed(4)}</b>
              <span className="muted"> · sarım oranı testinin referansı</span>
            </span>
          )}
          {derived.age !== null && (
            <span>Yaş <b>{derived.age.toFixed(1)}</b> yıl</span>
          )}
        </div>
      )}

      <Section title="Tasarım">
        <Field label="Soğutma tipi" hint="termal modelin girdisi">
          <select value={form.cooling} onChange={set('cooling')}>
            <option value="">— seçiniz —</option>
            {opts(schema.cooling).map(([code, label]) => (
              <option key={code} value={code}>{code} — {label}</option>
            ))}
          </select>
        </Field>
        <Field label="Yağ hacmi (litre)" error={errors.oil_volume_l}
          hint="ppm → mutlak gaz miktarı">
          <input type="number" step="1" value={form.oil_volume_l}
            onChange={set('oil_volume_l')} />
        </Field>
        <Field label="Sargı malzemesi">
          <select value={form.winding_material}
            onChange={set('winding_material')}>
            <option value="">— seçiniz —</option>
            {(schema.winding_materials || []).map((m) => (
              <option key={m} value={m}>{m === 'Cu' ? 'Cu — bakır'
                : 'Al — alüminyum'}</option>
            ))}
          </select>
        </Field>
        <Field label="Yalıtım tipi" hint="kağıt yaşlanma hızını etkiler">
          <select value={form.insulation_type}
            onChange={set('insulation_type')}>
            <option value="">— seçiniz —</option>
            {opts(schema.insulation_types).map(([code, label]) => (
              <option key={code} value={code}>{label}</option>
            ))}
          </select>
        </Field>
      </Section>

      <Section title="Kademe değiştirici">
        <Field label="Tip">
          <select value={form.tap_changer_type}
            onChange={set('tap_changer_type')}>
            <option value="">— seçiniz —</option>
            {opts(schema.tap_changer_types).map(([code, label]) => (
              <option key={code} value={code}>{label}</option>
            ))}
          </select>
        </Field>
        <Field label="Alt kademe" error={errors.tap_min}>
          <input type="number" value={form.tap_min} onChange={set('tap_min')}
            placeholder="-9" />
        </Field>
        <Field label="Üst kademe">
          <input type="number" value={form.tap_max} onChange={set('tap_max')}
            placeholder="9" />
        </Field>
        <Field label="Kademe adımı (%)">
          <input type="number" step="0.01" value={form.tap_step_percent}
            onChange={set('tap_step_percent')} placeholder="1.25" />
        </Field>
      </Section>

      <Section title="Anma sıcaklıkları">
        <Field label="Sıcak nokta (°C)" hint="IEEE C57.91 referansı 110">
          <input type="number" step="0.1" value={form.rated_hotspot_c}
            onChange={set('rated_hotspot_c')} placeholder="110" />
        </Field>
        <Field label="Üst yağ (°C)">
          <input type="number" step="0.1" value={form.rated_top_oil_c}
            onChange={set('rated_top_oil_c')} placeholder="95" />
        </Field>
      </Section>

      <Section title="Notlar">
        <Field label="Serbest not">
          <input value={form.notes} onChange={set('notes')}
            placeholder="Şebeke bağlantı noktası; yedeği yok." />
        </Field>
      </Section>

      <div className="np-actions">
        <button type="submit" className="primary" disabled={saving}>
          {saving ? 'Kaydediliyor…'
            : mode === 'create' ? 'Trafoyu kaydet' : 'Künyeyi güncelle'}
        </button>
        {onCancel && (
          <button type="button" className="chip" onClick={onCancel}>
            Vazgeç
          </button>
        )}
      </div>
    </form>
  )
}
