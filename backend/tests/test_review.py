"""Uzman incelemesi kararı (Faz 6.5)."""
from __future__ import annotations

from app.services.diagnosis import CONFIDENCE_THRESHOLD, _review


def test_confident_ordinary_diagnosis_needs_no_review():
    r = _review("T1", 0.97)
    assert r["needed"] is False
    assert r["reasons"] == []
    assert r["severe"] is False


def test_low_confidence_triggers_review():
    r = _review("T2", CONFIDENCE_THRESHOLD - 0.01)
    assert r["needed"] is True
    assert "kararsız" in r["reasons"][0]


def test_severe_is_a_separate_signal_not_an_uncertainty_reason():
    """D2 aciliyet bildirir; model emin olduğu sürece 'kararsız' demez.

    İkisini karıştırmak uyarıyı değersizleştirirdi: her ark tespitinde
    'model emin değil' demek yanlış olurdu.
    """
    r = _review("D2", 0.99)
    assert r["severe"] is True
    assert r["needed"] is False


def test_severe_and_unsure_can_coexist():
    r = _review("D2", 0.40)
    assert r["severe"] is True and r["needed"] is True
