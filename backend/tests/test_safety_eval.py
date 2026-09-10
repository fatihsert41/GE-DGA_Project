"""Emniyet ölçütlerinin mantığı (Faz 6.4)."""
from __future__ import annotations

import numpy as np

from app.core.gases import FAULT_CLASSES
from app.ml.safety_eval import FAMILY, SEVERE, _selective


def test_family_covers_every_class():
    """Her arıza sınıfının bir ailesi olmalı; yoksa ölçüt sessizce patlar."""
    assert set(FAULT_CLASSES) <= set(FAMILY)
    # DT (Duval'in karışık bölgesi) yedi sınıftan biri değil ama klasik
    # yöntemler onu üretebiliyor; ailesi "Belirsiz".
    assert FAMILY["DT"] == "Belirsiz"
    assert {FAMILY[c] for c in FAULT_CLASSES} == {"Normal", "Termal", "Deşarj"}
    assert SEVERE <= set(FAULT_CLASSES)


def test_selective_prediction_trades_coverage_for_accuracy():
    """Eşik yükseldikçe kapsama düşer, isabet düşmemeli."""
    y_true = ["Normal"] * 5 + ["D2"] * 5
    # İlk 5 doğru ve yüksek güvenli; son 5'in 3'ü yanlış ve düşük güvenli.
    y_pred = ["Normal"] * 5 + ["D2", "D2", "D1", "D1", "D1"]
    conf = np.array([0.95] * 5 + [0.95, 0.95, 0.55, 0.55, 0.55])

    rows = {r["threshold"]: r for r in _selective(y_true, y_pred, conf)}
    assert rows[0.0]["coverage"] == 1.0
    assert rows[0.9]["coverage"] == 0.7
    assert rows[0.9]["accuracy"] > rows[0.0]["accuracy"]


def test_selective_skips_empty_thresholds():
    """Hiçbir örneğin geçmediği eşik satır üretmemeli (sıfıra bölme)."""
    rows = _selective(["Normal"], ["Normal"], np.array([0.4]))
    assert all(r["threshold"] <= 0.4 for r in rows)
