# TransformerAI — DGA Tabanlı Trafo Arıza Tahmin ve Sağlık İzleme Sistemi

> **GE Vernova Staj Projesi.** Güç trafolarının yalıtım yağındaki çözünmüş
> gazlardan (DGA) arıza tipini tahmin eden, kararını **açıklayan**, klasik
> endüstri yöntemleriyle **karşılaştıran** ve trafonun sağlık **trendini**
> öngören tam kapsamlı bir web uygulaması.

Bu proje **tamamen açık standartlara ve sentetik (üretilmiş) veriye** dayanır;
hiçbir gizli/kurumsal saha verisi kullanmaz. Sentetik veri IEC 60599 ve Duval
üçgeni arıza imzalarına göre üretilir ve üreten kuralla otomatik etiketlenir.

---

## 🎯 Projeyi Özgün Kılan 3 Sütun

| Sütun | Ne yapar | Nerede |
|-------|----------|--------|
| **A — Açıklanabilir AI (SHAP)** | Model "D2 (ark)" derken hangi gazın bu kararı sürüklediğini sayısal olarak gösterir | `POST /explain` |
| **B — Çoklu Yöntem Karşılaştırma** | Duval, Rogers, IEC, Key Gas **vs** RandomForest, XGBoost, SVM, NeuralNet aynı test setinde yarışır | `GET /compare/leaderboard`, `POST /compare` |
| **C — Zaman Serisi Trend Tahmini** | Bir trafonun geçmiş ölçümlerinden "~N ay içinde kritik olacak" öngörüsü | `POST /trend`, `GET /trend/demo/{sınıf}` |

**Örnek çıktı (D2 / ark vakası):** ML tahmini `D2`, güven `1.00`, SHAP en etkili
gazlar `C2H2` (asetilen) ve `C2H4` (etilen) — fiziksel olarak birebir doğru.

---

## 🧪 Arıza Sınıfları (IEC 60599)

`Normal` · `PD` (kısmi deşarj) · `D1` (düşük enerjili deşarj) · `D2` (ark) ·
`T1` (<300 °C) · `T2` (300–700 °C) · `T3` (>700 °C)

Dashboard'da 4 gruba sadeleştirilebilir: **Normal / Termal / Deşarj / Ark**.

---

## 🏗️ Mimari

```
┌─────────────────┐      HTTP/JSON      ┌──────────────────────┐
│   React (SPA)   │ ◄─────────────────► │   FastAPI Backend    │
│  Veri giriş     │                     │  /predict  /explain  │
│  Dashboard      │                     │  /compare  /trend    │
│  Grafikler      │                     │  /transformers       │
└─────────────────┘                     └───────────┬──────────┘
                          ┌──────────────┬──────────┼───────────┐
                          ▼              ▼          ▼           ▼
                    ┌──────────┐  ┌───────────┐ ┌────────┐ ┌─────────┐
                    │ Klasik   │  │ ML Model  │ │  SHAP  │ │ SQLite  │
                    │ motor    │  │ (RF/XGB)  │ │Explainer│ │   DB    │
                    │Duval/IEC │  │           │ │        │ │         │
                    └──────────┘  └───────────┘ └────────┘ └─────────┘
```

### Backend dizin yapısı
```
backend/app/
├── core/          # Klasik DGA motoru (saf Python, ML'siz)
│   ├── gases.py       # 7 gaz, sınıflar, IEEE eşikleri, oranlar
│   ├── duval.py       # Duval Üçgeni 1
│   ├── rogers.py      # Rogers oran yöntemi
│   ├── iec_ratio.py   # IEC 60599 oran yöntemi
│   ├── key_gas.py     # Key Gas yöntemi
│   ├── risk.py        # IEEE C57.104 risk/kondisyon değerlendirmesi
│   └── classify.py    # Yöntemleri birleştiren konsensüs
├── ml/            # Makine öğrenmesi katmanı
│   ├── synth.py       # Standart-temelli sentetik veri üreteci
│   ├── features.py    # Öznitelik mühendisliği (gaz + oranlar)
│   ├── train.py       # Çoklu model eğitimi + karşılaştırma
│   └── predictor.py   # Model yükleme, tahmin, SHAP açıklama
├── services/      # trend.py (trend), diagnosis.py (birleşik tanı)
├── routers/       # FastAPI uç noktaları
├── database.py    # SQLite kalıcılık
├── schemas.py     # Pydantic modelleri
└── main.py        # FastAPI uygulaması
```

---

## 🚀 Kurulum ve Çalıştırma

### Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # opsiyonel
pip install -r requirements.txt

# 1) Modeli eğit (model.joblib + metrics.json üretir)
python -m app.ml.train

# 2) API'yi başlat
uvicorn app.main:app --reload
```
Swagger dokümantasyonu: **http://localhost:8000/docs**

### Testler
```bash
cd backend
pytest -q          # 18 birim testi
```

---

## 📡 API Uç Noktaları

| Metot | Yol | Açıklama |
|-------|-----|----------|
| `GET`  | `/` , `/health` | Servis durumu, model eğitilmiş mi |
| `POST` | `/predict` | Tam tanı: ML + klasik + risk (+ opsiyonel kayıt) |
| `POST` | `/explain` | SHAP gaz katkıları (Sütun A) |
| `POST` | `/compare` | Tek okuma için tüm yöntemler yan yana |
| `GET`  | `/compare/leaderboard` | ML vs klasik doğruluk tablosu (Sütun B) |
| `POST` | `/trend` | Verilen ölçüm geçmişinden trend (Sütun C) |
| `GET`  | `/trend/demo/{sınıf}` | Demo için sentetik yaşlanma serisi |
| `GET`  | `/transformers/{id}/measurements` | Trafo ölçüm geçmişi |

Örnek istek:
```bash
curl -X POST localhost:8000/predict -H "Content-Type: application/json" -d '{
  "gases": {"H2":280,"CH4":120,"C2H6":40,"C2H4":220,"C2H2":240,"CO":500,"CO2":3200}
}'
```

---

## 📚 Referans Standartlar

- **IEC 60599:2015** — çözünmüş gaz oran yorumlama
- **IEEE C57.104-2008** — gaz konsantrasyon eşikleri (Condition 1–4)
- **M. Duval (2002)** — Duval Üçgeni arıza bölgeleri

---

## 🗺️ Yol Haritası

- [x] **Faz 0–1** — İskelet + klasik DGA motoru + testler
- [x] **Faz 2** — Sentetik veri + çoklu model eğitimi + karşılaştırma
- [x] **Faz 3** — FastAPI backend (predict/explain/compare/trend) + SQLite
- [ ] **Faz 4** — React dashboard (veri giriş, SHAP grafiği, Duval üçgeni, trend)
- [ ] **Faz 5** — Cila, örnek veri, demo hazırlığı
- [ ] **Faz 6** — Rapor + sunum

Detaylı yol haritası: [`docs/ROADMAP.md`](docs/ROADMAP.md)

---

## ⚠️ Sınırlılıklar (rapora yazılacak)

- Veri **sentetiktir**; gerçek saha verisiyle yeniden eğitim önerilir.
- Klasik yöntemler tanım gereği bazı gaz desenlerinde "N/A" döndürür; bu
  bir hata değil, yöntemin doğasıdır.
- Trend modülü doğrusal regresyona dayanır; daha uzun geçmişte doğrusal
  olmayan modeller (ör. üstel) daha iyi olabilir.
