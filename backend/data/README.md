# `backend/data/` — gerçek DGA veri setleri (Faz 6)

Bu klasördeki **veri dosyaları git'e girmez** (`.gitignore`). Sebebi lisans:
açık erişimli veri setlerinin çoğu yeniden dağıtıma izin vermez veya atıf
zorunluluğu getirir. Veriyi herkes kendi indirir; kod ise veriden bağımsız
çalışacak şekilde yazıldı.

## Kullanılan veri seti

**IEEE DataPort** ilk tercihti ama abonelik gerektiriyor (erişilemedi).
Yerine, aynı kaynakların (IEC TC 10 + Çin şebeke verisi + literatür)
derlendiği açık GitHub deposu kullanıldı — ve bu daha büyük çıktı:

<https://github.com/alan-456/transformer-fault-dataset>

| Dosya (bizdeki ad) | Kaynak dosya | Satır (temiz) | Rol |
|---|---|---|---|
| `dga_china_2321.xlsx` | `data.xlsx` | 2321 → **1972** | Ana gerçek veri; 7 sınıfın hepsi |
| `dga_bench_589.xlsx` | `dataset_(589).xlsx` | 589 → **455** | Bağımsız ikinci test (Normal yok) |

İndirme (backend/ klasöründen):

```powershell
curl.exe -sL -o data/dga_china_2321.xlsx "https://raw.githubusercontent.com/alan-456/transformer-fault-dataset/main/data.xlsx"
curl.exe -sL -o data/dga_bench_589.xlsx  "https://raw.githubusercontent.com/alan-456/transformer-fault-dataset/main/dataset_(589).xlsx"
```

> ⚠ Deponun **lisansı yok**. Sonuçlar yayımlanabilir, veri yeniden
> dağıtılamaz — bu yüzden dosyalar `.gitignore` içinde. Sunumda kaynak
> belirtilmeli.

Etiketler **Çincedir** (`正常`, `局部放电`, `高温过热` …) ve
`app/ml/real_data.py::_LABEL_ALIASES` içinde bizim yedi sınıfımıza eşlenir.

## Veri hijyeni

Yükleyici iki sızıntı kaynağını otomatik temizler:

* **Tekrar eden ölçümler** — `data.xlsx` içinde 349 birebir kopya vardı.
  Temizlenmezse aynı satır hem eğitime hem teste düşer, doğruluk şişer.
* **İki dosya arasındaki kesişim** — 589'luk setin %22'si ana veriyle
  ortaktı; `evaluate_real.py` bunu otomatik çıkarır (582 → 455).

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
