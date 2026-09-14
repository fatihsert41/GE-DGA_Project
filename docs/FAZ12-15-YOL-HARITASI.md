# Faz 12–15 Yol Haritası — Mühendislik, Doküman, Stok, Akıllı Cihazlar

> 14 Eylül 2026. Kullanıcının dört fikri üzerine hazırlandı:
> **stok kontrolü** (büyük trafoların parçaları, stok personeli),
> **trafolardaki yapay zekâ kullanan cihazların durumu**,
> **Mühendislik departmanı**, **design dosyalarını yükleme ve trafo
> içinde görüntüleme**.
>
> ⚠ Veri politikası değişmiyor: gerçek/kurumsal veri yok. Parça
> kataloğu, stok hareketleri ve cihaz telemetrisi de sentetik üretilecek.
> Aşağıda adı geçen GE Vernova ürünleri yalnızca **alan bağlamı** için
> anılıyor; bu projede gerçek bir entegrasyon yok ve iddia edilmeyecek.

---

## Önerilen sıra ve nedeni

| Faz | Konu | Neden bu sırada |
|---|---|---|
| **12** | Mühendislik departmanı + onay akışı | En küçük adım, mevcut yetki sistemine oturuyor. Faz 6'nın en büyük bulgusunu ("en yüksek getiri: daha çok **gerçek, etiketli** veri") ürüne bağlıyor. |
| **13** | Doküman ve design yönetimi | **Dosya altyapısı** kuruyor. Stok (parça teknik föyü) ve cihazlar (kalibrasyon sertifikası) bu altyapıyı tekrar kullanacak. |
| **14** | Stok ve yedek parça yönetimi | İş emirleriyle birleşince sistemi gerçek bir ERP modülüne çeviriyor: "iş emri açıldı ama parça depoda yok". |
| **15** | Akıllı cihaz (IED) filosu ve sensör sağlığı | En karmaşığı. Önceki üçünü kullanıyor: cihazın dokümanı (13), yedeği (14), verisini onaylayan mühendis (12). |

Her faz sonunda: testler, belgeler, kullanıcı onayıyla push.

---

## Faz 12 — Mühendislik Departmanı ve Onay Akışı

### Fikir
Şu an bir test girildiği anda sağlık endeksini ve iş emri önerilerini
etkiliyor. Gerçek işletmelerde kritik bir sonuç **ikinci bir göz**
(mühendis onayı) olmadan karar üretmez. Mühendislik bu kararların sahibi.

### Mühendisliğin yapacakları
1. **Test onay kuyruğu (MH01).** Sınır dışı çıkan test sonuçları
   (ör. TTR sapması, BDV düşük) "onay bekliyor" durumuna düşer. Mühendis
   onaylar, reddeder ya da "tekrar ölçülsün" der. **Dört göz ilkesi:**
   testi giren kişi kendi testini onaylayamaz.
2. **Model inceleme kuyruğu (MH02).** Faz 6.5'te model emin olmadığında
   `needs_review` işareti koyuyor, ama bu işaretin sonrası yok. Mühendis
   gerçek arıza tipini seçer ve bu karar **etiketli veri** olarak
   saklanır. Faz 6.9'daki öğrenme eğrisi hâlâ yükseliyordu, yani her
   mühendis kararı modeli iyileştirebilecek bir veri. Bu fazın en özgün
   katkısı bu.
3. **Varlığa özel eşik (MH03).** "TR-07 eski tasarım, nem sınırı 20 değil
   25 ppm" gibi istisnalar. Gerekçe **zorunlu**, süresi ve onaylayan
   kişi kayıtlı. Sessiz eşik değişikliği yasak.
4. **Kök neden analizi (RCA) kaydı (MH04).** Kapanan kritik iş emrine
   bağlı: bulgu → neden → alınan önlem. Aynı arıza tekrarladığında geçmiş
   RCA'lar önerilir.

### Teknik tasarım
- **Departman:** `Engineering` + yetkiler `engineering.approve`,
  `engineering.review_model`, `engineering.limits`, `engineering.rca`.
  Yönetim hepsini alır (mevcut kural kendiliğinden işliyor).
- **Onay durumu nerede tutulur?** Test kayıtları Python'da, onay da
  **Python'da** tutulmalı (kaydın yanında). .NET'e taşımak iki
  veritabanında iki gerçek yaratırdı.
- **Sağlık endeksine etkisi:** "onay bekliyor" durumundaki sınır dışı
  test hesaba **girer ama işaretlenir** ("doğrulanmamış veri"). Onay
  beklerken kritik bir bulguyu yok saymak tehlikeli olurdu.
- **Model kararı veri seti:** `expert_labels` tablosu (ölçüm id, model
  tahmini, mühendis kararı, gerekçe). Eğitim betiğine
  `--include-expert-labels` bayrağı. ⚠ Sentetik veriyle karıştırılırken
  ağırlıklandırma ölçülerek seçilmeli (Faz 6.3 dersi: "karma eğitim saf
  gerçeği geçmedi").

### Testler
Dört göz kuralı; gerekçesiz eşik değişikliği reddi; onay bekleyen testin
endekse işaretli girmesi; mühendis etiketinin eğitim setine düşmesi.

### Yapma
Her testi onaya sokma: kuyruk şişer ve onay anlamsızlaşır ("damga
yorgunluğu"). Yalnızca **sınır dışı** sonuçlar onaya gider.

---

## Faz 13 — Doküman ve Design Yönetimi

### Fikir
Trafonun detayına girildiğinde yeni bir **"Dokümanlar"** sekmesi: genel
görünüş, kesit çizimi, bağlantı şeması, anma plakası fotoğrafı, fabrika
kabul testi (FAT) ve saha kabul testi (SAT) raporları. Dosya yüklenir,
tarayıcıda görüntülenir, revizyonları izlenir.

### Özellikler
1. **Doküman türleri:** Genel görünüş · Kesit · Bağlantı şeması ·
   Anma plakası · FAT/SAT raporu · Kalibrasyon sertifikası · Diğer.
2. **Revizyon kontrolü:** Rev A → B → C. Eski revizyon **silinmez**,
   "yerini aldı" olarak işaretlenir. Faz 8.6'daki "kayıt silinmez"
   ilkesinin dosya karşılığı: sahadaki ekip hangi revizyona göre
   çalıştığını sonradan kanıtlayabilmeli.
3. **Görüntüleyici (DK01):**
   - PDF → tarayıcının kendi PDF görüntüleyicisi. Harici kütüphane
     gerekmez.
   - PNG/JPG → yakınlaştırma ve kaydırma.
   - DWG/DXF → tarayıcı doğrudan gösteremez. Önerim: yüklemede **PDF
     çıktısı da istenir**, DWG arşiv için saklanır.
4. **Şemaya bağlama:** Faz 9.6'daki trafo şemasında bir parçaya (ör. B
   buşingi) tıklayınca o parçanın çizim sayfası açılır. Yükleme sırasında
   "bu doküman hangi parçayla ilgili" etiketi seçilir.
5. **Arama:** tür, trafo, revizyon ve yükleyene göre filo geneli liste.

### Teknik tasarım
- **Nerede?** .NET bakım servisinde (kurumsal kayıt), dosyalar diskte
  `storage/documents/<trafo>/<sha256>` altında, veritabanında yalnızca
  üst veri.
- **Güvenlik (baştan tasarlanmalı):**
  - **Boyut sınırı** (ör. 50 MB).
  - **Uzantıya değil içeriğe göre tür kontrolü:** PDF dosyası `%PDF` ile
    başlar. Uzantıyı değiştirilmiş bir dosya reddedilir.
  - **Dosya adı hiçbir zaman yol olarak kullanılmaz:** `../../` saldırısı
    engellenir, dosya SHA-256 adıyla saklanır.
  - İndirmede `Content-Disposition` ve `X-Content-Type-Options: nosniff`.
  - Virüs taraması demo kapsamı dışında; belgede açıkça yazılacak.
- **Yetkiler:** `documents.view` (herkes), `documents.upload`
  (Mühendislik + Yönetim), `documents.supersede` (Mühendislik).
- **Aynı dosya iki kez yüklenirse** SHA-256 aynıdır: tekrar saklanmaz,
  mevcut kayda bağlanır.

### Testler
Uzantısı değiştirilmiş dosya reddi; yol saldırısı; revizyon zinciri
(eski revizyon görünür kalır); yetkisiz yükleme 403; aynı içerik tek
kopya.

### Yapma
Dosyaları veritabanına BLOB olarak koyma: yedekleme ve sorgu performansı
bozulur. Dosyaları Python servisine koyma: doküman kurumsal bir kayıttır,
ölçüm değil.

---

## Faz 14 — Stok ve Yedek Parça Yönetimi

### Fikir
Büyük güç trafolarında (LPT) asıl risk parça **teslim süresidir**. Bir
buşing ya da kademe değiştirici aylarca, komple bir LPT yıllarca
beklenebilir. "Arıza çıktı, parça depoda var mı, yoksa ne zaman gelir?"
sorusu bakım kararını doğrudan belirler.

### Kapsam
1. **Parça kataloğu (ST01):** buşing (YG/AG), kademe değiştirici (OLTC)
   ve kontakları, radyatör, soğutma fanı, yağ pompası, Buchholz rölesi,
   basınç tahliye valfi, silikajel kartuşu, conta takımı, sıcaklık
   göstergeleri (OTI/WTI), trafo yağı (litre), online DGA monitörü.
   Alanlar: parça no, üretici, teknik özellik (gerilim sınıfı, akım,
   BIL), birim, **teslim süresi**, **raf ömrü** (conta ve silikajel
   eskir).
2. **Uyumluluk (malzeme listesi):** hangi parça hangi trafoya uyar?
   Künyeden türetilir (ör. 154 kV YG buşingi 34.5 kV'luk bir trafoya
   uymaz). Faz 8.1'deki künye burada tekrar karşılığını veriyor.
3. **Depolar ve stok (ST02):** depo, raf, miktar, **rezerve** miktar
   (bir iş emrine ayrılmış), seri numarası (buşing gibi izlenebilir
   parçalarda tek tek).
4. **Stok hareketleri (ST03):** giriş, çıkış (iş emrine), transfer,
   sayım farkı. Hareket **silinmez**, ters kayıtla düzeltilir (muhasebe
   ilkesi).
5. **Kritik yedek kuralı (hesap, tahmin değil):**
   ```
   Yeniden sipariş noktası = teslim süresindeki beklenen kullanım + emniyet stoğu
   Kritiklik = parçanın uyduğu varlıkların sınıf ağırlığı (LPT 1.0 · MPT 0.7 · SPT 0.45)
   ```
   Tek bir LPT'yi durduracak ve teslim süresi uzun olan parça, stokta
   sıfırsa **kırmızı alarm**. Faz 6.6'daki öncelik formülünün tekrar
   kullanımı.
6. **İş emriyle bağ:** iş emri açılınca gerekli parçalar önerilir ve
   rezerve edilir. Parça yoksa iş emri "parça bekliyor" durumuna geçer
   ve planlama bundan haberdar olur.
7. **Sayım (ST04):** stok personeli sayım listesini doldurur; sistem
   farkı gösterir, yönetim onaylar.
8. **Bildirim entegrasyonu:** asgari stok altına düşme ve raf ömrü
   dolması Faz 9.2'deki outbox üzerinden bildirim üretir.

### Teknik tasarım
- **Nerede?** .NET (işlemsel ERP verisi, iş emirleriyle aynı yerde).
- **Departman:** `Warehouse` (Stok Kontrol) + yetkiler `stock.view`,
  `stock.move`, `stock.count`, `stock.catalog`. Planlama rezerve eder
  ama stok hareketi yapamaz; stok personeli hareket yapar ama iş emri
  açamaz (görevler ayrılığı).
- **Eşzamanlılık:** aynı son parçayı iki iş emri aynı anda rezerve
  etmemeli. Satır sürüm alanıyla iyimser kilit (EF Core `RowVersion`).
  Faz 7'deki sıra numarası çakışmasının akrabası.

### Testler
Negatif stok engeli; eşzamanlı rezervasyon; uyumsuz parçanın önerilmemesi;
yeniden sipariş noktası hesabı; raf ömrü dolan parçanın "kullanılamaz"
sayılması; sayım farkının onaysız stoğa işlememesi.

### Yapma
Talep tahmini için ML kullanma. Arıza nadir olduğu için veri çok az;
teslim süresi + emniyet stoğu kuralı hem daha dürüst hem daha
açıklanabilir. (Faz 6.4 dersi: az veriyle karmaşık model güven vermez.)

---

## Faz 15 — Akıllı Cihaz (IED) Filosu ve Sensör Sağlığı

### Fikir
Modern trafolarda sürekli ölçüm yapan cihazlar var: online DGA
monitörleri (GE Vernova'nın Kelman ürün ailesi bu sınıfta), buşing
izleme, kademe değiştirici izleme, fiber optik sıcaklık, kısmi deşarj
sensörü. Bunlar bir **filo** olarak yönetilmeli. Sistemin sorması
gereken soru: **"Bu cihazın söylediğine güvenebilir miyim?"** Arızalı bir
sensör, sağlam trafoyu arızalı gösterir.

### Kapsam
1. **Cihaz kaydı (CH01):** tür, model, seri no, bağlı olduğu trafo,
   montaj tarihi, yazılım (firmware) sürümü, **üzerinde çalışan analiz
   modeli sürümü**, iletişim yöntemi.
2. **Cihaz durumu (CH02):** son veri zamanı (kalp atışı), iletişim
   kopukluğu, **kalibrasyon tarihi geçti mi**, pil ya da taşıyıcı gaz
   seviyesi (DGA monitörleri), hata kodları.
3. **Veri kalitesi analizi (bu fazın ML katkısı, Python'da):**
   - **Donmuş sinyal:** değer günlerdir hiç değişmiyor.
   - **Fiziksel olmayan sıçrama:** H2 bir saatte 10 katına çıkıp geri
     inmiş (arıza değil, iletişim hatası olabilir).
   - **Laboratuvar–sensör sapması:** aynı gün alınan laboratuvar DGA'sı
     ile online monitör karşılaştırılır; sistematik fark **kalibrasyon
     kayması** demektir. Faz 5'teki trend altyapısı yeniden kullanılır.
   - Sonuç: her cihaz için "veri güvenilir / şüpheli / kullanılamaz".
     Şüpheli cihazın verisi sağlık endeksine **girmez** ve bunu açıkça
     söyler (Faz 8.5'teki "bilinmeyen boyut sağlıklı sayılmaz" ilkesi).
4. **Model sürüm takibi:** hangi cihazda hangi model sürümü çalışıyor?
   Eski sürümde kalan cihazlar listelenir. Bu, küçük ölçekli bir MLOps.
   `model.joblib` içindeki `model_id` alanı (Faz 6'da eklendi) burada
   kullanılır.
5. **Kalibrasyon ve bakım:** kalibrasyonu yaklaşan cihaz için otomatik
   iş emri önerisi (Faz 7.5 planlayıcısına yeni kural) ve sertifika
   dosyası (Faz 13).
6. **Yedek cihaz:** arızalı monitör için stokta yedek var mı? (Faz 14)

### Teknik tasarım
- **Cihaz kaydı ve durumu** → .NET (varlık kaydı, iş emri bağlantısı).
- **Telemetri ve veri kalitesi analizi** → Python (zaman serisi ve ML).
- **Sentetik telemetri üreteci:** `ml/synth_telemetry.py`. Senaryolar
  elle seçilir, Faz 8.6'daki gibi: TR-03'te donmuş sensör, TR-08'de
  kalibrasyonu kaymış monitör (laboratuvar DGA'sı ile uyuşmuyor),
  TR-05'te iletişim kopukluğu.
- **Departman:** mevcut Elektriksel Test ekibi cihaz bakımını üstlenebilir
  ya da ayrı bir `Instrumentation` (Enstrümantasyon) birimi açılır.
  **Kullanıcı kararı.**

### Testler
Donmuş sinyal tespiti; laboratuvar–sensör sapması eşiği; şüpheli verinin
sağlık endeksinden çıkması; kalibrasyon kuralının iş emri önerisi
üretmesi; eski model sürümündeki cihazın listelenmesi.

### Yapma
Sensör verisini doğrulamadan modele besleme. Faz 6'nın dersi: model,
verisinin kalitesi kadar iyidir, ve şu an sensör verisini denetleyen
hiçbir katman yok.

---

## Faz 13–15 boyunca ERP ekranları (işlem kodları)

| Kod | Ekran | Faz |
|---|---|---|
| MH01 | Test onay kuyruğu | 12 |
| MH02 | Model inceleme kuyruğu (uzman etiketi) | 12 |
| MH03 | Varlığa özel eşikler | 12 |
| MH04 | Kök neden analizi kayıtları | 12 |
| DK01 | Doküman arşivi (filo geneli) + trafo "Dokümanlar" sekmesi | 13 |
| ST01 | Parça kataloğu ve uyumluluk | 14 |
| ST02 | Depo stok durumu, kritik yedek alarmı | 14 |
| ST03 | Stok hareketleri | 14 |
| ST04 | Sayım | 14 |
| CH01 | Cihaz kaydı | 15 |
| CH02 | Cihaz durumu ve veri kalitesi | 15 |

Menüye yeni modüller: **Mühendislik**, **Doküman Yönetimi**,
**Malzeme Yönetimi**, **Cihaz Yönetimi**.

---

## Ortak altyapı borçları (bu fazlarla birlikte ele alınmalı)

- **Denetim izi (audit log):** kim, ne zaman, neyi değiştirdi. Stok ve
  onay akışıyla zorunlu hâle geliyor.
- **SQLite sınırı:** dosya üst verisi, stok hareketleri ve eşzamanlı
  rezervasyon PostgreSQL'e geçişi gündeme getirecek. Yol haritasındaki
  "Faz 8+ PostgreSQL" maddesi en geç Faz 14'te gerekli olur.
- **Yedekleme:** dokümanlar diskte duracak; veritabanıyla birlikte
  yedeklenmeli.

---

## Başlamadan önce kullanıcıya sorulacaklar

1. **Mühendislik** mevcut personelden mi oluşacak (ör. Elif Demir veya
   Selin Öztürk taşınır mı), yoksa yeni demo personel mi eklenecek?
2. Design dosyaları için **DWG** desteği şart mı, yoksa PDF + görsel
   yeterli mi?
3. Kaç **depo** olacak (merkez depo + saha depoları)?
4. Akıllı cihaz bakımı hangi departmanın işi: Elektriksel Test mi, yeni
   bir Enstrümantasyon birimi mi?
5. Faz sırası önerildiği gibi mi (12 → 13 → 14 → 15)?
