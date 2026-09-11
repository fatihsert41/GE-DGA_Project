import { useEffect, useState } from 'react'
import api, { session } from './api'
import GasForm from './components/GasForm'
import DiagnosisResult from './components/DiagnosisResult'
import ShapChart from './components/ShapChart'
import DuvalTriangle from './components/DuvalTriangle'
import ComparePanel from './components/ComparePanel'
import TrendPanel from './components/TrendPanel'
import FleetOverview from './components/FleetOverview'
import TransformerDetail from './components/TransformerDetail'
import MaintenancePanel from './components/MaintenancePanel'
import NameplateForm from './components/NameplateForm'
import TestsOverview from './components/TestsOverview'
import LoginScreen from './components/LoginScreen'
import PersonnelPanel from './components/PersonnelPanel'

const TABS = [
  { id: 'diagnosis', label: 'Tanı' },
  { id: 'explain', label: 'Açıklama (SHAP)' },
  { id: 'compare', label: 'Karşılaştırma' },
  { id: 'trend', label: 'Trend Tahmini' },
]

const VIEWS = [
  { id: 'fleet', label: 'Filo' },
  { id: 'analysis', label: 'Numune Analizi' },
  // Filo geneli test durumu: "hangi trafo bozuk" değil, "nerede eksiğim".
  { id: 'tests', label: 'Testler' },
  // Bakım ekranı .NET servisinden beslenir (diğerleri Python'dan).
  { id: 'maintenance', label: 'Bakım Planlama' },
  // Personel kayıtları da .NET'te: kullanıcı ".NET kayıtlarını nerede
  // görüyorum?" diye sordu, cevabı buraya kadar yoktu.
  { id: 'personnel', label: 'Personel' },
]

const ROLE_TR = {
  Technician: 'Teknisyen',
  Engineer: 'Mühendis',
  Supervisor: 'Süpervizör',
}

export default function App() {
  // Oturum. Sayfa yenilendiğinde localStorage'tan geri okunur; belirtecin
  // hâlâ geçerli olup olmadığını /auth/me söyler.
  const [user, setUser] = useState(() => session.user())
  const [view, setView] = useState('fleet')
  // Seçili trafo kartı (null ise filo listesi görünür).
  const [selected, setSelected] = useState(null)
  // Yeni trafo kaydı formu açık mı? Filo listesinin yerine geçer.
  const [creating, setCreating] = useState(false)
  // Kayıt sonrası filo listesini tazelemek için sayaç: değeri değişince
  // FleetOverview yeniden monte olur ve veriyi baştan çeker.
  const [fleetVersion, setFleetVersion] = useState(0)
  const [tab, setTab] = useState('diagnosis')
  const [loading, setLoading] = useState(false)
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  // Sayfa açılışında saklanan belirteç hâlâ geçerli mi? Süresi dolmuş
  // ya da iptal edilmiş olabilir; o zaman kullanıcı yeniden giriş yapar.
  useEffect(() => {
    if (!session.token()) return
    api.me()
      .then((me) => setUser({
        employeeNo: me.employeeNo, name: me.name, role: me.role,
        region: me.region, specialty: me.specialty,
      }))
      .catch(() => { session.clear(); setUser(null) })
  }, [])

  const logout = () => {
    // Sunucuya haber ver (belirteç ANINDA iptal olsun), sonra yerelde
    // temizle. Sunucu ulaşılamazsa da yerel temizlik yapılır — yoksa
    // kullanıcı .NET kapalıyken çıkış yapamaz hâle gelirdi.
    api.logout().catch(() => {}).finally(() => {
      session.clear()
      setUser(null)
      setSelected(null)
      setView('fleet')
    })
  }

  const [result, setResult] = useState(null)
  const [explanation, setExplanation] = useState(null)
  const [compare, setCompare] = useState(null)
  const [leaderboard, setLeaderboard] = useState(null)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
    api.leaderboard().then(setLeaderboard).catch(() => {})
  }, [])

  const runAnalysis = async (payload) => {
    setLoading(true); setError(null)
    try {
      const res = await api.predict(payload)
      setResult(res)
      const cmp = await api.compare(payload.gases)
      setCompare(cmp)
      // SHAP only when a model is trained.
      if (health?.model_trained) {
        try { setExplanation(await api.explain(payload.gases)) }
        catch { setExplanation(null) }
      }
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || 'Bağlantı hatası')
    } finally {
      setLoading(false)
    }
  }

  const trained = health?.model_trained

  if (!user) return <LoginScreen onLogin={setUser} />

  return (
    <div className="app">
      <header className="top">
        <div>
          <h1>TransformerAI</h1>
          <div className="sub">
            DGA arıza izleme · açıklanabilir ML · klasik yöntem karşılaştırma
          </div>
        </div>
        <div className="top-right">
          <span className={`status-pill ${trained ? 'ok' : 'warn'}`}>
            {health == null ? 'API bağlantısı yok'
              : trained ? `Model hazır: ${health.model_name || 'ML'}`
                : 'Model eğitilmemiş (klasik mod)'}
          </span>
          <div className="who">
            <div className="who-name">{user.name}</div>
            <div className="who-meta">
              <span className="num">{user.employeeNo}</span>
              {' · '}{ROLE_TR[user.role] || user.role}
            </div>
          </div>
          <button type="button" className="chip" onClick={logout}>Çıkış</button>
        </div>
      </header>

      {error && (
        <div className="panel"
          style={{ borderLeft: '3px solid var(--critical)', marginBottom: 16 }}>
          <b>Hata:</b> {String(error)}
        </div>
      )}

      <div className="tabs view-switch">
        {VIEWS.map((v) => (
          <button key={v.id}
            className={view === v.id ? 'active' : ''}
            onClick={() => {
              setView(v.id); setSelected(null); setCreating(false)
            }}>{v.label}</button>
        ))}
      </div>

      {view === 'fleet' && (
        creating
          ? <NameplateForm mode="create"
              onCancel={() => setCreating(false)}
              onSaved={() => {
                setCreating(false)
                setFleetVersion((v) => v + 1)
              }} />
          : selected
            ? <TransformerDetail id={selected.id} meta={selected}
                onBack={() => setSelected(null)} />
            : <FleetOverview key={fleetVersion} onSelect={setSelected}
                onCreate={() => setCreating(true)} />
      )}

      {view === 'tests' && (
        selected
          ? <TransformerDetail id={selected.id} meta={selected}
              onBack={() => setSelected(null)} />
          // Test ekranından bir trafoya tıklayınca detayına gidilir;
          // ID'den kart verisi yok, en azından kimliği taşıyoruz.
          : <TestsOverview onSelect={(id) => setSelected({ id })} />
      )}

      {view === 'maintenance' && <MaintenancePanel />}

      {view === 'personnel' && <PersonnelPanel currentUser={user} />}

      {/* Analiz ekranı DOM'da kalır (sadece gizlenir) ki görünüm
          değiştirince girilen gaz değerleri ve sonuçlar kaybolmasın. */}
      <div className="grid" hidden={view !== 'analysis'}>
        <GasForm onSubmit={runAnalysis} loading={loading} />

        <div className="panel">
          <div className="tabs">
            {TABS.map((t) => (
              <button key={t.id}
                className={tab === t.id ? 'active' : ''}
                onClick={() => setTab(t.id)}>{t.label}</button>
            ))}
          </div>

          {tab === 'diagnosis' && (
            result ? <DiagnosisResult result={result} />
              : <p className="empty">Soldan değerleri girip "Analiz Et"e basın.</p>
          )}
          {tab === 'explain' && <ShapChart explanation={explanation} />}
          {tab === 'compare' && (
            <div>
              <DuvalTriangle duval={compare?.classical?.duval} />
              <ComparePanel compare={compare} leaderboard={leaderboard} />
            </div>
          )}
          {tab === 'trend' && <TrendPanel />}
        </div>
      </div>

      <p className="note" style={{
        textAlign: 'center', marginTop: 36, paddingTop: 16,
        borderTop: '1px solid var(--rule)',
      }}>
        Veriler tamamen sentetiktir (IEC 60599 / Duval / IEEE C57.104 temelli).
        Gerçek saha verisi kullanılmaz. — GE Vernova Staj Projesi
      </p>
    </div>
  )
}
