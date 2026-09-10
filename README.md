# TransformerAI — DGA Tabanlı Trafo Arıza Tahmini ve Bakım Planlama

> **GE Vernova Staj Projesi.** Güç trafolarının yalıtım yağındaki çözünmüş
> gazlardan (DGA) arıza tipini tahmin eden, kararını **açıklayan**, klasik
> endüstri yöntemleriyle **karşılaştıran**, sağlık **trendini** öngören ve
> sonucu **bakım iş emrine** dönüştüren polyglot bir sistem.

**Üç servis:** Python (ML) · .NET (bakım planlama) · React (arayüz).
**109 test** (73 Python + 36 .NET).

---

## Projeyi özgün kılan ne?

Çoğu öğrenci projesi "model %96 doğru" der ve orada biter. Bu proje
**kendi sınırlarını ölçtü** ve ölçümü ürüne taşıdı.

| | Ne yapar | Nerede |
|---|---|---|
| **A — Açıklanabilirlik** | Model "D2 (ark)" derken hangi gazın kararı sürüklediğini SHAP ile gösterir | `POST /explain` |
| **B — Karşılaştırma** | Duval, Rogers, IEC, Key Gas **vs** RandomForest, XGBoost, SVM, NeuralNet — aynı test setinde | `GET /compare/leaderboard` |
| **C — Trend** | Geçmiş ölçümlerden "~N ay içinde kritik olacak" öngörüsü | `GET /trend/{id}` |
| **D — Belirsizlik** | Model emin değilse **söyler** ve vaka uzmana gider | `review` alanı, her tanıda |
| **E — Eyleme dönüşüm** | Risk → iş emri → teknisyen ataması | .NET servisi |

---

## En önemli bulgu: dürüst ölçüm

Sentetik veriyle eğitilen model **gerçek trafo ölçümlerinde** sınandı
(2321 kayıt, açık kaynak derleme):

| | Sonuç |
|---|---|
| Sentetik test doğruluğu | %90.4 |
| **Gerçek veride F1** (5 katlı CV) | **0.772 ± 0.010** |
| **Arıza yakalama duyarlılığı** | **%97.4** |
| **Arıza ailesi doğruluğu** (Normal/Termal/Deşarj) | **%94.6** |
| Ciddi arızalarda (ark, >700 °C) kaçırma | 198 vakada **1** |

Yedi sınıflı F1'in düşük görünmesi yanıltıcıdır — ama **"aynı aile =
zararsız hata" demek de yanlıştır.** Dış inceleme bu savı çürüttü ve
ölçtük: doğru ölçüt aile doğruluğu değil, **gerekli bakımın geciktirildiği
vaka oranı**:

| Ölçüt | Sonuç |
|---|---|
| **Gerekli bakım gecikti** | **%6.1** (36 vaka) |
| ↳ bunların aynı ailede olanı | **22** — "zararsız" sanılanlar |
| Gereksiz aciliyet (boşa kaynak) | %5.7 (34 vaka) |
| Hatalı ama bakım kararı aynı | 18 vaka |

En sık gecikme **D2 → D1** (15 kez): ikisi de "Deşarj" ailesinde ama D2
ciddi arıza sayılıp 3 gün içinde inceleme ister, D1 ise 7-14 güne kayar.
**Aile aynı, karar farklı.**

📄 Ayrıntı: [`docs/FAZ6-GERCEK-VERI-BULGULARI.md`](docs/FAZ6-GERCEK-VERI-BULGULARI.md)
· [`docs/FAZ6-IYILESTIRME-YOL-HARITASI.md`](docs/FAZ6-IYILESTIRME-YOL-HARITASI.md)

---

## Mimari

```
                        ┌──────────────────────────────┐
                        │      React (Vite) :5173      │
                        │  Filo · Analiz · Bakım       │
                        └───┬──────────────────────┬───┘
                 /api       │                      │   /maint
                            ▼                      ▼
        ┌───────────────────────────┐   ┌──────────────────────────┐
        │   Python / FastAPI :8000  │◄──┤  .NET / ASP.NET  :5080   │
        │   ── ML SERVİSİ ──        │   │  ── BAKIM PLANLAMA ──    │
        │                           │   │                          │
        │  • klasik DGA motoru      │   │  • iş emri               │
        │  • ML tahmini + SHAP      │   │  • otomatik öneri        │
        │  • risk, trend, öncelik   │   │  • teknisyen ataması     │
        │                           │   │                          │
        │  SQLite: ölçümler         │   │  SQLite: iş emirleri     │
        └───────────────────────────┘   └──────────────────────────┘
```

**Neden iki dil?** Her servis kendi işine en uygun dilde. ML Python'da
(scikit-learn, SHAP orada); iş mantığı, veri bütünlüğü ve kurumsal iş akışı
.NET'te. Servisler HTTP/JSON ile konuşur ve **ayrı veritabanları** kullanır —
ortak veritabanı mikroservis mimarisinin en yaygın hatasıdır.

**Dayanıklılık:** ML servisi kapalıyken bakım servisi çalışmaya devam eder
(`/health` bağımlılığı `unreachable` olarak bildirir, iş emirleri açılır).

---

## Hızlı başlangıç

Gereksinimler: **Python 3.12+**, **Node 18+**, **.NET 10 SDK**.

### 1) Python ML servisi — Terminal 1

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m app.ml.train --field-like   # model.joblib + metrics.json
python -m app.ml.seed                 # demo filo: 9 trafo, 94 ölçüm
uvicorn app.main:app --reload         # http://localhost:8000/docs
```

> ⚠ `--field-like` bayrağı önemlidir: sentetik veriyi saha benzeri üretir
> (başlangıç evresindeki arızalar dahil). Bayraksız eğitirsen sentetik test
> doğruluğu yükselir ama gerçek dünyaya aktarım düşer.

### 2) .NET bakım servisi — Terminal 2

```powershell
cd maintenance/TransformerAI.Maintenance.Api
dotnet run --urls http://localhost:5080
```

Veritabanı ve demo teknisyenler ilk açılışta otomatik oluşur (EF Core
migration + `HasData`).

### 3) React arayüzü — Terminal 3

```powershell
cd frontend
npm install
npm run dev                           # http://localhost:5173
```

Vite iki servise birden yönlendirir: `/api` → :8000, `/maint` → :5080.

---

## Testler

```powershell
cd backend      ; pytest -q            # 73 test
cd maintenance  ; dotnet test          # 36 test
```

.NET testleri veritabanı ve HTTP kullanmaz (195 ms): iş kuralları saf
sınıflarda tutulduğu için doğrudan test edilebiliyor.

---

## Ekranlar

| Sekme | İçerik |
|---|---|
| **Filo** | 9 trafo, önceliğe göre sıralı; risk dağılımı, alarm listesi, arama/filtre. Karta tıklayınca: gaz geçmişi + 6 aylık öngörü + gaz bazında trend tablosu |
| **Numune Analizi** | Elle gaz girişi → tanı, SHAP grafiği, Duval üçgeni, yöntem karşılaştırması, gerçeklik kontrolü paneli |
| **Bakım Planlama** | İş emirleri, sistemin ürettiği öneriler, teknisyen yük tablosu, atama |

---

## Öne çıkan tasarım kararları

**Varlık sınıfları ve öncelik.** Trafolar GE Vernova hattına göre **LPT**
(≥100 MVA), **MPT** (10–100) ve **SPT** (üretimi durdu, saha üniteleri
izlenmeye devam ediyor) olarak ayrılır. Endüstride risk = olasılık × sonuç;
gaz analizi olasılığı verir, **sonucu varlık sınıfı verir**:

```
Öncelik = IEEE kondisyonu × varlık ağırlığı   (LPT 1.0 / MPT 0.7 / SPT 0.45)
```

Sonuç: yüksek riskli bir LPT (3.00), kritik riskli bir MPT'nin (2.80)
önüne geçer.

**Belirsizlik ürüne girdi — ve eşiğin kökeni açık.** Sistem güveni düşük
tahminleri işaretler ve iş emri önerisi üretir. Eşiğin dayanağı her tanı
cevabında `review.threshold_basis` alanında taşınır:

| | Değer |
|---|---|
| Ölçülen eşik (hizmet veren modelde) | **0.50** — %98 kapsama, %91 isabet |
| Kalibrasyon (ECE) | **0.021** — model kendi alanında dürüst |
| **Çalışma noktası** | **0.90** — bilinçli emniyet payı |

Çalışma noktası ölçülenden yüksek, çünkü ölçüm **sentetik** alanda yapıldı
ve bu modelin gerçek veriye aktarımının zayıf olduğu ölçüldü (F1 0.96 →
0.58). Kendi dağılımında dürüst olmak, farklı bir dağılımda dürüst olmayı
garanti etmez. Aradaki fark saklanmıyor, gerekçesiyle bildiriliyor.

> Bu şeffaflık bir dış inceleme sonrası eklendi: eşik daha önce **başka bir
> modelde** ölçülüp buraya taşınmıştı. Bkz.
> [`docs/DIS-INCELEME-DOGRULAMA.md`](docs/DIS-INCELEME-DOGRULAMA.md)

**Ölçülüp elenen kural.** İlk tasarımda "ML ve klasik yöntemler ayrışıyorsa
uzman baksın" kuralı vardı. Ölçünce elendi: %45 tetikleniyor ama
tetiklendiğinde model **daha** doğru (%92 vs %80) — yani modelin değil
klasik motorun zayıflığını gösteriyordu.

---

## Dizin yapısı

```
backend/app/            Python — ML servisi
├── core/               klasik DGA motoru (Duval, Rogers, IEC, Key Gas, risk)
│   └── assets.py       varlık sınıfları (LPT/MPT/SPT) ve öncelik skoru
├── ml/                 sentetik veri, eğitim, SHAP, gerçek veri değerlendirme
│   ├── synth.py        standart-temelli üreteç (+ saha benzeri profil)
│   ├── real_data.py    açık veri seti yükleyici (Çince etiket desteği dahil)
│   ├── evaluate_real.py  A/B/C/D senaryolu gerçek veri sınaması
│   ├── experiments.py  ablasyon deneyleri
│   ├── safety_eval.py  emniyet ölçütleri
│   └── diagnostics.py  öğrenme eğrisi + çapraz doğrulama
├── services/           tanı orkestrasyonu, trend, filo
└── routers/            /predict /explain /compare /trend /fleet /transformers

maintenance/            .NET — bakım planlama servisi
├── TransformerAI.Maintenance.Api/
│   ├── Models/         WorkOrder, Technician, ML cevap tipleri
│   ├── Data/           DbContext, repository'ler, migration'lar
│   ├── Services/       MlServiceClient, WorkOrderPlanner, AssignmentService
│   └── Program.cs      Minimal API uç noktaları
└── TransformerAI.Maintenance.Tests/   xUnit

frontend/src/           React (Vite)
├── components/         FleetOverview, TransformerDetail, MaintenancePanel, ...
└── theme.js            grafik renkleri (tek kaynak)
```

---

## API uç noktaları

### Python — ML servisi (:8000)

| Metot | Yol | Açıklama |
|---|---|---|
| `POST` | `/predict` | Tam tanı: ML + klasik + risk + belirsizlik değerlendirmesi |
| `POST` | `/explain` | SHAP gaz katkıları |
| `POST` | `/compare` | Tek okuma için tüm yöntemler yan yana |
| `GET` | `/compare/leaderboard` | ML vs klasik doğruluk tablosu |
| `GET` | `/compare/reality-check` | Sentetik test vs gerçek veri performansı |
| `GET` | `/fleet/overview` | Filo: her trafonun son tanısı, risk, öncelik |
| `GET` | `/trend/{id}` | Trafonun trendi + kritik olma süresi |

### .NET — Bakım servisi (:5080)

| Metot | Yol | Açıklama |
|---|---|---|
| `GET` | `/health` | Servis + ML bağımlılığı durumu |
| `GET` | `/fleet` | ML servisinden okunan filo (ayna, saklanmaz) |
| `GET` | `/transformers/{id}/risk` | Risk (Python) + iş emirleri (bu servis) |
| `GET`/`POST` | `/workorders` | İş emri listele / oluştur |
| `GET` | `/workorders/suggestions` | Sistemin önerdiği iş emirleri |
| `POST` | `/workorders/suggestions/apply` | Önerileri uygula (idempotent) |
| `PATCH` | `/workorders/{id}/status` | Durum güncelle |
| `POST` | `/workorders/{id}/assign` | Teknisyen ata (boş gövde = otomatik) |
| `GET` | `/technicians` | Teknisyenler ve anlık yükleri |

---

## Veri politikası

**Gizli/kurumsal veri yoktur.** Uygulamanın çalıştırdığı veri
`backend/app/ml/synth.py` içinde IEC 60599 / Duval imzalarına göre üretilir
ve üreten kuralla etiketlenir.

Faz 6'daki doğrulama için kullanılan gerçek veri seti açık kaynaklıdır ve
**repoya dahil edilmemiştir** (lisans belirsizliği); indirme talimatı
[`backend/data/README.md`](backend/data/README.md) dosyasındadır.

---

## Referans standartlar

- **IEC 60599:2015** — çözünmüş gaz oran yorumlama
- **IEEE C57.104-2008** — gaz konsantrasyon eşikleri (Condition 1–4)
- **M. Duval (2002)** — Duval Üçgeni arıza bölgeleri
- **US DOE** — LPT tanımı (≥100 MVA)

---

## Yol haritası

- [x] **Faz 0–1** — İskelet, klasik DGA motoru, testler
- [x] **Faz 2** — Sentetik veri, çoklu model eğitimi, karşılaştırma
- [x] **Faz 3** — FastAPI backend + SQLite
- [x] **Faz 4** — React dashboard (SHAP, Duval, trend)
- [x] **Faz 5** — Filo yönetimi (genel bakış, detay, alarm, filtre)
- [x] **Faz 6** — Gerçek veri doğrulaması, emniyet ölçütleri, belirsizlik
- [x] **Faz 7** — .NET bakım planlama servisi (polyglot mimari)
- [ ] **Faz 8+** — RUL, PostgreSQL, kimlik doğrulama, Docker, CI/CD

---

## Bilinen sınırlılıklar

- Uygulamanın verisi **sentetiktir**; gerçek saha verisiyle yeniden eğitim
  önerilir. Sentetik → gerçek aktarım farkı ölçülmüş ve belgelenmiştir.
- Açık veri setlerinde **CO ve CO₂ yoktur**; T1 (düşük sıcaklık aşırı ısınma)
  sınıfının ana göstergesi kağıt bozunmasıdır ve bu iki gazla görülür.
  T1'deki görece zayıflık doğrudan bu kısıtın sonucudur.
- Trend modülü doğrusal regresyona dayanır; uzun geçmişte doğrusal olmayan
  modeller daha iyi olabilir.
- Model güven değerleri **fazla iddialıdır** (ECE 0.096); kalibrasyon
  katmanı sonraki adım olarak belgelenmiştir.
- İş emri numaraları tek servis örneği varsayar; yatay ölçeklemede
  veritabanı dizisi (sequence) gerekir.
