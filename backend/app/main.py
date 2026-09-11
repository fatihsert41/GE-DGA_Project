"""FastAPI application entry point.

Run (from backend/):  uvicorn app.main:app --reload
Interactive docs:     http://localhost:8000/docs
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import database
from .ml import predictor
from .routers import (compare, electrical, explain, fleet, health_index,
                      oil, predict, transformers, trend)

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
    allow_origins=["*"],  # demo; restrict in production
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


@app.on_event("startup")
def _startup() -> None:
    database.init_db()


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
