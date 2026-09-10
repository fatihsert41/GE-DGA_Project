# Faz 6 — Sentetik veriyle eğitilen model gerçek veride ne yapıyor?

> Üretim: `cd backend; python -m app.ml.evaluate_real --real data/dga_china_2321.xlsx --bench data/dga_bench_589.xlsx`
> Ham çıktı: `backend/artifacts/real_data_report.json`

## Veri

| | Kaynak | Satır (temiz) | Sınıflar |
|---|---|---|---|
| Ana gerçek veri | Çin şebeke verisi + IEC TC 10 + literatür derlemesi ([GitHub: alan-456/transformer-fault-dataset](https://github.com/alan-456/transformer-fault-dataset)) | 2321 → **1972** | 7'sinin hepsi |
| Bağımsız ikinci test | Aynı deponun 589 satırlık ikinci dosyası | 589 → **455** | Normal hariç 6 |
| Sentetik | `app/ml/synth.py`, IEC 60599 imzaları | 400–4000 (deneye göre) | 7 |

Etiketler Çince (`局部放电` = kısmi deşarj, `高温过热` = yüksek sıcaklıkta aşırı
ısınma …) ve `app/ml/real_data.py` içinde bizim yedi sınıfımıza eşleniyor.

### Veri hijyeni — sonuçların sahte çıkmaması için yapılanlar

1. **349 birebir tekrar eden satır atıldı** (2321 → 1972). Derleme veri
   setlerinde aynı vaka birden çok kaynaktan girer. Temizlenmeseydi rastgele
   bölmede aynı ölçüm hem eğitime hem teste düşer, model ezberler ve doğruluk
   yapay olarak şişerdi (**veri sızıntısı**).
2. **İkinci dosyanın %22'si ana veriyle ortaktı** — 127 satır. "Bağımsız test"
   demek için bu kesişim de çıkarıldı (582 → 455).
3. Bölme **katmanlı** (stratified): her sınıfın eğitim/test oranı korunuyor.

### Gaz seti farkı (önemli)

Açık DGA veri setleri **beş gaz** içerir: `H2, CH4, C2H6, C2H4, C2H2`.
**CO ve CO2 yoktur** — bunlar kağıt yalıtımın bozunmasını gösterir, klasik
arıza veri tabanları ise yağdaki arıza tipine odaklanır. Bu yüzden tüm
karşılaştırmalar beş gazlı çekirdek özellik setinde
(`features.CORE_FEATURE_NAMES` = 5 gaz + 4 oran) yapıldı. Yedi gazlı model
(canlı API, demo filo) buna dokunmadan çalışmaya devam ediyor.

## Sonuçlar (1972 satırlık gerçek veri, %70/30 katmanlı bölme, n=592 test)

| Senaryo | Ne demek | En iyi model | Doğruluk | F1-makro |
|---|---|---|---|---|
| **B** gerçek → gerçek | Pratik üst sınır | XGBoost | 0.845 | **0.757** |
| **C** karma → gerçek | Sentetik + gerçek | XGBoost | 0.797 | 0.713 |
| **A** sentetik → gerçek | **Sıfır atış** | NeuralNet | 0.620 | **0.503** |
| **D** klasik konsensüs | Öğrenmesiz temel çizgi | — | 0.329 | 0.370 |

Karşılaştırma için: aynı hat **sentetik test verisinde** F1 ≈ 0.96 veriyor.

### Bulgu 1 — Alan kayması gerçek ve büyük

Sentetik veride 0.96 olan F1, gerçek veride **0.50**'ye düşüyor. Yani
IEC 60599 imzalarına göre üretilen veri, gerçek trafo ölçümlerinin
dağılımını yakalamıyor. Sebebi tahmin edilebilir: sentetik üreteç her
sınıfı "ders kitabı" oran aralıklarında üretirken, saha verisinde sınıflar
iç içe geçiyor, ölçüm gürültüsü ve karışık arızalar var.

Bu **olumsuz bir sonuç değil, ölçülmüş bir sonuç**: projenin sentetik veri
tercihinin sınırını rakamla gösteriyor.

### Bulgu 2 — Sentetik veri karışıma katkı sağlamıyor, seyreltiyor

Sentetik örnek sayısı azaldıkça karma eğitim iyileşiyor:

| Sentetik örnek | C (karma) F1 | B (saf gerçek) F1 |
|---|---|---|
| 4000 | 0.713 | 0.757 |
| 1400 | 0.730 | 0.757 |
| 400 | 0.749 | 0.757 |

Eğilim tek yönlü: sentetik pay küçüldükçe C, B'ye yaklaşıyor ama onu
geçmiyor. Yani bu ölçekte sentetik veri gerçek veriye **bilgi eklemiyor**;
sadece payı küçüldükçe daha az zarar veriyor.

### Bulgu 3 — Hangi sınıflarda hata yapıyor?

En iyi modelin (B / XGBoost) sınıf bazında doğruluğu:

| Sınıf | Doğru | Yorum |
|---|---|---|
| Normal | %95 | Kolay ayrılıyor |
| T3 | %94 | Yüksek sıcaklık imzası belirgin |
| PD | %88 | |
| D1 | %80 | 13 örnek D2 sanıldı |
| D2 | %70 | 17 örnek D1 sanıldı |
| T2 | %61 | |
| **T1** | **%36** | 8'i Normal, 6'sı T2, 6'sı T3 sanıldı |

İki hata kümesi var ve ikisi de fiziksel olarak beklenen:
* **D1 ↔ D2** (düşük/yüksek enerjili deşarj) — enerji seviyesi süreklidir,
  sınır keskin değildir.
* **T1** (< 300 °C) hem Normal'a hem üst termal sınıflara karışıyor. Düşük
  sıcaklıkta aşırı ısınma zaten zayıf bir imza üretir; üstelik CO/CO2 elimizde
  olsaydı ayırt etmek kolaylaşırdı (kağıt bozunması T1'in ana göstergesidir).
  **Yani T1'deki zayıflık doğrudan beş gaz kısıtının bedeli.**

### Bulgu 4 — Klasik yöntemler bağımsız test setinde ML'i geçiyor

| Bağımsız test (n=455, Normal sınıfı yok) | F1-makro |
|---|---|
| **Klasik konsensüs** | **0.650** |
| A / XGBoost (sentetik-eğitimli) | 0.492 |

Ana test setinde klasik konsensüs sonuncu (0.370) ama orada verinin ~%36'sı
Normal ve konsensüs "Normal" demekte isteksiz. Normal sınıfı olmayan
bağımsız sette ise klasik yöntemler sentetik-eğitimli ML'in **hepsini**
geçiyor.

Bu, projenin B sütunu (ML vs klasik karşılaştırma) için çok değerli:
**"ML her zaman kazanır" savı bu veride yanlış.** Klasik oran yöntemleri
onlarca yıllık saha bilgisinin damıtılmış hâli ve gerçek arıza vakalarında
hâlâ güçlü.

> Dürüstlük notu: klasik motora CO/CO2 = 0 verildi (veride yok), bu yüzden
> `key_gas` yönteminin karbonmonoksit dalı devre dışı. Klasik taraf bu
> deneyde bir miktar dezavantajlı çalıştı — yani gerçek performansı
> ölçtüğümüzden yüksek olabilir.

## Faz 6.3 — İyileştirme denemeleri (ablasyon)

> Üretim: `cd backend; python -m app.ml.experiments --real data/dga_china_2321.xlsx`
> Ham çıktı: `backend/artifacts/ablation_report.json`

Üç hamle **üst üste** eklendi; her adımda ölçüldü, fark o hamleye yazıldı.
Ablasyon yöntemi budur — "hepsini birden ekleyip iyileşti" demek hangi
hamlenin işe yaradığını gizler.

| Yapılandırma | Ne eklendi | A (sıfır atış) | B (gerçek eğitim) |
|---|---|---|---|
| E0 | çekirdek: 5 gaz + 4 oran | 0.503 | 0.757 |
| E1 | **+ klasik indikatörler** | 0.523 (+0.020) | 0.763 (+0.006) |
| E2 | + sınıf dengeleme (SMOTE) | 0.523 (±0.000) | 0.779 (+0.016) |
| E3 | + logaritmik ölçek | 0.520 (−0.003) | **0.780** (+0.001) |

**Klasik indikatörler** (`app/ml/hybrid.py`): Duval üçgeninin yüzde
koordinatları, dört yöntemin kararı (sınıf kodu olarak), Rogers'ın kod
üçlüsü, Key Gas'in baskın gazı ve payı, bir de yöntemlerin ne kadar
anlaştığını gösteren uzlaşma oranı — toplam 14 yeni özellik.

### Kazanç nereye gitti?

En iyi model (XGBoost) için E0 → E3 sınıf bazında:

| Sınıf | n | E0 F1 | E3 F1 | Fark | E0 duyarlılık | E3 duyarlılık |
|---|---|---|---|---|---|---|
| Normal | 212 | 0.95 | 0.95 | — | 0.95 | 0.95 |
| PD | 34 | 0.90 | 0.87 | −0.03 | 0.88 | 0.85 |
| D1 | 82 | 0.78 | 0.79 | +0.01 | 0.80 | 0.80 |
| D2 | 67 | 0.71 | 0.75 | +0.03 | 0.70 | 0.75 |
| **T1** | 33 | 0.44 | **0.56** | **+0.12** | **0.36** | **0.58** |
| T2 | 33 | 0.62 | 0.65 | +0.03 | 0.61 | 0.61 |
| T3 | 131 | 0.91 | 0.90 | — | 0.94 | 0.91 |
| **Makro** | | **0.76** | **0.78** | **+0.02** | | |

Kazancın neredeyse tamamı **T1'de** toplanmış: duyarlılık %36 → %58.
Bu tesadüf değil — 6.2'de T1'i "en zayıf halka" olarak işaretlemiştik ve
düzeltme tam oraya indi. Küçük bir bedel PD'de ödendi (−0.03).

### Yorum: neden bu kadar küçük bir kazanç?

Toplam +0.02 makro F1. Üç gözlem:

1. **İndikatörler B'ye çok az katkı yaptı (+0.006).** Beklenen: XGBoost
   zaten gaz oranlarından Duval/Rogers'ın kullandığı bilgiyi kendisi
   çıkarabiliyor. Klasik yöntemler ona *yeni* bilgi değil, aynı bilginin
   *özetini* veriyor.
2. **İndikatörler A'ya daha çok katkı yaptı (+0.020).** Bu da beklenen:
   sıfır atış senaryosunda model gerçek dağılımı hiç görmemiş, dolayısıyla
   dışarıdan gelen sağlam kurallara daha muhtaç.
3. **Log dönüşümü ağaç modellerini etkilemedi.** Doğal: karar ağaçları
   "x > eşik" diye böler, monoton bir dönüşüm bölmeyi değiştirmez. Log,
   SVM ve sinir ağı gibi mesafe/ağırlık temelli modeller için gerekliydi
   — nitekim orada belirgin düzeldiler, ama zaten en iyi model onlar değil.

**Asıl sonuç:** B tarafında ~0.78 bu veri ve beş gaz için gerçekçi bir
tavana yakın. Buradan sonraki ciddi kazanç özellik mühendisliğinden değil,
**daha iyi veriden** gelir: CO/CO2 içeren gerçek ölçümler (T1'in ana
göstergesi) veya daha fazla etiketli vaka.

A tarafı (0.52) ise hâlâ açık bir problem ve çaresi farklı: sentetik
üretecin gerçekçileştirilmesi (gürültü, sınıf örtüşmesi, gerçekçi
dağılımlar). Bu ayrı bir deney.

## Faz 6.4 — Doğru terazi: emniyet ölçütleri

> Üretim: `cd backend; python -m app.ml.safety_eval --real data/dga_china_2321.xlsx`
> Ham çıktı: `backend/artifacts/safety_report.json`

"F1 = 0.78" bir bakım mühendisine hiçbir şey söylemez, üstelik **yanıltıcıdır**.
Yedi sınıflı F1, iki taban tabana zıt hatayı aynı ağırlıkta cezalandırır:

* **T1 yerine T2 demek** → ikisi de "termal arıza var, incele". Sonuç aynı.
* **D2 yerine Normal demek** → ark var, "sorun yok" dedik. Felaket.

Aynı model, emniyet ölçütleriyle:

| Ölçüt | Sonuç |
|---|---|
| Yedi sınıflı tam isabet (referans) | doğruluk 0.851 · F1 0.780 |
| **Arıza yakalama duyarlılığı** | **%97.4** (380 arızanın 10'u kaçtı) |
| Yanlış alarm | %5.2 (212 normalin 11'i) |
| **Arıza ailesi** (Normal/Termal/Deşarj) | **doğruluk 0.938** |
| **Ciddi arızalar** (D2 ark, T3 >700 °C) | 198 vakanın **1**'ine "Normal" dendi |
| Ciddi arızada doğru aile | %96.5 |

Yani model **"%78 güvenli" değil**. Arızayı %97.4 yakalıyor, ne tür arıza
olduğunu %93.8 doğru sınıflandırıyor; 0.78 rakamı yalnızca "T1 mi T2 mi,
D1 mi D2 mi" gibi **aynı eylemi gerektiren** ayrımlardaki kararsızlıktan
düşüyor.

### Seçici tahmin — emniyet sistemlerinin çalışma biçimi

Model her vakada karar vermek zorunda değil. Güveni düşükse **susup uzmana
devredebilir**:

| Güven eşiği | Kapsama | Karar verilen | Doğruluk |
|---|---|---|---|
| yok (0.0) | %100 | 592 | 0.851 |
| 0.7 | %93 | 548 | 0.876 |
| 0.8 | %89 | 526 | 0.899 |
| **0.9** | **%84** | 495 | **0.913** |

Vakaların %84'ünde %91.3 isabetle otomatik karar, kalan %16'da "uzman
baksın" demek; her vakada %85 isabetten **operasyonel olarak çok daha
güvenli** bir sistemdir. Kaçırılan hata, fark edilmeyen hatadır; devredilen
vaka ise zaten insan gözüne gidiyor.

### "Oran zamanla artar mı?"

Kısmen. Artıracak şeyler:
* **Daha çok etiketli gerçek vaka** — 1380 eğitim örneği az; birkaç bin
  vakayla D1↔D2 ayrımı belirgin düzelir.
* **CO/CO2 içeren ölçümler** — T1'in ana göstergesi; bu veri setinde yok.
* **Zaman serisi** — tek numune yerine trafonun geçmişi. Projede `/trend`
  zaten var; tanıya da beslenebilir.

Artırmayacak şeyler:
* Daha karmaşık model. Ablasyon bunu gösterdi: özellik mühendisliği +0.02
  verdi, tavan veriden geliyor.
* **Etiket gürültüsü bir tavan koyar.** D1/D2 sınırı fiziksel olarak
  sürekli; etiketi koyan uzmanlar bile bazı vakalarda ayrılıyor. Hiçbir
  model "doğru cevabın kendisi belirsiz" olan veriyi %100 bilemez.

## Sonuç ve öneri

1. Demo/filo tarafı sentetik veriyle çalışmaya devam etmeli — orada amaç
   gerçekçi bir gösterim, kurumsal veri politikası da bunu gerektiriyor.
2. "Model %96 doğru" ifadesi **sentetik test verisi için** doğrudur ve öyle
   sunulmalıdır. Gerçek dünyada beş gazla beklenen aralık **F1 0.75 civarı**
   (gerçek veriyle eğitilirse).
3. Özellik mühendisliği (klasik indikatörler + dengeleme + log) B'yi
   0.757 → 0.780'e taşıdı; kazanç ağırlıklı olarak T1'de. Bu yol büyük
   ölçüde tüketildi.
4. **Doğru terazi emniyet ölçütleridir** (Faz 6.4): arıza yakalama %97.4,
   aile doğruluğu %93.8, ciddi arızalarda 198'de 1 kaçırma. Sistem
   yedi sınıflı F1'in ima ettiğinden çok daha güvenli.
5. Sonraki adım için en yüksek getirili iki iş:
   **(a)** CO/CO2 içeren gerçek veri bulmak — T1'in ana göstergesi;
   **(b)** `synth.py`'yi gerçekçileştirmek — sıfır atış (A) senaryosunu
   iyileştirmenin tek gerçek yolu bu.

## Lisans / atıf

Veri dosyaları `.gitignore` ile repo dışında tutuluyor: kaynak deponun
açık bir lisansı yok. Sonuçlar yayımlanabilir, veri yeniden dağıtılamaz.
Sunumda kaynak belirtilmeli.
