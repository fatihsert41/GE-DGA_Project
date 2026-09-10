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

## YARIN BURADAN BAŞLA (10 Eylül 2026 sonu itibarıyla)

```powershell
cd C:\Users\Esma\Desktop\Python\GE-DGA_Project
.\start.ps1                # üç servisi birden başlatır (~22 sn)
.\start.ps1 -Check         # sadece durum kontrolü
.\start.ps1 -Stop          # hepsini durdurur
```

Arayüz: http://localhost:5173 · API: http://localhost:8000/docs

**Durum:** Her şey commit'li ve push'lu. Faz 0-7 bitti, Faz 8 devam ediyor
(8.1-8.4 tamam). **145 test** (95 Python + 50 .NET).

**BEKLEYEN KARAR — ilk iş bunu sor:** Faz 8.5 için iki seçenek var,
kullanıcı henüz seçmedi:

* **(A) Elektriksel testler** — TTR (sarım oranı) öncelikli. Künye zaten
  beklenen oranı hesaplıyor (`core/nameplate.rated_turns_ratio`, kademe
  için `turns_ratio_at_tap`); ölçüleni girip sapmayı değerlendirmek
  kalıyor. Sargı direnci, yalıtım direnci/PI, tan δ da eklenebilir.
  Kural tabanlı ve açıklanabilir. **Kullanıcının kendi fikri.**
* **(B) Sağlık Endeksi** — üç boyutu (DGA riski, yağ kalitesi, kağıt DP)
  tek 0-100 skora indirger. Mevcut öncelik skorunun
  (`assets.priority_score` = kondisyon × varlık ağırlığı)
  genelleştirilmesi olur. **Claude'un önerisi**, çünkü artık
  birleştirilecek boyutlar var ve "hangi trafoya önce bakayım?" sorusunu
  gerçekten cevaplar.

**Sonra gelecek işler (sırasız):**
* Kalibrasyon katmanı (`docs/FAZ6-IYILESTIRME-YOL-HARITASI.md` 1. sıra) —
  ölçüldü ama uygulanmadı: hizmet modeli kendi alanında ECE 0.021 ile
  zaten kalibre çıktı, bu yüzden aciliyeti düştü.
* Zaman serisi özellikleri (gaz üretim hızı) — trend altyapısı hazır.
* Faz 8.6-8.7: termal model (IEEE C57.91), bileşen izleme (buşing/OLTC).

**Claude için teknik notlar:**
* Arayüz görsel olarak DOĞRULANMADI (tarayıcı otomasyonu kurulu değil).
  Ekran görünümüyle ilgili sorunları kullanıcı bildirir.
* `bash` heredoc içinde ters bölü kaçışları bozuluyor; Python/C# dizelerine
  `\n` yazarken satır indeksiyle düzenle ya da `chr(10)` kullan.
  Bugün beş kez buna takıldık.
* .NET servisi çalışırken `dotnet build` `.exe` kilidi yüzünden hata verir;
  önce `taskkill //F //IM "TransformerAI.Maintenance.Api.exe"`.
* Uvicorn `--reload` ile başlatılmalı, yoksa kod değişince eski kod
  çalışmaya devam eder (bugün üç kez buna takıldık).

---

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
  - ✅ 6.7 Sentetik üreteç gerçekçileştirildi. `synth.py`'ye beş bileşen
    eklendi (şiddet, başlangıç evresi, karışık arıza, ölçüm/etiket
    gürültüsü), her biri AYRI ayarlanabilir ve tek tek ölçüldü.
    Sonuç: yalnızca **başlangıç evresi + ölçüm gürültüsü** işe yarıyor
    (`PRESET_FIELD_LIKE`); sıfır atış F1 **0.530 → 0.578** (3 tohum).
    ⚠ En önemli ders: **şiddet** bileşeni dağılımı gerçeğe en çok
    yaklaştıran şeydi ama aktarıma EN ÇOK ZARAR verdi (−0.096). Yani
    "gerçek verinin histogramını taklit etmek" ile "karar problemini
    taklit etmek" aynı şey değil.
    `train.py --field-like` ile üretim modeli bu profille eğitilebilir
    (varsayılan KAPALI; açılınca sentetik test doğruluğu düşer, gerçek
    dünyaya aktarım artar — iki sayı farklı şeyleri ölçer).
  - ✅ 6.8 Üretim modeli saha benzeri profile GEÇİRİLDİ
    (`python -m app.ml.train --field-like`, `metrics.json.data_profile`).
    Sentetik test doğruluğu 0.967 → 0.904 (sınav zorlaştı, beklenen);
    gerçeğe aktarım 0.530 → 0.578. Demo filo yeniden tanılandı:
    **TR-09 artık "Normal %54" değil "D1 %85"** — erken evre arızayı doğru
    buluyor ve yine incelemeye gönderiyor. TR-08 de sınırda olduğu için
    incelemeye düştü (filoda 2 vaka).
    ⚠ Model yeniden eğitilirse `--field-like` KULLANILMALI, yoksa demo
    eski davranışa döner.
  - ✅ 6.9 İyileştirme yol haritası — teşhise dayalı analiz
    (`ml/diagnostics.py`, **`docs/FAZ6-IYILESTIRME-YOL-HARITASI.md`**):
    * 5 katlı CV: F1 **0.772 ± 0.010** (yani 0.78 şans değil, gerçek),
      aile doğruluğu 0.946 ± 0.009.
    * Öğrenme eğrisi HÂLÂ YÜKSELİYOR (son adım +0.019, doyma yok) →
      en yüksek getirili yatırım **daha çok gerçek veri**, model değil.
    * Kalibrasyon: ECE 0.096, model FAZLA İDDİALI ("%96 eminim" dediğinde
      gerçekte %76 tutturuyor) → sıradaki en iyi getiri/emek: kalibrasyon.
    * Hata yapısı: hataların %58'i aynı aile içi (bakım kararı değişmiyor);
      karar değiştiren gerçek hata oranı %14.9 değil **%6.3**.
      Tüm hataların %32'si D1↔D2 (fiziksel olarak sürekli sınır).
    Öneri sırası: kalibrasyon → zaman serisi özellikleri → hiyerarşik
    sınıflandırma → D1/D2 → conformal. YAPMA: derin öğrenme, daha fazla
    özellik mühendisliği, sentetiği daha "gerçekçi" yapmak.
  - 🏁 **Faz 6 BİTTİ.**
- 🔄 **Faz 7 — Bakım Planlama Servisi (.NET) — devam ediyor.**
  **Öğrenme fazı: hız değil anlama önceliklidir. Her adımda TEK yeni kavram,
  her adım sonunda ÇALIŞAN bir şey.** Yol haritası:
  **`docs/FAZ7-DOTNET-YOL-HARITASI.md`** (7.1 iskelet → 7.9 belgeler).
  - ✅ .NET 10.0.401 SDK kuruldu (kullanıcı .NET 7'den yükseltti).
  - ✅ 7.1 İskelet TAMAM: `maintenance/` altında çözüm + Web API projesi
    (`TransformerAI.Maintenance.Api`). Şablonun hava durumu kodu silindi,
    yerine `/` ve `/health` yazıldı. `.gitignore`'a bin/ obj/ eklendi.
    Servis portu **5080** (Python 8000, Vite 5173).
  - ✅ 7.2 İş emri modeli (bellekte) TAMAM.
    `Models/WorkOrder.cs`: `WorkOrderStatus`/`WorkOrderKind` enum'ları,
    `WorkOrder` **class** (durumu değişen varlık), `CreateWorkOrderRequest`
    ve `UpdateStatusRequest` **record** (değişmeyen istek gövdesi = DTO).
    `Data/WorkOrderStore.cs`: bellekte liste + LINQ süzme/sıralama.
    Uç noktalar: GET/POST /workorders, GET /workorders/{id},
    PATCH /workorders/{id}/status, GET /workorders/summary.
    ⚠ Öğrenilen tuzak: **JSON'da enum varsayılan olarak SAYIDIR**;
    `JsonStringEnumConverter` eklendi, artık {"status":"Planned"}.
  - ✅ 7.3 EF Core + SQLite TAMAM. `Data/MaintenanceDbContext.cs`
    (tablo/sütun tanımı, enum'lar METİN olarak saklanıyor, indeksler),
    `Data/WorkOrderRepository.cs` (bellekteki store'un yerini aldı, tüm
    metotlar `async`). Migration: `Migrations/*_IlkSema.cs`.
    Uygulama açılışında `db.Database.Migrate()` şemayı uyguluyor.
    DI ömürleri: DbContext ve repository **Scoped** (istek başına bir örnek);
    Singleton OLMAMALI — DbContext isteğe ait değişiklikleri izler.
    ⚠ Öğrenilen tuzak: **SQLite `DateTimeOffset` ile ORDER BY yapamıyor**
    (C#'ta derlenir, çalışma anında patlar). `DateTime` (UTC) kullanıldı.
    ORM soyutlaması sızdırır — veritabanının sınırlarını bilmek gerekir.
    Kalıcılık doğrulandı: servis kapatılıp açıldı, kayıtlar durdu.
    Komutlar: `dotnet ef migrations add <ad>`; araç: `dotnet tool install --global dotnet-ef`.
  - ✅ 7.4 İki servis konuşuyor TAMAM. `Services/MlServiceClient.cs`
    (tipli HttpClient), `Models/MlModels.cs` (Python cevabının C# karşılığı,
    hepsi record). `appsettings.json` → `MlService:BaseUrl`.
    Yeni uç noktalar: `GET /fleet` (Python'dan okur, saklamaz),
    `GET /transformers/{id}/risk` (**risk Python'dan + iş emirleri bizim
    DB'den** — iki kaynağı birleştiren ilk uç nokta),
    `GET /health` artık bağımlılığı da yokluyor.
    ⚠ Python `snake_case`, C# `PascalCase` yazar →
    `JsonNamingPolicy.SnakeCaseLower` ile otomatik eşleniyor.
    ⚠ `HttpClient`'ı elle `new` ile yaratmak soket tükenmesine yol açar;
    `AddHttpClient` fabrikası kullanılıyor + zaman aşımı zorunlu.
    **Dayanıklılık doğrulandı:** Python kapatıldığında /health
    "unreachable" diyor, /fleet 503 + açıklayıcı mesaj dönüyor, ama
    /workorders KENDİ verisiyle çalışmaya devam ediyor.
  - ✅ 7.5 Otomatik iş emri önerisi TAMAM. `Services/WorkOrderPlanner.cs`
    — kurallar uç noktada değil, HTTP ve veritabanı bilmeyen SAF bir
    sınıfta (girdi: filo + mevcut emirler + bugün → çıktı: öneri listesi).
    `today` parametre olarak alınıyor ki test tarihe bağlı olmasın.
    Dört kural: ciddi arıza (D2/T3) → 3 gün, kritik risk → 7 gün,
    yüksek risk → 14 gün, düşük güven → 30 gün, numune gecikmesi → 30 gün
    (önceliği yarıya indirilir ki incelemeler öne geçsin).
    Uç noktalar: `GET /workorders/suggestions` (önerir),
    `POST /workorders/suggestions/apply` (uygular) — ayrı olmalarının
    sebebi önermek ile uygulamanın farklı yetkiler istemesi.
    **İdempotent:** açık emri olan (trafo, tür) çifti atlanır; ikinci
    çağrıda 0 kayıt üretti. Doğrulandı: 5 öneri → 5 emir → tekrar 0.
  - ✅ 7.6 Teknisyen ve atama TAMAM. `Models/Technician.cs` (varlık +
    `Specialty` enum + `WorkOrders` navigation property),
    `WorkOrder.AssignedTo` serbest metni KALDIRILDI → `TechnicianId`
    yabancı anahtarı + `Technician` navigation. İlişki `DbContext`'te
    one-to-many; `OnDelete(SetNull)` — teknisyen silinirse iş emirleri
    SİLİNMEZ, ataması boşalır (bakım geçmişi korunur).
    Demo teknisyenler `HasData` ile migration'ın içinde (6 kişi, 4 bölge).
    `Services/AssignmentService.cs` saf seçim mantığı: bölge eşleşmesi +10,
    uzmanlık +5, genel +1; eşitlikte yükü az olan kazanır.
    `Data/TechnicianRepository.cs`: yük hesabı TEK sorguda (N+1 tuzağından
    kaçınmak için GroupBy), `Include` ile ilişkili veri.
    Uç noktalar: `GET /technicians`, `POST /workorders/{id}/assign`
    (gövde boşsa otomatik seçer, `technicianId` verilirse insanın kararı
    üstündür — kapasiteyi aşarsa `warning` alanıyla GÖRÜNÜR kılınır).
    Migration: `TeknisyenVeAtama` (veri kaybı uyarısı verdi: AssignedTo silindi).
  - ✅ 7.7 Arayüz TAMAM. `vite.config.js` artık İKİ servise yönlendiriyor:
    `/api` → Python :8000, `/maint` → .NET :5080 (tarayıcı ikisini de
    localhost:5173'ten görür, CORS derdi yok).
    `api.js` içinde ayrı `maintenance` istemcisi (ayrı olması bilinçli:
    .NET kapalıyken ML tarafı çalışmaya devam etmeli).
    `components/MaintenancePanel.jsx`: KPI'lar, öneri paneli (+uygula
    düğmesi), iş emri tablosu (ata / başlat / bitir), teknisyen yük tablosu.
    `App.jsx`'e "Bakım Planlama" sekmesi.
    ⚠ Öğrenilen tuzak: `Include` olmadan `order.Technician` null geliyordu
    ve arayüz "atanmadı" yazıyordu — ilişkiyi kurmak yetmiyor, o sorguda
    İSTEMEK gerekiyor. Ayrıca `Technician.WorkOrders` üzerine `[JsonIgnore]`
    şart: yoksa iş emri→teknisyen→iş emri sonsuz serileştirme döngüsü.
  - ✅ 7.8 Testler TAMAM. Çözüme ikinci proje: `TransformerAI.Maintenance.Tests`
    (xUnit). **33 test, 195 ms** — hiçbiri veritabanı veya HTTP kullanmıyor,
    çünkü `WorkOrderPlanner` ve `AssignmentService` saf tasarlanmıştı.
    `TestData.cs` adlandırılmış argümanlarla sahte veri üretir; test sadece
    ÖNEMSEDİĞİ alanı belirtir, gerisi gürültü olmaz.
    Kapsanan: beş öneri kuralı, idempotens (kapanmış emir engellemez,
    farklı tür engellemez), öncelik sıralaması, ölçümsüz trafo;
    bölge/uzmanlık puanlaması, kapasite, pasif teknisyen, yük dengeleme,
    determinizm.
    Komut (maintenance/ klasöründen): `dotnet test`.
    xUnit ↔ pytest: `[Fact]` ↔ `def test_`, `[Theory]+[InlineData]` ↔
    `@pytest.mark.parametrize`.
  - ✅ 7.9 Belgeler TAMAM. `README.md` baştan yazıldı: üç servisli mimari
    şeması, üç terminallik hızlı başlangıç, iki servisin uç nokta tabloları,
    gerçek veri bulguları, tasarım kararları, bilinen sınırlılıklar.
    ⚠ README'de `python -m app.ml.train --field-like` bayrağı vurgulandı.
    `docs/ROADMAP.md` başına tarihsel not: plandan sapılan 4 karar ve
    nedenleri (açık veri → sentetik+doğrulama, Tailwind → elle CSS,
    3 sütun → 5 sütun, tek servis → polyglot).
  - 🏁 **Faz 7 BİTTİ.** Üç servis, 81 test (48 Python + 33 .NET).
  ⚠ Kurallar: Python servisi DEĞİŞTİRİLMEZ, .NET onu dışarıdan tüketir.
  İş emirleri .NET'in KENDİ veritabanında durur (ortak DB mikroservis
  mimarisinin en yaygın hatası). Veritabanı 7.3'ten önce eklenmez.

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
