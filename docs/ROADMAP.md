> ⚠️ **Bu belge projenin BAŞLANGIÇTAKİ planıdır (tarihsel kayıt).**
> Uygulama sırasında bazı kararlar ölçüme dayanarak değişti:
>
> | Plandaki | Gerçekleşen | Neden |
> |---|---|---|
> | Açık veri setiyle eğitim | **Sentetik veriyle eğitim**, gerçek veriyle *doğrulama* | Erişilebilir etiketli set bulunamadı; sentetik veri IEC 60599 imzalarından üretildi ve sınırı ölçüldü ([bulgular](FAZ6-GERCEK-VERI-BULGULARI.md)) |
> | TailwindCSS | **Elle yazılmış CSS** ("endüstriyel kontrol odası" dili) | Tasarım dili özgün olsun istendi |
> | 3 sütun (XAI, karşılaştırma, trend) | **5 sütun** — belirsizlik ve eyleme dönüşüm eklendi | Gerçek veri, modelin belirsizliğini ölçmeyi gerektirdi |
> | Tek servis | **Polyglot: Python + .NET** | Bakım planlama iş mantığı için ayrı servis ([Faz 7](FAZ7-DOTNET-YOL-HARITASI.md)) |
>
> Güncel durum için ana [`README.md`](../README.md) dosyasına bakın.

---

# TransformerAI — DGA Tabanlı Trafo Arıza Tahmin ve Sağlık İzleme Sistemi
### Full-Stack + Yapay Zeka Staj Projesi Yol Haritası

---

## 1. Projenin Özü (Elevator Pitch)

Güç trafolarının yalıtım yağından alınan örneklerde çözünmüş gazlar (H₂, CH₄, C₂H₂, C₂H₄, C₂H₆, CO, CO₂) bulunur. Bu gazların oranları, trafonun içinde gelişmekte olan arızanın **türünü** ve **ciddiyetini** ele verir. Bu projede, uluslararası açık veri setleriyle eğitilmiş bir makine öğrenmesi sistemi, mühendisin girdiği gaz değerlerinden arıza tipini tahmin eder, kararını **açıklar**, klasik endüstri yöntemleriyle **karşılaştırır** ve trafonun zaman içindeki sağlık **trendini** öngörür.

**Tek cümlelik savunma:** "Akademide notebook'ta kalan DGA modellerini, gerçek zamanlı çalışan, kararını açıklayabilen, tam kapsamlı bir web ürününe dönüştürdüm."

---

## 2. Projeyi Özgün Kılan 3 Sütun

| Sütun | Ne Yapar | Neden Etkileyici |
|-------|----------|------------------|
| **A. Açıklanabilir AI (XAI)** | Model "termal arıza" derken hangi gazın bu kararı sürüklediğini SHAP ile gösterir | Kara kutu değil, mühendisin güvenebileceği şeffaf model |
| **B. Çoklu Yöntem Karşılaştırma** | Duval Üçgeni, Rogers Oranı, IEC Oran yöntemi vs. ML modelleri aynı veride yarışır | Akademik derinlik + klasik bilgiyle köprü |
| **C. Zaman Serisi Trend Tahmini** | Aynı trafonun geçmiş ölçümlerinden "3 ay sonra kritik olacak" öngörüsü | Reaktif değil, kestirimci bakım (predictive maintenance) |

---

## 3. Teknoloji Yığını (Tech Stack)

**Frontend**
- React (Vite ile) — hızlı ve modern
- TailwindCSS — temiz arayüz
- Recharts / Plotly.js — grafikler ve Duval üçgeni görselleştirmesi
- Axios — API iletişimi

**Backend**
- Python + FastAPI (Flask yerine öneriyorum: otomatik dokümantasyon, hız, modern)
- Pydantic — veri doğrulama
- Uvicorn — sunucu

**Makine Öğrenmesi / AI**
- scikit-learn — Random Forest, SVM, temel modeller
- XGBoost — en güçlü tahmin modeli
- SHAP — açıklanabilirlik
- pandas / numpy — veri işleme
- joblib — model kaydetme

**Veritabanı**
- SQLite (başlangıç için, sıfır kurulum)
- İleride PostgreSQL'e geçiş kolay

**Diğer**
- Git + GitHub — versiyon kontrol (hocaya commit geçmişi göstermek çok değerli)
- Docker (opsiyonel, bonus puan)

---

## 4. Veri Kaynakları (Fabrikadan Sıfır Veri!)

Bu proje internetteki halka açık verilerle tamamen çalışabilir:

1. **UCI / Kaggle DGA veri setleri** — "Dissolved Gas Analysis transformer" araması
2. **IEEE C57.104 standardı** — gaz eşik değerleri ve yorumlama tabloları
3. **IEC 60599 standardı** — arıza tipi sınıflandırma oranları
4. **Duval Üçgeni koordinatları** — açık literatürde hazır formüller
5. Gerekirse standart tablolara dayalı **kural bazlı sentetik veri üretimi** (etiketli, savunulabilir)

> Not: Veri setini bulduğunda ilk iş sütunları anlamak ve etiket dağılımını incelemek. Dengesiz sınıf varsa (ki genelde vardır) SMOTE gibi tekniklerle dengele — bu da rapora yazılacak güzel bir teknik detay.

---

## 5. Sistem Mimarisi

```
┌─────────────────┐      HTTP/JSON      ┌──────────────────┐
│   React (SPA)   │ ◄─────────────────► │  FastAPI Backend │
│                 │                     │                  │
│ • Veri giriş    │                     │ • /predict       │
│ • Dashboard     │                     │ • /explain       │
│ • Grafikler     │                     │ • /compare       │
│ • Trend ekranı  │                     │ • /trend         │
└─────────────────┘                     └────────┬─────────┘
                                                  │
                                    ┌─────────────┼─────────────┐
                                    ▼             ▼             ▼
                              ┌──────────┐  ┌──────────┐  ┌──────────┐
                              │ ML Model │  │   SHAP   │  │  SQLite  │
                              │ (XGBoost)│  │ Explainer│  │    DB    │
                              └──────────┘  └──────────┘  └──────────┘
```

---

## 6. Fazlara Bölünmüş Yol Haritası

### 🔹 FAZ 0 — Hazırlık ve Temel (1. Hafta)
- [ ] GitHub reposu aç, README ve klasör yapısını kur
- [ ] Python sanal ortam + gerekli kütüphaneleri kur
- [ ] React projesini Vite ile başlat
- [ ] DGA veri setini indir, incele, sütunları anla
- [ ] IEEE/IEC eşik tablolarını bir dokümana topla
- **Çıktı:** Çalışan boş iskelet + incelenmiş veri

### 🔹 FAZ 1 — Veri ve Model Çekirdeği (2. Hafta)
- [ ] Veri temizliği: eksik değer, aykırı değer, normalizasyon
- [ ] Sınıf dengesizliğini çöz (SMOTE vb.)
- [ ] İlk modelleri eğit: Random Forest, XGBoost, SVM
- [ ] Doğruluk, precision, recall, confusion matrix ölç
- [ ] En iyi modeli joblib ile kaydet
- **Çıktı:** Eğitilmiş, ölçülmüş, kaydedilmiş model

### 🔹 FAZ 2 — Backend API (3. Hafta)
- [ ] FastAPI kur, `/predict` endpoint'i yaz
- [ ] Klasik yöntemleri kodla: Duval, Rogers, IEC oran (`/compare`)
- [ ] SHAP açıklama endpoint'i (`/explain`)
- [ ] SQLite'a ölçüm kayıt/okuma
- [ ] Swagger dokümantasyonunu test et
- **Çıktı:** Postman/Swagger'da çalışan tüm API'ler

### 🔹 FAZ 3 — Frontend Temel (4. Hafta)
- [ ] Veri giriş formu (7 gaz değeri + trafo ID)
- [ ] Tahmin sonucu ekranı (arıza tipi + risk seviyesi renkli)
- [ ] API bağlantısını kur, uçtan uca test et
- [ ] Temiz, endüstriyel görünümlü tasarım
- **Çıktı:** Değer gir → tahmin al, çalışan temel akış

### 🔹 FAZ 4 — Özgün Sütunlar (5.–6. Hafta)
- [ ] **A:** SHAP grafiklerini frontend'de göster (hangi gaz kararı etkiledi)
- [ ] **B:** Duval üçgeni görselini çiz, ML vs klasik yöntem karşılaştırma paneli
- [ ] **C:** Trafo geçmiş ölçüm grafiği + basit trend/regresyon ile gelecek tahmini
- **Çıktı:** Projeyi rakiplerinden ayıran 3 modül

### 🔹 FAZ 5 — Dashboard ve Cila (7. Hafta)
- [ ] Ana dashboard: tüm trafolar, risk dağılımı, son analizler
- [ ] Filtreleme, arama, kritik trafoları vurgulama
- [ ] Responsive tasarım, loading/hata durumları
- [ ] Örnek verilerle sistemi doldur (demo hazırlığı)
- **Çıktı:** Sunuma hazır, dolu, profesyonel arayüz

### 🔹 FAZ 6 — Belgeleme ve Sunum (8. Hafta)
- [ ] Detaylı README (kurulum, ekran görüntüleri, mimari)
- [ ] Proje raporu (problem, yöntem, sonuçlar, metrikler)
- [ ] Sunum slaytları
- [ ] Demo senaryosu prova
- **Çıktı:** Teslim paketi tamam

---

## 7. Değerlendirmede Fark Yaratacak Detaylar

- **Metrik göster:** "%94 doğruluk" gibi somut sayılar sun, confusion matrix ekle
- **Git commit geçmişi:** Düzenli commit'ler süreç yönetimi becerisi gösterir
- **Karşılaştırma tablosu:** ML vs klasik yöntem doğruluk farkını grafikle göster
- **Gerçek standart referansları:** IEEE C57.104, IEC 60599 alıntıla — ciddiyet katar
- **Sınırlılıklar bölümü:** "Şu veri kısıtı vardı, şöyle aştım" demek olgunluk gösterir

---

## 8. Klasör Yapısı Önerisi

```
transformer-ai/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── models/          # ML model dosyaları
│   │   ├── routers/         # predict, compare, explain, trend
│   │   ├── services/        # klasik yöntemler (duval, rogers)
│   │   └── database.py
│   ├── ml/
│   │   ├── train.py         # model eğitim scripti
│   │   ├── data/            # veri setleri
│   │   └── notebooks/       # keşif analizi
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── api/
│   └── package.json
├── docs/                    # rapor, diyagramlar
└── README.md
```

---

## 9. Riskler ve Önlemler

| Risk | Önlem |
|------|-------|
| Veri seti küçük/dengesiz çıkar | SMOTE + veri artırma + standart tablolarla destek |
| SHAP kurulumu/performansı zorlar | Küçük örneklerle çalış, önceden hesapla |
| Zaman yetmez | Faz 4'teki 3 sütundan en az 2'sini bitir, biri bonus kalsın |
| Frontend tasarımı zaman alır | Hazır Tailwind bileşen kütüphanesi kullan |

---

## 10. İlk Adım (Bugün Yapılacak)

1. GitHub reposu aç
2. Kaggle/UCI'dan bir DGA veri seti indir
3. Bana veri setinin sütunlarını göster — birlikte incelemeye başlayalım

> Bu roadmap yaşayan bir belgedir. İlerledikçe kutucukları işaretle, gerekirse fazları kaydır. Sonraki adımda hangi fazdan başlamak istersen, o fazın kodunu satır satır birlikte yazarız.
