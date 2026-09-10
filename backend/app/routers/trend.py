"""Trend endpoints (Pillar C).

* POST /trend               - trend from a supplied list of samples.
* GET  /trend/{transformer} - trend from stored history for one asset.
* GET  /trend/demo/{class}  - synthetic aging series for demos.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

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


# Ortalama ay uzunluğu (365.25 / 12). Eğim birimi "ppm/ay" olduğu için
# gün farkını aya çevirirken bu kullanılıyor.
_DAYS_PER_MONTH = 30.4375

# Trend için gereken en az ölçüm sayısı. Tek noktadan eğim çıkarılamaz;
# iki nokta ise gürültüye tamamen açıktır ve "3 ay sonra kritik" gibi
# güvenilmez bir sayı üretir.
_MIN_SAMPLES = 3


def _months_axis(measurements: List[dict]) -> Optional[List[float]]:
    """Ölçüm zaman damgalarını, ilk ölçümden itibaren AY cinsine çevirir.

    ÖNCEDEN BURADA ``range(len(measurements))`` VARDI — yani ölçüm SIRASI
    kullanılıyordu, gerçek zaman değil. Sonuç fiziksel olarak yanlıştı:
    bir gün arayla alınan iki numune ile bir ay arayla alınanlar aynı
    "kritik süre" değerini üretiyordu. Oysa aynı artışı bir günde gösteren
    gaz otuz kat hızlı üretiliyor demektir.

    Bozuk zaman damgası varsa None döner: yanlış eksenle hesap yapmaktansa
    hiç hesap yapmamak doğrudur.
    """
    stamps: List[datetime] = []
    for m in measurements:
        raw = m.get("sampled_at")
        if not raw:
            return None
        try:
            ts = datetime.fromisoformat(str(raw))
        except ValueError:
            return None
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        stamps.append(ts)

    first = stamps[0]
    return [(ts - first).total_seconds() / 86400.0 / _DAYS_PER_MONTH
            for ts in stamps]


@router.get("/{transformer_id}")
def trend_from_history(transformer_id: str, horizon: int = 6) -> dict:
    measurements = database.get_measurements(transformer_id)
    if not measurements:
        raise HTTPException(status_code=404,
                            detail="Bu trafo için ölçüm bulunamadı.")

    if len(measurements) < _MIN_SAMPLES:
        # Yetersiz veriyle sayı üretmek, olmayan bir kesinlik iddia etmektir.
        return {
            "available": False,
            "reason": "insufficient_history",
            "message": (f"Trend için en az {_MIN_SAMPLES} ölçüm gerekir; "
                        f"bu trafoda {len(measurements)} ölçüm var."),
            "n_measurements": len(measurements),
            "measurements": measurements,
        }

    times = _months_axis(measurements)
    if times is None:
        return {
            "available": False,
            "reason": "invalid_timestamps",
            "message": "Ölçüm zaman damgaları okunamadı; trend hesaplanamaz.",
            "measurements": measurements,
        }

    span = times[-1] - times[0]
    if span <= 0:
        return {
            "available": False,
            "reason": "zero_time_span",
            "message": "Tüm ölçümler aynı ana ait görünüyor; eğim hesaplanamaz.",
            "measurements": measurements,
        }

    history = [m["gases"] for m in measurements]
    result = analyze_history(times, history, horizon=horizon)

    # Zaman ekseninin gerçekten kullanıldığını ve hangi birimde olduğunu
    # cevapta görünür kıl: "3.0" sayısının neyin 3'ü olduğu belli olmalı.
    result["time_axis"] = {
        "unit": "months",
        "source": "sampled_at",
        "span_months": round(span, 2),
        "n_measurements": len(measurements),
        "mean_interval_days": round(
            span * _DAYS_PER_MONTH / max(len(measurements) - 1, 1), 1),
    }
    result["measurements"] = measurements
    return result
