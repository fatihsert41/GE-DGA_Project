import { useState } from 'react'
import api, { session } from '../api'

/* Faz 9.0d — Giriş ekranı.
 *
 * Sisteme sicil numarası ve PIN ile girilir. Bunun sebebi yalnızca
 * erişim kontrolü değil, İZLENEBİLİRLİK: girilen her ölçüm "kim girdi"
 * bilgisiyle kaydediliyor. Kim olduğu bilinmeyen bir kayıt için denetim
 * izi tutmanın anlamı yok.
 *
 * Faz 10: girişle birlikte kişinin DEPARTMANI ve YETKİ LİSTESİ de gelir.
 * Arayüz menüyü ve düğmeleri buna göre çizer; sunucu her istekte ayrıca
 * kontrol eder.
 *
 * Ekran, sistemin ne sunup ne sunmadığını AÇIKÇA yazıyor. Yarım bir
 * güvenlik katmanını tam gibi göstermek, hiç olmamasından kötüdür:
 * kullanıcı var olmayan bir güvenceye dayanarak davranır.
 */

// Demo hesapları — yalnızca bu ekrandaki yardım tablosu için. Gerçek
// departman bilgisi girişte sunucudan gelir.
const DEMO_ACCOUNTS = [
  { no: '10502', name: 'Zeynep Şahin', dept: 'Yönetim', hint: 'tam yetki' },
  { no: '10318', name: 'Elif Demir', dept: 'Bakım Planlama', hint: 'iş emri planlama, atama' },
  { no: '10455', name: 'Mehmet Kaya', dept: 'Yağ Laboratuvarı', hint: 'DGA, yağ testi' },
  { no: '10740', name: 'Selin Öztürk', dept: 'Yağ Laboratuvarı', hint: 'DGA, yağ testi' },
  { no: '10247', name: 'Ahmet Yılmaz', dept: 'Elektriksel Test', hint: 'TTR, buşing' },
  { no: '10611', name: 'Burak Aydın', dept: 'Saha Bakım', hint: 'iş yürütme, gözlem' },
]

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
        specialty: result.specialty,
        department: result.department,
        departmentName: result.departmentName,
        permissions: result.permissions || [],
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

  // Demo tablosundaki satıra tıklamak sicili doldurur. PIN'i doldurmaz:
  // demo kuralı (son dört hane) ekranda yazılı, kullanıcı kendisi girer.
  const pick = (no) => { setEmployeeNo(no); setPin(''); setError(null) }

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
          denetim değeri yoktur. Hangi ekranı kullanıp hangi testi
          girebileceğiniz <b>departmanınıza</b> bağlıdır.
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
          <b>Demo hesapları</b> — PIN, sicilin son dört hanesidir. Satıra
          tıklayınca sicil doldurulur.
          <table className="compare login-accounts">
            <tbody>
              {DEMO_ACCOUNTS.map((a) => (
                <tr key={a.no} onClick={() => pick(a.no)}
                  style={{ cursor: 'pointer' }}>
                  <td className="num">{a.no}</td>
                  <td>{a.name}</td>
                  <td>{a.dept}</td>
                  <td className="muted">{a.hint}</td>
                </tr>
              ))}
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
              parola karşılaştırması sabit sürede yapılır; yetkiler
              departmana bağlıdır ve her istekte sunucuda kontrol edilir.</p>
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
