"""Filo özetinin toplama/sıralama mantığı (Faz 5.2)."""
from __future__ import annotations

from app.services.fleet import build_overview

_GASES = {"H2": 10.0, "CH4": 5.0, "C2H6": 2.0, "C2H4": 3.0,
          "C2H2": 0.0, "CO": 100.0, "CO2": 900.0}


def _row(tid: str, level: str, condition: int, pred: str, count: int = 3) -> dict:
    """database.latest_measurements() satırını taklit eden yardımcı."""
    return {
        "transformer_id": tid, "transformer_name": f"Trafo {tid}",
        "location": "Test", "measurement_id": 1,
        "sampled_at": "2026-01-01T00:00:00+00:00",
        "prediction": pred, "confidence": 0.9,
        "risk_level": level, "risk_condition": condition,
        "measurement_count": count, "gases": dict(_GASES),
    }


def test_overview_sorts_by_risk_and_aggregates():
    rows = [_row("TR-A", "low", 1, "Normal"),
            _row("TR-B", "critical", 4, "D2"),
            _row("TR-C", "high", 3, "T3")]
    o = build_overview(rows)

    # En riskli en üstte.
    assert [t["id"] for t in o["transformers"]] == ["TR-B", "TR-C", "TR-A"]

    s = o["summary"]
    assert s["total"] == 3 and s["with_data"] == 3
    assert s["total_measurements"] == 9
    # Boş seviyeler de anahtar olarak dönmeli (grafik sabitliği).
    assert s["risk_distribution"] == {"low": 1, "medium": 0, "high": 1, "critical": 1}
    assert s["needs_attention"] == 2
    assert s["attention_ids"] == ["TR-B", "TR-C"]


def test_overview_handles_transformer_without_measurements():
    empty = {
        "transformer_id": "TR-Z", "transformer_name": "Yeni Trafo",
        "location": "", "measurement_id": None, "sampled_at": None,
        "prediction": None, "confidence": None, "risk_level": None,
        "risk_condition": None, "measurement_count": 0, "gases": None,
    }
    card = build_overview([empty])["transformers"][0]
    assert card["has_data"] is False
    assert card["tdcg"] is None and card["prediction_label"] is None
