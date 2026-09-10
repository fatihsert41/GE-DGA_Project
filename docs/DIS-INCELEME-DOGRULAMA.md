# Dış inceleme raporunun doğrulanması

> Dışarıdan gelen bir inceleme raporu (10 Eylül 2026, `555219e` sürümü) yedi
> kod sorunu ve bir kavramsal itiraz bildirdi. Bu belge her iddianın **kendi
> ortamımızda tekrar üretilmiş** sonucunu kaydeder.
>
> Yöntem: rapora güvenmek yerine her bulgu için ayrı bir deney çalıştırıldı.
> Bir bulgunun raporda yazması onu doğru yapmaz; ölçüm yapar.

## Sonuç özeti

| # | İddia | Doğrulama | Öncelik |
|---|---|---|---|
| 1 | Tahmin yolu varlık künyesini eziyor | ✅ **Doğrulandı** | P0 |
| 2 | Trend gerçek zamanı kullanmıyor | ✅ **Doğrulandı** | P0 |
| 3 | Numunesiz trafo plan dışında kalıyor | ✅ **Doğrulandı** | P0 |
| 4 | Güven eşiği farklı modelde ölçülmüş | ✅ **Doğrulandı** | P0 |
| 5 | Açık iş kötüleşen riski yansıtmıyor | ✅ Doğrulandı | P1 |
| 6 | İş emri numarası yarışa ve 9999'a açık | ✅ **Doğrulandı** | P1 |
| 7 | Durum geçişi kuralsız | ✅ Doğrulandı | P1 |
| — | "Aynı aile = zararsız hata" savı güvensiz | ✅ **Doğrulandı, bizim iddiamız çürüdü** | P0 |

Yedi iddianın **yedisi de gerçek.** Bir tanesi (aşağıdaki 8. madde) bizim
belgelerimizde yazan bir savı doğrudan çürütüyor.

---

## 1 · Tahmin yolu varlık künyesini eziyor (P0)

`routers/predict.py`, kayıt sırasında `upsert_transformer(tid, name)` çağırıyor.
Diğer alanlar varsayılana düşüyor.

```
ÖNCE : name='Gebze Trafosu' location='Gebze' asset_class='LPT' mva=150.0
SONRA: name='Gebze Trafosu' location=''      asset_class='MPT' mva=None
```

**Etkisi ölçüldü:** tek bir `/predict` çağrısı bir LPT'yi MPT'ye düşürüyor.
Öncelik skoru `kondisyon × varlık ağırlığı` olduğuna göre, kritik durumdaki
bir trafonun önceliği **4.00'ten 2.80'e** sessizce iniyor.

Künye alanları (Faz 8.1) hayatta kaldı — çünkü `upsert_transformer` yalnızca
kendisine verilen künye alanlarını yazıyor. Ama çekirdek dört alan kayboluyor.

## 2 · Trend gerçek zamanı kullanmıyor (P0)

`routers/trend.py:49` → `times = list(range(len(measurements)))`

Ölçüm **sırası** kullanılıyor, gerçek zaman damgaları değil.

```
Aynı iki ölçüm, 1 ay arayla  -> H2 kritik süre 0.3 ay
Aynı iki ölçüm, 1 gün arayla -> H2 kritik süre 0.0 ay
Router her ikisinde de       -> 0.3 ay
```

Bir gün içinde aynı artışı gösteren gaz, otuz kat hızlı üretiliyor demektir.
Router bu farkı tamamen kaybediyor. Demo verimizde aralıklar 30 güne sabit
olduğu için sorun görünmüyor — bu **şans**, doğruluk değil.

## 3 · Numunesiz trafo plan dışında kalıyor (P0)

15 yaşında, hiç numune alınmamış bir LPT için:

```
has_data = False · sampling_overdue = False · priority = 0.0
```

Hiçbir uyarı üretmiyor. "Veri yok" ile "güncel" aynı sayılıyor. Oysa hiç
numune alınmamış varlık, numune alma açısından **en acil** olandır.

Üç ayrı durum olmalı: **veri yok** / **güncel** / **gecikmiş**.

## 4 · Güven eşiğinin dayanağı farklı model (P0) — en sert bulgu

| | Hizmet veren model | Eşiğin ölçüldüğü model |
|---|---|---|
| Algoritma | RandomForest | XGBoost + SMOTE |
| Özellik | 12 (7 gaz + 5 oran) | 23 (5 gaz + oran + klasik indikatör) |
| Eğitim verisi | Sentetik (field_like), 4000 | **Gerçek**, 1380 |
| Ortak özellik | — | yalnızca **9** |

`CONFIDENCE_THRESHOLD = 0.90` değeri ikinci modelde ölçüldü, **birincisinde
uygulanıyor.** "Bu eşiğin altında doğruluk %54" cümlesi hizmet veren model
için **kanıtlanmamıştır**.

Üstelik hizmet modeli gerçek veride doğrudan sınanamıyor: 7 gaz istiyor,
gerçek veri 5 gaz içeriyor. Yani eşiğin dayanağı yalnızca zayıf değil,
mevcut veriyle **ölçülemez** durumda.

## 5 · Açık iş kötüleşen riski yansıtmıyor (P1)

`WorkOrderPlanner` açık emri olan (trafo, tür) çiftini atlıyor. Bu idempotens
için doğru, ama **risk kötüleşirse** mevcut emrin aciliyeti güncellenmiyor.
"İzlemede" diye açılmış bir emir, trafo kritik hâle gelse bile 30 günlük
son tarihiyle kalıyor.

## 6 · İş emri numarası yarışa ve 9999'a açık (P1)

`NextIdAsync` en büyük id'yi metin olarak sıralıyor:

```
sıralama: WO-9999 > WO-10001 > WO-10000 > WO-0999
```

9999'dan sonra en büyük "WO-9999" sanılıyor → üretici tekrar `WO-10000`
veriyor → **birincil anahtar çakışması**. Ayrıca paralel iki istek aynı
numarayı alabilir (kod yorumunda not edilmişti ama çözülmemişti).

## 7 · Durum geçişi kuralsız (P1)

```
Planned  -> Done      : HTTP 200
Done     -> Planned   : HTTP 200
Planned  -> Cancelled : HTTP 200
```

Hiçbir geçiş kuralı yok. Başlanmamış bir iş "tamamlandı" olabiliyor,
tamamlanan iş sessizce geri alınabiliyor, tamamlanma kanıtı istenmiyor.

## 8 · "Aynı aile = zararsız hata" savı — BİZİM İDDİAMIZ ÇÜRÜDÜ

Faz 6.4'te şunu yazmıştık:

> *"Hataların %58'i aynı aile içinde ve bakım kararını değiştirmez.
> Karar değiştiren gerçek hata oranı %6.3."*

Rapor bunun güvenli olmadığını söyledi. **Ölçtük, haklı:**

```
Test kümesi: 592 örnek
  Toplam hata               : 88  (%14.9)
  Aynı aile içi hata        : 51  (hatanın %58)

  GEREKLİ BAKIM GECİKTİ     : 36  (%6.1)
    bunların 22'si AYNI AİLEDE   <- "zararsız" saydıklarımız
  Gereksiz aciliyet         : 34  (%5.7)  (boşa kaynak)
```

Gecikmeye yol açan en sık hata **D2 → D1 (15 kez)** ve ikisi de "Deşarj"
ailesinde. Ama planlayıcımızda D2 **ciddi arıza** sayılıp 3 gün içinde
inceleme istiyor; D1 ise yüksek risk kuralına düşüp 7-14 güne kayıyor.
Aile aynı, **karar farklı**.

Aynı şekilde T3 → T1 (5 kez): ikisi de "Termal", ama T3 ciddi sınıf.

**Doğru ölçüt:** aile doğruluğu değil, **gerekli bakımın geciktirildiği vaka
oranı**. Bizim %6.3'ümüz "aile dışı hata oranı"ydı — farklı bir kümeyi
ölçüyordu ve rakamın yakın çıkması tesadüf. 36 gecikme vakasının yalnızca
14'ü aile dışıydı.

---

## Katılmadığım / nüanslı bulduğum noktalar

**Uzmanlık zorunlu koşul mu olmalı?** Rapor, atamada uzmanlığın zorunlu,
bölgenin tercih puanı olmasını öneriyor. Mevcut tasarımda bölge (+10)
uzmanlığı (+5) bastırabiliyor ve bu **bilinçliydi**: yol süresi sahada en
pahalı kalemdir. Yine de numune alma gibi yetkinlik gerektiren işlerde
zorunlu filtre mantıklı. Sonuç: iş **türüne göre** karar verilmeli —
tek kural değil.

**SQLite ve async.** Rapor haklı: Microsoft belgelerine göre SQLite gerçek
asenkron I/O desteklemez, `async` ADO.NET çağrıları senkron çalışır. Faz
7.3'te "await ile iş parçacığı serbest kalır" derken bunu belirtmedim.
Kavram doğru ve PostgreSQL'e geçildiğinde aynen geçerli; ama **SQLite'ta
bugün bu kazanç yok**. Bu, öğretirken düzeltilmesi gereken bir eksiklik.

**Performans/ölçek önerileri.** Rapor da söylüyor: darboğaz ölçülmeden
PostgreSQL veya kuyruk eklemek öğrenme yükü artırır, sorunu çözdüğünü
göstermez. Katılıyorum — 9 trafoda indeks ayarı yapmak erken optimizasyon.

---

## Düzeltme sırası

Rapor haklı: **büyümeden önce düzeltmek** gerekiyor. Yeni özellik eklemek,
bozuk temelin üstüne kat çıkmaktır.

| Sıra | İş | Neden önce |
|---|---|---|
| 1 | Varlık künyesinin ezilmesi (P0-1) | Sessiz veri kaybı; öncelik skorunu bozuyor |
| 2 | Trend zaman ekseni (P0-2) | "Kaç ay kaldı" sayısı şu an fiziksel olarak yanlış |
| 3 | Numunesiz varlık durumu (P0-3) | En acil vaka görünmez durumda |
| 4 | Eşiğin dayanağı + model kimliği (P0-4) | Emniyet anlatısının temeli |
| 5 | Geciktirilen bakım ölçütü (madde 8) | Belgelerdeki yanlış savı düzeltmek |
| 6 | İş emri kimliği ve durum geçişleri (P1-6,7) | Veri bütünlüğü |
| 7 | Aciliyet yükseltme (P1-5) | Kötüleşen risk sessiz kalmamalı |
