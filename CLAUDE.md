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
  - ✅ 6.2 Gerçek veriyle değerlendirme TAMAM. IEEE DataPort aboneliği
    alınamadı; yerine açık GitHub derlemesi kullanıldı (2321 satır, 7 sınıf,
    Çince etiketler) — IEEE setinden 4 kat büyük. Bulgular:
    **`docs/FAZ6-GERCEK-VERI-BULGULARI.md`**. Özet: sentetik test F1 0.96 →
    gerçek veride sıfır atış **F1 0.50**; gerçekle eğitim 0.757; karma eğitim
    saf gerçeği hiç geçmiyor; klasik konsensüs bağımsız sette (Normal yok)
    sentetik-eğitimli ML'in hepsini geçiyor (0.650 vs 0.492).
    Yükleyiciye Çince etiket desteği + tekrar/kesişim temizliği eklendi.
  - ✅ 6.3 İyileştirme denemeleri (ablasyon) TAMAM. `ml/hybrid.py` klasik
    yöntemlerin kararlarını ML'e GİRDİ olarak verir (14 indikatör);
    `ml/experiments.py` üç hamleyi üst üste ekleyip her birinin katkısını
    ölçer. Sonuç: B 0.757 → **0.780**, kazancın neredeyse tamamı T1'de
    (duyarlılık %36 → %58). A (sıfır atış) 0.503 → 0.520, yani indikatörler
    sıfır atışa daha çok yarıyor ama sorunu çözmüyor.
    Ayrıntı: `docs/FAZ6-GERCEK-VERI-BULGULARI.md`.
  - ✅ 6.4 Emniyet ölçütleri TAMAM (`ml/safety_eval.py`). Yedi sınıflı F1
    yanıltıcı: "T1 yerine T2" ile "D2 yerine Normal" hatalarını aynı
    ağırlıkta cezalandırıyor. Doğru ölçütlerle aynı model:
    **arıza yakalama %97.4**, aile doğruluğu (Normal/Termal/Deşarj) **%93.8**,
    ciddi arızalarda (D2/T3) 198 vakada **1** kaçırma. Seçici tahmin:
    güven ≥0.9'da %84 kapsama ile %91.3 doğruluk, kalanı uzmana devir.
  - ✅ 6.5 Belirsizlik ürüne girdi. `services/diagnosis.py` her tanıya
    `review` (uzman incelemesi gerekli mi + gerekçe) ve `prediction_family`
    ekler. Eşik **ölçülerek** seçildi (`CONFIDENCE_THRESHOLD = 0.90`).
    ⚠ İlk tasarımda "ML ve klasik ayrışıyor" da tetikleyiciydi; ÖLÇÜLDÜ ve
    ELENDİ: %45 tetikleniyor ama tetiklendiğinde model %92 doğru
    (tetiklenmediğinde %80) — yani modelin değil klasik motorun zayıflığını
    gösteriyor. Kural eklemeden önce ölç.
    Ayrıca: `GET /compare/reality-check` (sentetik vs gerçek), filo kartında
    `needs_review`/`severe`, arayüzde inceleme şeridi ve Gerçeklik Kontrolü
    paneli. Demo filoya TR-09 eklendi (erken evre D1: model "Normal" diyor
    ama güven %54) — belirsiz vaka olmadan özellik demoda görünmüyordu.
  - ✅ 6.6 Varlık sınıfları (GE Vernova bağlamı) TAMAM. `core/assets.py`:
    **LPT** (>=100 MVA) ve **MPT** (10-100) üretimde, **SPT** (<10) hattı
    kapandı ama saha üniteleri izlenmeye devam ediyor (`active: False`).
    Sınıf sadece etiket değil: **öncelik = IEEE kondisyonu × varlık ağırlığı**
    (LPT 1.0 / MPT 0.7 / SPT 0.45). Böylece yüksek riskli bir LPT (3.00),
    kritik riskli bir MPT'nin (2.80) önüne geçiyor — risk = olasılık × SONUÇ.
    Numune aralığı da sınıfa göre (6/12/24 ay) ve gecikme işaretleniyor.
    `database.py::_ensure_column` ile güvenli göç: eski dga.db'ler
    silinmeden yeni sütunları alıyor. Demo filo 9 trafo; TR-06 ve TR-09
    kasten "numunesi gecikmiş" (ihmal edilen varlık senaryosu).
    Testler: `tests/test_assets.py` (toplam 43 test).
  - ⏭️ **SIRADAKİ:** `synth.py`'yi gerçekçileştirip A senaryosunu
    iyileştirmek (gürültü, sınıf örtüşmesi) — sentetik veri tercihini
    savunmanın tek yolu. Not: sentetik üreteç şu an belirsiz vaka HİÇ
    üretemiyor (Faz 6.5'te fark edildi), bu da alan kaymasının kanıtı.
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
