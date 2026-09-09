# CLAUDE.md — TransformerAI (DGA Trafo Arıza Tahmin)

> Bu dosya, VS Code / Claude Code oturumlarının projeyi hızlıca anlaması için
> yazılmıştır. Yeni bir oturum açıldığında ÖNCE bunu oku.

## Proje tek cümlede
Güç trafolarının yalıtım yağındaki çözünmüş gazlardan (DGA) arıza tipini tahmin
eden; kararını **SHAP** ile açıklayan, klasik yöntemlerle **karşılaştıran** ve
trafonun sağlık **trendini** öngören full-stack + ML sistemi. (GE Vernova staj
projesi, tamamen demo.)

## ⚠️ Çalışma tarzı (ÇOK ÖNEMLİ — kullanıcıyla nasıl ilerlenir)
- Kullanıcı **öğrenci** ve öğrenmek istiyor. Türkçe konuş.
- **Adım adım** ilerle: küçük parçalar ver, her parçayı **neden** yaptığını açıkla.
- Kullanıcı kodu **kendi yazmak** istiyor (öğrenmek için). Kodu ver, açıkla; o yazsın.
  VS Code eklentisi kullanılıyorsa değişiklikleri **diff olarak göster, onay iste.**
- Yeni bir kavram geçtiğinde (ör. `iloc`, SHAP, API) **kısa bir açıklama** ekle.
- Aynı anda çok şey yapma; bir adım bitince kullanıcıdan çıktı/onay al, sonra devam.

## Veri politikası
**Gerçek/kurumsal veri YOK.** Tüm veri, IEC 60599 / Duval imzalarına göre
`backend/app/ml/synth.py` içinde sentetik üretilir ve üreten kuralla etiketlenir.
Bu bilinçli bir tercihtir ("standart-temelli sentetik veri"). ML'i Python'da tut.

## Mimari
```
React (Vite) dashboard  ──HTTP/JSON──►  FastAPI backend
  frontend/                               backend/app/
                                            core/   → klasik DGA motoru (saf Python)
                                            ml/     → sentetik veri, eğitim, SHAP, tahmin
                                            services/→ tanı orkestrasyon, trend
                                            routers/ → /predict /explain /compare /trend /transformers
                                            database.py → SQLite
```

### Üç sütun (projenin özü)
- **A — Açıklanabilirlik:** SHAP, `ml/predictor.py::explain`, uç nokta `/explain`.
- **B — Karşılaştırma:** ML vs klasik, `ml/train.py` leaderboard, `/compare`.
- **C — Trend:** doğrusal regresyon + kritik-süre, `services/trend.py`, `/trend`.

## Arıza sınıfları (IEC 60599)
`Normal, PD, D1, D2, T1, T2, T3` — tanımlar `core/gases.py::FAULT_LABELS_TR`.
7 gaz: `H2, CH4, C2H6, C2H4, C2H2, CO, CO2`.

## Nasıl çalıştırılır (Windows / PowerShell)
```powershell
# Backend (Terminal 1)
cd backend
.\.venv\Scripts\Activate.ps1        # venv izole: backend\.venv
python -m app.ml.train              # model.joblib + metrics.json üretir
python -m app.ml.seed               # demo filoyu (8 trafo) DB'ye yükler
uvicorn app.main:app --reload       # http://localhost:8000/docs

# Frontend (Terminal 2)
cd frontend
npm run dev                         # http://localhost:5173
```
Testler: `cd backend; pytest -q` (18 test).

## Konvansiyonlar
- Kod ve değişken isimleri **İngilizce**; arayüz metinleri **Türkçe**.
- Model DataFrame ile eğitilir ve DataFrame ile tahmin edilir (train/serve tutarlılığı).
- `.venv`, `node_modules`, `*.db`, `model.joblib` git'e girmez (.gitignore).
- ML katmanı Python'da kalır; CRUD/iş mantığı için .NET düşünülüyor (aşağıya bak).

## Nerede kaldık (güncel durum)
- ✅ Faz 0–4 bitti: klasik motor, ML+karşılaştırma, SHAP, FastAPI, React dashboard.
- 🔄 **Faz 5 — Filo Dashboard (devam ediyor):**
  - ✅ 5.1 `ml/seed.py` demo filo üreteci (8 trafo, ~89 ölçüm) — TAMAM.
  - ⏭️ **SIRADAKİ: 5.2** — `/fleet/overview` API'si (her trafonun son tanısı +
    filo geneli risk dağılımı).
  - ⏳ 5.3 Frontend filo ekranı (kartlar + risk dağılımı).
  - ⏳ 5.4 Trafo detay sayfası (geçmiş + trend).
  - ⏳ 5.5 Cila (filtre, arama, alarm).

## Yol haritası (ileri fazlar)
- **Faz 6** — Gerçek açık veri seti entegrasyonu (opsiyonel; kullanıcı şimdilik istemedi).
- **Faz 7 — Bakım Planlama Servisi (.NET, ASP.NET Core + EF Core):** iş emri,
  planlama tablosu, teknisyen atama. Python ML servisinden risk okur.
  Polyglot mikroservis mimarisi. (Kullanıcı .NET bilmiyor → çok temelden anlat.)
- **Faz 8+** — RUL/kestirimci bakım, PostgreSQL, kimlik doğrulama, Docker, CI/CD.
