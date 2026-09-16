"""FastAPI application entry point.

Run (from backend/):  uvicorn app.main:app --reload
Interactive docs:     http://localhost:8000/docs
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import auth, database
from .ml import predictor
from .routers import (compare, components, electrical, explain, fleet,
                      health_index, lifecycle, limits, model_reviews, oil,
                      physical, predict, reviews, schematic,
                      transformers, trend)
from .services import review as review_service

# Güvenlik sertleştirme: yanlış yapılandırmayla (üretimde anahtar yok ya da
# geliştirme anahtarı) servis HİÇ AÇILMAZ. Import anında çağrılıyor ki hata,
# ilk kimlikli isteğe kadar gizli kalmasın.
auth.validate_configuration()


def _cors_origins() -> list[str]:
    """İzin verilen tarayıcı kökenleri.

    Önceden ``["*"]`` idi: herhangi bir web sitesi, kullanıcının tarayıcısı
    üzerinden bu API'ye istek atabilirdi. Arayüz Vite vekili üzerinden AYNI
    kökenden geldiği için CORS'a aslında ihtiyacı yok; varsayılan yalnızca
    arayüzün adresi. Başka bir köken gerekirse ortam değişkeniyle eklenir.
    """
    # (16 Eyl) Vite artık TLS ile açılıyor; https:// köken varsayılana
    # eklendi. http:// olan duruyor: sertifikası olmayan bir bilgisayarda
    # dev sunucusu HTTP'ye düşüyor.
    raw = os.environ.get(
        "TRANSFORMERAI_CORS_ORIGINS",
        "https://localhost:5173,http://localhost:5173",
    )
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(
    title="TransformerAI - DGA Fault Prediction API",
    description=(
        "Trafo yalıtım yağı çözünmüş gaz analizi (DGA) ile arıza tahmini. "
        "Klasik yöntemler (Duval, Rogers, IEC, Key Gas), makine öğrenmesi, "
        "açıklanabilirlik (SHAP) ve trend tahmini."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predict.router)
app.include_router(compare.router)
app.include_router(explain.router)
app.include_router(trend.router)
app.include_router(transformers.router)
app.include_router(fleet.router)
app.include_router(oil.router)
app.include_router(health_index.router)
app.include_router(electrical.router)
app.include_router(lifecycle.router)
app.include_router(physical.router)
app.include_router(components.router)
app.include_router(schematic.router)
app.include_router(reviews.router)
app.include_router(model_reviews.router)
app.include_router(limits.router)


@app.on_event("startup")
def _startup() -> None:
    database.init_db()
    # Faz 12.2: onay sütunundan ÖNCE kaydedilmiş testleri bir kez
    # sınıflandır (sınır dışı olanlar mühendis kuyruğuna düşer).
    # Yinelenebilir: yalnızca durumu boş satırlara dokunur.
    review_service.backfill()
    if auth.using_development_secret():
        print("[UYARI] Belirtec imzasi GELISTIRME anahtariyla dogrulaniyor; "
              "bu anahtar kaynak kodda ve GIZLI DEGILDIR.")


@app.get("/", tags=["meta"])
def root() -> dict:
    return {
        "name": "TransformerAI DGA API",
        "version": app.version,
        "model_trained": predictor.is_ready(),
        "model_name": predictor.model_name(),
        "docs": "/docs",
    }


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {"status": "ok", "model_trained": predictor.is_ready()}
