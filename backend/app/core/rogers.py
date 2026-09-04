"""Rogers Ratio method (IEC 60599 four-ratio variant).

Encodes three ratios into discrete codes and maps the code triple to a
fault type. Returns "N/A" when the gas pattern falls outside the defined
code table (a genuine outcome of the method, not an error).
"""
from __future__ import annotations

from typing import Dict

from .gases import safe_ratio


def _code_c2h2_c2h4(r: float) -> int:
    if r < 0.1:
        return 0
    if r < 3.0:
        return 1
    return 2


def _code_ch4_h2(r: float) -> int:
    if r < 0.1:
        return 1
    if r < 1.0:
        return 0
    if r < 3.0:
        return 2
    return 2


def _code_c2h4_c2h6(r: float) -> int:
    if r < 1.0:
        return 0
    if r < 3.0:
        return 1
    return 2


def analyze(g: Dict[str, float]) -> Dict[str, object]:
    r1 = safe_ratio(g.get("C2H2", 0.0), g.get("C2H4", 0.0))
    r2 = safe_ratio(g.get("CH4", 0.0), g.get("H2", 0.0))
    r3 = safe_ratio(g.get("C2H4", 0.0), g.get("C2H6", 0.0))

    c1, c2, c3 = _code_c2h2_c2h4(r1), _code_ch4_h2(r2), _code_c2h4_c2h6(r3)

    # Rogers code table -> fault type.
    table = {
        (0, 0, 0): "Normal",
        (0, 1, 0): "PD",
        (1, 0, 0): "D2",
        (1, 1, 0): "D1",
        (0, 0, 1): "T1",
        (0, 0, 2): "T2",
        (0, 2, 2): "T3",
        (0, 2, 1): "T2",
        (0, 2, 0): "T1",
    }
    fault = table.get((c1, c2, c3), "N/A")
    return {
        "method": "Rogers Ratio",
        "fault": fault,
        "codes": {"C2H2/C2H4": c1, "CH4/H2": c2, "C2H4/C2H6": c3},
        "ratios": {"C2H2/C2H4": r1, "CH4/H2": r2, "C2H4/C2H6": r3},
    }
