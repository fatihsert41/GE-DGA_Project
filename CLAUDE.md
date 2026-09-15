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

## YARIN BURADAN BAŞLA (14 Eylül 2026 sonu itibarıyla)

```powershell
cd C:\Users\Lenovo\Desktop\Python\GE-DGA_Project   # 14 Eyl: yeni bilgisayar
.\start.ps1                # üç servisi birden başlatır (~22 sn)
.\start.ps1 -Check         # sadece durum kontrolü
.\start.ps1 -Stop          # hepsini durdurur
```

Arayüz: http://localhost:5173 · API: http://localhost:8000/docs

**Durum:** Faz 0-11 BİTTİ. **349 test** (232 Python + 117 .NET).
Üç servis: Python :8000 · .NET :5080 · React :5173.

**Faz 11 — ERP arayüzü (Canias tarzı) TAMAM (14 Eyl).** Kullanıcı:
"AI frontendinden uzaklaşalım." Kabuk `App.jsx`: lacivert başlık çubuğu +
**işlem kodu** kutusu (FL01 Filo · TS01 Testler · NA01 Numune Analizi ·
BK01 Bakım · YN01 Yönetim · PR01 Personel · BL01 Bildirimler; kod ya da
ekran adının başı yazılıp Enter), sol **modül ağacı**, açık ekranlar
**sekme** olur, araç çubuğu (Geri · Yenile [önbelleği temizler] ·
Yazdır · Kapat), alt **durum çubuğu** (servis bağlantıları, kullanıcı).
Stil `index.css` sonunda AYRI KATMAN ("Faz 11 — ERP arayüzü"): önceki
kurallar silinmedi, eziliyor — geri almak o bloğu silmek kadar kolay.
Sistem fontları (Segoe UI/Consolas), Google Fonts kaldırıldı. Risk
rampası ve seri renkleri DEĞİŞMEDİ.
**Bildirimler tek ekran (BL01):** klasörler (Gelen Kutusu · Okunmamış ·
Gönderilenler) + "Yeni Bildirim" + liste + önizleme. Açılan bildirim
otomatik okundu sayılır. **Bildirim göndermek kayıtlı herkese açık**
(kullanıcı kararı): `notifications.send` her departmana verildi, anahtar
duruyor ki ileride tek satırla kısıtlanabilsin.
⚠ "Görsel dil" bölümü (aşağıda) Faz 9.7 öncesini anlatıyor, geçersiz.

**Faz 12–15 — kullanıcı kararları (15 Eyl):** sıra 12→13→14→15 ONAYLANDI ·
Mühendislik YENİ demo personelle kuruldu (kimse taşınmadı) · akıllı cihaz
bakımı Faz 15'te YENİ **Enstrümantasyon** departmanı olacak. Faz 13
(DWG desteği) ve Faz 14 (depo sayısı) soruları o fazlara gelince sorulacak.

**Faz 12 alt adımları:** 12.1 departman+yetki ✅ · 12.2 test onay kuyruğu ·
12.3 model inceleme/uzman etiketi · 12.4 varlığa özel eşik · 12.5 kök neden
analizi · 12.6 ERP ekranları MH01–04 + belgeler.

**✅ 12.1 TAMAM (15 Eyl, commit edilmedi):** `Department.Engineering` +
`engineering.approve / review_model / limits / rca` (+ analysis.run,
manager.view, notifications.send). Mühendislik test GİRMEZ ve iş emri
YÜRÜTMEZ (dört göz; testle korunuyor). Demo: **10833 Deniz Koç**,
**10921 Can Yıldız** (Mühendislik). Migration `MuhendislikDepartmani`.
⚠ Bulunan hata düzeltildi: `AssignmentService` otomatik atamada yetkiye
bakmıyordu — iş, yürütme yetkisi olmayan birine (ör. laboratuvar) atanıp
403 ile kilitlenebiliyordu. Artık yalnızca `workorders.execute` sahipleri
aday. Testler: 232 Python + **123 .NET**.
**✅ 12.2 TAMAM (15 Eyl, commit edilmedi) — Test onay kuyruğu (MH01).**
Kurallar saf modülde: `backend/app/core/review.py`; DB/servis
`services/review.py`; uç noktalar `routers/reviews.py`
(`GET /reviews/queue?folder=pending|retest|approved|rejected|all`,
`POST /reviews/{oil|electrical|components}/{id}/decision`, `GET /reviews/schema`).
* Genel hükmü **"kötü"** olan yağ/elektriksel/buşing-kademe testi `pending`
  olur (fiziksel gözlem dışarıda: ölçüm değil göz kontrolü).
* Kararlar: onayla · **tekrar ölçülsün** (hesapta KALIR, doğrulanmamış) ·
  **reddet** (hükme/endekse GİRMEZ, silinmez — `core_review.is_usable`).
* **Dört göz kişiye bakar** (`recorded_by_id` = karar veren → 403), çünkü
  Yönetim hem test girip hem onaylayabiliyor. Red/tekrar için gerekçe ≥10.
* Karar bir kez: `UPDATE … WHERE review_status='pending'` (yarışta 409).
* Sağlık endeksi `compute(unverified=[...])`: boyut `unverified: true`,
  `unverified_dimensions`, uyarı metni. Yağ testi oil + paper'ı birlikte
  işaretler.
* `review_status` NULL başlar; açılışta `review_service.backfill()` eski
  testleri bir kez sınıflandırır. Demo DB: 34 sınıflandı, **8 onay
  bekliyor** (TR-05 spir kaybı, TR-08 buşing, TR-03 asitlik…).
* Canlı doğrulandı: .NET'ten alınan mühendis belirteci Python'da karar
  yetkisi olarak tanınıyor; laboratuvar 403.
Testler: `tests/test_reviews.py` (16) → 248 Python + 123 .NET.

**✅ 12.3 TAMAM (15 Eyl, commit edilmedi) — Model inceleme / uzman etiketi (MH02).**
Kurallar `core/expert_label.py`; servis `services/model_review.py`; uç
noktalar `routers/model_reviews.py` (`/model-reviews/queue|stats|dataset`
[`?format=csv`], `GET /model-reviews/{mid}`, `POST …/{mid}/label`).
Yeni tablo `expert_labels` (measurement_id UNIQUE; model tahmini ve güveni
ANLIK GÖRÜNTÜ olarak kopyalanır). Kararlar:
* **Uzman kararı modelin önüne geçer:** `expert_label.apply_to_card` filo
  kartında `prediction/severe/prediction_family`'i uzmandan alır,
  `needs_review=False`, `prediction_source="expert"`, modelinki
  `model_prediction`'da kalır → .NET planlayıcısı doğru iş emrini üretir.
* **"Belirlenemedi"** tanıyı değiştirmez, inceleme bayrağı KALIR, veri
  setine GİRMEZ (uydurulmuş etiket modele yanlış öğretir).
* Emin olunan tanı da etiketlenebilir (en tehlikeli hata: emin + yanlış).
* Kuyruk: güven < 0.90 ve etiketsiz; önce trafonun SON ölçümü, sonra LPT.
* Dört göz ölçümü KAYDEDENE bakar → `save_measurement(recorded_by=…)`
  artık dolduruluyor (Faz 9.0c'den beri boş kalıyordu; `/predict` kimliği
  yazıyor). Modelden farklı karar ve "belirlenemedi" gerekçe ≥10 ister.
* Arayüzde modelin cevabı ÖNCEDEN SEÇİLİ DEĞİL (otomasyon yanlılığı).
* İstatistik: alt tip uyumu, AİLE uyumu, modelin kaçırdığı ciddi arıza
  (Faz 6.4 dersi: tek uyum oranı yetmez).
* ⚠ Etiketler modeli OTOMATİK yeniden eğitmiyor (bilinçli): az sayıda
  etiket + Faz 6.3'te "karma eğitim saf gerçeği geçmedi" bulgusu. Veri seti
  CSV olarak dışa aktarılıyor; eğitime katmak ayrı, ÖLÇÜLEREK yapılacak iş.
Demo DB: 26 düşük güvenli ölçüm kuyrukta (son ölçüm: TR-08, TR-09).
Testler: `tests/test_model_reviews.py` (13) → **261 Python** + 123 .NET.
**✅ 12.4 TAMAM (15 Eyl, eski bilgisayarda) — Varlığa özel eşik (MH03).**
Kurallar `core/asset_limits.py` (saf); servis `services/limits.py`; uç
noktalar `routers/limits.py` (`GET /limits/schema`, `GET /limits/queue?
folder=pending|active|closed|all`, `GET|POST /transformers/{id}/limits`,
`POST /limits/{oid}/decision`, `POST /limits/{oid}/revoke`). Yetki
`engineering.limits`. Yeni tablo `limit_overrides` (standart sınırlar da
kayda KOPYALANIR; kayıt silinmez). Kararlar:
* **Yalnızca yağ kalitesi eşikleri** (nem, BDV, asitlik, IFT) — tasarıma
  bağlılar. Elektriksel/buşing eşikleri ARIZA İMZASI, istisna alamaz.
* Gerekçe ≥20 · süre zorunlu, ≤365 gün, **bugünden önce başlayamaz** ·
  standarttan en fazla **%50** sapma (25 yerine 250 = yazım hatası).
* **Dört göz:** öneren onaylayamaz/reddedemez (403). Bekleyen istisna
  UYGULANMAZ. Geri çekme dört göz İSTEMEZ (standarda dönmek korumacı).
* Trafo+parametre başına tek açık istisna: **kısmi benzersiz indeks**
  (`WHERE status IN ('pending','active')`) → yarışta 409.
* Uygulama **test tarihine** göre (`select_for_test`): geçmiş testin
  hükmü değişmez. Süre dolunca her okumada `expired` olur.
* **Sessiz değil:** `oil_quality.assess` artık `overall_standard`,
  `overrides_applied`, `warnings` ve parametre başına `limit_source`,
  `standard_*_limit`, `standard_condition` döner. Yağ panelinde
  "varlığa özel eşik" etiketi + standart sınır yan yana.
* Onay ekranı **etki önizlemesi** gösterir: son test bu sınırlarla
  değerlendirilseydi hüküm değişir mi (`impact.changes_verdict`).
⚠ Onay kuyruğu (12.2) sınıflandırması testin KAYIT anındaki hükmüyle
kalır; sonradan onaylanan istisna eski `pending` kaydı geri almaz.
Demo DB'de istisna YOK (kasıtlı: sahte kayıt üretilmedi; akış arayüzden
iki mühendisle denenmeli — 10833 önerir, 10921 onaylar).
Testler: `tests/test_asset_limits.py` (21) → **282 Python** + 123 .NET.
Ayrıca: gaz üretim hızı deneyi ölçüldü ve rafa kaldırıldı
(`docs/DENEY-GAZ-URETIM-HIZI.md`).
**✅ 12.5 TAMAM (15 Eyl, eski bilgisayarda) — Kök neden analizi (MH04).**
**.NET'te** (iş emirleri orada; ortak DB yok kuralı). Model
`Models/RootCauseAnalysis.cs` (`FailureMode` enum: 10 tür, "Belirlenemedi"
dahil), kurallar SAF `Services/RcaRules.cs`, depo `Data/RcaRepository.cs`,
migration `KokNedenAnalizi` (yalnızca CreateTable + 3 indeks). Uç noktalar:
`GET /rca/schema`, `GET /rca/pending`, `GET /rca?transformerId&failureMode`,
`GET /rca/similar`, `GET|POST /workorders/{id}/rca` (yazma
`engineering.rca`). Kararlar:
* **Zorunlu olduğu iş:** tamamlanmış VE (öncelik ≥ 2.5 ya da
  Onarım/Değişim). 2.5 = bildirimlerdeki "yüksek" eşiğiyle aynı. Rutin iş
  kuyruğa düşmez (damga yorgunluğu). Kural bellekte süzülür, SQL'e ikinci
  kez yazılmadı.
* Yalnızca **Done** işe (Cancelled/Planned/InProgress → 409). İş emri başına
  **tek** RCA (benzersiz indeks → yarışta 409). **Güncelleme uç noktası YOK**
  (denetim kaydı). Kimlik `RCA-{iş emri Seq}`: ayrı sayaç yarışı yok.
* Bulgu / kök neden / alınan önlem ≥20 karakter; tekrarı önleme isteğe bağlı.
  Arıza türü yalnızca HARF: `Enum.TryParse("Winding, Core")` sessizce
  1|2=3=Bushing yapıyordu, testle korunuyor.
* **Benzer analiz:** aynı tür +3, aynı trafo +2; "Belirlenemedi" tür
  eşleşmesi sayılmaz; en yeni üstte, en fazla 5. Form YAZMADAN ÖNCE gösterir.
* İş emri silinirse RCA gitmez (`Restrict`) — bildirimdeki Cascade'in tersi.
⚠ **Bulunan hata düzeltildi:** arayüzdeki "Bitir" düğmesi hiç
çalışmıyordu — sunucu tamamlarken not istiyor (Faz 7'den beri), arayüz
göndermiyordu, her tıklama 409. Artık not formu açılıyor
(`MaintenancePanel.jsx`, `api.maintenance.setStatus(id, status, note)`).
Demo DB'de tamamlanmış iş emri YOK → MH04 kuyruğu boş başlar; akış: BK01'de
kritik işi başlat/bitir (10502 veya planlamacı) → MH04'te 10833 yazar.
Doğrulama: DB KOPYASI üzerinde ayrı örnekle (5099) uçtan uca 20/20.
Testler: `RcaRulesTests.cs` (27) → 282 Python + **150 .NET**.
**✅ Sistem Yönetimi TAMAM (15 Eyl, eski bilgisayarda; 12.6'nın önüne alındı).**
Kullanıcı kararları: sicil + parola · ayrı Sistem Yöneticisi · geçici parola
ilk girişte değişir · önce bu, sonra 12.6.
* Yeni `Department.SystemAdmin` + `users.manage`. **Yönetim bu yetkiyi
  ALMAZ** (`All` eksi `UsersManage`): işi yapan ile hesabı veren ayrı.
  Sistem Yönetimi operasyona dokunmaz (test/iş emri/mühendislik yok).
* Kurallar SAF: `Services/PasswordPolicy.cs` (≥10 karakter, sicil/ad/yaygın
  parola yok, karmaşıklık kuralı YOK — NIST 800-63B) ve
  `Services/UserAdminRules.cs`. **Yetki yükseltme koruması:** kimse kendi
  departmanını değiştiremez (403), admin kendini pasife alamaz; son aktif
  Sistem Yöneticisi / Yönetim taşınamaz, pasife alınamaz.
* Geçici parola: SİSTEM üretir (12 karakter, 0/O/1/l/I yok), bir kez
  gösterir. `MustChangePassword` iken belirteçte yetki listesi BOŞ (Python
  da yazamaz) ve oturum 15 dk; .NET'te `RequireAsync` ayrıca 403
  `password_change_required` döner — çünkü .NET yetkiyi departmandan okur.
* Parola değişince / sıfırlanınca / pasife alınca / departman değişince
  kişinin BÜTÜN oturumları kapanır. Değiştirme kapısı da giriş sayacına
  yazılır (kaba kuvvete kilitlenir).
* `PinHasher` → `PasswordHasher`; C# adı `PasswordHash`, DB sütunu hâlâ
  `PinHash` (`HasColumnName`). Migration `SistemYonetimi`'ne **ELLE** SQL
  eklendi: eski PIN özetleri ve oturumlar silinir, açılış bloğu herkese
  `Demo-<sicil>` atar. Olmasaydı herkes eski PIN'le girmeye devam ederdi.
* Yeni tablo `user_audit_events` (FK yok, kayıt silinmez): açıldı,
  sıfırlandı, değiştirildi, kilitlendi (yapan=sistem), kilit açıldı,
  pasife alındı, etkinleştirildi, departman değişti.
* Açık bulundu ve kapatıldı: `/personnel/by-employee-no/{sicil}` kimliksizdi
  (kullanıcı sayımı) → artık `personnel.view` istiyor. Giriş ekranındaki
  demo hesap tablosu ve "PIN = son 4 hane" ipucu kaldırıldı. Pasif hesap
  mesajı artık yalnızca DOĞRU parolayla gösteriliyor.
* Arayüz: `AdminPanel.jsx` (AD01), `ChangePasswordScreen.jsx` (zorunlu tam
  sayfa + PW01 "Hesabım"), `LoginScreen.jsx` parolaya geçti.
* **İlk .NET entegrasyon testleri:** `AuthServiceTests.cs` bellek içi SQLite
  (EF InMemory DEĞİL — benzersiz indeks ve SQL davranışını taklit etmez).
Testler: `PasswordHasherTests`, `UserAdminRulesTests`, `AuthServiceTests`,
`PermissionTests` güncellendi → 282 Python + **199 .NET**. Uçtan uca (PIN
dönemi DB kopyası, migration dahil) 36/36.
⚠ Bilinen sınır: kapatılan oturumun belirteci Python'da süresi dolana kadar
geçerli (imzalı belirteç ödünleşimi, TokenIssuer).

**SIRADAKİ: 12.6 Mühendislik ekranları MH01–04 son hâli + belgeler (Faz 12'yi kapatır).**

**Yol haritası belgesi: `docs/FAZ12-15-YOL-HARITASI.md`**.
Önerilen sıra: **12 Mühendislik departmanı + onay akışı** (test onay
kuyruğu, dört göz; model inceleme kuyruğu → uzman etiketi = gerçek veri) →
**13 Doküman/design yönetimi** (yükleme, revizyon, tarayıcıda PDF/görsel,
şema parçasına bağlama) → **14 Stok ve yedek parça** (parça kataloğu,
künyeden uyumluluk, depo, rezervasyon, teslim süresi + emniyet stoğu,
yeni Stok Kontrol departmanı) → **15 Akıllı cihaz (IED) filosu** (cihaz
kaydı, kalp atışı, kalibrasyon, laboratuvar–sensör sapması ile veri
kalitesi, model sürüm takibi). İLK İŞ: belgenin sonundaki 5 soruyu sor.

**Yeni bilgisayara geçiş (14 Eyl):** git'e girmeyen dosyalar yeniden
üretildi — `npm ci`, `python -m app.ml.train --field-like`,
`python -m app.ml.seed`; `dotnet-ef` global araç olarak kuruldu.
⚠ `start.ps1` artık `npm.cmd` çağırıyor: yeni Windows'ta betik politikası
Restricted olduğu için `npm` (npm.ps1) engelleniyor, arayüz penceresi
sessizce açılmıyordu.

**Giriş gerekli: sicil + PAROLA** (15 Eyl'de PIN'den geçildi). Demo
hesapların geçici parolası `Demo-<sicil>` (ör. `Demo-10502`); ilk girişte
kendi parolanı belirlemeden hiçbir işlem yapılamaz. Kullanıcı hesapları
**AD01**'den açılır — **10001 Kerem Aksoy (Sistem Yönetimi)**.

**Faz 10 — Departmanlar, yetkiler, bildirim gönderme TAMAM.**
Yetki ROLE değil DEPARTMANA bağlı ve işlem bazlı. Harita TEK YERDE:
`maintenance/.../Models/Department.cs`. Belirtece yazılıyor; Python
yetkiyi belirteçten okur (`auth.require_permission`), .NET'e sormaz.

| Sicil | Kişi | Departman | Yapabildikleri |
|---|---|---|---|
| 10001 | Kerem Aksoy | **Sistem Yönetimi** | kullanıcı aç/sıfırla/kilit aç/pasife al, departman değiştir — operasyon YOK |
| 10502 | Zeynep Şahin | **Yönetim** | kullanıcı yönetimi HARİÇ tam yetki |
| 10318 | Elif Demir | Bakım Planlama | iş emri planla/ata, bildirim gönder, personeli gör |
| 10455, 10740 | Mehmet Kaya, Selin Öztürk | Yağ Laboratuvarı | DGA + yağ testi, numune analizi |
| 10247 | Ahmet Yılmaz | Elektriksel Test | elektriksel + buşing/kademe testi |
| 10611 | Burak Aydın | Saha Bakım | KENDİ işini başlat/bitir, saha gözlemi |

Kararlar: her test türü tek departmana ait (testle korunuyor) · saha
personeli yalnızca kendisine atanan işi yürütür · son Yönetim personelinin
departmanı değiştirilemez (409) · yeni kayıt en dar yetkiyle başlar ·
yetki listesi olmayan eski belirteç HİÇBİR ŞEY yazamaz · atanmamış iş
emri bildirimi artık role değil planlama YETKİSİNE gidiyor · menüde
yetkisiz ekran gizlenmez, kilitli görünür ve kime başvurulacağını söyler.
Bildirim gönderme: `POST /notifications/messages` (kişi + departman +
herkes birleşir, tekrar yok, gönderen ve pasif hariç), `GET
/notifications/sent` (okundu durumu). `Notification.WorkOrderId` artık
isteğe bağlı. Migration: `DepartmanVeMesajlar`.
Bedel (bilinçli): departmanı değişen kişinin Python tarafındaki yetkisi
yeniden girişe kadar eski kalır; .NET tarafında anında geçerli.
⚠ Aynı fazda bulunan açık kapatıldı: `/workorders` cevabı atanan
teknisyenin `PinHash`/`PinSalt` alanlarını da döndürüyordu → `[JsonIgnore]`.

**Optimizasyon (14 Eyl):** ekranlar `React.lazy` ile bölündü (ana paket
730 → 215 KB) · Yönetim ekranı filoyu iki kez hesaplatıyordu →
`services/health.build_renewal_list(cards)` saf fonksiyonu,
`/fleet/overview.summary.renewal` · `api.js`'de 30 sn önbellek (yazma
isteği temizler) · `[hidden]{display:none!important}` — `.grid` kuralı
gizli analiz ekranını her sayfanın altına çiziyordu.

**Sağlık endeksi ALTI boyutlu:** DGA ×4 · kağıt ×3 · elektriksel ×3 ·
buşing/kademe ×2 · yağ ×2 · fiziksel gözlem ×1 (payda 15).

⚠ Uvicorn `--reload` Windows'ta değişiklikleri KAÇIRIYOR; kod
değişince servisi yeniden başlat. Ayrıca arka planda birden çok
uvicorn kalabiliyor (port 8000'i üç süreç dinledi) — şüphede
`netstat -ano | grep :8000` ile kontrol et.

**BEKLEYEN İSTEK (kullanıcı 11 Eyl'de söyledi):** Arayüz hâlâ "AI yapımı"
duruyor; **.NET/kurumsal platform görünümüne** çekilmesi isteniyor.
Kullanıcı "sonraya bırakalım" dedi, ama bu bir sonraki cila turunun
konusu olmalı. (Görsel dil bölümüne bak: kağıt zemin + mürekkep.)

**Faz 8.5 — Sağlık Endeksi TAMAM** (kullanıcı B'yi seçti).
`core/health_index.py` üç boyutu (DGA kondisyonu ×4, kağıt DP ×3, yağ
kalitesi ×2) tek 0-100 skorda birleştirir. Üç tasarım kararı:
* **Bilinmeyen boyut "sağlıklı" sayılmaz** — ortalamadan çıkarılır,
  `coverage` skorun ne kadar veriye dayandığını söyler.
* **Kritik boyut tavanı (45)** — iki iyi boyut, ark yapan bir trafoyu
  gizleyemez. (`oil_quality.assess`'teki "en kötü parametre" ile aynı
  gerekçe.)
* **Yaş ayrı boyut DEĞİL** — etkisi zaten kağıt DP'sinin içinde; iki kez
  saymak olurdu.
Ayrıca `weakest` (skoru en çok çeken boyut) döner: tek sayı hikâyeyi
gizler. Demo filoda ortalama **59.6**, en kötü TR-07 (25.5).
`renewal_priority` = (100−skor)/100 × varlık ağırlığı — mevcut `priority`
ACİLİYETİ ölçer, bu DURUMU ölçer; filo sıralaması DEĞİŞTİRİLMEDİ.
Uç noktalar: `/health-index/schema`, `/health-index/fleet`,
`/transformers/{id}/health`. Arayüz: filo kartında `HealthStrip`,
detayda dördüncü sekme `HealthPanel` (formülü satır satır gösterir).
Testler: `tests/test_health_index.py` (14 test) — toplam 109 Python.

**Faz 8.6 — Elektriksel testler TAMAM** (kullanıcının kendi fikriydi).
`core/electrical.py`: TTR, sargı direnci, yalıtım direnci/PI, tan δ.
Bu faz sisteme **bağımsız bir duyu** ekledi: şimdiye kadarki her ölçüt
yağdan okunuyordu, bunlar trafo ENERJİSİZKEN ölçülür.

Üç önemli tasarım kararı (hepsi "kolay ama yanlış" olanı reddediyor):
* **TTR'de sapmanın DESENİ tanı koydurur**, sadece büyüklüğü değil.
  Tek faz ayrışmışsa "kısa devre spir → devreden çıkar"; üçü birlikte
  kaymışsa "KADEME POZİSYONU yanlış girilmiş, önce onu doğrula". Bu
  ayrım olmadan sistem bir kağıt hatasını devreden çıkarma sebebi gibi
  raporlardı.
* **PI'ın anlamını yitirdiği bölge tanınıyor** (IR > 5000 MΩ,
  IEEE C57.152). Naif kod, filonun EN KURU trafosunu "ıslak" ilan
  ederdi. Demo filoda TR-02 tam olarak bu tuzak vakası.
* **tan δ'da sıcaklık düzeltmesi UYGULANMIYOR** — yalıtım tipine bağlı
  ampirik tablo gerekir, elimizde yok. Uydurmak yerine sınırı söylüyoruz.

Sargı direncinde ölçüt **mutlak ohm değil DENGESİZLİK**: mutlak direnç
künyede yazmaz ama üç faz birbirinin doğal referansıdır.

Uç nokta kuralları (ikisi de gerçek saha hatası): kademeli trafoda TTR
girerken kademe zorunlu (400); sadece kademe girip kaydetmek yasak (400).

Demo filo senaryoları elle seçildi (`ml/synth_electrical.py`,
`ml/seed.py::ELECTRICAL_SCENARIOS`) — rastgele üretim "yağı temiz ama
sargısı bozuk" gibi bir hikâye üretemezdi:
* **TR-05** yağı temiz + DGA sakin ama B fazında spir kaybı →
  YAĞIN GÖREMEDİĞİ ARIZA (bu fazın var oluş sebebi)
* **TR-04** DGA "T1" diyor + sargı direnci kademe kontağında aşınma
  gösteriyor → İKİ BAĞIMSIZ KAYNAK AYNI ŞEYİ SÖYLÜYOR
* **TR-06** PD + PI 1.06 (ıslak yalıtım)
* **TR-02** tuzak: PI 1.30 ama IR 32967 MΩ → hüküm "iyi"
* **TR-09** kasten testsiz (elektriksel test seyrektir, "veri yok" kural)

**Sağlık endeksine DÖRDÜNCÜ boyut olarak girdi** (ağırlık 3, yağdan
yüksek: kötü yağ filtrelenebilir, bozuk sargı sarılmak zorundadır).
Payda 9 → 12. TR-05 bunun kanıtı: ham ortalama 77 ("İyi") ama tavan
kuralı 45'e indiriyor. Tavan birden çok trafoyu 45'te yığdığı için
`fleet_health` sıralaması ham skoru ikincil ölçüt olarak kullanıyor.

Uç noktalar: `/electrical/schema`, `/electrical/fleet`,
`/transformers/{id}/electrical-tests` (GET+POST),
`/transformers/{id}/expected-ratio` (form ölçüm GİRİLİRKEN hedefi
göstersin diye ayrı). Arayüz: `ElectricalPanel.jsx`, detayda 5. sekme,
formda canlı sapma göstergesi.
Testler: `tests/test_electrical.py` (20) + `tests/test_electrical_api.py`
(12) + sağlık endeksine 4 test → toplam **145 Python**.

**Sıradaki seçenekler:**
* Arayüz cilası (yukarıdaki bekleyen istek) — .NET/kurumsal görünüm.
* Elektriksel testleri .NET bakım planlayıcısına bağlamak: şu an iş
  emri önerileri yalnızca DGA'ya bakıyor, oysa "B fazında spir kaybı"
  en az kritik risk kadar acil.

**Sonra gelecek işler (sırasız):**
* Kalibrasyon katmanı (`docs/FAZ6-IYILESTIRME-YOL-HARITASI.md` 1. sıra) —
  ölçüldü ama uygulanmadı: hizmet modeli kendi alanında ECE 0.021 ile
  zaten kalibre çıktı, bu yüzden aciliyeti düştü.
* ~~Zaman serisi özellikleri (gaz üretim hızı)~~ — **ÖLÇÜLDÜ, RAFA KALDIRILDI
  (15 Eyl).** `core/rate.py` + `ml/rate_eval.py` depoda ama ürüne bağlı
  değil: 106 seride 0 erken yakalama (sentetik en yüksek TDCG hızı ~2.5
  ppm/gün, IEEE 1991 eşiği 10). Yeniden açma koşulları:
  `docs/DENEY-GAZ-URETIM-HIZI.md`.
* Faz 8.6-8.7: termal model (IEEE C57.91), bileşen izleme (buşing/OLTC).

**Claude için teknik notlar:**
* ⚠ PowerShell `[regex]::Replace(metin, desen, yerine, 1)` — 4. parametre
  "kaç kez" DEĞİL, `RegexOptions` (1 = IgnoreCase). Bütün eşleşmeler
  değişir. 14 Eyl'de migration'ın Down() bölümünü bu yüzden bozdu;
  tek değişiklik için `[regex]::new(desen).Replace(metin, yerine, 1)`.
* Enum sütununa `HasDefaultValue` KOYMA, eğer enum'un 0 değeri anlamlıysa
  (ör. `Department.Management = 0`): EF 0'ı "atanmamış" sayıp veritabanı
  varsayılanını yazar. Varsayılanı migration dosyasında ver.
* bash heredoc Python kodundaki `'''` tırnaklarıyla da bozuluyor; uzun
  yama betiklerini scratchpad'e Write ile yazıp oradan çalıştır.
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
