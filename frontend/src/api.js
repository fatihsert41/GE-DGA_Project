import axios from 'axios'

// In dev, Vite proxies /api -> http://localhost:8000 (see vite.config.js).
// Override with VITE_API_BASE for other deployments.
const baseURL = import.meta.env.VITE_API_BASE || '/api'

const client = axios.create({ baseURL, timeout: 30000 })

// .NET bakım servisi ayrı bir istemci. Ayrı olmasının sebebi sadece adres
// değil: bu servis kapalıyken ML tarafı çalışmaya devam etmeli, o yüzden
// hataları da ayrı ele alıyoruz.
const maintBase = import.meta.env.VITE_MAINT_BASE || '/maint'
const maint = axios.create({ baseURL: maintBase, timeout: 30000 })

// --- Oturum belirteci (Faz 9.0d) -------------------------------------------
//
// Belirteç tarayıcıda `localStorage`ta tutulur, böylece sayfa
// yenilendiğinde oturum kaybolmaz.
//
// ⚠ SINIR: localStorage, sayfaya kod enjekte edebilen bir saldırgana
// (XSS) açıktır. Daha güvenlisi HttpOnly çerezdir — JavaScript onu
// okuyamaz. Bu demoda localStorage seçildi çünkü çerez, iki ayrı servise
// (8000 ve 5080) giden istekler için alan/CORS ayarı gerektiriyor ve
// konuyu dağıtıyordu. Gerçek kurulumda HttpOnly çerez + TLS kullanılmalı.
const TOKEN_KEY = 'transformerai.token'
const USER_KEY = 'transformerai.user'

export const session = {
  token: () => {
    try { return localStorage.getItem(TOKEN_KEY) } catch { return null }
  },
  user: () => {
    try { return JSON.parse(localStorage.getItem(USER_KEY) || 'null') }
    catch { return null }
  },
  save: (token, user) => {
    try {
      localStorage.setItem(TOKEN_KEY, token)
      localStorage.setItem(USER_KEY, JSON.stringify(user))
    } catch { /* özel sekme: oturum sayfa ömrü kadar sürer */ }
  },
  clear: () => {
    try {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
    } catch { /* yok sayılır */ }
  },
}

// Her isteğe belirteci ekle. İki istemciye de ayrı ayrı takılıyor:
// Python kimliği imzadan doğrular, .NET hem imzayı hem oturum satırını.
const attachToken = (config) => {
  const token = session.token()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
}
client.interceptors.request.use(attachToken)
maint.interceptors.request.use(attachToken)

export const api = {
  // --- Kimlik (Faz 9.0) ---------------------------------------------------
  // Giriş .NET'te: personel kaydı orada duruyor. Python belirteci
  // imzasından doğruluyor, kimlik için .NET'e SORMUYOR — böylece .NET
  // kapalıyken de ölçüm girilebilir.
  login: (employeeNo, pin) =>
    maint.post('/auth/login', { employeeNo, pin }).then((r) => r.data),
  logout: () => maint.post('/auth/logout').then((r) => r.data),
  me: () => maint.get('/auth/me').then((r) => r.data),
  personnel: () => maint.get('/technicians').then((r) => r.data),

  // --- Bildirimler (Faz 9.2) ----------------------------------------------
  notifications: (unreadOnly = false) =>
    maint.get('/notifications', { params: { unreadOnly } }).then((r) => r.data),
  markNotificationRead: (id) =>
    maint.post(`/notifications/${id}/read`).then((r) => r.data),

  health: () => client.get('/health').then((r) => r.data),
  predict: (payload) => client.post('/predict', payload).then((r) => r.data),
  explain: (gases) => client.post('/explain', gases).then((r) => r.data),
  compare: (gases) => client.post('/compare', gases).then((r) => r.data),
  leaderboard: () => client.get('/compare/leaderboard').then((r) => r.data),
  realityCheck: () => client.get('/compare/reality-check').then((r) => r.data),
  trendDemo: (cls, months = 24, horizon = 6) =>
    client.get(`/trend/demo/${cls}`, { params: { months, horizon } })
      .then((r) => r.data),
  trendFromSamples: (payload) =>
    client.post('/trend', payload).then((r) => r.data),
  fleetOverview: () => client.get('/fleet/overview').then((r) => r.data),
  transformerTrend: (id, horizon = 6) =>
    client.get(`/trend/${id}`, { params: { horizon } }).then((r) => r.data),
  measurements: (id) =>
    client.get(`/transformers/${id}/measurements`).then((r) => r.data),

  // --- Varlık kaydı / künye (Faz 8.1-8.2) ---------------------------------
  transformer: (id) => client.get(`/transformers/${id}`).then((r) => r.data),
  // Form açılır listeleri backend'den gelir; seçenekleri burada tekrar
  // yazmak iki yerde iki farklı gerçek yaratırdı.
  nameplateSchema: () => client.get('/transformers/schema').then((r) => r.data),
  createTransformer: (payload) =>
    client.post('/transformers', payload).then((r) => r.data),
  updateNameplate: (id, fields) =>
    client.put(`/transformers/${id}/nameplate`, fields).then((r) => r.data),

  // --- Yağ kalitesi ve kağıt yaşlanması (Faz 8.3-8.4) ---------------------
  oilSchema: () => client.get('/oil/schema').then((r) => r.data),
  oilFleet: () => client.get('/oil/fleet').then((r) => r.data),
  oilTests: (id) =>
    client.get(`/transformers/${id}/oil-tests`).then((r) => r.data),
  createOilTest: (id, payload) =>
    client.post(`/transformers/${id}/oil-tests`, payload).then((r) => r.data),

  // --- Elektriksel testler (Faz 8.6) --------------------------------------
  electricalSchema: () => client.get('/electrical/schema').then((r) => r.data),
  electricalFleet: () => client.get('/electrical/fleet').then((r) => r.data),
  electricalTests: (id) =>
    client.get(`/transformers/${id}/electrical-tests`).then((r) => r.data),
  createElectricalTest: (id, payload) =>
    client.post(`/transformers/${id}/electrical-tests`, payload)
      .then((r) => r.data),
  // Ayrı uç nokta olmasının sebebi: teknisyen ölçtüğü sayıyı GİRERKEN
  // beklenen değeri görmeli, kaydettikten sonra değil. Kademe seçilir
  // seçilmez beklenti güncellenir.
  expectedRatio: (id, tap) =>
    client.get(`/transformers/${id}/expected-ratio`,
      { params: tap == null ? {} : { tap } }).then((r) => r.data),

  // Hatalı kayıt SİLİNMEZ, geçersiz işaretlenir: denetim izi korunur.
  voidElectricalTest: (id, testId, reason) =>
    client.post(`/transformers/${id}/electrical-tests/${testId}/void`,
      { reason }).then((r) => r.data),
  unvoidElectricalTest: (id, testId) =>
    client.delete(`/transformers/${id}/electrical-tests/${testId}/void`)
      .then((r) => r.data),

  // --- Sağlık endeksi (Faz 8.5) -------------------------------------------
  // Ağırlıklar ve bantlar backend'den gelir; arayüze sabit yazmak formül
  // değiştiğinde ekranın yalan söylemesine yol açardı.
  healthSchema: () => client.get('/health-index/schema').then((r) => r.data),
  healthFleet: () => client.get('/health-index/fleet').then((r) => r.data),
  transformerHealth: (id) =>
    client.get(`/transformers/${id}/health`).then((r) => r.data),

  // --- Bakım planlama servisi (.NET) ---------------------------------------
  maintenance: {
    health: () => maint.get('/health').then((r) => r.data),
    workOrders: (params = {}) =>
      maint.get('/workorders', { params }).then((r) => r.data),
    summary: () => maint.get('/workorders/summary').then((r) => r.data),
    suggestions: () => maint.get('/workorders/suggestions').then((r) => r.data),
    applySuggestions: () =>
      maint.post('/workorders/suggestions/apply').then((r) => r.data),
    technicians: () => maint.get('/technicians').then((r) => r.data),
    assign: (id, technicianId = null) =>
      maint.post(`/workorders/${id}/assign`, { technicianId })
        .then((r) => r.data),
    setStatus: (id, status) =>
      maint.patch(`/workorders/${id}/status`, { status }).then((r) => r.data),
  },
}

export default api
