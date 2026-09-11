import { useState } from 'react'
import api, { session } from '../api'

/* Faz 9.0d — Giriş ekranı.
 *
 * Sisteme sicil numarası ve PIN ile girilir. Bunun sebebi yalnızca
 * erişim kontrolü değil, İZLENEBİLİRLİK: girilen her ölçüm "kim girdi"
 * bilgisiyle kaydediliyor. Kim olduğu bilinmeyen bir kayıt için denetim
 * izi tutmanın anlamı yok.
 *
 * Ekran, sistemin ne sunup ne sunmadığını AÇIKÇA yazıyor. Yarım bir
 * güvenlik katmanını tam gibi göstermek, hiç olmamasından kötüdür:
 * kullanıcı var olmayan bir güvenceye dayanarak davranır.
 */

export default function LoginScreen({ onLogin }) {
  const [employeeNo, setEmployeeNo] = useState('')
  const [pin, setPin] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    if (!employeeNo.trim() || !pin.trim()) {
      setError('Sicil numarası ve PIN gerekli.')
      return
    }

    setBusy(true); setError(null)
    try {
      const result = await api.login(employeeNo.trim(), pin.trim())
      const user = {
        employeeNo: result.employeeNo,
        name: result.name,
        role: result.role,
        region: result.region,
        specialty: result.specialty,
        expiresAt: result.expiresAt,
      }
      session.save(result.token, user)
      onLogin(user)
    } catch (err) {
      // 401 gövdesi { message, lockedUntil } taşır.
      const data = err?.response?.data
      setError(data?.message || err.message || 'Giriş başarısız.')
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
          Bu yüzden giriş zorunludur: sorumlusu bilinmeyen bir kaydın
          denetim değeri yoktur.
        </p>

        {error && <div className="np-problems login-error"><b>{error}</b></div>}

        <div className="field np-field">
          <label htmlFor="employeeNo">Sicil numarası</label>
          <input id="employeeNo" inputMode="numeric" autoComplete="username"
            value={employeeNo} onChange={(e) => setEmployeeNo(e.target.value)}
            placeholder="ör. 10247" autoFocus />
        </div>

        <div className="field np-field">
          <label htmlFor="pin">PIN</label>
          <input id="pin" type="password" inputMode="numeric"
            autoComplete="current-password" value={pin}
            onChange={(e) => setPin(e.target.value)} placeholder="••••" />
        </div>

        <button type="submit" className="primary" disabled={busy}>
          {busy ? 'Kontrol ediliyor…' : 'Giriş'}
        </button>

        <div className="login-demo">
          <b>Demo hesapları</b> — PIN, sicilin son dört hanesidir.
          <table className="compare login-accounts">
            <tbody>
              <tr><td className="num">10247</td><td>Ahmet Yılmaz</td>
                <td className="muted">Teknisyen</td></tr>
              <tr><td className="num">10318</td><td>Elif Demir</td>
                <td className="muted">Mühendis</td></tr>
              <tr><td className="num">10502</td><td>Zeynep Şahin</td>
                <td className="muted">Süpervizör</td></tr>
            </tbody>
          </table>
        </div>

        {/* Sistemin sınırlarını gizlemek, kullanıcıyı var olmayan bir
            güvenceye dayandırmaktır. Bu yüzden açıkça yazılıyor. */}
        <details className="login-scope">
          <summary>Bu giriş ne kadar koruyor?</summary>
          <div className="login-scope-body">
            <p><b>Var olanlar:</b> PIN veritabanında düz metin olarak
              saklanmaz (PBKDF2 + kişiye özel tuz); 5 hatalı denemeden
              sonra 15 dakika kilit; oturum süreli ve iptal edilebilir;
              parola karşılaştırması sabit sürede yapılır.</p>
            <p><b>Olmayanlar:</b> HTTPS/TLS yok — bu demo yerel ağda
              çalışıyor, gerçek kurulumda şarttır, aksi halde oturum
              anahtarı ağda açık gider. Çok faktörlü doğrulama, parola
              politikası ve sıfırlama akışı da yok.</p>
            <p className="muted">Dört haneli bir PIN güçlü bir parola
              değildir. Buradaki önlemler onu <i>banka kartı</i>
              seviyesinde kılar: sicilinizi bilen birine karşı korur,
              sistemi elinde tutan birine karşı değil. Amaç güvenlikten
              çok <b>izlenebilirliktir</b>.</p>
          </div>
        </details>
      </form>
    </div>
  )
}
