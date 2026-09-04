"""IEC 60599 ratio method (Table A.1).

Three ratios -> discrete codes -> fault case. This is the reference
ratio interpretation in IEC 60599 and complements the Duval triangle.
"""
from __future__ import annotations

from typing import Dict

from .gases import safe_ratio


def _code_r1(r: float) -> str:  # C2H2 / C2H4
    if r < 0.1:
        return "<0.1"
    if r <= 3.0:
        return "0.1-3"
    return ">3"


def _code_r2(r: float) -> str:  # CH4 / H2
    if r < 0.1:
        return "<0.1"
    if r <= 1.0:
        return "0.1-1"
    return ">1"


def _code_r3(r: float) -> str:  # C2H4 / C2H6
    if r < 1.0:
        return "<1"
    if r <= 3.0:
        return "1-3"
    return ">3"


def analyze(g: Dict[str, float]) -> Dict[str, object]:
    r1 = safe_ratio(g.get("C2H2", 0.0), g.get("C2H4", 0.0))
    r2 = safe_ratio(g.get("CH4", 0.0), g.get("H2", 0.0))
    r3 = safe_ratio(g.get("C2H4", 0.0), g.get("C2H6", 0.0))
    c1, c2, c3 = _code_r1(r1), _code_r2(r2), _code_r3(r3)

    # IEC 60599 Table A.1 characteristic fault cases.
    fault = "N/A"
    if c2 == ">1" and c1 == "<0.1" and c3 == "<1":
        fault = "PD"
    elif c1 == ">3" and c2 == "0.1-1" and c3 == ">3":
        fault = "D1"
    elif c1 == "0.1-3" and c2 == "0.1-1" and c3 == ">3":
        fault = "D2"
    elif c1 == "<0.1" and c3 == "<1":
        fault = "T1"
    elif c1 == "<0.1" and c2 == ">1" and c3 == "1-3":
        fault = "T2"
    elif c1 == "<0.1" and c2 == ">1" and c3 == ">3":
        fault = "T3"

    return {
        "method": "IEC 60599 Ratios",
        "fault": fault,
        "codes": {"C2H2/C2H4": c1, "CH4/H2": c2, "C2H4/C2H6": c3},
        "ratios": {"C2H2/C2H4": r1, "CH4/H2": r2, "C2H4/C2H6": r3},
    }
