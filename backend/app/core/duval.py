"""Duval Triangle 1 - the classic graphical DGA method.

Uses the three fault gases CH4, C2H4, C2H2. Their relative percentages
place the sample in one of seven zones. Boundaries follow M. Duval's
published Triangle 1 definition (IEEE Elec. Insul. Mag., 2002); the "DT"
zone captures mixtures of thermal and electrical faults.
"""
from __future__ import annotations

import math
from typing import Dict

# Cartesian vertices of the equilateral triangle used for plotting.
# Bottom-left = 100% CH4, bottom-right = 100% C2H4, top = 100% C2H2.
_V_CH4 = (0.0, 0.0)
_V_C2H4 = (1.0, 0.0)
_V_C2H2 = (0.5, math.sqrt(3) / 2)


def percentages(ch4: float, c2h4: float, c2h2: float) -> Dict[str, float]:
    """Relative % of the three fault gases (each in [0, 100])."""
    total = ch4 + c2h4 + c2h2
    if total <= 0:
        return {"CH4": 0.0, "C2H4": 0.0, "C2H2": 0.0}
    return {
        "CH4": 100.0 * ch4 / total,
        "C2H4": 100.0 * c2h4 / total,
        "C2H2": 100.0 * c2h2 / total,
    }


def to_cartesian(pct: Dict[str, float]) -> Dict[str, float]:
    """Barycentric (%CH4, %C2H4, %C2H2) -> (x, y) for the frontend plot."""
    a, b, c = pct["CH4"] / 100.0, pct["C2H4"] / 100.0, pct["C2H2"] / 100.0
    x = a * _V_CH4[0] + b * _V_C2H4[0] + c * _V_C2H2[0]
    y = a * _V_CH4[1] + b * _V_C2H4[1] + c * _V_C2H2[1]
    return {"x": x, "y": y}


def zone(ch4: float, c2h4: float, c2h2: float) -> str:
    """Return the Duval Triangle 1 zone code for the given gas amounts."""
    p = percentages(ch4, c2h4, c2h2)
    ch4_p, c2h4_p, c2h2_p = p["CH4"], p["C2H4"], p["C2H2"]

    # Boundaries per Duval Triangle 1.
    if ch4_p >= 98.0:
        return "PD"
    if c2h2_p >= 13.0 and c2h4_p <= 23.0:
        return "D1"
    if c2h2_p >= 13.0 and c2h4_p <= 40.0:
        return "D2"
    if c2h2_p >= 29.0 and c2h4_p > 40.0:
        return "D2"
    if c2h2_p < 15.0 and c2h4_p >= 50.0:
        return "T3"
    if c2h2_p < 4.0 and 20.0 <= c2h4_p < 50.0:
        return "T2"
    if c2h2_p < 4.0 and c2h4_p < 20.0:
        return "T1"
    # Mixture of electrical + thermal faults.
    return "DT"


def analyze(g: Dict[str, float]) -> Dict[str, object]:
    """Full Duval result: zone, percentages and plot coordinates."""
    ch4, c2h4, c2h2 = g.get("CH4", 0.0), g.get("C2H4", 0.0), g.get("C2H2", 0.0)
    pct = percentages(ch4, c2h4, c2h2)
    z = zone(ch4, c2h4, c2h2)
    return {
        "method": "Duval Triangle 1",
        "zone": z,
        "percentages": pct,
        "point": to_cartesian(pct),
        "applicable": (ch4 + c2h4 + c2h2) > 0,
    }
