import { useEffect, useState } from 'react'
import api from './api'
import GasForm from './components/GasForm'
import DiagnosisResult from './components/DiagnosisResult'
import ShapChart from './components/ShapChart'
import DuvalTriangle from './components/DuvalTriangle'
import ComparePanel from './components/ComparePanel'
import TrendPanel from './components/TrendPanel'

const TABS = [
  { id: 'diagnosis', label: 'Tanı' },
  { id: 'explain', label: 'Açıklama (SHAP)' },
  { id: 'compare', label: 'Karşılaştırma' },
  { id: 'trend', label: 'Trend Tahmini' },
]

export default function App() {
  const [tab, setTab] = useState('diagnosis')
  const [loading, setLoading] = useState(false)
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

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

  return (
    <div className="app">
      <header className="top">
        <div>
          <h1>⚡ TransformerAI — DGA Arıza Tahmin</h1>
          <div className="sub">
            Çözünmüş gaz analizi · açıklanabilir AI · klasik yöntem karşılaştırma · trend
          </div>
        </div>
        <span className={`status-pill ${trained ? 'ok' : 'warn'}`}>
          {health == null ? 'API bağlantısı yok'
            : trained ? `Model hazır: ${health.model_name || 'ML'}`
              : 'Model eğitilmemiş (klasik mod)'}
        </span>
      </header>

      {error && (
        <div className="panel" style={{ borderColor: '#ef4444', marginBottom: 16 }}>
          <b>Hata:</b> {String(error)}
        </div>
      )}

      <div className="grid">
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

      <p className="note" style={{ textAlign: 'center', marginTop: 24 }}>
        Veriler tamamen sentetiktir (IEC 60599 / Duval / IEEE C57.104 temelli).
        Gerçek saha verisi kullanılmaz. — GE Vernova Staj Projesi
      </p>
    </div>
  )
}
