"""Feature engineering shared by training and inference.

Raw gas concentrations are augmented with the diagnostic ratios used by
the classical methods, so the ML model can exploit the same physics the
engineers rely on. A single ``build_features`` keeps train/serve identical.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd

from ..core.gases import GASES, safe_ratio

# Order matters: this list is the model's input contract.
RATIO_FEATURES: List[str] = [
    "C2H2/C2H4", "CH4/H2", "C2H4/C2H6", "C2H6/CH4", "CO2/CO",
]
FEATURE_NAMES: List[str] = [*GASES, *RATIO_FEATURES]


def _ratios(row: Dict[str, float]) -> Dict[str, float]:
    return {
        "C2H2/C2H4": safe_ratio(row.get("C2H2", 0.0), row.get("C2H4", 0.0)),
        "CH4/H2": safe_ratio(row.get("CH4", 0.0), row.get("H2", 0.0)),
        "C2H4/C2H6": safe_ratio(row.get("C2H4", 0.0), row.get("C2H6", 0.0)),
        "C2H6/CH4": safe_ratio(row.get("C2H6", 0.0), row.get("CH4", 0.0)),
        "CO2/CO": safe_ratio(row.get("CO2", 0.0), row.get("CO", 0.0)),
    }


def features_from_dict(g: Dict[str, float]) -> np.ndarray:
    """Single sample -> 1 x n_features array in FEATURE_NAMES order."""
    ratios = _ratios(g)
    values = [float(g.get(name, 0.0)) for name in GASES]
    values += [ratios[name] for name in RATIO_FEATURES]
    return pd.DataFrame([values], columns=FEATURE_NAMES)


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame of raw gases -> DataFrame with ratio columns appended."""
    out = df.copy()
    ratios = df.apply(lambda r: _ratios(r.to_dict()), axis=1, result_type="expand")
    for col in RATIO_FEATURES:
        out[col] = ratios[col]
    return out[FEATURE_NAMES]
