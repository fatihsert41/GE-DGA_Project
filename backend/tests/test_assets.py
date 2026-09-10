"""Varlık sınıfları ve öncelik skoru (Faz 6.6)."""
from __future__ import annotations

from app.core import assets


def test_mva_bands_match_convention():
    """LPT eşiği 100 MVA (DOE tanımı), SPT 10 MVA altı."""
    assert assets.classify_by_mva(250) == "LPT"
    assert assets.classify_by_mva(100) == "LPT"      # sınır dahil
    assert assets.classify_by_mva(99.9) == "MPT"
    assert assets.classify_by_mva(10) == "MPT"
    assert assets.classify_by_mva(9.9) == "SPT"


def test_unknown_class_falls_back_instead_of_crashing():
    """Bozuk/eksik sınıf kodu sistemi durdurmamalı."""
    assert assets.get(None)["code"] == assets.DEFAULT_CLASS
    assert assets.get("")["code"] == assets.DEFAULT_CLASS
    assert assets.get("XYZ")["code"] == assets.DEFAULT_CLASS
    assert assets.get("lpt")["code"] == "LPT"        # küçük harf de geçer


def test_spt_is_discontinued_but_still_tracked():
    """Ürün hattı kalktı; saha üniteleri izlenmeye devam etmeli."""
    assert assets.ASSET_CLASSES["SPT"]["active"] is False
    assert assets.ASSET_CLASSES["SPT"]["sampling_months"] > 0
    assert assets.weight("SPT") > 0


def test_priority_lets_a_large_unit_outrank_a_smaller_critical_one():
    """Faz 6.6'nın çekirdek kuralı: risk = olasılık × SONUÇ.

    Kondisyon 3'teki bir LPT, kondisyon 4'teki bir MPT'nin önüne geçer.
    """
    lpt_high = assets.priority_score(3, "LPT")       # 3.0
    mpt_critical = assets.priority_score(4, "MPT")   # 2.8
    spt_critical = assets.priority_score(4, "SPT")   # 1.8
    assert lpt_high > mpt_critical > spt_critical


def test_priority_is_zero_without_a_condition():
    """Ölçümü olmayan trafo öncelik sıralamasında öne çıkmamalı."""
    assert assets.priority_score(None, "LPT") == 0.0
