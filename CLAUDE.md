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
- **Kodu Claude yazar** (2026-09-09'da değişti — kullanıcı elle yazmıyor).
  Değişikliği uygula, sonra **ne yaptığını ve nedenini detaylı anlat.**
- Bir dosyadan bahsederken **tam yolunu** yaz (`backend/app/database.py`), sadece
  dosya adını değil. Terminal komutu verirken **hangi dizinden** çalıştırılacağını
  belirt (komutların çoğu `backend/` klasöründen çalışır).
- **git push yalnızca büyük aşamalar sonunda ve kullanıcının onayıyla.** Sürekli push yok.
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
  - ✅ 5.1 `ml/seed.py` demo filo üreteci (8 trafo, 89 ölçüm) — TAMAM.
  - ✅ 5.2 `GET /fleet/overview` — TAMAM. Zinciri:
    `database.latest_measurements()` (pencere fonksiyonu ile trafo başına son
    ölçüm, LEFT JOIN ile ölçümsüz trafolar da) → `services/fleet.py`
    (`build_overview` saf hesap + `overview` I/O sarmalayıcı) → `routers/fleet.py`.
    `core/risk.py` içine `RISK_LEVELS_TR` / `RISK_ORDER` eklendi.
    Testler: `tests/test_fleet.py` (toplam 20 test).
  - ✅ 5.3 Frontend filo ekranı — TAMAM. `components/FleetOverview.jsx`
    (KPI kutuları + tek çubuklu risk kompozisyonu + trafo kartları),
    `App.jsx` içine "Filo / Tek Numune Analizi" görünüm anahtarı,
    `index.css` sonuna filo stilleri, `api.js` içine `fleetOverview()`.
  - ✅ 5.4 Trafo detay sayfası — TAMAM. `components/TransformerDetail.jsx`:
    trend hükmü şeridi, ölçülen geçmiş + kesikli 6 aylık öngörü grafiği,
    gaz bazında trend tablosu (eğim/R²/kalan süre), ölçüm geçmişi tablosu.
    Tamamı TEK istekten beslenir: `GET /trend/{id}`. Filo kartları artık
    `<button>` (klavye erişilebilir) ve `App.jsx` `selected` durumunu tutar.
  - ✅ 5.5 Cila — TAMAM. `FleetOverview.jsx` içine alarm paneli (yüksek+kritik,
    tıklayınca detaya gider), arama kutusu ve risk filtresi çipleri.
    Filtreleme istemcide (8 varlık, API'ye tekrar gitmeye gerek yok).
    `constants.js::fold()` Türkçe duyarlı arama katlaması yapar (I/ı/İ/i).
  - 🏁 **Faz 5 BİTTİ.**
- 🔄 **Faz 6 — Gerçek veri seti entegrasyonu (devam ediyor):**
  - ✅ 6.1 Altyapı TAMAM (veriden bağımsız, veri gelmeden yazıldı):
    - `ml/real_data.py` — dağınık dosyayı projenin şemasına çevirir
      (sütun eşanlamlıları, metin+tam sayı etiketler, bozuk satır raporu).
    - `ml/features.py` — `CORE_FEATURE_NAMES` (5 gaz + 4 oran) varyantı.
      Açık veri setlerinde **CO/CO2 YOK**; karşılaştırma bu sette yapılır.
    - `ml/evaluate_real.py` — dört senaryo: A sentetik→gerçek (sıfır atış),
      B gerçek→gerçek, C karma, D klasik konsensüs. Çıktı:
      `artifacts/real_data_report.json`.
    - `data/README.md` + `.gitignore`: veri dosyaları repoya GİRMEZ (lisans).
    - `tests/test_real_data.py` (toplam 25 test).
  - ⏭️ **SIRADAKİ: 6.2** — kullanıcı IEEE DataPort'tan üç dosyayı indirip
    `backend/data/` içine koyacak; sonra `python -m app.ml.evaluate_real`
    çalıştırılıp gerçek sonuçlar yorumlanacak.
  - ⏳ 6.3 Sonuçları `/compare` ve frontend'e taşı (veri kaynağı rozeti).
- ⏳ **Faz 7 (.NET) — kullanıcı .NET bilmiyor, çok temelden ve yavaş anlatılacak.**

### Görsel dil (2026-09-09'da yenilendi)
"Endüstriyel kontrol odası": kağıt zemin (#f5f2ea), mürekkep metin, saç teli
çizgiler. Tipografi **Plus Jakarta Sans**; monospace (JetBrains Mono) SADECE
rakamlarda. Renkler `frontend/src/theme.js` + `index.css :root` içinde İKİ YERDE
tanımlı, ikisi de aynı tutulmalı. Risk rampası tek hüzmeli sıralı rampa
(#cda760→#78380f) ve grafik serileri paleti, dataviz doğrulayıcısından geçirildi
— renk körlüğü kontrolünden geçmeyen yeşil/sarı/turuncu/kırmızı kombinasyonu
bilinçli olarak KULLANILMADI. Renk hiçbir yerde tek başına anlam taşımaz.
  - ⏳ 5.4 Trafo detay sayfası (geçmiş + trend).
  - ⏳ 5.5 Cila (filtre, arama, alarm).

## Yol haritası (ileri fazlar)
- **Faz 6** — Gerçek açık veri seti entegrasyonu (opsiyonel; kullanıcı şimdilik istemedi).
- **Faz 7 — Bakım Planlama Servisi (.NET, ASP.NET Core + EF Core):** iş emri,
  planlama tablosu, teknisyen atama. Python ML servisinden risk okur.
  Polyglot mikroservis mimarisi. (Kullanıcı .NET bilmiyor → çok temelden anlat.)
- **Faz 8+** — RUL/kestirimci bakım, PostgreSQL, kimlik doğrulama, Docker, CI/CD.
