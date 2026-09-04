"""Time-series trend & predictive-maintenance module (Pillar C).

Given a transformer's historical measurements (timestamps + gases), fit a
simple per-gas linear trend, project it forward, and estimate how long
until each gas crosses its IEEE Condition-1 limit. The earliest crossing
is reported as the transformer's "time to critical".
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from ..core.gases import GASES, IEEE_CONDITION1_PPM


def _linfit(t: np.ndarray, y: np.ndarray) -> Dict[str, float]:
    """Least-squares slope/intercept with an R^2 goodness measure."""
    if len(t) < 2:
        return {"slope": 0.0, "intercept": float(y[-1]) if len(y) else 0.0,
                "r2": 0.0}
    slope, intercept = np.polyfit(t, y, 1)
    pred = slope * t + intercept
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1e-9
    return {"slope": float(slope), "intercept": float(intercept),
            "r2": max(0.0, 1.0 - ss_res / ss_tot)}


def _months_to_limit(fit: Dict[str, float], limit: float,
                     last_t: float) -> Optional[float]:
    slope = fit["slope"]
    current = slope * last_t + fit["intercept"]
    if current >= limit:
        return 0.0
    if slope <= 1e-6:  # flat or falling -> no crossing foreseen
        return None
    t_cross = (limit - fit["intercept"]) / slope
    delta = t_cross - last_t
    return float(delta) if delta > 0 else 0.0


def analyze_history(times: List[float], history: List[Dict[str, float]],
                    horizon: int = 6) -> Dict[str, object]:
    """Trend analysis over a transformer's measurement history.

    ``times`` are month indices (or any monotonic unit); ``history`` is the
    matching list of gas dicts. Returns per-gas trend, forecast points, and
    the estimated time-to-critical.
    """
    if not history:
        return {"available": False, "reason": "no history"}

    t = np.asarray(times, dtype=float)
    last_t = float(t[-1])
    per_gas: Dict[str, object] = {}
    soonest: Optional[float] = None
    driver: Optional[str] = None

    for gas in GASES:
        y = np.asarray([float(h.get(gas, 0.0)) for h in history])
        fit = _linfit(t, y)
        limit = IEEE_CONDITION1_PPM[gas]
        eta = _months_to_limit(fit, limit, last_t)
        forecast = [
            {"month": last_t + k,
             "value": round(float(fit["slope"] * (last_t + k) + fit["intercept"]), 2)}
            for k in range(1, horizon + 1)
        ]
        per_gas[gas] = {
            "slope": round(fit["slope"], 4),
            "r2": round(fit["r2"], 3),
            "current": round(float(y[-1]), 2),
            "limit": limit,
            "months_to_limit": (round(eta, 1) if eta is not None else None),
            "forecast": forecast,
        }
        if eta is not None and (soonest is None or eta < soonest):
            soonest, driver = eta, gas

    if soonest is None:
        status = "stable"
        message = "Belirgin bir kötüleşme eğilimi görünmüyor."
    elif soonest <= 0:
        status = "critical_soon"
        message = f"{driver} eşik değerini şimdiden aşmış durumda."
    elif soonest <= 3:
        status = "critical_soon"
        message = f"~{soonest:.0f} ay içinde {driver} eşiği aşabilir."
    elif soonest <= 12:
        status = "watch"
        message = f"~{soonest:.0f} ay içinde {driver} kritik seviyeye yaklaşıyor."
    else:
        status = "stable"
        message = f"Uzun vadede ({soonest:.0f}+ ay) {driver} izlenmeli."

    return {
        "available": True,
        "status": status,
        "message": message,
        "months_to_critical": (round(soonest, 1) if soonest is not None else None),
        "driver_gas": driver,
        "per_gas": per_gas,
    }
