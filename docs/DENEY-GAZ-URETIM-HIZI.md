# Deney: Gaz Üretim Hızı Ölçütü — RAFA KALDIRILDI

> 11 Eylül 2026'da eski bilgisayarda başlandı, 15 Eylül 2026'da ölçüldü.
> Kod depoda duruyor ama **ürüne bağlı değil**: hiçbir uç nokta, filo
> kartı, sağlık endeksi ya da iş emri kuralı onu çağırmıyor.
>
> * Kural: `backend/app/core/rate.py`
> * Ölçüm: `backend/app/ml/rate_eval.py` → `python -m app.ml.rate_eval`
>   (`backend/` klasöründen)

## Fikir

Sistem gazlara yalnızca **mutlak derişim** olarak bakıyor ("H2 = 180 ppm").
IEEE C57.104'ün bir ölçütü de **değişim hızı** ("H2 ayda 40 ppm artıyor").
İkisi farklı şeyler söyler:

| Durum | Derişim | Hız | Anlamı |
|---|---|---|---|
| 10 yıldır 180 ppm, sabit | yüksek | ~0 | eski, kararlı — acil değil |
| 3 ayda 40 → 180 ppm | yüksek | çok yüksek | gelişen arıza — acil |

Kural: TDCG üretim hızı (en küçük kareler eğimi, ppm/gün) → IEEE 1991
Tablo 3 kondisyonu; derişim kondisyonuyla **kötüsü** alınır.

## Nasıl ölçüldü

Faz 6.5 ve 6.7'nin dersi: *makul görünen bir kural, işe yaradığı anlamına
gelmez.* Bu yüzden eklemeden önce iki soru soruldu:

1. Hız ölçütü arızayı derişimden **daha erken** yakalıyor mu?
2. Sağlıklı trafoda **yanlış alarm** üretiyor mu?

6 arıza tipi × 20 tohum = 120 sentetik seri, 18 ay, aylık numune.
Her ay yalnızca **o ana kadarki** ölçümlerle karar verildi (geleceği
görmemek için). Alarm eşiği: kondisyon ≥ 3.

## Sonuç

| Ölçüt | Değer |
|---|---|
| Daha erken yakalanan seri | **0 / 106** |
| Daha geç yakalanan seri | 0 / 106 |
| Yalnızca hızın gördüğü | 0 |
| Yanlış alarm (sağlıklı, 20 seri) | 0 → 0 |
| **Hüküm** | **EKLEME** |

## Neden hiç etkisi yok?

Kod hatası değil, eşik ile veri arasında büyüklük farkı var:

| | ppm/gün |
|---|---|
| Sentetik serilerde görülen **en yüksek** TDCG hızı | ~2.5 |
| IEEE 1991'de kondisyon 2'nin başladığı hız | 10 |

Hız ölçütü hiçbir seride kondisyon 1'in üstüne çıkmıyor, dolayısıyla
"kötüsünü al" kuralında derişim her zaman kazanıyor. Kural yazılı ama
hiçbir kararı değiştirmiyor, yani **ölü bir kural.**

## Neyi bilmiyoruz (dürüstlük notu)

Bu sonuç iki şekilde okunabilir ve elimizdeki veriyle ayırt edilemez:

* **Eşik çok kaba:** 1991 tablosu ppm/gün cinsinden, çevrimiçi izleme
  için düşünülmüş. Aylık numunede anlamlı hızlar çok daha düşük olabilir.
* **Sentetik seri çok yavaş:** `synth.make_aging_series` gerçek gelişen
  arızalardan daha yavaş gaz üretiyor olabilir.

Hangisinin doğru olduğunu anlamak için **aynı trafonun art arda
ölçümlerini** içeren gerçek veri gerekir. Faz 6'daki açık veri seti
(2321 kayıt) tek noktalı; hız hesaplanamıyor.

## Yeniden açılırsa

1. IEEE C57.104-2019'un **gaz bazlı** hız sınırlarını (ppm/yıl, 90.
   yüzdelik değişim) dene — TDCG toplamı yerine tek tek gazlar.
2. Faz 12.3'teki uzman etiketleri art arda ölçüm biriktiriyor; yeterli
   seri olduğunda ölçümü **gerçek serilerle** tekrarla.
3. Aynı ölçüt: erken yakalama > 0 **ve** yanlış alarm artışı ≤ 2.
