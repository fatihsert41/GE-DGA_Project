import { useCallback, useEffect, useState } from 'react'
import api from '../api'
import { can } from '../permissions'

/* Sistem Yönetimi — AD01 Kullanıcı Yönetimi.
 *
 * Bu ekranın en önemli işi KULLANICI EKLEMEK. Onun yanında: parola sıfırlama,
 * kilit açma, pasife alma / yeniden etkinleştirme ve bütün bunların denetim izi.
 *
 * Üç kural ekranın her yerinde görünür olmalı:
 *
 *   1. Geçici parolayı SİSTEM üretir ve yalnızca BİR KEZ gösterir. Veritabanında
 *      yalnızca özeti durur; admin de dahil kimse sonradan okuyamaz.
 *   2. Kayıt SİLİNMEZ, pasife alınır: kişinin girdiği testler, yürüttüğü iş
 *      emirleri ve yazdığı analizler sahipsiz kalmamalı.
 *   3. Admin KENDİ hesabına dokunamaz (departman, pasife alma, sıfırlama).
 *      Dokunabilseydi kendini Yönetim'e taşıyıp her yetkiyi alabilirdi.
 *
 * Kurallar sunucuda da uygulanıyor (UserAdminRules); burada düğmeleri
 * gizlemek yalnızca kullanıcıyı ret mesajıyla karşılamamak için.
 */

const ROLE_TR = { Technician: 'Teknisyen', Engineer: 'Mühendis', Supervisor: 'Süpervizör' }
const SPECIALTY_TR = { General: 'Genel', Electrical: 'Elektriksel', Thermal: 'Termal', Sampling: 'Numune' }

const fmtDateTime = (iso) => (iso
  ? new Date(iso).toLocaleString('tr-TR', {
    day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit',
  })
  : '—')

const errorOf = (err) => {
  const data = err?.response?.data
  return {
    message: data?.message || data?.title || err.message,
    problems: Array.isArray(data?.problems) ? data.problems : [],
  }
}

function ErrorBox({ error }) {
  if (!error) return null
  return (
    <div className="np-problems" role="alert">
      <b>{error.message}</b>
      {error.problems?.length > 0 && <ul>{error.problems.map((p) => <li key={p}>{p}</li>)}</ul>}
    </div>
  )
}

/** Geçici parola — bir kez gösterilir. */
function TemporaryPassword({ secret, onClose }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(secret.password)
      setCopied(true)
    } catch {
      setCopied(false)   // pano izni yoksa kullanıcı elle seçer (user-select: all)
    }
  }

  return (
    <div className="panel">
      <h2>Geçici Parola — {secret.name}</h2>
      <p className="note" style={{ marginTop: 0 }}>{secret.title}</p>

      <div className="mail-meta">
        <span className="k">Sicil</span><span className="num"><b>{secret.employeeNo}</b></span>
        <span className="k">Departman</span><span>{secret.departmentName}</span>
      </div>

      <div className="temp-password" aria-label="Geçici parola">{secret.password}</div>

      <div className="msg-actions">
        <button type="button" className="erp-tb" onClick={copy}>
          {copied ? 'Kopyalandı' : 'Kopyala'}
        </button>
        <button type="button" className="erp-tb primary-tb" onClick={onClose}>
          İlettim, kapat
        </button>
      </div>

      <div className="hi-note warn" style={{ marginTop: 10 }}>
        <b>Bu parola bir daha gösterilmez.</b> Sistemde yalnızca özeti tutulur;
        siz dahil kimse okuyamaz. Kullanıcıya güvenli bir yoldan iletin (yüz
        yüze ya da telefonla). Kullanıcı ilk girişte kendi parolasını
        belirlemeden hiçbir işlem yapamaz.
      </div>
    </div>
  )
}

function CreateUserForm({ departments, onCreated, onCancel }) {
  const [employeeNo, setEmployeeNo] = useState('')
  const [name, setName] = useState('')
  // Yeni hesap EN DAR yetkiyle başlar; genişletmek bilinçli bir seçim olmalı.
  const [department, setDepartment] = useState('FieldService')
  const [role, setRole] = useState('Technician')
  const [specialty, setSpecialty] = useState('General')
  const [maxOpen, setMaxOpen] = useState(3)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const selected = departments.find((d) => d.code === department)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      const res = await api.admin.createUser({
        employeeNo: employeeNo.trim(),
        name: name.trim(),
        department,
        role,
        specialty,
        maxOpenOrders: Number(maxOpen),
      })
      onCreated(res)
    } catch (err) {
      setError(errorOf(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="panel">
      <div className="np-head">
        <h2>Yeni Kullanıcı</h2>
        <button type="button" className="erp-tb" onClick={onCancel}>Vazgeç</button>
      </div>

      <form onSubmit={submit}>
        <ErrorBox error={error} />

        <div className="np-grid">
          <div className="field np-field">
            <label htmlFor="u-no">Sicil numarası<span className="np-hint"> · 5–10 hane</span></label>
            <input id="u-no" inputMode="numeric" value={employeeNo}
              onChange={(e) => setEmployeeNo(e.target.value)} autoFocus />
          </div>
          <div className="field np-field">
            <label htmlFor="u-name">Ad soyad</label>
            <input id="u-name" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="field np-field">
            <label htmlFor="u-dept">Departman<span className="np-hint"> · yetkileri belirler</span></label>
            <select id="u-dept" value={department} onChange={(e) => setDepartment(e.target.value)}>
              {departments.map((d) => <option key={d.code} value={d.code}>{d.name}</option>)}
            </select>
          </div>
          <div className="field np-field">
            <label htmlFor="u-role">Rol<span className="np-hint"> · kıdem</span></label>
            <select id="u-role" value={role} onChange={(e) => setRole(e.target.value)}>
              {Object.entries(ROLE_TR).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="field np-field">
            <label htmlFor="u-spec">Uzmanlık<span className="np-hint"> · otomatik atama</span></label>
            <select id="u-spec" value={specialty} onChange={(e) => setSpecialty(e.target.value)}>
              {Object.entries(SPECIALTY_TR).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </div>
          <div className="field np-field">
            <label htmlFor="u-cap">Açık iş kapasitesi</label>
            <input id="u-cap" type="number" min="0" max="10" value={maxOpen}
              onChange={(e) => setMaxOpen(e.target.value)} />
          </div>
        </div>

        {selected && (
          <p className="note">
            <b>{selected.name}:</b> {selected.description}
            {department === 'Management' && (
              <b> Bu departman bütün operasyon işlemlerine yetki verir.</b>
            )}
            {department === 'SystemAdmin' && (
              <b> Bu departman kullanıcı hesabı açabilir.</b>
            )}
          </p>
        )}

        <div className="msg-actions">
          <button type="submit" className="erp-tb primary-tb"
            disabled={busy || !employeeNo.trim() || !name.trim()}>
            {busy ? 'Oluşturuluyor…' : 'Hesabı oluştur'}
          </button>
          <span className="note">Geçici parolayı sistem üretir ve bir kez gösterir.</span>
        </div>
      </form>
    </div>
  )
}

function DeactivateForm({ person, onDone, onCancel }) {
  const [reason, setReason] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      onDone(await api.admin.deactivate(person.id, reason.trim()))
    } catch (err) {
      setError(errorOf(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <form className="review-form" onSubmit={submit}>
      <ErrorBox error={error} />
      <div className="field np-field">
        <label htmlFor="deact-reason">
          {person.name} ({person.employeeNo}) · pasife alma gerekçesi
          <span className="np-hint"> · zorunlu, en az 10 karakter ({reason.trim().length})</span>
        </label>
        <textarea id="deact-reason" rows={2} maxLength={500} value={reason}
          onChange={(e) => setReason(e.target.value)}
          placeholder="ör. İşten ayrıldı, 15.09.2026." />
      </div>
      <div className="msg-actions">
        <button type="submit" className="erp-tb primary-tb"
          disabled={busy || reason.trim().length < 10}>
          Pasife al
        </button>
        <button type="button" className="erp-tb" onClick={onCancel}>Vazgeç</button>
        <span className="note">
          Kayıt silinmez; açık oturumlar kapanır, geçmiş kayıtlar kişiyle kalır.
        </span>
      </div>
    </form>
  )
}

function Flags({ u }) {
  return (
    <span className="user-flags">
      {u.isActive
        ? <span className="badge sm low">Aktif</span>
        : <span className="badge sm">Pasif</span>}
      {u.locked && <span className="badge sm high" title={`${fmtDateTime(u.lockedUntil)} tarihine kadar`}>Kilitli</span>}
      {u.isActive && u.mustChangePassword && (
        <span className="badge sm medium" title="Geçici parolası var; ilk girişte değiştirecek">
          Parola bekliyor
        </span>
      )}
    </span>
  )
}

export default function AdminPanel({ currentUser }) {
  const [users, setUsers] = useState(null)
  const [audit, setAudit] = useState(null)
  const [departments, setDepartments] = useState([])
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)
  const [busyId, setBusyId] = useState(null)
  const [creating, setCreating] = useState(false)
  const [secret, setSecret] = useState(null)
  const [deactivating, setDeactivating] = useState(null)

  const load = useCallback(() => {
    Promise.all([api.admin.users(), api.admin.audit(50)])
      .then(([u, a]) => { setUsers(u); setAudit(a) })
      .catch((e) => setError(errorOf(e)))
  }, [])

  useEffect(() => {
    load()
    api.departments().then((c) => setDepartments(c.departments || [])).catch(() => setDepartments([]))
  }, [load])

  if (!can('users.manage')) {
    return (
      <div className="panel">
        <h2>Kullanıcı Yönetimi</h2>
        <p className="empty">
          Bu ekran <b>Sistem Yönetimi</b> departmanına aittir. Yönetim departmanı
          dahil diğer birimler kullanıcı hesabı açamaz.
        </p>
      </div>
    )
  }

  if (error && !users) {
    return <div className="panel"><h2>Kullanıcı Yönetimi</h2><ErrorBox error={error} /></div>
  }
  if (!users) return <div className="panel"><p className="empty">Yükleniyor…</p></div>

  const items = users.items || []
  const isMe = (u) => u.employeeNo === currentUser?.employeeNo

  const run = async (u, action, onSuccess) => {
    setBusyId(u.id); setNotice(null); setError(null)
    try {
      onSuccess(await action())
      load()
    } catch (err) {
      setError(errorOf(err))
    } finally {
      setBusyId(null)
    }
  }

  const reset = (u) => {
    if (!window.confirm(`${u.name} için yeni geçici parola üretilsin mi?\n\n`
      + 'Mevcut parolası geçersiz olur ve açık oturumları kapanır.')) return
    run(u, () => api.admin.resetPassword(u.id), (res) => setSecret({
      title: `Parola sıfırlandı; ${res.closedSessions} açık oturum kapatıldı.`,
      name: u.name, employeeNo: u.employeeNo, departmentName: u.departmentName,
      password: res.temporaryPassword,
    }))
  }

  const unlock = (u) => run(u, () => api.admin.unlock(u.id),
    () => setNotice(`${u.name} hesabının kilidi açıldı.`))

  const activate = (u) => {
    if (!window.confirm(`${u.name} yeniden etkinleştirilsin mi?\n\n`
      + 'Eski parolası geçerli olmaz; yeni geçici parola üretilir.')) return
    run(u, () => api.admin.activate(u.id), (res) => setSecret({
      title: 'Hesap yeniden etkinleştirildi.',
      name: u.name, employeeNo: u.employeeNo, departmentName: u.departmentName,
      password: res.temporaryPassword,
    }))
  }

  const count = (pred) => items.filter(pred).length

  return (
    <div>
      <div className="panel">
        <div className="np-head">
          <h2>Kullanıcı Yönetimi</h2>
          {!creating && (
            <button type="button" className="erp-tb primary-tb"
              onClick={() => { setCreating(true); setSecret(null); setNotice(null) }}>
              + Yeni kullanıcı
            </button>
          )}
        </div>
        <div className="kpis">
          <div className="kpi"><div className="kpi-label">Hesap</div>
            <div className="kpi-value">{items.length}</div><div className="kpi-hint">kayıtlı</div></div>
          <div className="kpi"><div className="kpi-label">Aktif</div>
            <div className="kpi-value">{count((u) => u.isActive)}</div><div className="kpi-hint">giriş yapabilir</div></div>
          <div className={`kpi${count((u) => u.isActive && u.mustChangePassword) ? ' alert' : ''}`}>
            <div className="kpi-label">Parola bekliyor</div>
            <div className="kpi-value">{count((u) => u.isActive && u.mustChangePassword)}</div>
            <div className="kpi-hint">geçici parolalı</div></div>
          <div className={`kpi${count((u) => u.locked) ? ' danger' : ''}`}>
            <div className="kpi-label">Kilitli</div>
            <div className="kpi-value">{count((u) => u.locked)}</div>
            <div className="kpi-hint">hatalı deneme</div></div>
        </div>
        {notice && <div className="hi-note" style={{ marginTop: 10 }}><b>{notice}</b></div>}
        {error && <div style={{ marginTop: 10 }}><ErrorBox error={error} /></div>}
      </div>

      {secret && <TemporaryPassword secret={secret} onClose={() => setSecret(null)} />}

      {creating && (
        <CreateUserForm departments={departments}
          onCancel={() => setCreating(false)}
          onCreated={(res) => {
            setCreating(false)
            setSecret({
              title: 'Hesap oluşturuldu.',
              name: res.user.name, employeeNo: res.user.employeeNo,
              departmentName: res.user.departmentName, password: res.temporaryPassword,
            })
            load()
          }} />
      )}

      <div className="panel">
        <h2>Hesaplar</h2>
        <div className="table-scroll">
          <table className="compare">
            <thead>
              <tr>
                <th>Sicil</th><th>Ad</th><th>Departman</th><th>Rol</th>
                <th>Durum</th><th>Son giriş</th><th>İşlemler</th>
              </tr>
            </thead>
            <tbody>
              {items.map((u) => (
                <tr key={u.id} className={isMe(u) ? 'selected' : ''}>
                  <td className="num"><b>{u.employeeNo}</b></td>
                  <td>
                    {u.name}
                    {isMe(u) && <span className="me-chip">siz</span>}
                    {!u.isActive && u.deactivationReason && (
                      <div className="muted" style={{ fontSize: '0.74rem' }}>{u.deactivationReason}</div>
                    )}
                  </td>
                  <td>{u.departmentName}</td>
                  <td className="muted">{ROLE_TR[u.role] || u.role}</td>
                  <td><Flags u={u} /></td>
                  <td className="num muted">{u.lastLoginAt ? fmtDateTime(u.lastLoginAt) : 'hiç'}</td>
                  <td className="wo-actions">
                    {isMe(u) ? (
                      <span className="muted" style={{ fontSize: '0.76rem' }}>
                        kendi hesabınız — PW01
                      </span>
                    ) : (
                      <>
                        {u.locked && (
                          <button type="button" className="chip" disabled={busyId === u.id}
                            onClick={() => unlock(u)}>Kilidi aç</button>
                        )}
                        {u.isActive && (
                          <button type="button" className="chip" disabled={busyId === u.id}
                            onClick={() => reset(u)}>Parola sıfırla</button>
                        )}
                        {u.isActive ? (
                          <button type="button" className="chip" disabled={busyId === u.id}
                            onClick={() => { setDeactivating(u); setNotice(null); setError(null) }}>
                            Pasife al
                          </button>
                        ) : (
                          <button type="button" className="chip" disabled={busyId === u.id}
                            onClick={() => activate(u)}>Etkinleştir</button>
                        )}
                      </>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {deactivating && (
          <DeactivateForm key={deactivating.id} person={deactivating}
            onCancel={() => setDeactivating(null)}
            onDone={(res) => {
              setDeactivating(null)
              setNotice(`${res.user.name} pasife alındı; ${res.closedSessions} oturum kapatıldı.`
                + (res.warning ? ` ${res.warning}` : ''))
              load()
            }} />
        )}

        <p className="note">
          Departman değişikliği <b>PR01 Personel</b> ekranından yapılır. Kimse kendi
          departmanını değiştiremez ve son aktif Sistem Yöneticisi ile son aktif
          Yönetim personeli pasife alınamaz.
        </p>
      </div>

      <div className="panel">
        <h2>Denetim İzi <span className="muted" style={{ fontSize: '0.8rem' }}>son {audit?.count ?? 0} olay</span></h2>
        {!audit?.items?.length ? (
          <p className="empty">Henüz hesap işlemi yok.</p>
        ) : (
          <div className="table-scroll">
            <table className="compare audit-table">
              <thead>
                <tr><th>Zaman</th><th>İşlem</th><th>Hesap</th><th>Yapan</th><th>Ayrıntı</th></tr>
              </thead>
              <tbody>
                {audit.items.map((e) => (
                  <tr key={e.id}>
                    <td className="num">{fmtDateTime(e.at)}</td>
                    <td>{e.actionLabel}</td>
                    <td>{e.targetName} <span className="muted">· {e.targetEmployeeNo}</span></td>
                    <td>{e.actorName
                      ? <>{e.actorName} <span className="muted">· {e.actorEmployeeNo}</span></>
                      : <span className="muted">sistem</span>}</td>
                    <td className="muted">{e.detail || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="note">
          Kayıtlar silinmez ve değiştirilmez. Kişi bilgisi anlık görüntü olarak
          yazılır: hesap sonradan değişse de olayın kime ait olduğu okunabilir.
        </p>
      </div>
    </div>
  )
}
