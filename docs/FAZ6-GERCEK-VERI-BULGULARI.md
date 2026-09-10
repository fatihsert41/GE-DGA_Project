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

## Sonuç ve öneri

1. Demo/filo tarafı sentetik veriyle çalışmaya devam etmeli — orada amaç
   gerçekçi bir gösterim, kurumsal veri politikası da bunu gerektiriyor.
2. "Model %96 doğru" ifadesi **sentetik test verisi için** doğrudur ve öyle
   sunulmalıdır. Gerçek dünyada beş gazla beklenen aralık **F1 0.75 civarı**
   (gerçek veriyle eğitilirse).
3. Sonraki adım için en yüksek getirili iş: **CO/CO2 içeren gerçek veri
   bulmak.** T1'deki %36'lık zayıflık büyük ölçüde bu eksikten geliyor.

## Lisans / atıf

Veri dosyaları `.gitignore` ile repo dışında tutuluyor: kaynak deponun
açık bir lisansı yok. Sonuçlar yayımlanabilir, veri yeniden dağıtılamaz.
Sunumda kaynak belirtilmeli.
