# TransformerAI — Frontend (React + Vite)

DGA arıza tahmin sisteminin gösterge paneli.

## Çalıştırma

```bash
npm install
npm run dev      # http://localhost:5173
```

Dev sunucusu `/api` isteklerini `http://localhost:8000` (FastAPI backend'e)
yönlendirir (bkz. `vite.config.js`). Farklı bir backend adresi için:

```bash
VITE_API_BASE=http://sunucu:8000 npm run dev
```

> Backend'in çalışıyor olması gerekir. Model eğitilmemişse panel "klasik mod"
> ile çalışır; SHAP açıklaması için önce `python -m app.ml.train` çalıştırın.

## Ekranlar

- **Tanı** — arıza tipi, risk rozeti, ML ↔ klasik uyumu
- **Açıklama (SHAP)** — kararı süren gazların katkı grafiği
- **Karşılaştırma** — Duval üçgeni + yöntem tablosu + model doğruluk grafiği
- **Trend Tahmini** — trafo yaşlanma senaryosu ve "kritik süre" öngörüsü
