"""Risk / condition assessment based on IEEE C57.104 concentration limits.

Independent of fault *type*: this answers "how urgent?" by counting how
many gases exceed their Condition-1 limit and where TDCG falls.
"""
from __future__ import annotations

from typing import Dict, List

from .gases import IEEE_CONDITION1_PPM, TDCG_LIMITS, total_combustible

# Condition -> (risk level, Turkish label, action).
_LEVELS = {
    1: ("low", "Düşük", "Normal işletme. Rutin izlemeye devam."),
    2: ("medium", "Orta", "Gaz üretimi normalin üstünde. Örnekleme sıklığını artır."),
    3: ("high", "Yüksek", "Belirgin arıza gelişimi. Detaylı inceleme planla."),
    4: ("critical", "Kritik", "İleri düzey arıza. Acil değerlendirme gerekli."),
}
# Public views of _LEVELS so other modules don't re-declare these strings.
RISK_LEVELS_TR: Dict[str, str] = {lvl: tr for lvl, tr, _ in _LEVELS.values()}
RISK_ORDER: Dict[str, int] = {lvl: cond for cond, (lvl, _, _) in _LEVELS.items()}


def _tdcg_condition(tdcg: float) -> int:
    if tdcg <= TDCG_LIMITS["C1"]:
        return 1
    if tdcg <= TDCG_LIMITS["C2"]:
        return 2
    if tdcg <= TDCG_LIMITS["C3"]:
        return 3
    return 4


def assess(g: Dict[str, float]) -> Dict[str, object]:
    exceeded: List[str] = [
        k for k, limit in IEEE_CONDITION1_PPM.items() if g.get(k, 0.0) > limit
    ]
    tdcg = total_combustible(g)
    tdcg_cond = _tdcg_condition(tdcg)

    # Condition is the worse of the TDCG bucket and the count of exceedances.
    by_count = 1
    if len(exceeded) >= 1:
        by_count = 2
    if len(exceeded) >= 3:
        by_count = 3
    if "C2H2" in exceeded or len(exceeded) >= 5:
        by_count = 4

    condition = max(tdcg_cond, by_count)
    level, level_tr, action = _LEVELS[condition]
    return {
        "condition": condition,
        "level": level,
        "level_tr": level_tr,
        "action": action,
        "tdcg": tdcg,
        "exceeded_gases": exceeded,
    }
