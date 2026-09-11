"""Fiziksel gözlem turlarının değerlendirilmesi. — Faz 9.5

``core/physical`` saf hesaptır; bu modül onu veritabanına bağlar.
Aynı ayrım yağ ve elektriksel testlerde de var.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .. import database
from ..core import physical


def assess_inspection(record: Dict[str, object]) -> Dict[str, object]:
    """Bir gözlem kaydını değerlendirir."""
    result = physical.assess(record.get("observations") or {})
    result["inspected_at"] = record.get("inspected_at")
    result["notes"] = record.get("notes")
    result["recorded_by_name"] = record.get("recorded_by_name")
    result["recorded_by_id"] = record.get("recorded_by_id")
    result["id"] = record.get("id")
    return result


def history(transformer_id: str) -> Dict[str, object]:
    """Trafonun gözlem geçmişi + en sonun değerlendirmesi."""
    records = database.get_physical_inspections(transformer_id)
    if not records:
        return {"available": False, "reason": "no_inspections",
                "message": "Bu trafo için fiziksel gözlem kaydı yok.",
                "inspections": []}

    assessments = [assess_inspection(r) for r in records]
    return {
        "available": True,
        "n_inspections": len(records),
        "latest": assessments[-1],
        # Geçmiş turlar da değerlendirilmiş hâlde dönüyor: bir bulgunun
        # ne zaman ortaya çıktığı, bulgunun kendisi kadar bilgi taşır.
        # "Korozyon üç turdur var" ile "bu tur çıktı" farklı şeylerdir.
        "inspections": assessments,
    }


def physical_card(record: Optional[Dict[str, object]]) -> Dict[str, object]:
    """Filo kartına eklenecek kısa özet (gözlem yoksa da güvenli)."""
    if not record:
        return {"has_inspection": False, "physical_overall": None,
                "physical_inspected_at": None, "physical_findings": []}

    a = assess_inspection(record)
    if not a.get("available"):
        return {"has_inspection": False, "physical_overall": None,
                "physical_inspected_at": record.get("inspected_at"),
                "physical_findings": []}

    return {
        "has_inspection": True,
        "physical_overall": a["overall"],
        "physical_inspected_at": record.get("inspected_at"),
        "physical_findings": a["critical_findings"],
        "physical_coverage_pct": a["coverage_pct"],
    }


def fleet_summary() -> Dict[str, object]:
    """Filo geneli gözlem durumu."""
    latest = database.latest_physical_inspections()

    rows: List[Dict[str, object]] = []
    for tid, record in latest.items():
        a = assess_inspection(record)
        if not a.get("available"):
            continue
        rows.append({
            "transformer_id": tid,
            "inspected_at": record["inspected_at"],
            "overall": a["overall"],
            "problems": a["problems"],
            "critical_findings": a["critical_findings"],
            "coverage_pct": a["coverage_pct"],
        })

    counts: Dict[str, int] = {}
    for r in rows:
        counts[str(r["overall"])] = counts.get(str(r["overall"]), 0) + 1

    all_ids = {t["id"] for t in database.list_transformers()}
    return {
        "inspected": len(rows),
        "never_inspected": sorted(all_ids - set(latest)),
        "condition_counts": counts,
        "items": sorted(rows, key=lambda r: str(r["transformer_id"])),
    }
