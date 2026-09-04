"""Trend endpoints (Pillar C).

* POST /trend               - trend from a supplied list of samples.
* GET  /trend/{transformer} - trend from stored history for one asset.
* GET  /trend/demo/{class}  - synthetic aging series for demos.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import database
from ..core.gases import FAULT_CLASSES
from ..ml.synth import make_aging_series
from ..schemas import TrendRequest
from ..services.trend import analyze_history

router = APIRouter(prefix="/trend", tags=["trend"])


@router.post("")
def trend_from_samples(req: TrendRequest) -> dict:
    times = [s.month for s in req.samples]
    history = [s.gases.as_dict() for s in req.samples]
    return analyze_history(times, history, horizon=req.horizon)


@router.get("/demo/{fault_class}")
def trend_demo(fault_class: str, months: int = 24, horizon: int = 6) -> dict:
    if fault_class not in FAULT_CLASSES:
        raise HTTPException(status_code=400,
                            detail=f"Bilinmeyen sınıf: {fault_class}")
    df = make_aging_series(fault_class=fault_class, months=months)
    times = df["month"].tolist()
    history = [
        {k: float(row[k]) for k in df.columns if k != "month"}
        for _, row in df.iterrows()
    ]
    result = analyze_history(times, history, horizon=horizon)
    result["series"] = df.to_dict(orient="records")
    return result


@router.get("/{transformer_id}")
def trend_from_history(transformer_id: str, horizon: int = 6) -> dict:
    measurements = database.get_measurements(transformer_id)
    if not measurements:
        raise HTTPException(status_code=404,
                            detail="Bu trafo için ölçüm bulunamadı.")
    times = list(range(len(measurements)))
    history = [m["gases"] for m in measurements]
    result = analyze_history([float(t) for t in times], history, horizon=horizon)
    result["measurements"] = measurements
    return result
