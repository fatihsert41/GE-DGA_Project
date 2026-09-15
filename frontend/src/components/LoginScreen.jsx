import { useState } from 'react'
import api, { session, userFromLogin } from '../api'

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
          <span className="login-mark" aria-hidden="true" />
          <div>
            <h1 className="login-title">TransformerAI</h1>
            <div className="muted login-sub">
              DGA Tabanlı Trafo İzleme ve Bakım Planlama
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

        {/* Sistemin sınırlarını gizlemek, kullanıcıyı var olmayan bir
            güvenceye dayandırmaktır. Bu yüzden açıkça yazılıyor. */}
        <details className="login-scope">
          <summary>Bu giriş ne kadar koruyor?</summary>
          <div className="login-scope-body">
            <p><b>Var olanlar:</b> parola veritabanında düz metin olarak
              saklanmaz (PBKDF2, 100.000 tur, kişiye özel tuz); en az 10
              karakter, sicil ya da ad içeremez; 5 hatalı denemeden sonra
              15 dakika kilit; geçici parolayla açılan oturum parola
              değişene kadar hiçbir işlem yapamaz; oturum süreli ve iptal
              edilebilir; yetkiler departmana bağlıdır ve her istekte
              sunucuda kontrol edilir; hesap işlemleri denetim izine yazılır.</p>
            <p><b>Olmayanlar:</b> HTTPS/TLS yok — bu demo yerel ağda
              çalışıyor, gerçek kurulumda şarttır, aksi halde parola ve
              oturum anahtarı ağda açık gider. Çok faktörlü doğrulama ve
              e-postayla parola sıfırlama da yok.</p>
          </div>
        </details>
      </form>
    </div>
  )
}
