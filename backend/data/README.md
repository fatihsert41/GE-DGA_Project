# `backend/data/` — gerçek DGA veri setleri (Faz 6)

Bu klasördeki **veri dosyaları git'e girmez** (`.gitignore`). Sebebi lisans:
açık erişimli veri setlerinin çoğu yeniden dağıtıma izin vermez veya atıf
zorunluluğu getirir. Veriyi herkes kendi indirir; kod ise veriden bağımsız
çalışacak şekilde yazıldı.

## Seçilen veri seti

**IEEE DataPort — DGA dataset**
<https://ieee-dataport.org/documents/dga-dataset>

Üç dosya içerir:

| Dosya | Satır | Ne işe yarar |
|---|---|---|
| `DGA_train.xlsx` | 584 | Sınıf-dengeli eğitim seti |
| `DGA_test_unseen.xlsx` | 70 | Görülmemiş gerçek dünya test seti |
| `IEC_TC_10_data.xlsx` | 49 | IEC TC 10 karşılaştırma (benchmark) seti |

İndirdikten sonra üç dosyayı **bu klasöre** koy. Dosya adlarının aynı
olması şart değil — yükleyici sütun adlarını kendi eşler.

> Erişim IEEE DataPort aboneliği gerektirir. Üniversitelerin çoğunda kurumsal
> IEEE erişimi vardır; kampüs ağından veya öğrenci hesabınla dene.

## Veri şeması ve bizim şemamızla farkı

Veri seti **beş gaz** içerir: `H2, CH4, C2H6, C2H4, C2H2`.
**CO ve CO2 yoktur** — bunlar kağıt yalıtımın bozunmasını gösterir, klasik
arıza veri tabanları ise yağdaki arıza tipine odaklanır.

Bu yüzden projede iki özellik seti var (`app/ml/features.py`):

* `FEATURE_NAMES` — 7 gaz + 5 oran (sentetik veri, demo filo, canlı API)
* `CORE_FEATURE_NAMES` — 5 gaz + 4 oran (gerçek veriyle karşılaştırma)

Etiketler tam sayıdır (`0..6`). Varsayılan sıra
`Normal, PD, D1, D2, T1, T2, T3` olarak kabul edilir
(`real_data.DEFAULT_INT_ORDER`). Veri seti bu sırayı belgelemiyorsa
**sınıf dağılımına bakarak doğrula**: yükleyici her çalıştığında dağılımı
yazdırır, dağılım mantıksızsa sıra yanlıştır.

## Kullanım

```powershell
cd backend
python -m app.ml.real_data data/DGA_train.xlsx      # yükle + rapor
```
