"""Standards-based synthetic DGA data generator.

The project intentionally uses no proprietary field data. Instead we
synthesise labelled samples whose gas signatures follow the fault
characteristics defined by IEC 60599 and the Duval triangle, then label
each sample by the fault class that generated it (unambiguous ground
truth). This is a defensible, reproducible substitute for scarce field
data and is documented as such in the report.

Two products:
* ``make_dataset``       - i.i.d. labelled samples for model training.
* ``make_aging_series``  - one transformer's gases evolving over time,
                            used by the trend / predictive-maintenance module.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from ..core.gases import GASES

# Per-class gas *signature*: (median ppm, log-normal sigma) for each gas.
# Chosen so that the resulting ratios land in the correct IEC/Duval region
# for that fault class. CO/CO2 track cellulose involvement.
_PROFILES: Dict[str, Dict[str, Tuple[float, float]]] = {
    "Normal": {
        "H2": (15, 0.5), "CH4": (10, 0.5), "C2H6": (8, 0.5),
        "C2H4": (6, 0.5), "C2H2": (0.3, 0.6), "CO": (250, 0.4),
        "CO2": (2000, 0.3),
    },
    "PD": {  # partial discharge: hydrogen dominant
        "H2": (400, 0.5), "CH4": (60, 0.5), "C2H6": (15, 0.5),
        "C2H4": (8, 0.5), "C2H2": (1, 0.7), "CO": (300, 0.4),
        "CO2": (2500, 0.3),
    },
    "D1": {  # low-energy discharge: acetylene present, low ethylene
        "H2": (180, 0.5), "CH4": (90, 0.5), "C2H6": (25, 0.5),
        "C2H4": (40, 0.5), "C2H2": (90, 0.5), "CO": (350, 0.4),
        "CO2": (2600, 0.3),
    },
    "D2": {  # high-energy arcing: high acetylene + ethylene
        "H2": (280, 0.5), "CH4": (120, 0.5), "C2H6": (40, 0.5),
        "C2H4": (220, 0.5), "C2H2": (240, 0.5), "CO": (500, 0.4),
        "CO2": (3200, 0.3),
    },
    "T1": {  # thermal <300C: methane/ethane, cellulose (CO) elevated
        "H2": (60, 0.5), "CH4": (140, 0.5), "C2H6": (110, 0.5),
        "C2H4": (30, 0.5), "C2H2": (0.5, 0.6), "CO": (700, 0.4),
        "CO2": (4500, 0.3),
    },
    "T2": {  # thermal 300-700C: ethylene rising
        "H2": (90, 0.5), "CH4": (150, 0.5), "C2H6": (90, 0.5),
        "C2H4": (180, 0.5), "C2H2": (1.5, 0.6), "CO": (500, 0.4),
        "CO2": (3500, 0.3),
    },
    "T3": {  # thermal >700C: ethylene dominant
        "H2": (120, 0.5), "CH4": (200, 0.5), "C2H6": (70, 0.5),
        "C2H4": (520, 0.5), "C2H2": (4, 0.6), "CO": (450, 0.4),
        "CO2": (3300, 0.3),
    },
}

# Relative prevalence of each class (mild imbalance, like the field).
_CLASS_WEIGHTS = {
    "Normal": 0.24, "PD": 0.12, "D1": 0.12, "D2": 0.13,
    "T1": 0.13, "T2": 0.13, "T3": 0.13,
}


def _sample_gas(profile: Dict[str, Tuple[float, float]],
                rng: np.random.Generator) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for gas in GASES:
        median, sigma = profile[gas]
        # log-normal keeps values positive and right-skewed like real DGA.
        value = float(rng.lognormal(mean=np.log(median), sigma=sigma))
        out[gas] = round(value, 2)
    return out


def make_dataset(n: int = 4000, seed: int = 42) -> pd.DataFrame:
    """Return a DataFrame of ``n`` labelled samples (columns: gases + label)."""
    rng = np.random.default_rng(seed)
    classes = list(_CLASS_WEIGHTS)
    weights = np.array([_CLASS_WEIGHTS[c] for c in classes])
    weights /= weights.sum()

    rows: List[Dict[str, float]] = []
    labels = rng.choice(classes, size=n, p=weights)
    for label in labels:
        row = _sample_gas(_PROFILES[label], rng)
        row["label"] = label
        rows.append(row)
    return pd.DataFrame(rows, columns=[*GASES, "label"])


def make_aging_series(fault_class: str = "T2", months: int = 24,
                      seed: int = 7) -> pd.DataFrame:
    """Simulate one transformer degrading toward ``fault_class`` over time.

    Gases start near-normal and ramp (with noise) toward the target fault
    signature, giving the trend module a realistic worsening curve.
    """
    rng = np.random.default_rng(seed)
    start = _PROFILES["Normal"]
    end = _PROFILES[fault_class]
    rows: List[Dict[str, float]] = []
    for m in range(months):
        # non-linear (accelerating) progression
        t = (m / max(months - 1, 1)) ** 1.6
        row: Dict[str, float] = {"month": m}
        for gas in GASES:
            base = (1 - t) * start[gas][0] + t * end[gas][0]
            noise = rng.lognormal(mean=0.0, sigma=0.18)
            row[gas] = round(float(base * noise), 2)
        rows.append(row)
    return pd.DataFrame(rows, columns=["month", *GASES])
