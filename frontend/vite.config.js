import fs from 'node:fs'
import path from 'node:path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev sunucusu iki servise birden yönlendirir:
//   /api   -> Python / FastAPI  :8000  (ölçüm, ML, risk)
//   /maint -> .NET / ASP.NET    :5080  (iş emri, teknisyen, planlama)
//
// Tarayıcı ikisini de aynı adresten görür; böylece CORS ayarıyla uğraşmaya
// gerek kalmaz. Gerçek dağıtımda bu işi bir ters vekil sunucu (nginx) yapar.

// --- TLS (16 Eyl) ---------------------------------------------------------
// Giriş ekranı "HTTPS/TLS yok" diyordu; artık var. Sertifika depoya GİRMEZ
// (`certs/` .gitignore'da), çünkü özel anahtar sürüm kontrolüne konmaz.
// Üretmek için proje kökünden:
//
//   openssl req -x509 -newkey rsa:2048 -nodes -days 825 \
//     -keyout certs/dev-key.pem -out certs/dev-cert.pem \
//     -subj "/C=TR/O=GE Vernova Demo/CN=localhost" \
//     -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"
//
// Dosya yoksa sunucu HTTP'ye düşer: sertifikası olmayan bir bilgisayarda
// (veya CI'da) `npm run dev` yine çalışsın istiyoruz. Kendinden imzalı
// sertifikada tarayıcı bir kez uyarır — şifreleme gerçek, güveni onaylayan
// bir otorite yok; üretimde kurumun sertifikası kullanılır.
const certDir = path.resolve(__dirname, '..', 'certs')
const certFile = path.join(certDir, 'dev-cert.pem')
const keyFile = path.join(certDir, 'dev-key.pem')
const hasCert = fs.existsSync(certFile) && fs.existsSync(keyFile)
const https = hasCert
  ? { cert: fs.readFileSync(certFile), key: fs.readFileSync(keyFile) }
  : undefined

if (!hasCert) {
  console.warn('[vite] certs/dev-cert.pem yok — arayüz HTTP ile açılıyor.')
}

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    https,
    proxy: {
      // Arka uç servisleri localhost'ta HTTP konuşmaya devam ediyor; TLS
      // tarayıcı ile Vite arasında sonlanıyor (nginx kurulumundaki ile
      // aynı model: "TLS termination at the edge").
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
