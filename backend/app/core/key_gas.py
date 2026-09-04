"""Key Gas method (IEEE C57.104).

Identifies the dominant combustible gas and maps it to the fault type it
most characteristically indicates.
"""
from __future__ import annotations

from typing import Dict

# Dominant gas -> characteristic fault.
_KEY = {
    "H2": "PD",       # hydrogen dominant -> partial discharge / corona
    "C2H2": "D2",     # acetylene dominant -> arcing
    "C2H4": "T3",     # ethylene dominant -> hot metal, high temp
    "CH4": "T1",      # methane dominant -> low-temp thermal
    "C2H6": "T1",     # ethane dominant -> low-temp thermal
    "CO": "T1",       # carbon monoxide dominant -> cellulose overheating
}


def analyze(g: Dict[str, float]) -> Dict[str, object]:
    combustible = {k: g.get(k, 0.0) for k in _KEY}
    total = sum(combustible.values())
    if total <= 0:
        return {"method": "Key Gas", "fault": "Normal", "key_gas": None,
                "share": 0.0}
    key = max(combustible, key=combustible.get)
    share = 100.0 * combustible[key] / total
    return {
        "method": "Key Gas",
        "fault": _KEY[key],
        "key_gas": key,
        "share": share,
    }
