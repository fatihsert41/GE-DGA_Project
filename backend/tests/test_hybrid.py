"""Klasik indikatör özellikleri (Faz 6.3)."""
from __future__ import annotations

import pandas as pd

from app.core.gases import FAULT_CLASSES
from app.ml.hybrid import (HYBRID_FEATURE_NAMES, INDICATOR_NAMES,
                           build_hybrid_features, classical_indicators)

_ARC = {"H2": 280, "CH4": 120, "C2H6": 40, "C2H4": 220, "C2H2": 240}
_THERMAL = {"H2": 120, "CH4": 200, "C2H6": 70, "C2H4": 520, "C2H2": 4}


def test_indicators_are_complete_and_numeric():
    ind = classical_indicators(_ARC)
    assert set(ind) == set(INDICATOR_NAMES)
    assert all(isinstance(v, float) for v in ind.values())


def test_duval_percentages_are_scale_invariant():
    """Duval koordinatları oransaldır: numuneyi 10 katına çıkarmak
    arıza tipini değiştirmemeli."""
    a = classical_indicators(_ARC)
    b = classical_indicators({k: v * 10 for k, v in _ARC.items()})
    for key in ("pct_CH4", "pct_C2H4", "pct_C2H2", "duval_code"):
        assert abs(a[key] - b[key]) < 1e-6


def test_method_codes_are_valid_class_indices():
    """Karar kodları ya geçerli bir sınıf indeksi ya da -1 (kararsız)."""
    ind = classical_indicators(_THERMAL)
    for key in ("duval_code", "rogers_code", "iec_code", "keygas_code"):
        assert -1 <= ind[key] <= len(FAULT_CLASSES)


def test_build_hybrid_features_shape_and_order():
    df = pd.DataFrame([_ARC, _THERMAL])
    X = build_hybrid_features(df)
    assert list(X.columns) == HYBRID_FEATURE_NAMES
    assert len(X) == 2
    assert not X.isnull().any().any()
