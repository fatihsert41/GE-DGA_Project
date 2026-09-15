import { useState } from 'react'
import api, { session, userFromLogin } from '../api'

/* Parola değiştirme. (Sistem Yönetimi)
 *
 * İki kullanımı var:
 *   1. ZORUNLU — geçici parolayla girildiyse uygulama açılmadan önce
 *      tam sayfa gösterilir (embedded = false).
 *   2. İSTEĞE BAĞLI — "Hesabım → Parolamı Değiştir" (PW01) ekranı
 *      (embedded = true).
 *
 * Sunucu başarılı değişiklikte kişinin BÜTÜN oturumlarını kapatır ve yeni
 * bir belirteç döner. Bu yüzden eski belirteç burada yenisiyle değiştirilir;
 * yapılmasaydı bir sonraki istek 401 alırdı.
 *
 * Buradaki kurallar yalnızca kullanıcıya YAZARKEN yol göstermek için:
 * asıl denetim sunucuda (PasswordPolicy). İkisi ayrışırsa sunucu kazanır ve
 * gerekçesini "problems" listesinde döner.
 */

const MIN = 10

function Rule({ ok, children }) {
  return <li className={ok ? 'ok' : 'bad'}>{ok ? '✓' : '•'} {children}</li>
}

export default function ChangePasswordScreen({ user, onDone, onLogout, embedded = false }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)

  const longEnough = next.length >= MIN
  const differs = next.length > 0 && next !== current
  const noEmployeeNo = !user?.employeeNo || !next.includes(user.employeeNo)
  const matches = next.length > 0 && next === confirm
  const ready = current && longEnough && differs && noEmployeeNo && matches

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null); setDone(false)
    try {
      const result = await api.changePassword(current, next)
      const updated = userFromLogin(result)
      session.save(result.token, updated)
      setCurrent(''); setNext(''); setConfirm('')
      setDone(true)
      onDone(updated)
    } catch (err) {
      const data = err?.response?.data
      setError({
        message: data?.message || err.message || 'Parola değiştirilemedi.',
        problems: Array.isArray(data?.problems) ? data.problems : [],
      })
      // 401: oturum kapandı (ör. çok fazla hatalı deneme). Girişe dön.
      if (err?.response?.status === 401 && onLogout) onLogout()
    } finally {
      setBusy(false)
    }
  }

  const form = (
    <form onSubmit={submit}>
      {error && (
        <div className="np-problems" role="alert">
          <b>{error.message}</b>
          {error.problems.length > 0 && (
            <ul>{error.problems.map((p) => <li key={p}>{p}</li>)}</ul>
          )}
        </div>
      )}
      {done && embedded && (
        <div className="hi-note"><b>Parolanız değiştirildi.</b> Diğer cihazlardaki
          oturumlarınız kapatıldı.</div>
      )}

      <div className="field np-field">
        <label htmlFor="pw-current">{embedded ? 'Mevcut parola' : 'Geçici parola'}</label>
        <input id="pw-current" type="password" autoComplete="current-password"
          value={current} onChange={(e) => setCurrent(e.target.value)} autoFocus />
      </div>

      <div className="field np-field">
        <label htmlFor="pw-new">Yeni parola</label>
        <input id="pw-new" type="password" autoComplete="new-password"
          value={next} onChange={(e) => setNext(e.target.value)} />
        <ul className="pw-rules" aria-live="polite">
          <Rule ok={longEnough}>En az {MIN} karakter ({next.length})</Rule>
          <Rule ok={differs}>Mevcut paroladan farklı</Rule>
          <Rule ok={noEmployeeNo}>Sicil numaranızı içermiyor</Rule>
        </ul>
      </div>

      <div className="field np-field">
        <label htmlFor="pw-confirm">Yeni parola (tekrar)</label>
        <input id="pw-confirm" type="password" autoComplete="new-password"
          value={confirm} onChange={(e) => setConfirm(e.target.value)} />
        {confirm && !matches && <div className="over-limit">Parolalar eşleşmiyor.</div>}
      </div>

      <p className="note">
        Uzunluk, karmaşıklıktan daha değerlidir: <i>"trafo yağı temiz çıktı"</i>
        gibi bir cümle, <i>"Parola1!"</i> gibi kısa ve kalıplı bir paroladan çok
        daha güçlüdür. Büyük harf ya da sembol zorunlu değil.
      </p>

      <button type="submit" className="primary" disabled={busy || !ready}>
        {busy ? 'Kaydediliyor…' : 'Parolayı değiştir'}
      </button>
    </form>
  )

  if (embedded) {
    return (
      <div className="panel" style={{ maxWidth: 560 }}>
        <h2>Parolamı Değiştir</h2>
        {form}
      </div>
    )
  }

  return (
    <div className="login-wrap">
      <div className="panel login-card">
        <div className="login-brand">
          <span className="login-mark" aria-hidden="true" />
          <div>
            <h1 className="login-title">Parolanızı belirleyin</h1>
            <div className="muted login-sub">{user?.name} · sicil {user?.employeeNo}</div>
          </div>
        </div>

        <p className="note login-why">
          Geçici bir parolayla giriş yaptınız. Geçici parolayı iki kişi bilir:
          siz ve onu veren Sistem Yöneticisi. Bu yüzden kendi parolanızı
          belirlemeden <b>hiçbir işlem yapamazsınız</b>.
        </p>

        {form}

        <button type="button" className="chip" style={{ marginTop: 12 }} onClick={onLogout}>
          Çıkış yap
        </button>
      </div>
    </div>
  )
}
