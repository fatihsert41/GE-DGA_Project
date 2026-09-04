"""Aggregate the classical DGA methods into one consensus diagnosis.

Runs Duval, Rogers, IEC and Key Gas, then takes a majority vote over the
usable results. This consensus is both a standalone diagnosis and the
"classical" competitor in the ML-vs-classical comparison.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, List

from . import duval, iec_ratio, key_gas, rogers, risk

# Duval's DT (mixed) maps to the nearest actionable class for voting.
_NORMALISE = {"DT": "D1"}


def _clean(fault: str) -> str:
    return _NORMALISE.get(fault, fault)


def classical_methods(g: Dict[str, float]) -> Dict[str, object]:
    """Raw output of every classical method (for the /compare panel)."""
    return {
        "duval": duval.analyze(g),
        "rogers": rogers.analyze(g),
        "iec": iec_ratio.analyze(g),
        "key_gas": key_gas.analyze(g),
    }


def _votes(methods: Dict[str, object]) -> List[str]:
    votes: List[str] = []
    votes.append(_clean(str(methods["duval"]["zone"])))          # type: ignore[index]
    for m in ("rogers", "iec", "key_gas"):
        fault = _clean(str(methods[m]["fault"]))                  # type: ignore[index]
        if fault not in ("N/A", None, ""):
            votes.append(fault)
    return votes


def consensus(g: Dict[str, float]) -> Dict[str, object]:
    """Majority-vote consensus across classical methods + risk assessment."""
    methods = classical_methods(g)
    votes = _votes(methods)

    if not votes:
        prediction, confidence = "Normal", 0.0
    else:
        counts = Counter(votes)
        prediction, top = counts.most_common(1)[0]
        confidence = top / len(votes)

    return {
        "prediction": prediction,
        "confidence": round(confidence, 3),
        "votes": votes,
        "methods": methods,
        "risk": risk.assess(g),
    }
