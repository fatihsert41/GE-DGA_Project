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

/** Giriş (ya da parola değiştirme) cevabından oturum kullanıcısı. */
export const userFromLogin = (result) => ({
  employeeNo: result.employeeNo,
  name: result.name,
  role: result.role,
  specialty: result.specialty,
  department: result.department,
  departmentName: result.departmentName,
  permissions: result.permissions || [],
  mustChangePassword: Boolean(result.mustChangePassword),
  expiresAt: result.expiresAt,
})

// Her isteğe belirteci ekle. İki istemciye de ayrı ayrı takılıyor:
// Python kimliği imzadan doğrular, .NET hem imzayı hem oturum satırını.
const attachToken = (config) => {
  const token = session.token()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
}
client.interceptors.request.use(attachToken)
maint.interceptors.request.use(attachToken)

// --- Kısa süreli önbellek (optimizasyon) -----------------------------------
//
// Filo, Testler ve Yönetim ekranları aynı filo listelerini kullanıyor ve
// her ekran geçişinde hepsini baştan çekiyordu. Artık bir GET cevabı
// 30 saniye saklanıyor; o sürede aynı istek sunucuya gitmeden dönüyor.
//
// İki kural bunu güvenli tutuyor:
// 1. Veri DEĞİŞTİREN her istek (POST/PUT/PATCH/DELETE) önbelleği tamamen
//    siler. Yağ testi kaydeden kullanıcı eski listeyi görmez.
// 2. Cevabın kendisi değil SÖZ (Promise) saklanır. Aynı anda iki ekran
//    aynı veriyi isterse sunucuya tek istek gider. Hata olursa kayıt
//    silinir ki bir sonraki deneme gerçekten yeniden denesin.
//
// Yalnızca yavaş değişen listeler önbelleğe alınıyor (filo özetleri,
// şemalar). Bildirimler ve iş emirleri başka kullanıcılar tarafından da
// değiştirilebildiği için her seferinde tazeleniyor.
const CACHE_MS = 30000
const cache = new Map()

const cachedGet = (http, url) => {
  const key = `${http.defaults.baseURL}${url}`
  const hit = cache.get(key)
  if (hit && Date.now() - hit.at < CACHE_MS) return hit.promise
  const promise = http.get(url).then((r) => r.data)
  cache.set(key, { at: Date.now(), promise })
  promise.catch(() => cache.delete(key))
  return promise
}

const clearCacheOnWrite = (response) => {
  if ((response.config.method || 'get').toLowerCase() !== 'get') cache.clear()
  return response
}
// Faz 10: Python yetki reddini {detail: {message, required_permission}}
// biçiminde döndürüyor. Bileşenlerin çoğu hata metnini `detail`ten okuyup
// doğrudan ekrana yazıyor; nesneyi ekrana basmaya çalışmak React'i
// çökertirdi. Burada mesaj metne indiriliyor, ayrıntı `permission`da
// saklanıyor. (Künye doğrulamasının {message, problems} biçimine
// DOKUNULMUYOR — onu NameplateForm ayrıca okuyor.)
const normalizePermissionError = (error) => {
  const data = error?.response?.data
  const detail = data?.detail
  if (detail && typeof detail === 'object' && detail.required_permission) {
    data.permission = detail
    data.detail = detail.message
  }
  return Promise.reject(error)
}

client.interceptors.response.use(clearCacheOnWrite, normalizePermissionError)
maint.interceptors.response.use(clearCacheOnWrite)

// Araç çubuğundaki "Yenile": kullanıcı sunucudaki son hâli istiyor,
// 30 saniyelik önbelleği beklememeli.
export const clearApiCache = () => cache.clear()

export const api = {
  // --- Kimlik (Faz 9.0) ---------------------------------------------------
  // Giriş .NET'te: personel kaydı orada duruyor. Python belirteci
  // imzasından doğruluyor, kimlik için .NET'e SORMUYOR — böylece .NET
  // kapalıyken de ölçüm girilebilir.
  login: (employeeNo, password) =>
    maint.post('/auth/login', { employeeNo, password }).then((r) => r.data),
  // Başarılıysa sunucu kişinin BÜTÜN oturumlarını kapatır ve yeni belirteç
  // döner; çağıran onu saklamalı (bkz. ChangePasswordScreen).
  changePassword: (currentPassword, newPassword) =>
    maint.post('/auth/change-password', { currentPassword, newPassword })
      .then((r) => r.data),
  logout: () => maint.post('/auth/logout')
    .then((r) => r.data)
    // Oturum kapanınca başka kullanıcının verisi önbellekte kalmasın.
    .finally(() => cache.clear()),
  me: () => maint.get('/auth/me').then((r) => r.data),
  personnel: () => maint.get('/technicians').then((r) => r.data),

  // --- Sistem Yönetimi — kullanıcı hesapları (AD01) -----------------------
  // Önbelleğe ALINMIYOR: kilit durumu ve son giriş sürekli değişir.
  admin: {
    users: () => maint.get('/admin/users').then((r) => r.data),
    createUser: (body) => maint.post('/admin/users', body).then((r) => r.data),
    resetPassword: (id) =>
      maint.post(`/admin/users/${id}/reset-password`).then((r) => r.data),
    unlock: (id) => maint.post(`/admin/users/${id}/unlock`).then((r) => r.data),
    deactivate: (id, reason) =>
      maint.post(`/admin/users/${id}/deactivate`, { reason }).then((r) => r.data),
    activate: (id) => maint.post(`/admin/users/${id}/activate`).then((r) => r.data),
    audit: (limit = 100) =>
      maint.get('/admin/audit', { params: { limit } }).then((r) => r.data),
  },

  // --- Bildirimler (Faz 9.2) ----------------------------------------------
  notifications: (unreadOnly = false) =>
    maint.get('/notifications', { params: { unreadOnly } }).then((r) => r.data),
  markNotificationRead: (id) =>
    maint.post(`/notifications/${id}/read`).then((r) => r.data),
  // Faz 10: personele elle bildirim gönderme ve gönderilenler kutusu.
  sendMessage: (payload) =>
    maint.post('/notifications/messages', payload).then((r) => r.data),
  sentMessages: () => maint.get('/notifications/sent').then((r) => r.data),

  // --- Departmanlar ve yetkiler (Faz 10) ----------------------------------
  // Katalog nadiren değişir, önbelleğe alınıyor. Departman değiştirmek bir
  // yazma isteği olduğu için önbelleği zaten kendisi temizler.
  departments: () => cachedGet(maint, '/departments'),
  changeDepartment: (id, department) =>
    maint.put(`/technicians/${id}/department`, { department })
      .then((r) => r.data),

  // --- Mühendislik test onay kuyruğu (Faz 12.2) ---------------------------
  // Önbelleğe ALINMIYOR: kuyruk başka mühendislerin kararıyla değişir.
  reviewQueue: (folder = 'pending') =>
    client.get('/reviews/queue', { params: { folder } }).then((r) => r.data),
  reviewDecision: (kind, testId, body) =>
    client.post(`/reviews/${kind}/${testId}/decision`, body).then((r) => r.data),

  // --- Model inceleme / uzman etiketi (Faz 12.3) --------------------------
  modelReviewQueue: (folder = 'pending') =>
    client.get('/model-reviews/queue', { params: { folder } }).then((r) => r.data),
  modelReviewDetail: (id) =>
    client.get(`/model-reviews/${id}`).then((r) => r.data),
  modelReviewLabel: (id, body) =>
    client.post(`/model-reviews/${id}/label`, body).then((r) => r.data),

  // --- Varlığa özel eşik (Faz 12.4) ---------------------------------------
  // Önbelleğe ALINMIYOR: istisnanın durumu başka mühendislerin kararıyla
  // ve süre dolunca kendiliğinden değişir.
  limitsSchema: () => client.get('/limits/schema').then((r) => r.data),
  limitsQueue: (folder = 'pending') =>
    client.get('/limits/queue', { params: { folder } }).then((r) => r.data),
  transformerLimits: (id) =>
    client.get(`/transformers/${id}/limits`).then((r) => r.data),
  proposeLimit: (id, body) =>
    client.post(`/transformers/${id}/limits`, body).then((r) => r.data),
  limitDecision: (overrideId, body) =>
    client.post(`/limits/${overrideId}/decision`, body).then((r) => r.data),
  revokeLimit: (overrideId, body) =>
    client.post(`/limits/${overrideId}/revoke`, body).then((r) => r.data),

  health: () => client.get('/health').then((r) => r.data),
  predict: (payload) => client.post('/predict', payload).then((r) => r.data),
  explain: (gases) => client.post('/explain', gases).then((r) => r.data),
  compare: (gases) => client.post('/compare', gases).then((r) => r.data),
  leaderboard: () => cachedGet(client, '/compare/leaderboard'),
  realityCheck: () => client.get('/compare/reality-check').then((r) => r.data),
  trendDemo: (cls, months = 24, horizon = 6) =>
    client.get(`/trend/demo/${cls}`, { params: { months, horizon } })
      .then((r) => r.data),
  trendFromSamples: (payload) =>
    client.post('/trend', payload).then((r) => r.data),
  fleetOverview: () => cachedGet(client, '/fleet/overview'),
  transformerTrend: (id, horizon = 6) =>
    client.get(`/trend/${id}`, { params: { horizon } }).then((r) => r.data),
  measurements: (id) =>
    client.get(`/transformers/${id}/measurements`).then((r) => r.data),

  // --- Varlık kaydı / künye (Faz 8.1-8.2) ---------------------------------
  transformer: (id) => client.get(`/transformers/${id}`).then((r) => r.data),
  // Form açılır listeleri backend'den gelir; seçenekleri burada tekrar
  // yazmak iki yerde iki farklı gerçek yaratırdı.
  nameplateSchema: () => cachedGet(client, '/transformers/schema'),
  createTransformer: (payload) =>
    client.post('/transformers', payload).then((r) => r.data),
  updateNameplate: (id, fields) =>
    client.put(`/transformers/${id}/nameplate`, fields).then((r) => r.data),

  // --- Yağ kalitesi ve kağıt yaşlanması (Faz 8.3-8.4) ---------------------
  oilSchema: () => cachedGet(client, '/oil/schema'),
  oilFleet: () => cachedGet(client, '/oil/fleet'),
  oilTests: (id) =>
    client.get(`/transformers/${id}/oil-tests`).then((r) => r.data),
  createOilTest: (id, payload) =>
    client.post(`/transformers/${id}/oil-tests`, payload).then((r) => r.data),

  // --- Elektriksel testler (Faz 8.6) --------------------------------------
  electricalSchema: () => cachedGet(client, '/electrical/schema'),
  electricalFleet: () => cachedGet(client, '/electrical/fleet'),
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

  // --- Trafo şeması (Faz 9.6) ---------------------------------------------
  // Parça renklerini belirleyen kurallar BACKEND'de; arayüz yalnızca
  // çizer. Kuralı iki yerde tutmak, iki farklı gerçek yaratırdı.
  schematic: (id) =>
    client.get(`/transformers/${id}/schematic`).then((r) => r.data),

  // --- Buşing ve kademe değiştirici (Faz 9.4) -----------------------------
  componentsSchema: () => cachedGet(client, '/components/schema'),
  componentsFleet: () => cachedGet(client, '/components/fleet'),
  componentTests: (id) =>
    client.get(`/transformers/${id}/component-tests`).then((r) => r.data),
  createComponentTest: (id, payload) =>
    client.post(`/transformers/${id}/component-tests`, payload)
      .then((r) => r.data),

  // --- Fiziksel saha gözlemi (Faz 9.5) ------------------------------------
  physicalSchema: () => cachedGet(client, '/physical/schema'),
  physicalFleet: () => cachedGet(client, '/physical/fleet'),
  inspections: (id) =>
    client.get(`/transformers/${id}/inspections`).then((r) => r.data),
  createInspection: (id, payload) =>
    client.post(`/transformers/${id}/inspections`, payload).then((r) => r.data),

  // --- Varlık yaşam döngüsü (Faz 9.35) ------------------------------------
  lifecycleSchema: () => cachedGet(client, '/lifecycle/schema'),
  lifecycle: (id) =>
    client.get(`/transformers/${id}/lifecycle`).then((r) => r.data),
  changeLifecycle: (id, status, note) =>
    client.put(`/transformers/${id}/lifecycle`, { status, note })
      .then((r) => r.data),

  // --- Sağlık endeksi (Faz 8.5) -------------------------------------------
  // Ağırlıklar ve bantlar backend'den gelir; arayüze sabit yazmak formül
  // değiştiğinde ekranın yalan söylemesine yol açardı.
  healthSchema: () => cachedGet(client, '/health-index/schema'),
  healthFleet: () => cachedGet(client, '/health-index/fleet'),
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
    // Tamamlarken not ZORUNLU (sunucu kuralı). Önceden not gönderilmiyordu
    // ve "Bitir" her seferinde reddediliyordu.
    setStatus: (id, status, note = null) =>
      maint.patch(`/workorders/${id}/status`, { status, note }).then((r) => r.data),

    // --- Kök neden analizi (Faz 12.5) ---------------------------------
    rcaSchema: () => maint.get('/rca/schema').then((r) => r.data),
    rcaPending: () => maint.get('/rca/pending').then((r) => r.data),
    rcaList: (params = {}) => maint.get('/rca', { params }).then((r) => r.data),
    rcaSimilar: (params) => maint.get('/rca/similar', { params }).then((r) => r.data),
    workOrderRca: (id) => maint.get(`/workorders/${id}/rca`).then((r) => r.data),
    createRca: (id, body) =>
      maint.post(`/workorders/${id}/rca`, body).then((r) => r.data),
  },
}

export default api
