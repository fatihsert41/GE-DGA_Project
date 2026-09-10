# Faz 6 sonrası: ML daha ne kadar iyileştirilebilir?

> Bu belge fikir listesi değil, **teşhise dayalı** bir yol haritasıdır.
> Her öneri, gerçek veri üzerinde yapılmış bir ölçüme dayanıyor.
> Teşhis betikleri: öğrenme eğrisi, çapraz doğrulama, kalibrasyon, hata yapısı.

## Önce: elimizdeki sayı ne kadar sağlam?

Tek bölmeye dayanan "F1 = 0.780" güvenilir bir sayı mı? 5 katlı çapraz
doğrulama:

| Ölçüt | Sonuç |
|---|---|
| F1-makro | **0.772 ± 0.010** |
| Doğruluk | 0.846 ± 0.006 |
| Aile doğruluğu | **0.946 ± 0.009** |

Katlar: 0.763, 0.766, 0.775, 0.766, 0.790. Yani **0.78 rakamı gerçek**;
tek bölmenin şansı değil. Dürüst ifade: **F1 ≈ 0.77 ± 0.01**.

Aile doğruluğu 0.946 çıktı — tek bölmedeki 0.938'den bile iyi.

## Teşhis 1 — Hataların %58'i zaten zararsız

592 test numunesinde 88 hata (%14.9). Ama hepsi aynı ağırlıkta değil:

| Hata türü | Adet | Payı | Bakım kararına etkisi |
|---|---|---|---|
| Aynı aile içi | 51 | %58 | **Yok** — aynı iş yapılır |
| Aile dışı | 37 | %42 | Var |

En sık karışan çiftler:

| | Adet | Tür |
|---|---|---|
| D2 → D1 | 15 | aynı aile |
| D1 → D2 | 13 | aynı aile |
| T1 → Normal | 8 | **aile dışı** |
| T2 → T1 | 6 | aynı aile |
| T3 → T1 | 5 | aynı aile |
| PD → T1 | 4 | **aile dışı** |

**D1 ↔ D2 tek başına tüm hataların %32'si.** Deşarj enerjisi fiziksel olarak
sürekli bir büyüklüktür; "düşük" ile "yüksek" arasındaki sınır tanım gereği
bulanıktır ve etiketi koyan uzmanlar da bu bölgede ayrışır.

**Sonuç:** karar değiştiren gerçek hata oranı %14.9 değil, **%6.3**
(37/592). Ve o 37'nin bir kısmı da T1 ile ilgili — CO/CO₂ eksikliğinin bedeli.

## Teşhis 2 — Öğrenme eğrisi hâlâ yükseliyor

Gerçek eğitim verisinin bir kısmıyla eğitip tam test setinde ölçtük:

| Eğitim verisi | n | F1 | Önceki adıma göre |
|---|---|---|---|
| %15 | 207 | 0.699 | — |
| %30 | 414 | 0.733 | +0.034 |
| %50 | 690 | 0.745 | +0.012 |
| %75 | 1035 | 0.761 | +0.016 |
| %100 | 1380 | 0.780 | **+0.019** |

Son adım hâlâ +0.019 veriyor ve eğri **düzleşme belirtisi göstermiyor**.

**En yüksek getirili yatırım budur: daha çok etiketli gerçek vaka.**
Model mimarisi değil, veri. Kaba bir tahminle veriyi ikiye katlamak
+0.02–0.04 getirir.

## Teşhis 3 — Model kendine fazla güveniyor

Uzman incelemesi özelliği modelin güven değerine dayanıyor. Peki o değer
dürüst mü? Model "%90 eminim" derken gerçekten %90 tutturuyor mu?

| Güven aralığı | n | Model ne diyor | Gerçekte ne oluyor | Fark |
|---|---|---|---|---|
| 0.70 – 0.80 | 22 | %76 | **%32** | −0.45 |
| 0.80 – 0.90 | 31 | %86 | %68 | −0.18 |
| 0.90 – 0.99 | 98 | %96 | %76 | −0.21 |
| 0.99 – 1.00 | 397 | %99.9 | %95 | −0.05 |

**ECE (beklenen kalibrasyon hatası) = 0.096.** (0.05 altı iyi, 0.15 üstü kötü.)

Model sistematik olarak **fazla iddialı**. Sadece "%99'dan emin" dediğinde
dürüst davranıyor. Bu, eşiğin 0.90 seçilmiş olmasını açıklıyor: pratikte
ancak orada anlamlı bir ayrım oluşuyor.

## Yol haritası — beklenen getiriye göre sıralı

### 1. Kalibrasyon ⭐ en iyi getiri/emek oranı
**Sorun:** ECE 0.096, model fazla iddialı.
**Çözüm:** `CalibratedClassifierCV` (isotonic veya Platt) — mevcut modelin
üstüne çapraz doğrulamalı bir kalibrasyon katmanı.
**Beklenen kazanç:** F1'e ~0 katkı, ama **güven değerleri anlamlı hale
gelir**. "Sistem %90 dediğinde 10 vakanın 9'unda haklı" cümlesini
kurabilmek, uzman incelemesi özelliğinin bütün temeli.
**Emek:** düşük (birkaç satır + ölçüm).

### 2. Zaman serisi özellikleri ⭐ projeye özgü avantaj
**Sorun:** Tek numuneden tanı koymak fiziksel olarak belirsiz.
**Gözlem:** Sahada uzmanlar tek ölçüme bakmaz; **gaz üretim hızına** bakar
(IEEE C57.104 "gassing rate"). Aynı 200 ppm H₂, bir yılda oluştuysa farklı,
bir ayda oluştuysa çok farklı anlama gelir.
**Çözüm:** `services/trend.py` zaten her gazın eğimini hesaplıyor. Bu
eğimleri tanı modeline özellik olarak vermek.
**Kısıt:** Gerçek veri setinde zaman serisi **yok** (tek numuneler), yani
bu kazanç gerçek veride ölçülemez — ama uygulamanın kendi filosunda ölçülebilir.
**Emek:** orta. **Sunum değeri: yüksek** (kimsenin yapmadığı şey).

### 3. Hiyerarşik sınıflandırma
**Gözlem:** Aile doğruluğu zaten 0.946, alt tip 0.846.
**Çözüm:** İki aşama — önce aile (Normal/Termal/Deşarj), sonra aile içinde
alt tip. Her alt model kendi ayrımına odaklanır.
**Beklenen kazanç:** +0.01–0.03. Asıl faydası **yapısal**: model doğal
olarak "aileyi biliyorum, alt tipten emin değilim" diyebilir.
**Emek:** orta.

### 4. D1/D2 sınırını dürüstçe ele almak
**Gözlem:** Tüm hataların %32'si D1↔D2.
**Seçenekler:**
  - **(a)** Raporlamada "Deşarj (D1/D2)" olarak birleştirip, ayrımı ancak
    model emin olduğunda göstermek.
  - **(b)** Enerji seviyesini ayırt edebilecek özellik eklemek: toplam gaz
    miktarı ve C₂H₂'nin mutlak seviyesi (oranlar bu bilgiyi kaybediyor).
**Beklenen kazanç:** (b) için +0.01–0.02; (a) için F1 kazancı yok ama
**dürüstlük kazancı** var.
**Emek:** düşük.

### 5. Uyumlu tahmin (conformal prediction)
**Fikir:** Tek bir sınıf yerine, **garantili kapsama** oranı olan bir sınıf
KÜMESİ döndürmek: "bu vaka %90 olasılıkla {D1, D2} içindedir".
**Neden güçlü:** Bizim eşik yaklaşımının matematiksel olarak garantili
hali. Belirsizlik varsa küme büyür, model kendiliğinden "emin değilim" der.
**Beklenen kazanç:** Doğrulukta değil, **güvenilirlikte**.
**Emek:** orta-yüksek. Sunumda çok etkileyici.

### 6. Topluluk (ensemble) ve hiperparametre araması
**Beklenen kazanç:** +0.005–0.015. Ablasyonda görüldüğü gibi bu yol
büyük ölçüde tüketildi.
**Emek:** düşük ama getirisi de düşük. **Öncelik verme.**

### 7. CO/CO₂ içeren gerçek veri
**Gözlem:** T1 → Normal hataları (8 adet) en tehlikeli olanlar ve T1'in ana
göstergesi kağıt bozunması, yani CO/CO₂.
**Kısıt:** Böyle bir açık veri seti bulunamadı.
**Not:** Bulunursa 1. sıraya çıkar.

## Ne yapmamalı

* **Derin öğrenme.** 1380 örnek ve 23 özellikle sinir ağı, ağaç
  modellerinin gerisinde kalır — nitekim deneylerimizde de öyle oldu.
* **Daha fazla özellik mühendisliği.** Faz 6.3 ablasyonu bu yolun
  tükendiğini gösterdi (+0.02).
* **Sentetik veriyi daha da "gerçekçi" yapmak.** Faz 6.7 gösterdi ki
  dağılımı benzetmek aktarımı iyileştirmiyor; ölçmeden eklenen her
  gerçekçilik bileşeni zarar verdi.

## Özet: tavan nerede?

| | Değer |
|---|---|
| Şu anki F1 | 0.77 ± 0.01 |
| Karar değiştiren hata oranı | %6.3 |
| Aile doğruluğu | 0.946 |
| Arıza yakalama | %97.4 |

Aynı veri ve beş gazla ulaşılabilecek tavan tahmini **F1 ≈ 0.82–0.85**
(kalibrasyon + hiyerarşi + D1/D2 çalışması). Bunun üstü **veri gerektirir**:
daha çok vaka ve CO/CO₂.

Ama asıl mesaj şu: **F1'i kovalamak yanlış hedef.** Sistem arızayı %97.4
yakalıyor, aileyi %94.6 doğru buluyor ve emin olmadığında söylüyor.
Bakım kararı için yeterli olan bunlar.
