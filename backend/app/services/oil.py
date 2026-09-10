"""Yağ kalitesi testlerinin değerlendirilmesi. — Faz 8.3

Bu servis, ham test değerlerini künyeyle BİRLEŞTİREREK yorumlar:

* Eşikler **gerilim sınıfına** göre değişir → künyedeki ``hv_kv`` gerekir.
* Kağıt yaşlanma bağıntısı **kağıt tipine** göre sapar → ``insulation_type``
  gerekir.

Yani Faz 8.1'de eklenen künye burada karşılığını veriyor: aynı furan
değeri, kağıt tipi bilinmeden güvenle yorumlanamaz.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .. import database
from ..core import oil_quality


def _context(transformer_id: str) -> Dict[str, object]:
    """Değerlendirme için gereken künye bilgisi."""
    record = database.get_transformer(transformer_id) or {}
    np = record.get("nameplate") or {}
    return {
        "hv_kv": np.get("hv_kv"),
        "insulation_type": np.get("insulation_type"),
        "commissioned_at": np.get("commissioned_at"),
        "age_years": (record.get("derived") or {}).get("age_years"),
    }


def assess_test(transformer_id: str, test: Dict[str, object]
                ) -> Dict[str, object]:
    """Tek bir testi künye bağlamıyla değerlendirir."""
    ctx = _context(transformer_id)
    result = oil_quality.assess(
        test,
        hv_kv=ctx["hv_kv"],                     # type: ignore[arg-type]
        insulation_type=ctx["insulation_type"],  # type: ignore[arg-type]
    )
    result["test"] = test
    result["context"] = ctx
    return result


def history(transformer_id: str) -> Dict[str, object]:
    """Trafonun tüm yağ testleri + en sonun değerlendirmesi."""
    tests = database.get_oil_tests(transformer_id)
    if not tests:
        return {"available": False, "reason": "no_oil_tests",
                "message": "Bu trafo için yağ kalitesi testi kaydı yok.",
                "tests": []}

    latest = assess_test(transformer_id, tests[-1])

    # Kağıt bozunması geri DÖNÜŞSÜZDÜR: DP yalnızca düşer. İki ölçüm varsa
    # düşüş hızını göstermek, tek bir DP değerinden daha bilgilendiricidir.
    dp_series = [
        {"sampled_at": t["sampled_at"],
         "dp": oil_quality.estimate_dp(t.get("furan_2fal_mgl")).get("dp_estimate")}
        for t in tests
        if t.get("furan_2fal_mgl") is not None
    ]

    return {
        "available": True,
        "n_tests": len(tests),
        "tests": tests,
        "latest_assessment": latest,
        "dp_series": dp_series,
    }


def fleet_summary() -> Dict[str, object]:
    """Filo geneli yağ durumu — her trafonun son testi."""
    latest = database.latest_oil_tests()

    rows: List[Dict[str, object]] = []
    for tid, test in latest.items():
        assessment = assess_test(tid, test)
        paper = assessment["paper"]
        rows.append({
            "transformer_id": tid,
            "sampled_at": test["sampled_at"],
            "overall": assessment["overall"],
            "problems": assessment["problems"],
            "dp_estimate": paper.get("dp_estimate"),
            "paper_band": paper.get("band"),
            "life_consumed_pct": paper.get("life_consumed_pct"),
            "paper_reliable": paper.get("reliable"),
        })

    counts = {c: 0 for c in oil_quality.CONDITIONS}
    for r in rows:
        counts[str(r["overall"])] = counts.get(str(r["overall"]), 0) + 1

    # En yaşlı kağıt: yenileme planlamasının ilk bakacağı yer.
    aged = [r for r in rows if r["dp_estimate"] is not None]
    aged.sort(key=lambda r: r["dp_estimate"])  # type: ignore[arg-type,return-value]

    return {
        "tested": len(rows),
        "condition_counts": counts,
        "items": sorted(rows, key=lambda r: str(r["transformer_id"])),
        "most_aged_paper": aged[:3],
    }


def oil_card(transformer_id: str,
             test: Optional[Dict[str, object]]) -> Dict[str, object]:
    """Filo kartına eklenecek kısa yağ özeti (test yoksa da güvenli)."""
    if not test:
        return {"has_oil_test": False, "oil_overall": None,
                "dp_estimate": None, "paper_band": None,
                "life_consumed_pct": None}

    assessment = assess_test(transformer_id, test)
    paper = assessment["paper"]
    return {
        "has_oil_test": True,
        "oil_overall": assessment["overall"],
        "oil_sampled_at": test.get("sampled_at"),
        "dp_estimate": paper.get("dp_estimate"),
        "paper_band": paper.get("band"),
        "life_consumed_pct": paper.get("life_consumed_pct"),
        "paper_reliable": paper.get("reliable"),
    }
