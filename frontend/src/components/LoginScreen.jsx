import { useState } from 'react'
import api, { session, userFromLogin } from '../api'
import BrandLogo from './BrandLogo'

/* Giriş ekranı. (Faz 9.0d, Sistem Yönetimi ile parolaya geçti)
 *
 * Sisteme sicil numarası ve PAROLA ile girilir. Bunun sebebi yalnızca
 * erişim kontrolü değil, İZLENEBİLİRLİK: girilen her ölçüm "kim girdi"
 * bilgisiyle kaydediliyor.
 *
 * Önceki sürümde burada demo hesap tablosu ve "PIN = sicilin son dört
 * hanesi" ipucu vardı. İkisi de KALDIRILDI: giriş ekranında hangi
 * sicillerin var olduğunu listelemek, parolanın korumaya çalıştığı
 * bilgiyi herkese vermekti. Hesapları artık Sistem Yönetimi açar.
 *
 * Geçici parolayla girildiyse sunucu `mustChangePassword: true` döner;
 * App uygulamayı açmadan önce parola değiştirme ekranını gösterir.
 *
 * (16 Eyl) Buradaki "Bu giriş ne kadar koruyor?" açılır bölümü kaldırıldı:
 * sıraladığı eksiklerin başında HTTPS/TLS geliyordu, o da artık kuruldu
 * (bkz. `frontend/vite.config.js` ve `frontend/nginx.conf`). Güvenlik
 * özetinin yeri README; giriş ekranı kurumsal ve sade kalıyor.
 */

export default function LoginScreen({ onLogin }) {
  const [employeeNo, setEmployeeNo] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!employeeNo.trim() || !password) {
      setError('Sicil numarası ve parola gerekli.')
      return
    }

    setBusy(true); setError(null)
    try {
      const result = await api.login(employeeNo.trim(), password)
      const user = userFromLogin(result)
      session.save(result.token, user)
      onLogin(user)
    } catch (err) {
      // 401 gövdesi { message, lockedUntil } taşır.
      const data = err?.response?.data
      setError(data?.message || err.message || 'Giriş başarısız.')
      // Parola alanı temizlenir; sicil kalır (yazım hatası çoğunlukla parolada).
      setPassword('')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="login-wrap">
      <form className="panel login-card" onSubmit={submit}>
        <div className="login-brand">
          <BrandLogo variant="mark" className="login-mark-img" />
          <div>
            <h1 className="login-title">GE Vernova</h1>
            <div className="muted login-sub">
              Grid Solutions · TransformerAI
            </div>
          </div>
        </div>

        <p className="note login-why">
          Girilen her ölçüm, <b>kimin kaydettiği</b> bilgisiyle saklanır.
          Bu yüzden giriş zorunludur. Hangi ekranı kullanıp hangi işlemi
          yapabileceğiniz <b>departmanınıza</b> bağlıdır.
        </p>

        {error && <div className="np-problems login-error" role="alert"><b>{error}</b></div>}

        <div className="field np-field">
          <label htmlFor="employeeNo">Sicil numarası</label>
          <input id="employeeNo" inputMode="numeric" autoComplete="username"
            value={employeeNo} onChange={(e) => setEmployeeNo(e.target.value)}
            autoFocus />
        </div>

        <div className="field np-field">
          <label htmlFor="password">Parola</label>
          <input id="password" type="password" autoComplete="current-password"
            value={password} onChange={(e) => setPassword(e.target.value)} />
        </div>

        <button type="submit" className="primary" disabled={busy}>
          {busy ? 'Kontrol ediliyor…' : 'Giriş'}
        </button>

        <p className="note">
          Hesabınız yoksa, parolanızı unuttuysanız ya da hesabınız
          kilitlendiyse <b>Sistem Yöneticinize</b> başvurun.
        </p>

        <div className="login-foot">
          <BrandLogo variant="lockup" className="login-lockup" />
        </div>
      </form>
    </div>
  )
}
