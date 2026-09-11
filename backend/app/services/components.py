"""Bileşen testlerinin değerlendirilmesi. — Faz 9.4

Künye bağlamı gerekiyor: kademe değiştiricisi olmayan bir trafoda OLTC
bölümü değerlendirilmemeli. Aynı desen yağ (gerilim sınıfı) ve
elektriksel (sargı malzemesi) testlerinde de var.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .. import database
from ..core import components


def _has_tap_changer(transformer_id: str) -> bool:
    record = database.get_transformer(transformer_id) or {}
    np = record.get("nameplate") or {}
    return bool(np.get("tap_changer_type"))


def assess_test(transformer_id: str,
                test: Dict[str, object]) -> Dict[str, object]:
    result = components.assess(test, _has_tap_changer(transformer_id))
    result["test"] = test
    return result


def history(transformer_id: str) -> Dict[str, object]:
    tests = database.get_component_tests(transformer_id)
    if not tests:
        return {"available": False, "reason": "no_component_tests",
                "message": "Bu trafo için buşing/kademe testi kaydı yok.",
                "tests": []}

    latest = assess_test(transformer_id, tests[-1])

    # Kapasitans sapmasının SEYRİ, tek ölçümden çok daha bilgilendirici:
    # yüzde 3 sapma tek başına kabul edilebilir, ama iki yılda yüzde
    # 0.5'ten yüzde 3'e çıkmışsa katmanlar delinmeye devam ediyor
    # demektir. Süreç hızlanarak ilerler.
    deviation_series: List[Dict[str, object]] = []
    for t in tests:
        row: Dict[str, object] = {"tested_at": t["tested_at"]}
        section = components.assess_bushings(t)
        if section.get("available"):
            for ph in section["phases"]:
                row[str(ph["phase"])] = ph["deviation_pct"]
            deviation_series.append(row)

    return {
        "available": True,
        "n_tests": len(tests),
        "tests": tests,
        "latest_assessment": latest,
        "deviation_series": deviation_series,
    }


def component_card(transformer_id: str,
                   test: Optional[Dict[str, object]]) -> Dict[str, object]:
    """Filo kartına eklenecek kısa özet (test yoksa da güvenli)."""
    if not test:
        return {"has_component_test": False, "component_overall": None,
                "component_tested_at": None, "component_problems": []}

    a = assess_test(transformer_id, test)
    return {
        "has_component_test": True,
        "component_overall": a["overall"],
        "component_tested_at": test.get("tested_at"),
        "component_problems": a["problems"],
    }


def fleet_summary() -> Dict[str, object]:
    """Filo geneli bileşen durumu + hiç test edilmemişler."""
    latest = database.latest_component_tests()

    rows: List[Dict[str, object]] = []
    for tid, test in latest.items():
        a = assess_test(tid, test)
        rows.append({
            "transformer_id": tid,
            "tested_at": test["tested_at"],
            "overall": a["overall"],
            "problems": a["problems"],
            "sections_measured": a["measured_count"],
        })

    counts: Dict[str, int] = {}
    for r in rows:
        counts[str(r["overall"])] = counts.get(str(r["overall"]), 0) + 1

    all_ids = {t["id"] for t in database.list_transformers()}
    return {
        "tested": len(rows),
        "never_tested": sorted(all_ids - set(latest)),
        "condition_counts": counts,
        "items": sorted(rows, key=lambda r: str(r["transformer_id"])),
    }
