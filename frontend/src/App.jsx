import { lazy, Suspense, useCallback, useEffect, useState } from 'react'
import api, { clearApiCache, session } from './api'
import { can, canAny } from './permissions'
// Giriş ekranı HEMEN yüklenir: kullanıcının ilk gördüğü şey o.
import LoginScreen from './components/LoginScreen'
import NoPermission from './components/NoPermission'

// Kod bölme: her ekran İLK AÇILDIĞINDA ayrı dosya olarak indirilir.
// `lazy` bileşeni ilk çizileceği ana kadar indirmez; `Suspense` indirme
// sürerken yerine ne gösterileceğini belirler.
const GasForm = lazy(() => import('./components/GasForm'))
const DiagnosisResult = lazy(() => import('./components/DiagnosisResult'))
const ShapChart = lazy(() => import('./components/ShapChart'))
const DuvalTriangle = lazy(() => import('./components/DuvalTriangle'))
const ComparePanel = lazy(() => import('./components/ComparePanel'))
const TrendPanel = lazy(() => import('./components/TrendPanel'))
const FleetOverview = lazy(() => import('./components/FleetOverview'))
const TransformerDetail = lazy(() => import('./components/TransformerDetail'))
const MaintenancePanel = lazy(() => import('./components/MaintenancePanel'))
const NameplateForm = lazy(() => import('./components/NameplateForm'))
const TestsOverview = lazy(() => import('./components/TestsOverview'))
const PersonnelPanel = lazy(() => import('./components/PersonnelPanel'))
const NotificationsPanel = lazy(() => import('./components/NotificationsPanel'))
const ManagerDashboard = lazy(() => import('./components/ManagerDashboard'))
const ReviewQueue = lazy(() => import('./components/ReviewQueue'))
const ModelReviewQueue = lazy(() => import('./components/ModelReviewQueue'))

const Loading = () => (
  <div className="panel"><p className="empty">Yükleniyor…</p></div>
)

const TABS = [
  { id: 'diagnosis', label: 'Tanı' },
  { id: 'explain', label: 'Açıklama (SHAP)' },
  { id: 'compare', label: 'Karşılaştırma' },
  { id: 'trend', label: 'Trend Tahmini' },
]

/* Faz 11 — ERP kabuğu.
 *
 * Kullanıcı isteği: "Canias ERP gibi bir ekran, AI frontendinden
 * uzaklaşalım." Kurumsal ERP'lerin (Canias, SAP, Logo) ortak yapısı
 * burada birebir kuruldu:
 *
 *   * MODÜL AĞACI — ekranlar işlevsel modüllere (Varlık, Analiz, Bakım,
 *     Yönetim, İletişim) klasör klasör ayrılır.
 *   * İŞLEM KODU — her ekranın kısa bir kodu var (FL01, BK01…). Sık
 *     kullanan personel menüde gezinmez, kodu yazıp Enter'a basar.
 *   * ÇOKLU PENCERE — açılan ekranlar sekme olur; kullanıcı işini
 *     kaybetmeden ekranlar arasında geçer.
 *   * ARAÇ ÇUBUĞU ve DURUM ÇUBUĞU — her ekranda aynı yerde aynı
 *     komutlar; altta bağlantı ve oturum bilgisi.
 *
 * Yetki mantığı Faz 10'daki gibi: ekranın `permission` alanı listeyse
 * listedekilerden BİRİ yeterli. Yetkisiz ekran menüde kilitli görünür.
 * ⚠ Bu bir GÜVENLİK sınırı DEĞİLDİR; asıl kontrol sunucuda (403).
 */
const MODULES = [
  { id: 'assets', label: 'Varlık Yönetimi' },
  { id: 'analysis', label: 'Analiz' },
  { id: 'maintenance', label: 'Bakım Yönetimi' },
  { id: 'engineering', label: 'Mühendislik' },
  { id: 'admin', label: 'Yönetim' },
  { id: 'comm', label: 'İletişim' },
]

const VIEWS = [
  { id: 'fleet', code: 'FL01', label: 'Filo Durumu', module: 'assets' },
  { id: 'tests', code: 'TS01', label: 'Test Durumu', module: 'assets' },
  { id: 'analysis', code: 'NA01', label: 'Numune Analizi', module: 'analysis',
    permission: 'analysis.run' },
  { id: 'maintenance', code: 'BK01', label: 'Bakım Planlama', module: 'maintenance',
    permission: ['workorders.plan', 'workorders.execute'] },
  // Faz 12.2 — sınır dışı test sonuçları mühendis kararını bekler.
  { id: 'reviews', code: 'MH01', label: 'Test Onay Kuyruğu', module: 'engineering',
    permission: 'engineering.approve' },
  // Faz 12.3 — model kararsız kaldığında mühendis gerçek tanıyı seçer.
  { id: 'model-reviews', code: 'MH02', label: 'Model İnceleme', module: 'engineering',
    permission: 'engineering.review_model' },
  { id: 'manager', code: 'YN01', label: 'Yönetim Özeti', module: 'admin',
    permission: 'manager.view' },
  { id: 'personnel', code: 'PR01', label: 'Personel', module: 'admin',
    permission: 'personnel.view' },
  // Gelen kutusu, yeni bildirim ve gönderilenler TEK ekranda (Faz 11).
  { id: 'notifications', code: 'BL01', label: 'Bildirimler', module: 'comm' },
]

const ROLE_TR = {
  Technician: 'Teknisyen',
  Engineer: 'Mühendis',
  Supervisor: 'Süpervizör',
}

const viewById = (id) => VIEWS.find((v) => v.id === id)
const allowedFor = (viewDef, user) =>
  !viewDef?.permission || canAny(viewDef.permission, user)
const upperTr = (s) => s.toLocaleUpperCase('tr-TR')

export default function App() {
  // Oturum. Sayfa yenilendiğinde localStorage'tan geri okunur; belirtecin
  // hâlâ geçerli olup olmadığını /auth/me söyler.
  const [user, setUser] = useState(() => {
    const saved = session.user()
    // Faz 10 öncesi açılmış oturumda yetki listesi yok → yeniden giriş.
    if (saved && !Array.isArray(saved.permissions)) {
      session.clear()
      return null
    }
    return saved
  })

  // Açık pencereler (sekmeler) ve etkin olan.
  const [openTabs, setOpenTabs] = useState(['fleet'])
  const [view, setView] = useState('fleet')
  // Menüde kapatılmış modül klasörleri.
  const [collapsed, setCollapsed] = useState(() => new Set())
  const [tcode, setTcode] = useState('')
  const [statusMsg, setStatusMsg] = useState('Hazır')
  // "Yenile" düğmesi: değeri değişince etkin ekran baştan kurulur.
  const [refreshKey, setRefreshKey] = useState(0)

  // Seçili trafo kartı (null ise liste görünür).
  const [selected, setSelected] = useState(null)
  // Yeni trafo kaydı formu açık mı? Filo listesinin yerine geçer.
  const [creating, setCreating] = useState(false)
  const [fleetVersion, setFleetVersion] = useState(0)
  const [tab, setTab] = useState('diagnosis')
  const [loading, setLoading] = useState(false)
  const [health, setHealth] = useState(null)
  const [maintUp, setMaintUp] = useState(null)
  const [error, setError] = useState(null)

  // Departman ve yetkiler buradan TAZELENİR: yönetim birinin departmanını
  // değiştirdiyse menü sayfa yenilenince güncellenir.
  useEffect(() => {
    if (!session.token()) return
    api.me()
      .then((me) => {
        const next = {
          ...session.user(),
          employeeNo: me.employeeNo, name: me.name, role: me.role,
          specialty: me.specialty, department: me.department,
          departmentName: me.departmentName, permissions: me.permissions,
        }
        session.save(session.token(), next)
        setUser(next)
      })
      .catch(() => { session.clear(); setUser(null) })
  }, [])

  // Okunmamış bildirim sayısı ve bakım servisi bağlantısı: 60 sn'de bir.
  const [unread, setUnread] = useState(0)

  const refreshUnread = useCallback(() => {
    if (!session.token()) return
    api.notifications(true)
      .then((d) => setUnread(d.unread ?? 0))
      .catch(() => {})
    api.maintenance.health()
      .then(() => setMaintUp(true))
      .catch(() => setMaintUp(false))
  }, [])

  useEffect(() => {
    refreshUnread()
    const timer = setInterval(refreshUnread, 60000)
    return () => clearInterval(timer)
  }, [refreshUnread, view])

  const [result, setResult] = useState(null)
  const [explanation, setExplanation] = useState(null)
  const [compare, setCompare] = useState(null)
  const [leaderboard, setLeaderboard] = useState(null)

  // Numune Analizi ilk kez açıldı mı? Açılmadıysa hiç çizilmez (kodu da
  // inmez). Açıldıktan sonra DOM'da kalır ki girilen değerler kaybolmasın.
  const [analysisOpened, setAnalysisOpened] = useState(false)

  const viewDef = viewById(view)
  const allowed = allowedFor(viewDef, user)
  const analysisAllowed = allowedFor(viewById('analysis'), user)

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null))
  }, [])

  useEffect(() => {
    if (view !== 'analysis' || analysisOpened || !analysisAllowed) return
    setAnalysisOpened(true)
    api.leaderboard().then(setLeaderboard).catch(() => {})
  }, [view, analysisOpened, analysisAllowed])

  // --- Pencere yönetimi -----------------------------------------------------

  const openView = (id) => {
    setOpenTabs((prev) => (prev.includes(id) ? prev : [...prev, id]))
    setView(id)
    setSelected(null)
    setCreating(false)
  }

  const closeTab = (id) => {
    if (openTabs.length <= 1) return            // en az bir pencere açık kalır
    const idx = openTabs.indexOf(id)
    const next = openTabs.filter((t) => t !== id)
    setOpenTabs(next)
    if (id === view) {
      setView(next[Math.max(0, idx - 1)])
      setSelected(null)
      setCreating(false)
    }
  }

  const toggleModule = (id) => setCollapsed((prev) => {
    const next = new Set(prev)
    if (next.has(id)) next.delete(id); else next.add(id)
    return next
  })

  // İşlem kodu: tam kod (FL01) ya da ekran adının başı ("bak", "per").
  const runCode = (e) => {
    e.preventDefault()
    const q = upperTr(tcode.trim())
    if (!q) return
    const target = VIEWS.find((v) => v.code === q)
      || VIEWS.find((v) => upperTr(v.label).startsWith(q))
    if (!target) {
      setStatusMsg(`İşlem kodu bulunamadı: ${q}`)
      return
    }
    openView(target.id)
    setTcode('')
    setStatusMsg(`${target.code} · ${target.label} açıldı`)
  }

  const refresh = () => {
    // Önbellekteki liste 30 sn saklanıyor; "Yenile" diyen kullanıcı
    // gerçekten sunucudaki son hâli görmeli.
    clearApiCache()
    setRefreshKey((k) => k + 1)
    refreshUnread()
    setStatusMsg(`${viewDef?.code} yenilendi · ${new Date().toLocaleTimeString('tr-TR')}`)
  }

  const logout = () => {
    // Sunucuya haber ver (belirteç ANINDA iptal olsun), sonra yerelde
    // temizle. Sunucu ulaşılamazsa da yerel temizlik yapılır.
    api.logout().catch(() => {}).finally(() => {
      session.clear()
      setUser(null)
      setSelected(null)
      setOpenTabs(['fleet'])
      setView('fleet')
      setAnalysisOpened(false)
    })
  }

  const runAnalysis = async (payload) => {
    setLoading(true); setError(null)
    try {
      const res = await api.predict(payload)
      setResult(res)
      const cmp = await api.compare(payload.gases)
      setCompare(cmp)
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

  const today = new Date().toLocaleDateString('tr-TR',
    { day: '2-digit', month: '2-digit', year: 'numeric' })

  return (
    <div className="erp">
      {/* --- Başlık çubuğu ------------------------------------------------ */}
      <header className="erp-titlebar">
        <div className="erp-brand">
          <span className="erp-logo" aria-hidden="true" />
          <div>
            <b>TransformerAI</b>
            <span>Varlık İzleme ve Bakım Yönetim Sistemi</span>
          </div>
        </div>

        <form className="erp-tcode" onSubmit={runCode} role="search">
          <label htmlFor="tcode">İşlem kodu</label>
          <input id="tcode" value={tcode} list="tcodes" autoComplete="off"
            onChange={(e) => setTcode(e.target.value)} placeholder="ör. BK01" />
          <datalist id="tcodes">
            {VIEWS.map((v) => <option key={v.id} value={v.code}>{v.label}</option>)}
          </datalist>
          <button type="submit">Git</button>
        </form>

        <div className="erp-user">
          <div className="erp-user-text">
            <span className="erp-user-name">{user.name}</span>
            <span className="erp-user-meta">
              {user.employeeNo} · {user.departmentName}
            </span>
          </div>
          <button type="button" className="erp-logout" onClick={logout}>Çıkış</button>
        </div>
      </header>

      <div className="erp-body">
        {/* --- Modül ağacı ------------------------------------------------ */}
        <nav className="erp-menu" aria-label="Ana menü">
          <div className="erp-menu-head">Ana Menü</div>
          {MODULES.map((m) => {
            const isOpen = !collapsed.has(m.id)
            return (
              <div key={m.id} className="erp-module">
                <button type="button" className="erp-module-head"
                  aria-expanded={isOpen} onClick={() => toggleModule(m.id)}>
                  <span className={`erp-folder${isOpen ? ' open' : ''}`} aria-hidden="true" />
                  {m.label}
                </button>
                {isOpen && (
                  <ul>
                    {VIEWS.filter((v) => v.module === m.id).map((v) => {
                      const locked = !allowedFor(v, user)
                      return (
                        <li key={v.id}>
                          <button type="button"
                            className={[view === v.id ? 'active' : '', locked ? 'locked' : '']
                              .filter(Boolean).join(' ')}
                            aria-current={view === v.id ? 'page' : undefined}
                            title={locked ? 'Departmanınızın bu ekrana yetkisi yok' : undefined}
                            onClick={() => openView(v.id)}>
                            <span className="erp-code">{v.code}</span>
                            <span className="erp-item-label">{v.label}</span>
                            {v.id === 'notifications' && unread > 0 && (
                              <span className="sidebar-count">{unread}</span>
                            )}
                            {locked && <span className="sidebar-lock" aria-label="yetki yok" />}
                          </button>
                        </li>
                      )
                    })}
                  </ul>
                )}
              </div>
            )
          })}
        </nav>

        <main className="erp-workspace">
          {/* --- Açık pencereler ------------------------------------------ */}
          <div className="erp-tabs" role="tablist" aria-label="Açık ekranlar">
            {openTabs.map((id) => {
              const v = viewById(id)
              const active = id === view
              return (
                <div key={id} className={`erp-tab${active ? ' active' : ''}`}>
                  <button type="button" role="tab" aria-selected={active}
                    className="erp-tab-label"
                    onClick={() => { setView(id); setSelected(null); setCreating(false) }}>
                    <span className="erp-code">{v.code}</span> {v.label}
                  </button>
                  {openTabs.length > 1 && (
                    <button type="button" className="erp-tab-close"
                      aria-label={`${v.label} penceresini kapat`}
                      onClick={() => closeTab(id)}>×</button>
                  )}
                </div>
              )
            })}
          </div>

          {/* --- Araç çubuğu ---------------------------------------------- */}
          <div className="erp-toolbar">
            <div className="erp-toolbar-title">
              <span className="erp-code">{viewDef.code}</span> {viewDef.label}
              {selected && (
                <><span className="erp-crumb">›</span>{selected.id}</>
              )}
              {creating && (
                <><span className="erp-crumb">›</span>Yeni trafo kaydı</>
              )}
            </div>
            <div className="erp-toolbar-actions">
              {(selected || creating) && (
                <button type="button" className="erp-tb"
                  onClick={() => { setSelected(null); setCreating(false) }}>Geri</button>
              )}
              <button type="button" className="erp-tb" onClick={refresh}>Yenile</button>
              <button type="button" className="erp-tb" onClick={() => window.print()}>Yazdır</button>
              {openTabs.length > 1 && (
                <button type="button" className="erp-tb" onClick={() => closeTab(view)}>Kapat</button>
              )}
            </div>
          </div>

          <div className="erp-content">
            {error && (
              <div className="np-problems" style={{ marginBottom: 10 }}>
                <b>Hata:</b> {String(error)}
              </div>
            )}

            {!allowed && (
              <NoPermission permission={viewDef.permission} screen={viewDef.label} />
            )}

            {allowed && (
              <Suspense fallback={<Loading />}>
                <div key={`${view}-${refreshKey}`}>
                  {view === 'fleet' && (
                    creating && can('assets.edit')
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
                            onCreate={can('assets.edit') ? () => setCreating(true) : undefined} />
                  )}

                  {view === 'tests' && (
                    selected
                      ? <TransformerDetail id={selected.id} meta={selected}
                          onBack={() => setSelected(null)} />
                      : <TestsOverview onSelect={(id) => setSelected({ id })} />
                  )}

                  {view === 'maintenance' && <MaintenancePanel />}

                  {view === 'reviews' && (
                    selected
                      ? <TransformerDetail id={selected.id} meta={selected}
                          onBack={() => setSelected(null)} />
                      : <ReviewQueue onOpenTransformer={(id) => setSelected({ id })} />
                  )}

                  {view === 'model-reviews' && (
                    selected
                      ? <TransformerDetail id={selected.id} meta={selected}
                          onBack={() => setSelected(null)} />
                      : <ModelReviewQueue onOpenTransformer={(id) => setSelected({ id })} />
                  )}

                  {view === 'manager' && (
                    selected
                      ? <TransformerDetail id={selected.id} meta={selected}
                          onBack={() => setSelected(null)} />
                      : <ManagerDashboard onSelect={setSelected} />
                  )}

                  {view === 'personnel' && <PersonnelPanel currentUser={user} />}

                  {view === 'notifications' && (
                    selected
                      ? <TransformerDetail id={selected.id} meta={selected}
                          onBack={() => setSelected(null)} />
                      : <NotificationsPanel
                          onOpenTransformer={(id) => setSelected({ id })}
                          onChange={refreshUnread} />
                  )}
                </div>
              </Suspense>
            )}

            {analysisOpened && analysisAllowed && (
              <Suspense fallback={view === 'analysis' ? <Loading /> : null}>
                <div className="grid" hidden={view !== 'analysis'}>
                  <GasForm onSubmit={runAnalysis} loading={loading} />

                  <div className="panel">
                    <div className="tabs">
                      {TABS.map((t) => (
                        <button key={t.id} type="button"
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
              </Suspense>
            )}
          </div>
        </main>
      </div>

      {/* --- Durum çubuğu ------------------------------------------------- */}
      <footer className="erp-statusbar">
        <span className="erp-status-msg" role="status">{statusMsg}</span>
        <span className={`erp-svc ${health ? 'ok' : 'down'}`}>
          Analiz servisi: {health
            ? (trained ? `bağlı · ${health.model_name || 'model'} hazır` : 'bağlı · klasik mod')
            : 'bağlantı yok'}
        </span>
        <span className={`erp-svc ${maintUp ? 'ok' : maintUp === null ? '' : 'down'}`}>
          Bakım servisi: {maintUp ? 'bağlı' : maintUp === null ? 'kontrol ediliyor' : 'bağlantı yok'}
        </span>
        <span>{user.employeeNo} · {ROLE_TR[user.role] || user.role}</span>
        <span className="num">{today}</span>
      </footer>
    </div>
  )
}
