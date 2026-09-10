# Faz 8 — Platform genişleme planı

> **Tespit:** Proje şu an trafo izlemenin **yedi modülünden birini** yapıyor.
> Bu belge kalan altısını ve GE Vernova bağlamını inceleyip genişleme
> önceliklerini sıralıyor.

## GE Vernova ne yapıyor? (araştırma bulgusu)

GE Vernova, trafo izleme pazarının lider oyuncularından. Ürün hattı:

* **Güç trafoları** — 5 MVA'dan çok büyük güçlere, 1200 kV AC / ±1100 kV DC'ye
  kadar. Konvansiyonel, faz kaydırıcı, SVC, HVDC, düşük bakımlı, yeşil trafolar.
* **Endüstriyel özel trafolar** — redresör trafoları (elektroliz), ark ocağı
  (EAF) trafoları (300 MVA'ya kadar).
* **İzleme ve tanı** — tek/çok gazlı DGA monitörleri, **MS 3000** çevrimiçi
  izleme ve uzman sistemi.
* **Servisler** — tüm yaşam döngüsü boyunca saha uzmanlığı, durum
  değerlendirmesi, onarım ve modernizasyon.

**MS 3000'in kapsamı** (bizim için yol haritası niteliğinde): DGA monitörü +
diğer trafo sensörlerine bağlanarak **aktif kısım, buşingler, soğutma
sistemi, kademe değiştirici (OLTC)**, geçici aşırı gerilimler ve **kısmi
deşarj** izleme.

## Endüstri standardı: yedi izleme modülü

Tam kapsamlı bir trafo durum izleme sistemi şu modüllerden oluşur:

| # | Modül | Bizde var mı? |
|---|---|---|
| 1 | **Çevrimiçi DGA** (çözünmüş gaz analizi) | ✅ **var** |
| 2 | Kısmi deşarj (PD) izleme | ❌ |
| 3 | Fiber optik sıcaklık (sıcak nokta) | ❌ |
| 4 | Buşing izleme (kapasitans + tan δ) | ❌ |
| 5 | OLTC (kademe değiştirici) izleme | ❌ |
| 6 | Yağdaki nem izleme | ❌ |
| 7 | Titreşim izleme | ❌ |

Ayrıca hepsini tek skora indiren **Sağlık Endeksi (Health Index)** katmanı
ve **IEEE C57.91 / IEC 60076-7** termal yaşlanma modeli var.

**Bu tespit projenin en güçlü genişleme argümanı:** "DGA yaptım" demek yerine
"trafo izlemenin yedi modülünden şu üçünü uçtan uca kurdum, kalanların
mimari yerini açtım" demek çok daha olgun bir anlatı.

---

## Önerilen genişleme adımları

### 8.1 — Trafo künyesi (nameplate) ⭐ temel

Şu an bir trafo hakkında sadece `id, name, location, asset_class, mva`
biliyoruz. Gerçek bir varlık kaydı çok daha zengindir ve **sonraki her
modül buna dayanır**:

| Alan | Neden gerekli |
|---|---|
| Üretici, seri no, üretim yılı | Kimlik, garanti, filo istatistiği |
| Devreye alma tarihi | Yaş hesabı, yaşlanma modeli |
| Anma gücü (MVA), YG/AG gerilim (kV) | Yük hesabı, sınıflandırma |
| Bağlantı grubu (Dyn11 vb.) | **Sarım oranı testinin beklenen değeri** |
| Soğutma tipi (ONAN/ONAF/OFAF/ODAF) | Termal model parametreleri |
| Yağ hacmi (litre) | Gaz ppm → mutlak gaz miktarı dönüşümü |
| Sargı malzemesi (Cu/Al), yalıtım tipi | Yaşlanma davranışı |
| Kademe değiştirici tipi ve aralığı | OLTC izleme, TTR beklenen değerleri |
| Sıcak nokta / yağ sıcaklığı anma değerleri | IEEE C57.91 girdileri |

**Neden ilk sırada:** Sarım oranı testinin "doğru" değeri bağlantı grubundan
ve kademe pozisyonundan gelir. Termal model soğutma tipini ister. Yaşlanma
modeli devreye alma tarihini ister. Künye olmadan diğer modüller havada kalır.

### 8.2 — Yağ kalitesi ve kağıt yaşlanması ⭐ en yüksek teknik derinlik

DGA, **yağdaki arızayı** söyler. Ama trafonun ömrünü belirleyen şey
**kağıt yalıtımın** bozunmasıdır ve DGA bunu göstermez. Aynı yağ
numunesinden ölçülen farklı parametreler:

| Test | Standart | Ne söyler |
|---|---|---|
| Nem (ppm / % bağıl doygunluk) | IEC 60814 | Yalıtım nemlenmesi, delinme riski |
| Delinme gerilimi (BDV, kV) | IEC 60156 | Yağın dielektrik dayanımı |
| Asitlik (mg KOH/g) | IEC 62021 | Yağ oksidasyonu, tortu riski |
| Arayüzey gerilimi (mN/m) | ASTM D971 | Yağ bozunma ürünleri |
| **Furan (2-FAL, mg/L)** | IEC 61198 | **Kağıt bozunması** |

**Furan → DP → kalan ömür.** Kağıdın polimerizasyon derecesi (DP) yeni
trafoda ~1000-1200'dür; 200'e düştüğünde kağıt mekanik dayanımını yitirmiş
sayılır. DP'yi doğrudan ölçmek için trafodan kağıt örneği almak gerekir —
yani trafoyu açmak. Ama yağdaki furan konsantrasyonundan tahmin edilebilir.
**Chendong bağıntısı:**

```
log₁₀(2FAL) = 1.51 − 0.0035 × DP
```

Bu tek formül projeye yeni bir boyut katar: **"bu trafo ne kadar yaşadı,
ne kadar ömrü kaldı?"** — DGA'nın cevaplayamadığı soru.

> Not: Chendong modeli kağıt tipine göre sınırlıdır (termal yükseltilmiş
> kağıtta sapar). Bunu belgelemek, körü körüne uygulamaktan iyidir —
> projenin "sınırını bilen sistem" çizgisine de uyar.

### 8.3 — Elektriksel testler (çevrimdışı) ⭐ senin önerin

Yağ analizi trafonun **içinde ne olduğunu** söyler; elektriksel testler
**sargıların fiziksel bütünlüğünü** söyler. Bunlar periyodik bakımda,
trafo devre dışıyken yapılır:

| Test | Ne bulur | Kabul ölçütü (tipik) |
|---|---|---|
| **Sarım oranı (TTR)** | Kısa devre olmuş sarım, yanlış kademe | Anma oranından sapma **< %0.5** |
| Sargı direnci | Gevşek bağlantı, kopmuş tel, OLTC kontak sorunu | Fazlar arası fark < %2-3 |
| Yalıtım direnci / PI | Nem, kirlenme | PI > 2.0 iyi, < 1.0 kötü |
| Tan δ / güç faktörü | Yalıtım bozunması, buşing sorunu | < %0.5 (yeni), artış eğilimi kritik |
| Mıknatıslanma akımı | Çekirdek sorunu, sarım kısa devresi | Fazlar arası desen tutarlılığı |
| **SFRA (frekans tepkisi)** | **Sargı deformasyonu** — kısa devre veya nakliye sonrası | Parmak izi karşılaştırması |

**Sarım oranı testi neden değerli:** Beklenen oran künyedeki gerilim
oranından ve kademe pozisyonundan hesaplanır. Yani 8.1 ile doğrudan
bağlanır ve sistem "ölçülen 20.51, beklenen 20.45, sapma %0.29 → kabul"
diyebilir. Kural tabanlı, açıklanabilir, standarda dayalı.

### 8.4 — Termal model ve ömür tüketimi (IEEE C57.91)

Yük ve ortam sıcaklığından **sıcak nokta sıcaklığı** hesaplanır; oradan
yaşlanma hızı ve tüketilen ömür çıkar. Standardın temel kuralı:

* Referans sıcak nokta **110 °C** → normal yalıtım ömrü ≈ **180.000 saat**
* Her **+6 °C**, yaşlanma hızını yaklaşık **iki katına** çıkarır

Bu modül projeye **zaman boyutu** katar: "bu trafo bugüne kadar ömrünün
%37'sini tüketti" gibi bir sayı üretir. `services/trend.py` altyapısı bunun
için hazır.

### 8.5 — Sağlık Endeksi (Health Index) ⭐ taç modül

Endüstride yapılan iş: DGA + yağ kalitesi + nem + PD + buşing tan δ + OLTC
aşınması + termal geçmiş → **tek normalize skor (0-100)**. Ağırlıklı
birleştirme.

Bunun projedeki değeri: şu an her boyut ayrı ayrı duruyor. Sağlık Endeksi
onları **tek bir karara** indirger ve filo sıralaması gerçekten
"hangi trafoya önce bakayım?" sorusunu cevaplar. Mevcut öncelik skorumuz
(kondisyon × varlık ağırlığı) bunun basit hâli; Sağlık Endeksi genelleştirir.

### 8.6 — Veri giriş ekranı ⭐ senin önerin

Şu an tek bir gaz giriş formu var. Genişleyen platform için gereken:

* **Sekmeli test giriş formu** — DGA / yağ kalitesi / elektriksel test /
  yük kaydı, her biri kendi alanlarıyla ve birim etiketleriyle
* **Anında doğrulama** — fiziksel olarak imkânsız değerler (negatif ppm,
  %101 nem) girilirken uyarı
* **Künye düzenleme ekranı** — trafo ekleme/güncelleme
* **Toplu içe aktarma** — CSV/Excel'den ölçüm yükleme (laboratuvarlar
  sonuçları böyle gönderir)
* **Test geçmişi tablosu** — trafo başına tüm test tipleri tek zaman
  çizelgesinde

### 8.7 — Bileşen izleme (MS 3000 kapsamı)

Buşing (kapasitans + tan δ trendi), OLTC (kademe sayacı, motor akımı,
kontak aşınması), soğutma sistemi (fan/pompa durumu, verim), kısmi deşarj.
Bunlar sensör verisi ister; simüle edilebilir ama en az fiziksel temele
sahip olanlar.

---

## Önerilen sıra ve gerekçe

| Sıra | Adım | Neden bu sırada | Emek |
|---|---|---|---|
| 1 | **8.1 Künye** | Diğer her şeyin dayanağı | Düşük |
| 2 | **8.6 Veri giriş (künye + DGA)** | Künyeyi kullanılabilir kılar | Orta |
| 3 | **8.2 Yağ kalitesi + furan/DP** | En yüksek teknik derinlik/emek oranı; yeni bir soru cevaplar | Orta |
| 4 | **8.3 Elektriksel testler (TTR öncelikli)** | Künyeye bağlanır, kural tabanlı ve açıklanabilir | Orta |
| 5 | **8.5 Sağlık Endeksi** | Ancak birden çok boyut varken anlamlı | Orta |
| 6 | **8.4 Termal model** | Yük verisi üretmeyi gerektirir | Orta-yüksek |
| 7 | **8.7 Bileşen izleme** | En az fiziksel temele sahip, en çok simülasyon | Yüksek |

## Mimari yerleşim

| Ne | Nerede | Neden |
|---|---|---|
| Künye, test sonuçları, ML | **Python** | Varlık ve ölçüm alanı zaten orada; `asset_class`/`mva` de öyle |
| Sağlık Endeksi hesabı | **Python** | Ölçüm verisine yakın olmalı |
| İş emri, teknisyen, planlama | **.NET** | İş akışı ve kurumsal mantık |
| Test giriş ekranları | **React** | — |

Bu ayrım Faz 7'de koyduğumuz kuralı bozmaz: Python ölçer ve değerlendirir,
.NET karar verir ve planlar.

---

## Veri politikası (değişmiyor)

Tüm yeni test verileri de **sentetik** üretilecek, fiziksel olarak tutarlı
aralıklarda ve standartlara dayalı. Faz 6'da öğrendiğimiz ders geçerli:
üretecin gerçekliği **ölçülmeden** iddia edilmez.
