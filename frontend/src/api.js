import axios from 'axios'

// In dev, Vite proxies /api -> http://localhost:8000 (see vite.config.js).
// Override with VITE_API_BASE for other deployments.
const baseURL = import.meta.env.VITE_API_BASE || '/api'

const client = axios.create({ baseURL, timeout: 30000 })

export const api = {
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
}

export default api
