# TransformerAI — DGA Tabanlı Trafo Arıza Tahmini ve Bakım Planlama

> **GE Vernova Staj Projesi.** Güç trafolarının yalıtım yağındaki çözünmüş
> gazlardan (DGA) arıza tipini tahmin eden, kararını **açıklayan**, klasik
> endüstri yöntemleriyle **karşılaştıran**, sağlık **trendini** öngören ve
> sonucu **bakım iş emrine** dönüştüren polyglot bir sistem.

**Üç servis:** Python (ML) · .NET (bakım planlama) · React (arayüz).
**525 test** (300 Python + 225 .NET, HTTP entegrasyon testleri dahil) — her
push'ta GitHub Actions'ta çalışır. `docker compose up` ile tek komutla kurulur.
Arayüz kurumsal ERP düzeninde: işlem kodları, modül ağacı, çoklu pencere,
durum çubuğu.

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
| **F — Kalan ömür** | Furan → DP → kağıdın tüketilen ömrü (DGA'nın göremediği) | `GET /transformers/{id}/oil-tests` |
| **G — Tek skor** | Dört boyut (DGA · kağıt · elektriksel · yağ) → 0-100 sağlık endeksi, formülü açık | `GET /transformers/{id}/health` |
| **H — Bağımsız duyu** | TTR, sargı direnci, PI, tan δ — yağın göremediği arızalar | `GET /transformers/{id}/electrical-tests` |
| **I — Sorumluluk** | Departman bazlı yetki: her testi kendi birimi girer; personele bildirim gönderme | `GET /departments`, `POST /notifications/messages` |
| **J — İkinci göz** | Mühendislik: sınır dışı test onayı, model tanısına uzman etiketi, varlığa özel eşik, kök neden analizi — hepsi dört gözlü ve denetim izli | MH01–MH04 |
| **K — Hesap güvenliği** | Parola politikası, geçici parola, kilitleme, belirteç yenileme, görev ayrılığı (hesap açan ≠ işi yapan) | `POST /auth/refresh`, `/admin/users` |

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

### Seçenek A — Docker (tek komut)

Tek ön koşul **Docker**. Model imaj oluşturulurken eğitilir, demo verisi ilk
açılışta yüklenir:

```powershell
copy .env.example .env          # TRANSFORMERAI_AUTH_SECRET'i doldurun
docker compose up --build       # http://localhost:8080
```

Anahtar üretmek için: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
Anahtarsız servisler **açılmayı reddeder** (üretim kuralları). Demo verisini
sıfırlamak: `.\scripts\reset-demo.ps1 -Docker`.

### Seçenek B — Yerel geliştirme

Gereksinimler: **Python 3.12+**, **Node 18+**, **.NET 10 SDK**.

Kurulum bir kez yapıldıysa üç servisi tek komutla başlatabilirsiniz:

```powershell
.\start.ps1          # üç servisi ayrı pencerelerde başlatır
.\start.ps1 -Check   # durum kontrolü
.\start.ps1 -Stop    # hepsini durdurur
```

İlk kurulum için aşağıdaki adımları izleyin.

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
cd backend      ; pytest -q            # 300 test
cd maintenance  ; dotnet test          # 225 test
```

Üç katman:

- **Saf kurallar** (çoğunluk): iş kuralları veritabanı ve HTTP bilmeyen
  sınıflarda — yetki haritası, parola politikası, RCA kuralları, dört göz.
- **Veritabanı** (`AuthServiceTests`): bellek içi SQLite ile giriş, kilit,
  parola değiştirme, belirteç yenileme.
- **HTTP entegrasyon** (`Integration/`): `WebApplicationFactory` uygulamayı
  bellekte gerçek boru hattıyla başlatır; her test kendi geçici veritabanıyla
  giriş → yetki → iş emri → kök neden analizi akışlarını uçtan uca sınar.

**CI** (`.github/workflows/ci.yml`): her push'ta üç paralel iş — Python
(model eğitimi + testler), .NET (testler), arayüz (üretim derlemesi). Testler
Linux'ta çalışır; Windows'a özgü varsayımlar orada ortaya çıkar.

---

## Departmanlar ve yetkiler

Giriş sicil numarası + parola ile yapılır. Demo hesapların geçici parolası
`Demo-<sicil>` (ör. `Demo-10502`); ilk girişte kendi parolanızı belirlemeniz
zorunludur. Yeni kullanıcıları **10001 · Kerem Aksoy (Sistem Yönetimi)** AD01
ekranından açar; Yönetim departmanı kullanıcı hesabı açamaz.

**Üretim / Docker kurulumu:** `.env.example` dosyasını `.env` olarak kopyalayıp
`TRANSFORMERAI_AUTH_SECRET` değerini doldurun (en az 32 karakter, iki serviste
aynı). Geliştirme ortamı dışında anahtar yoksa servisler **açılmayı reddeder** —
kaynak koddaki geliştirme anahtarıyla çalışan bir sunucuda herkes geçerli
belirteç üretebilirdi. Yerel geliştirmede (`start.ps1`) ayar gerekmez.
Yetki **kişiye veya role değil departmana** bağlıdır ve işlem bazlıdır —
"Testler ekranı" diye bir yetki yok, "yağ testi kaydetme" diye bir yetki var.

| Departman | Demo hesabı | Yapabildikleri |
|---|---|---|
| **Sistem Yönetimi** | 10001 | Kullanıcı hesabı açma, parola sıfırlama, kilit açma, pasife alma — **operasyon yetkisi yok** |
| **Yönetim** | 10502 | Bütün operasyon ekranları ve işlemleri — **kullanıcı hesabı açamaz** |
| **Mühendislik** | 10833, 10921 | Test onayı, model incelemesi, varlığa özel eşik, kök neden analizi — test girmez, iş yürütmez |
| **Bakım Planlama** | 10318 | İş emri açma/atama, personel listesi |
| **Yağ Laboratuvarı** | 10455, 10740 | DGA ölçümü, yağ kalitesi testi, numune analizi |
| **Elektriksel Test** | 10247 | Elektriksel test, buşing/kademe testi |
| **Saha Bakım** | 10611 | Kendisine atanan işi başlatma/bitirme, saha gözlemi |

- Yetki haritası **tek yerde** (`Models/Department.cs`) ve imzalı giriş
  belirtecine yazılıyor. Python yetkiyi belirteçten okur, .NET'e sormaz —
  .NET kapalıyken de ölçüm girilebilir.
- Kontrol **sunucuda**: yetkisiz istek 403 alır ve mesaj işi hangi
  departmanın yapabileceğini söyler. Arayüzdeki kilitler yalnızca yol
  gösterir.
- **Görev ayrılığı:** hesap açan (Sistem Yönetimi) işi yapamaz, işi yapan
  (Yönetim) hesap açamaz; ölçen (laboratuvar) onaylayamaz, onaylayan
  (Mühendislik) ölçemez.
- **Yetki yükseltme koruması:** kimse kendi departmanını değiştiremez; son
  aktif Sistem Yöneticisi ve son aktif Yönetim personeli pasife alınamaz.
- Geçici parolayla açılan oturum parola değişene kadar hiçbir işlem yapamaz;
  bütün hesap işlemleri denetim izine yazılır. Yeni kayıt en dar yetkiyle başlar.

---

## Ekranlar

| Sekme | İçerik |
|---|---|
| **Filo** | 9 trafo, önceliğe göre sıralı; risk dağılımı, alarm listesi, arama/filtre. Karta tıklayınca: gaz geçmişi + 6 aylık öngörü + gaz bazında trend tablosu |
| **Numune Analizi** | Elle gaz girişi → tanı, SHAP grafiği, Duval üçgeni, yöntem karşılaştırması, gerçeklik kontrolü paneli |
| **Bakım Planlama** | İş emirleri, sistemin ürettiği öneriler, teknisyen yük tablosu, atama |
| **Test Onay Kuyruğu (MH01)** | Sınır dışı yağ/elektriksel/buşing testleri: onayla · tekrar ölçülsün · reddet (dört göz) |
| **Model İnceleme (MH02)** | Modelin emin olmadığı tanılar; uzman etiketi gerçek etiketli veri olarak birikir |
| **Varlığa Özel Eşik (MH03)** | Tek trafo için süreli, gerekçeli, dört gözlü yağ eşiği istisnası; onaydan önce etki önizlemesi |
| **Kök Neden Analizi (MH04)** | Kapanan kritik iş emrine bulgu → neden → önlem; benzer geçmiş analizler önerilir |
| **Yönetim Özeti (YN01)** | Filo sağlığı, sınıf × bant matrisi, yenileme adayları, iş yükü |
| **Personel (PR01)** | Kayıtlar, departman ataması, departman → yetki tablosu |
| **Kullanıcı Yönetimi (AD01)** | Hesap açma (geçici parola bir kez gösterilir), sıfırlama, kilit açma, pasife alma, denetim izi |
| **Bildirimler (BL01)** | Tek ekran: gelen kutusu, okunmamışlar, yeni bildirim (kişiye / departmana / herkese) ve gönderilenler |
| **Parolamı Değiştir (PW01)** | Herkes kendi parolasını değiştirir; diğer oturumlar kapanır |

Trafo detayı dokuz sekmeden oluşur: **Ölçümler ve Trend** · **Şema** (bütün
boyutlar tek görselde) · **Yağ Kalitesi** · **Elektriksel** (TTR, sargı
direnci, PI, tan δ) · **Buşing/Kademe** · **Saha Gözlemi** · **Sağlık
Endeksi** (altı boyut, skorun aritmetiği satır satır) · **Künye** ·
**Yaşam Döngüsü**.

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

**Elektriksel testler: yağın göremediği arızalar.** DGA, nem, furan —
hepsi aynı yağ numunesinden okunur. Ama bazı arızalar yağa iz bırakmaz:
sargıda kısa devre olmuş bir spir, kademe değiştiricide aşınmış bir
kontak. Bu testler trafo **enerjisizken** yapılır ve sisteme bağımsız
bir duyu ekler.

İki vaka bunu anlatıyor. **TR-05**: yağı temiz, DGA'sı "Normal" — ama
TTR B fazında %1.4 düşük, yani spir kaybı. Yalnızca yağa bakan bir sistem
bunu göremezdi. **TR-04**: DGA "T1 (düşük sıcaklıkta ısınma)" diyor,
sargı direnci de kademe kontağında %4.5 dengesizlik gösteriyor — iki
**bağımsız** kaynak aynı sonuca varıyor, ki bu tek kaynağın iki kez
söylemesinden çok daha güçlü bir kanıttır.

Üç yerde "kolay ama yanlış" olan reddedildi:

| Karar | Neden |
|---|---|
| TTR'de sapmanın **deseni** tanı koyar | Tek faz ayrışmışsa spir kaybı; üçü birlikte kaymışsa kademe yanlış girilmiş. Aynı sapma, biri kağıt hatası diğeri devreden çıkarma sebebi |
| IR > 5000 MΩ'da **PI'a bakılmaz** | Naif kod filonun en kuru trafosunu "ıslak" ilan ederdi (IEEE C57.152) |
| tan δ'da sıcaklık düzeltmesi **yapılmaz** | Yalıtım tipine bağlı ampirik tablo gerekir; uydurmak yerine sınırı söylüyoruz |

**Sağlık endeksi: tek skor, ama kara kutu değil.** DGA riski, kağıt DP'si,
elektriksel testler ve yağ kalitesi ortak bir 0-100 ölçeğine çevrilip
ağırlıklı ortalaması alınır (DGA ×4, kağıt ×3, elektriksel ×3, yağ ×2):

```
Sağlık = Σ(ağırlık × puan) ÷ Σ(ağırlık)
```

Üç kural formülü dürüst tutuyor:

| Kural | Neden |
|---|---|
| Bilinmeyen boyut ortalamadan **çıkarılır** | Yağ testi olmayan trafo, yağı iyi olanla aynı skoru alamaz |
| Bir boyut en kötü seviyedeyse skor **45'i aşamaz** | Üç iyi boyut, ark yapan (ya da sargısı bozuk) bir trafoyu gizleyemez — TR-05'in ham ortalaması 77, tavanla 45 |
| **Yaş ayrı boyut değil** | Etkisi zaten kağıt DP'sinin içinde; iki kez saymak olurdu |

Skorun yanında onu **en çok aşağı çeken boyut** da bildirilir. Demo
filodaki TR-09 bunun tam örneği: DGA'sı sakin, yağı kabul edilebilir, ama
kağıdının %82'si tüketilmiş — skor "Orta" (65) çıkıyor ve tek başına
bakıldığında asıl sorun görünmüyor.

Ayrıca iki farklı öncelik ayrı tutuldu: filo sıralamasındaki `priority`
**aciliyeti** ölçer (bugün kime koşayım), `renewal_priority` ise
**durumu** (bu yıl hangi ünitenin bütçesini ayırayım).

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

docker-compose.yml      üç servis + kalıcı birimler (tek komut kurulum)
.env.example            ortam değişkenleri şablonu (.env git'e girmez)
.github/workflows/      CI: Python + .NET + arayüz, her push'ta
scripts/reset-demo.ps1  demo verisini sıfırla (yerel veya Docker)
start.ps1               yerel geliştirme: üç servisi başlat / durdur / kontrol
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
| `GET` | `/reviews/queue` · `POST /reviews/{tür}/{id}/decision` | Test onay kuyruğu (MH01) |
| `GET` | `/model-reviews/queue` · `POST /model-reviews/{id}/label` | Model inceleme / uzman etiketi (MH02) |
| `GET` | `/limits/queue` · `POST /transformers/{id}/limits` | Varlığa özel eşik (MH03) |

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
| `POST` | `/auth/login` · `/auth/logout` · `/auth/refresh` · `/auth/change-password` | Giriş, çıkış, belirteç yenileme (döndürme), parola değiştirme |
| `GET`/`POST` | `/admin/users` (+ `/reset-password`, `/unlock`, `/deactivate`, `/activate`) | Kullanıcı yönetimi — yalnızca Sistem Yönetimi |
| `GET` | `/admin/audit` | Hesap işlemleri denetim izi |
| `GET` | `/rca/pending` · `POST /workorders/{id}/rca` · `GET /rca/similar` | Kök neden analizi (MH04) |

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
- [x] **Faz 8–9** — Yağ/kağıt, elektriksel testler, buşing/kademe, saha gözlemi, sağlık endeksi, kimlik
- [x] **Faz 10–11** — Departman yetkileri, bildirimler, ERP arayüzü
- [x] **Faz 12** — Mühendislik: test onayı, uzman etiketi, varlığa özel eşik, kök neden analizi
- [x] **Sistem Yönetimi** — parola ile giriş, kullanıcı yönetimi, denetim izi
- [x] **Sağlamlaştırma** — güvenlik sertleştirme, HTTP entegrasyon testleri, CI, Docker
- [ ] **Faz 13** — Doküman / çizim yönetimi
- [ ] **Faz 14** — Stok ve yedek parça
- [ ] **Faz 15** — Akıllı cihaz (IED) filosu

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
- **HTTPS yoktur.** Docker kurulumu yerel ağ içindir; gerçek kurulumda nginx
  önüne TLS sertifikası şarttır, aksi hâlde parola ve belirteç ağda açık gider.
- Python servisi oturum tablosunu görmez: .NET'te kapatılan bir oturumun
  belirteci Python'da **en fazla 20 dakika** daha geçerli kalabilir (imzalı
  belirteç + yenileme ödünleşimi; önceden 9 saatti).
- Gaz üretim hızı (IEEE C57.104) ölçütü denendi ve ölçüldüğünde hiçbir kararı
  değiştirmediği için **rafa kaldırıldı**: `docs/DENEY-GAZ-URETIM-HIZI.md`.
