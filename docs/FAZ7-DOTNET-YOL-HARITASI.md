# Faz 7 — Bakım Planlama Servisi (.NET)

> **Bu faz bir öğrenme fazıdır.** Hız değil, anlama önceliklidir.
> Her adımda **tek yeni kavram** öğrenilir ve her adımın sonunda
> **çalışan** bir şey olur.

## Neden .NET, neyi çözüyor?

Şu ana kadarki sistem **"trafoda ne var?"** sorusunu cevaplıyor: gaz analizi,
arıza tahmini, risk, öncelik. Bakım Planlama Servisi bir sonraki soruyu
cevaplayacak: **"Peki şimdi ne yapacağız?"**

İş emri açmak, teknisyen atamak, planlamak, durum takip etmek, kayıt tutmak.
Bu tür iş mantığı endüstriyel şirketlerde ağırlıklı olarak .NET ile yazılır.

**Polyglot mikroservis mimarisi:** her servis kendi işine en uygun dilde.
ML Python'da kalır (scikit-learn, SHAP orada), iş mantığı .NET'e gider.

```
        ┌──────────────────────────────────┐
        │      React Dashboard             │
        └───┬──────────────────────────┬───┘
            │ "risk ne?"               │ "iş emri aç"
            ▼                          ▼
  ┌──────────────────────┐   ┌──────────────────────┐
  │ Python / FastAPI     │◄──┤ .NET / ASP.NET Core  │
  │ :8000                │   │ :5080                │
  │ DGA, ML, SHAP, trend │   │ iş emri, planlama    │
  │ SQLite: ölçümler     │   │ SQLite: iş emirleri  │
  └──────────────────────┘   └──────────────────────┘
```

## Adımlar

| # | Adım | Öğrenilecek kavram | Sonunda elimizde ne olur |
|---|---|---|---|
| **7.1** | Proje iskeleti ve temizlik | çözüm/proje yapısı, `Program.cs`, Minimal API | Kendi yazdığımız ilk uç nokta |
| **7.2** | İş emri modeli (bellekte) | `record`, `enum`, `List<T>`, LINQ | Listeleme/oluşturma uç noktaları |
| **7.3** | Veritabanı — EF Core + SQLite | `DbContext`, migration, **`async/await`** | Kalıcı iş emirleri |
| **7.4** | Python servisini okumak | `HttpClient`, **bağımlılık enjeksiyonu (DI)**, `appsettings` | .NET, trafo riskini Python'dan alır |
| **7.5** | Otomatik iş emri önerisi | iş mantığı katmanı, kural motoru | Riskli trafolar için öneri listesi |
| **7.6** | Teknisyen ve planlama | ilişkiler (foreign key), navigation property | Atama ve takvim |
| **7.7** | Arayüz — Planlama ekranı | iki servisli frontend | React'te bakım sekmesi |
| **7.8** | Testler | xUnit, .NET'te test yazımı | Güvenlik ağı |
| **7.9** | Çalıştırma belgeleri | üç servisi birlikte ayağa kaldırmak | README güncel |

## Yol boyunca öğrenilecek büyük kavramlar

Bunlar Python'da ya yok ya farklı; geldiklerinde ayrıca anlatılacak:

1. **Statik tipler** — hata çalışma anında değil, derleme anında yakalanır.
2. **Bağımlılık enjeksiyonu (DI)** — .NET'in kalbi. Sınıflar ihtiyaç duyduğu
   şeyi kendisi yaratmaz, dışarıdan alır. Test edilebilirliğin temeli.
3. **`async` / `await`** — Python'da da var ama .NET'te her yerde kullanılır;
   veritabanı ve HTTP çağrılarının tamamı asenkrondur.
4. **LINQ** — koleksiyon sorgulama dili. Python'daki liste üreteçlerinin
   (list comprehension) çok daha güçlü hâli.
5. **`null` güvenliği** — `string` ile `string?` farklı tiplerdir.

## Kurallar

* Her adımda **çalışan** bir şey olacak; yarım bırakılmayacak.
* Veritabanı 7.3'ten önce eklenmeyecek — tek seferde tek kavram.
* Python servisi **değiştirilmeyecek**; .NET onu dışarıdan tüketecek.
  (Mikroservis ayrımının anlamı budur: bir servis diğerinin içine girmez.)
* İş emri verisi .NET'in **kendi** veritabanında durur; ölçümler Python'da
  kalır. Tek veritabanını paylaşmak mikroservis mimarisinin en yaygın
  hatasıdır.

## Şu anki durum

* ✅ .NET 10.0.401 SDK kurulu
* ✅ Çözüm + Web API projesi oluşturuldu (`maintenance/`)
* ⏭️ 7.1 devam ediyor: şablon artıklarının temizliği ve ilk kendi uç noktamız
