# Faz 9 — Derinleşme Analizi ve Yol Haritası

> 11 Eylül 2026. Faz 8 bitti (künye, yağ kalitesi, kağıt yaşlanması, sağlık
> endeksi, elektriksel testler). Bu belge **nereye gideceğimizi** değil,
> önce **nerede durduğumuzu ve neyin eksik olduğunu** tespit ediyor.

---

## 1. Envanter: elimizde ne var?

| Katman | Ne ölçüyor | Nereden okunuyor | Ne zaman alınır |
|---|---|---|---|
| DGA | Aktif arıza (PD/D1/D2/T1/T2/T3) | Yağ numunesi | İşletmede, 6-24 ay |
| Yağ kalitesi | Nem, BDV, asitlik, IFT | Aynı numune | Yılda ~1 |
| Kağıt (furan→DP) | Tüketilen mekanik ömür | Aynı numune | Birkaç yılda 1 |
| Elektriksel | TTR, sargı direnci, PI, tan δ | Enerjisiz test | Devreye alma + büyük bakım |
| Künye | Bağlam (gerilim, bağlantı grubu, kağıt tipi, sargı malzemesi) | Elle girilir | Bir kez |
| Sağlık endeksi | Yukarıdakilerin ağırlıklı birleşimi | Türetilmiş | Sürekli |
| İş emri (.NET) | Eyleme dönüşüm | DGA'dan | Kural tetikli |
| **Kimlik** | ❌ **YOK** | — | — |

**Üç servis, 155 Python + 50 .NET testi.**

---

## 2. En büyük yapısal boşluk: dört duyu, tek tetikleyici

Bu, bu belgedeki en önemli tespit.

Faz 8 boyunca sisteme **dört bağımsız duyu** eklendi. Ama iş emri üreten
`WorkOrderPlanner` hâlâ **yalnızca DGA'ya bakıyor.** Kuralları:

```
severe-fault (D2/T3)   → 3 gün
critical-risk          → 7 gün
high-risk              → 14 gün
low-confidence         → 30 gün
sampling-overdue       → 30 gün
```

Hepsi `TransformerRisk` üzerinden, yani gaz analizinden geliyor. Sonuç:

| Bulgu | Sistem biliyor mu? | İş emri üretiyor mu? |
|---|---|---|
| TR-05: B fazında kısa devre spir | ✅ | ❌ |
| TR-04: kademe kontağında %4.5 dengesizlik | ✅ | ❌ |
| TR-06: yalıtım ıslak (PI 1.06) | ✅ | ❌ |
| TR-09: kağıdın %82'si tüketilmiş | ✅ | ❌ |
| TR-07: sağlık endeksi 24.1 (kritik) | ✅ | ❌ |

**Yani sistem gördüğünü söylüyor ama yapılacak işe çeviremiyor.** Kısa
devre olmuş bir spir, "yüksek risk" bir DGA sonucundan daha acildir ve
şu anda hiçbir iş emri üretmiyor. Bu, bir izleme sisteminin yapabileceği
en sessiz hatadır: doğru bilgiyi üretip kimseye ulaştırmamak.

Kullanıcının "test sonrası yetkililere mesaj gönderen / ticket açan yapı"
fikri tam olarak bu boşluğu işaret ediyor — **fikir doğru, ama çözümün
sırası önemli**: önce bulgu iş emrine dönmeli, sonra iş emri kişiye
ulaşmalı. Bildirim, olmayan bir iş emrini haber veremez.

---

## 2b. İkinci yapısal boşluk: kaydı kim girdi?

Sistemde **hiçbir kimlik doğrulama yok** ve bunun iki ayrı sonucu var.

### Sorun 1 — "Test eden" alanı serbest metin

`electrical_tests.tested_by` ve `oil_tests.lab` birer `TEXT` sütunu.
Kullanıcı ne yazarsa o kaydediliyor; hiçbir doğrulama yok. Demo sırasında
"Fatih Sert" yazıldı — "asdf" da yazılabilirdi ve sistem kabul ederdi.

Bu, Faz 8.6'da aldığımız **"kayıt silinmez, geçersiz işaretlenir"**
kararıyla doğrudan çelişiyor. Denetim izi tutmanın amacı kaydın
**sorumlusunun** bilinmesidir. Kim yaptığı doğrulanmayan bir kayıt,
denetim izi değil sadece bir metindir. "Geçersiz işaretlendi" diyoruz
ama **kim tarafından, ne zaman** onu da bilmiyoruz.

### Sorun 2 — Personel iki servise bölünmüş

| | Nerede | Ne var |
|---|---|---|
| Teknisyen kaydı | .NET (`Technician`) | Id, Ad, Bölge, Uzmanlık, Kapasite |
| Test girişi | Python (`tested_by`) | serbest metin |

Yani **personeli tanıyan servis ile kaydı yazan servis farklı.** Bir
teknisyen .NET'te tanımlı ama Python'a test girerken adını elle yazıyor.
İki taraf birbirini tanımıyor. Ayrıca `Technician`'da **sicil numarası
yok** — sadece `Id` (ör. "t-01") ve ad var.

### Doğru çözüm: personel .NET'te, kimlik anlık görüntüsü kayıtta

* **Personel sicili .NET'te kalır.** O servis zaten teknisyen, uzmanlık,
  kapasite ve atamayı yönetiyor; ikinci bir personel tablosu açmak
  mikroservis mimarisinin klasik hatası olurdu.
* **Python kayıtları kimliğin ANLIK GÖRÜNTÜSÜNÜ saklar:** sicil no + ad,
  kaydın yazıldığı andaki hâliyle.

İkinci madde önemli ve sezgiye aykırı görünebilir: neden sadece sicil no
tutup adı .NET'ten okumuyoruz? Çünkü **geçmiş kayıt değişmemelidir.** Bir
personel işten ayrılsa, soyadı değişse ya da kaydı silinse bile, üç yıl
önceki testin kim tarafından yapıldığı okunabilir kalmalı. Bu, "silme
yok, geçersiz işaretle" kararıyla aynı ilkenin devamıdır.

### Kapsam: KARAR — sicil + PIN ile gerçek giriş

İlk öneri "parolasız oturum kullanıcısı" idi (öğretici değeri düşük diye).
**Kullanıcı aksini istedi ve karar onundur:** sisteme sicil numarası +
PIN ile girilecek, arkasında gerçek bir doğrulama olacak.

Karar doğru gerekçelendirilebilir: kayıtların sorumlusu bilinecekse,
"herkes herkesin sicilini seçebilir" durumu izlenebilirliği de çürütür.
İmzasız bir imza defteri işe yaramaz.

**Uygulanacaklar:**

| Önlem | Neden |
|---|---|
| PIN **özetlenerek** saklanır (PBKDF2 + kişiye özel tuz) | Veritabanı sızsa bile PIN okunamaz. Düz metin saklamak en yaygın ve en ağır hatadır |
| Kişiye özel tuz (salt) | Aynı PIN'e sahip iki kişi aynı özeti üretmemeli; yoksa tablo bakarak eşleşme çıkarılır |
| Yanlış deneme sayacı + kilitleme | 4 haneli PIN'in 10.000 olasılığı var; sınırsız deneme onu anlamsız kılar |
| Oturum belirteci (token), süreli | Her istekte PIN göndermemek için. Sunucu tarafında saklanır, iptal edilebilir |
| Rol bazlı yetki | Süpervizör onayı gereken işlemler teknisyene kapalı |
| Python, belirteci .NET'e doğrulatır | Kimlik tek yerde; iki servis iki gerçek üretmemeli |

**Uygulanmayacaklar ve nedenleri — bunlar açıkça yazılmalı:**

| Yok | Neden |
|---|---|
| HTTPS/TLS | Demo localhost'ta çalışıyor. Gerçek kurulumda **şart**: TLS olmadan belirteç ağda açık gider |
| Çok faktörlü doğrulama (MFA) | Kurumsal kimlik sağlayıcı (LDAP/Entra ID) gerektirir |
| Parola politikası, sıfırlama akışı | PIN demo amaçlı sabit atanıyor |
| CSRF/XSS sertleştirmesi | Tek kullanıcılı yerel demo |

⚠ **Dürüstlük notu:** 4-6 haneli bir PIN, güçlü bir parola değildir.
Özetleme ve kilitlemeyle birlikte **banka kartı seviyesinde** bir koruma
sağlar: cihazı/sistemi elinde tutan birine karşı değil, sicilini bilen
birine karşı korur. Bu, izlenebilirlik için yeterli, gerçek bir üretim
sistemi için değildir. Arayüzde bu yazacak.

---

## 3. GE Vernova analizi — bu proje nereye oturuyor?

### 3.1 GE Vernova'nın ürün gerçeği

GE Vernova'nın varlık izleme portföyü iki katmanlı:

* **APM (Asset Performance Management)** — genel sanayi varlık platformu.
  IoT verisi, AI/ML analitiği, **dijital ikiz** simülasyonu, kestirimci
  bakım. **Mikroservis tabanlı**: her uygulama tek başına ya da
  birleştirilerek kullanılabiliyor. Bulut ya da yerinde kurulum.
* **GridBeats™ APM** — iletim/dağıtım varlıklarına özel katman;
  gerçek zamanlı veriyi saha uzmanlığı ve analitikle birleştirip
  **trafo merkezi** yönetimine odaklanıyor.

Ayrıca portföyde **Asset Strategy Management** (hangi varlığa hangi bakım
stratejisi), **Reliability Analysis** ve **Configuration Templates**
(varlık tipine göre hazır şablonlar) var.

### 3.2 Bu projeyle örtüşen ve ayrışan yanlar

| GE Vernova APM | Bu proje | Değerlendirme |
|---|---|---|
| Mikroservis mimarisi | ✅ Python + .NET, ayrı DB | **Örtüşüyor** — bilinçli tercihti |
| AI/ML analitiği | ✅ RF/XGB + SHAP | Örtüşüyor, üstelik açıklanabilir |
| Kestirimci bakım | ✅ trend + kalan süre | Örtüşüyor |
| Sağlık endeksi | ✅ 4 boyut | Örtüşüyor ama **dar** (aşağı bak) |
| Varlık kritikliği | ✅ LPT/MPT/SPT ağırlığı | Örtüşüyor |
| **Rol bazlı ekranlar** | ❌ tek ekran herkese | **BOŞLUK** |
| **Dijital ikiz** | ❌ | Kapsam dışı (fiziksel model gerekir) |
| **Varlık stratejisi yönetimi** | ❌ | Boşluk, orta vadeli |
| **Bildirim / iş akışı** | ❌ | **BOŞLUK** |

APM'nin hitap ettiği roller açıkça sayılıyor: **operatör, güvenilirlik/
performans mühendisi, süpervizör** ve varlık programlarından sorumlu
ekipler. Bizim arayüzümüz bu üç rolün üçüne de **aynı ekranı** gösteriyor.
Kullanıcının "yöneticiler ekranı" fikri buradan doğru: bir süpervizör
"TTR B fazı %1.4 düşük" satırını okumaz; "kaç varlığım riskli, bütçe
nereye gitmeli, ekibim yetişiyor mu" sorusunu sorar.

### 3.3 Sağlık endeksi literatürü — bizimki ne kadar eksik?

Akademik ve endüstriyel HI modelleri tipik olarak şunları içerir:

> DGA, yağ kalitesi, furan, **güç faktörü (tan δ)**, **kademe
> değiştirici durumu**, **buşing durumu**, **fiziksel gözlem**,
> **yük geçmişi**, **bakım iş emirleri** ve **yaş**.

Bizim dört boyutumuz (DGA, kağıt, elektriksel, yağ) bu listenin **yaklaşık
yarısı**. Eksikler ve değerlendirmesi:

| Boyut | Durum | Yorum |
|---|---|---|
| tan δ | ✅ elektriksel içinde | Var |
| Kademe değiştirici | 🟡 kısmen (sargı direnci) | Ayrı boyut olabilir: işletme sayacı, yağ, revizyon tarihi |
| Buşing | ❌ | Trafo arızalarının önemli bir kısmı buşing kaynaklı |
| Fiziksel gözlem | ❌ | Kaçak, korozyon, silikajel, radyatör — **ucuz ve etkili** |
| Yük geçmişi | ❌ | IEEE C57.91 termal model bunu ister |
| Bakım geçmişi | ❌ | .NET'te var ama endekse girmiyor |
| Yaş | 🟡 bilinçli olarak dışarıda | Kağıt DP'sinin içinde sayılıyor; gerekçeli |

**En yüksek getiri/emek oranı: fiziksel gözlem.** Cihaz gerektirmez,
teknisyen zaten sahada, ve endüstride HI'ın gerçek bileşenlerinden biri.

---

## 4. Kullanıcı fikirlerinin değerlendirmesi

### 4.1 "Yöneticiler ekranı, kategoriler şeklinde" — **YAPILMALI**

Gerekçe güçlü: APM'nin kendisi rol bazlı. Ama dikkat edilmesi gereken bir
tuzak var — **yönetici ekranı, aynı verinin daha büyük puntolu hâli
değildir.** Farklı sorulara cevap vermeli:

| Saha ekranı (mevcut) | Yönetici ekranı (yeni) |
|---|---|
| "Bu trafo ne durumda?" | "Filomun sağlığı nereye gidiyor?" |
| "TTR B fazı %1.4 düşük" | "3 varlık kritik, ikisi LPT" |
| "Bu testi gir" | "Hangi varlığa bütçe ayırayım?" |
| Tek ünite, derin | Filo, agregat, eğilim |

Kategoriler şu eksende olmalı: **varlık sınıfı × sağlık bandı × veri
kapsaması × açık iş yükü.** Dördüncüsü kritik ve genelde unutulur: bir
yönetici sadece varlığın durumunu değil, **ekibinin o duruma yetişip
yetişmediğini** bilmek ister.

### 4.2 "Test sonrası mesaj / ticket" — **YAPILMALI, ama sırayla**

Fikir doğru, sıra önemli:

1. **Önce** bulgular iş emri üretmeli (Bölüm 2'deki boşluk).
2. **Sonra** iş emri bir kişiye/role bildirilmeli.

Bildirim tek başına eklenirse "e-posta gönderen bir uyarı kutusu" olur;
iş emrine bağlanırsa **takip edilebilir bir iş akışı** olur. İkisi
arasındaki fark, demo ile ürün arasındaki farktır.

⚠ Teknik sınır: gerçek e-posta/SMS göndermek kimlik bilgisi ve dış servis
ister; bu proje demo. Doğru çözüm **bildirim kaydı** (outbox) tutmak:
sistem "kime, ne zaman, hangi kanaldan, hangi içerikle" haber verdiğini
saklar, arayüzde gösterir. Gerçek gönderim adaptörü sonradan takılır.
Bu, kurumsal sistemlerde de böyle kurulur ve test edilebilir kalır.

### 4.3 "Trafo design ekranı" — **KAPSAM NETLEŞTİRİLMELİ**

İki farklı okuma var:
* **(a) Künye/tasarım verisi ekranı** — zaten var (Künye sekmesi).
* **(b) Trafonun şematik görünümü** — sargılar, kademe değiştirici,
  buşingler, radyatörler üzerinde durum gösterimi.

(b) değerliyse ancak **bileşen bazlı veri** varsa değerlidir. Şu anda
buşing/OLTC verisi yok, dolayısıyla şema boş bir çizim olurdu. Bu yüzden
**önce bileşen izleme (9.4), sonra şema** sırası doğru.

---

## 4b. Üçüncü boşluk: trafonun yaşam döngüsü

Şimdiye kadar sisteme **işletmedeki** trafo gözüyle bakıldı: sahada duran,
yağı alınan, ölçülen bir varlık. Ama GE Vernova bu trafoları **üretip
satıyor.** Bir ünitenin hayatı fabrikada başlıyor ve sahaya varması aylar
sürüyor.

Bu bir künye alanı değil, **ayrı bir durum makinesi**:

```
Üretimde → Fabrika testinde → Sevkiyata hazır → Vinç/nakliye bekliyor
        → Yolda → Sahada (montaj) → Devreye alma testleri → Devrede
        → Hizmet dışı / Yedek / Hurda
```

**Neden değerli?**

* **DGA'nın anlamı duruma göre değişir.** Devreye alma öncesi alınan
  numunede gaz beklenmez; iki yıldır devrede olan bir ünitede beklenir.
  Sistem şu anda ikisini aynı ölçütle değerlendirir.
* **Numune gecikmesi kuralı yanlış çalışıyor.** Fabrikada bekleyen bir
  ünite "numunesi gecikmiş" sayılmamalı — henüz işletmede değil.
* **Yedek ünite planlaması.** Kritik bir LPT arızalandığında "yedekte
  ne var, nerede, ne kadar sürede gelir" sorusu bakım kararını
  doğrudan değiştirir. Faz 6.6'da "LPT'nin yedeklenmesi aylar sürer"
  demiştik ama sistem yedeği takip etmiyor.
* **Yönetici ekranının eksik yarısı.** Süpervizör yalnızca sahadaki
  varlıkları değil, gelmekte olanları da görmek ister.

⚠ Durum geçişleri **kurallı** olmalı (.NET'teki `WorkOrderTransitions`
gibi): "Devrede" durumundan "Üretimde"ye dönülemez. Her geçiş kim
tarafından, ne zaman yapıldı — kaydedilmeli (9.0'daki izlenebilirlik
buraya da uygulanır).

---

## 5. Yol haritası

Sıra, **bağımlılık** ve **getiri/emek** oranına göre kuruldu. Her aşama
sonunda çalışan bir şey var.

### 9.0 — Kimlik ve izlenebilirlik · **.NET + Python + React** ⭐ ÖNCE BU

Bölüm 2b'deki boşluk. Neden ilk sırada: **bundan sonra yazılan her kayıt
kimlik taşımalı.** Sonraya bırakılırsa, o zamana kadar girilen tüm
kayıtlar sahipsiz kalır ve geriye dönük doldurulamaz.

* **.NET:** `Technician` → `Personnel`; `EmployeeNo` (sicil), `Role`
  (Teknisyen / Mühendis / Süpervizör), `Email` alanları. Migration.
  `GET /personnel`, `GET /personnel/by-employee-no/{no}`.
* **Python:** her yazılabilir tabloya `recorded_by_id`,
  `recorded_by_name`, `recorded_at`. `_ensure_column` ile güvenli göç.
  `tested_by` serbest metni yerini bunlara bırakır.
  Geçersiz işaretleme de kim yaptığını kaydeder (`voided_by`).
* **React:** giriş ekranı (sicil no ile personel seçimi), üst çubukta
  aktif kullanıcı, her yazma isteğinde kimlik başlığı, kayıtların yanında
  "kim girdi" bilgisi.
* Arayüzde açık uyarı: *"Bu bir güvenlik katmanı değildir; amaç
  izlenebilirliktir."*

**Öğrenilecek kavramlar:** HTTP başlığı ile bağlam taşıma, servisler arası
referans (Python .NET'in personel kaydını okur ama saklamaz), anlık
görüntü (snapshot) vs referans tartışması.

### 9.0b — PIN, oturum ve yetki · **.NET** ⭐ 9.0'ın devamı

* `Technician`'a `PinHash`, `PinSalt`, `FailedAttempts`, `LockedUntil`.
* `PinHasher`: PBKDF2, kişiye özel tuz, sabit iterasyon.
* `POST /auth/login` (sicil + PIN) → oturum belirteci + rol.
* `Session` varlığı: belirteç, personel, oluşma/bitiş zamanı.
* `POST /auth/logout`, `GET /auth/me`.
* Yazma uç noktalarında belirteç zorunlu; bazılarında rol kontrolü.
* Kilitleme: 5 yanlış deneme → 15 dakika.

**Öğrenilecek kavramlar:** özetleme (hashing) vs şifreleme farkı, tuz
(salt) neden gerekli, ara katman (middleware), `IHostedService` ile süresi
dolmuş oturumların temizlenmesi.

### 9.0c — Kimlik kayıtlara işlensin · **Python**

Her yazılabilir tabloya `recorded_by_id` (sicil), `recorded_by_name`,
`recorded_at`. Geçersiz işaretleme de `voided_by` taşır. Python, gelen
belirteci .NET'e doğrulatır (kimlik tek yerde kalır).

### 9.0d — Giriş ekranı ve personel ekranı · **React**

* Giriş: sicil + PIN. Kilitlenme ve hatalı deneme geri bildirimi.
* Üst çubukta aktif kullanıcı + rol + çıkış.
* **Personel ekranı** (.NET kayıtlarının görünür olduğu yer): sicil, ad,
  rol, uzmanlık, bölge, kapasite, açık iş yükü.
* Her kaydın yanında "kim girdi, ne zaman".
* Görünür uyarı: hangi güvenlik önlemleri var, hangileri yok.

### 9.1 — Bulgular iş emrine dönsün · **.NET** ⭐ en yüksek öncelik

Python `/fleet/overview` zaten sağlık endeksi, yağ, elektriksel ve kağıt
özetlerini taşıyor; .NET bunları okumuyor. Yapılacak:

* `TransformerRisk` modeline yeni alanlar (health_score, electrical_overall,
  paper band, oil overall).
* `WorkOrderPlanner`'a yeni kurallar:
  * `electrical-fault` → hüküm *kötü* → **3 gün** (spir kaybı D2 kadar acil)
  * `data-suspect` → ölçüm şüpheli → **7 gün, Sampling türü** (testi tekrarla)
  * `wet-insulation` → PI < 1.5 → 14 gün
  * `paper-end-of-life` → tüketilen ömür > %80 → **Replacement türü**, 180 gün
  * `health-critical` → endeks < 30 → 7 gün
* `WorkOrderKind`'a `Test` (elektriksel test) eklenebilir.
* Testler: her kural + idempotens.

**Neden ilk?** Sistemin bildiği ama söylemediği her şey burada eyleme
dönüşüyor. Bildirim de, yönetici ekranı da bunun üstüne kurulacak.

### 9.2 — Bildirim / ticket altyapısı · **.NET**

* `Notification` varlığı: iş emri, alıcı (teknisyen/rol), kanal, içerik,
  `created_at`, `sent_at`, `read_at`.
* Kural: iş emri **oluştuğunda** ve **aciliyeti yükseldiğinde** bildirim
  üretilir (`WorkOrderTransitions` ve `EscalateAsync` zaten var).
* Gönderim `INotificationSender` arayüzü; demo `LoggingSender`.
* Arayüzde "Bildirimler" paneli: kime ne zaman ne gitti.

**Öğrenilecek .NET kavramları:** arayüz (interface) ve bağımlılık ters
çevirme, arka plan servisi (`BackgroundService`/`IHostedService`).

### 9.3 — Yönetici ekranı · **React**

Kategoriler:
1. **Filo sağlığı** — bant dağılımı, ortalama, eğilim
2. **Varlık sınıfı kırılımı** — LPT/MPT/SPT × sağlık bandı matrisi
3. **Veri kapsaması** — kaç varlığın kaç boyutu ölçülü (Testler ekranının özeti)
4. **İş yükü** — açık/geciken iş emirleri, teknisyen doluluğu (.NET'ten)
5. **Yenileme adayları** — `renewal_priority` sıralı liste

Kural: her karo bir **soruya** cevap versin ve tıklanınca detayına gitsin.

### 9.35 — Varlık yaşam döngüsü · **Python + React**

Bölüm 4b'deki boşluk. `transformers` tablosuna `lifecycle_status` +
geçiş geçmişi. Kurallı durum makinesi. Devreye alma öncesi ölçütlerin
farklılaşması; numune gecikmesi kuralının yalnızca "Devrede" ünitelere
uygulanması. Yedek ünite görünürlüğü.

### 9.4 — Bileşen izleme: buşing ve kademe değiştirici · **Python**

* Buşing: tan δ, kapasitans (C1), yağ seviyesi, termografi.
* OLTC: işletme sayacı, son revizyon, kontak direnci, yağ durumu.
* İkisi de sağlık endeksine **beşinci ve altıncı boyut** olarak girer.
* Literatürdeki HI bileşenlerinin en önemli eksiklerinden biri kapanır.

### 9.5 — Fiziksel gözlem kontrol listesi · **Python + React** 💡 ucuz kazanç

Cihaz gerektirmez: kaçak, korozyon, silikajel rengi, radyatör tıkanıklığı,
gürültü, koruma cihazı durumu. Teknisyen sahadayken doldurur. Endüstriyel
HI modellerinin gerçek bileşenlerinden biri ve **emek/getiri oranı en
yüksek** madde.

### 9.6 — Trafo şeması · **React**

9.4 bittikten sonra anlamlı: sargılar, buşingler, OLTC, radyatörler
üzerinde bileşen durumu. Boş bir çizim olmaması için veri önce gelmeli.

### 9.7 — Arayüz cilası: kurumsal görünüm · **React**

Kullanıcının bekleyen isteği (.NET/kurumsal platform havası). Yönetici
ekranıyla birlikte yapılması mantıklı — yeni ekran zaten yeni bir görsel
dil gerektirecek.

---

## 6. Yapılmayacaklar ve nedenleri

| Fikir | Neden hayır |
|---|---|
| Dijital ikiz | Fiziksel/termal model ister; DGA verisinden kurulamaz |
| Gerçek e-posta/SMS | Kimlik bilgisi + dış servis; demo kapsamı dışı. Outbox deseni yeterli |
| Derin öğrenme | Faz 6.9'da ölçüldü: öğrenme eğrisi hâlâ yükseliyor, sorun model değil veri |
| Yaşı ayrı HI boyutu yapmak | Kağıt DP'sinin içinde zaten sayılıyor; çift sayım olur |
| Kayıt silme | Denetim izi; "geçersiz işaretle" doğru çözüm (Faz 8.6'da karar verildi) |
| HTTPS/TLS, MFA, CSRF sertleştirmesi | Demo localhost'ta. Gerçek kurulumda TLS ŞART — belirteç aksi halde ağda açık gider. Bu sınır arayüzde yazılı |

---

## 7. Önerilen sıra (özet)

```
9.0a Personel + sicil          (.NET)     ✅ TAMAM
9.0b PIN + oturum + yetki      (.NET)     ✅ TAMAM
9.0c Kimlik kayıtlara işlensin (Python)   ✅ TAMAM
9.0d Giriş + personel ekranı   (React)    ✅ TAMAM
9.1  Bulgular → iş emri        (.NET)     ✅ TAMAM
9.2  Bildirim / ticket         (.NET)     ✅ TAMAM
9.3  Yönetici ekranı           (React)    ⭐ ŞİMDİ
9.35 Varlık yaşam döngüsü      (Python+React)
9.5  Fiziksel gözlem           (Python)   💡 ucuz kazanç
9.4  Buşing + OLTC             (Python)
9.6  Trafo şeması              (React)
9.7  Kurumsal görünüm cilası   (React)
```

**9.0 neden ertelenemez:** kimlik, veri modelinin parçasıdır. Bugün
girilen her test kaydı, yarın "bunu kim girdi?" sorusuna cevap veremeyecek
bir kayıt olarak kalıcı hâle geliyor. Bildirim ve iş emri ise sonradan
eklenebilir — geçmişi bozmaz.

**9.1 ve 9.2 .NET tarafında**, yani kullanıcının öğrenmek istediği alanda —
ve yeni kavramlar getiriyor (interface, dependency inversion, background
service). Faz 7'deki öğrenme temposuyla devam edilebilir.

---

## Kaynaklar

* [GE Vernova — Asset Performance Management](https://www.gevernova.com/software/products/asset-performance-management)
* [GE Vernova — GridBeats™ APM](https://www.gevernova.com/grid-solutions/automation/gridbeats-apm)
* [GE Vernova — Asset Strategy Management](https://www.gevernova.com/software/products/asset-performance-management/asset-strategy-management)
* [Health Index Assessment for Power Transformer Strategic Asset Management (Sunderland)](https://sure.sunderland.ac.uk/id/eprint/17347/1/Wthout%20publisher%20template%202023_IJSEAM-143749%20Authors%20Original.pdf)
* [TJ|H2b — Transformer Tier 1 Asset Health Index Scoring](https://tjh2b.com/white-papers/transformer-tier-1-asset-health-index-scoring/)
* [Review of Transformer Health Index from the Perspective of Survivability and Condition Assessment](https://www.researchgate.net/publication/371043943_Review_of_Transformer_Health_Index_from_the_Perspective_of_Survivability_and_Condition_Assessment)
