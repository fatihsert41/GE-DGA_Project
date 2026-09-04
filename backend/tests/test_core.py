"""Unit tests for the classical DGA engine and helpers."""
from __future__ import annotations

from app.core import duval, iec_ratio, key_gas, risk, rogers
from app.core.classify import consensus
from app.core.gases import key_ratios, total_combustible


def test_duval_percentages_sum_to_100():
    p = duval.percentages(50, 30, 20)
    assert abs(sum(p.values()) - 100.0) < 1e-6


def test_duval_arcing_zone_high_acetylene():
    # High acetylene + ethylene -> high-energy discharge (D2).
    assert duval.zone(ch4=20, c2h4=60, c2h2=60) == "D2"


def test_duval_thermal_zone_high_ethylene():
    # Ethylene dominant, ~no acetylene -> hot thermal (T3).
    assert duval.zone(ch4=50, c2h4=400, c2h2=1) == "T3"


def test_duval_pd_zone_methane_dominant():
    assert duval.zone(ch4=980, c2h4=5, c2h2=1) == "PD"


def test_duval_point_inside_unit_triangle():
    pt = duval.to_cartesian(duval.percentages(33, 33, 34))
    assert 0.0 <= pt["x"] <= 1.0
    assert 0.0 <= pt["y"] <= 1.0


def test_key_gas_acetylene_dominant_is_arcing():
    g = {"H2": 10, "CH4": 10, "C2H6": 5, "C2H4": 20, "C2H2": 200, "CO": 30}
    assert key_gas.analyze(g)["fault"] == "D2"


def test_rogers_returns_known_or_na():
    g = {"H2": 60, "CH4": 140, "C2H6": 110, "C2H4": 30, "C2H2": 0.5}
    out = rogers.analyze(g)
    assert out["fault"] in {"Normal", "PD", "D1", "D2", "T1", "T2", "T3", "N/A"}


def test_iec_ratio_shape():
    g = {"H2": 90, "CH4": 150, "C2H6": 90, "C2H4": 180, "C2H2": 1.5}
    out = iec_ratio.analyze(g)
    assert set(out["codes"]) == {"C2H2/C2H4", "CH4/H2", "C2H4/C2H6"}


def test_risk_flags_acetylene_as_critical():
    g = {"H2": 10, "CH4": 10, "C2H6": 5, "C2H4": 10, "C2H2": 60, "CO": 100,
         "CO2": 1000}
    out = risk.assess(g)
    assert out["condition"] == 4
    assert "C2H2" in out["exceeded_gases"]


def test_risk_normal_is_low():
    g = {"H2": 10, "CH4": 8, "C2H6": 5, "C2H4": 4, "C2H2": 0.2, "CO": 100,
         "CO2": 900}
    assert risk.assess(g)["condition"] == 1


def test_total_combustible_excludes_co2():
    g = {"H2": 1, "CH4": 1, "C2H6": 1, "C2H4": 1, "C2H2": 1, "CO": 1,
         "CO2": 9999}
    assert total_combustible(g) == 6.0


def test_key_ratios_no_zero_division():
    ratios = key_ratios({g: 0.0 for g in
                         ["H2", "CH4", "C2H6", "C2H4", "C2H2", "CO", "CO2"]})
    assert all(v == v for v in ratios.values())  # no NaN


def test_consensus_arcing_case():
    g = {"H2": 280, "CH4": 120, "C2H6": 40, "C2H4": 220, "C2H2": 240,
         "CO": 500, "CO2": 3200}
    out = consensus(g)
    assert out["prediction"] in {"D1", "D2"}
    assert 0.0 <= out["confidence"] <= 1.0
