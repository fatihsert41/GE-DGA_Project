import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev sunucusu iki servise birden yönlendirir:
//   /api   -> Python / FastAPI  :8000  (ölçüm, ML, risk)
//   /maint -> .NET / ASP.NET    :5080  (iş emri, teknisyen, planlama)
//
// Tarayıcı ikisini de aynı adresten (localhost:5173) görür; böylece CORS
// ayarıyla uğraşmaya gerek kalmaz. Gerçek dağıtımda bu işi bir ters vekil
// sunucu (nginx gibi) veya API ağ geçidi yapar.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/api/, ''),
      },
      '/maint': {
        target: 'http://localhost:5080',
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/maint/, ''),
      },
    },
  },
})
