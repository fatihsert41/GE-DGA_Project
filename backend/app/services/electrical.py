"""Elektriksel testlerin değerlendirilmesi. — Faz 8.6

Bu servis, ham ölçümleri **künyeyle birleştirerek** yorumlar — 8.3'teki
yağ servisiyle aynı desen, ama bağımlılık burada çok daha sıkı:

* **Beklenen sarım oranı künyeden gelir.** Gerilimler ve bağlantı grubu
  olmadan TTR ölçümü bir sayı yığınıdır; neyle karşılaştıracağımızı
  bilmeyiz.
* **Kademe pozisyonu beklentiyi kaydırır.** Aynı ölçüm, 0 kademede
  "arızalı", +3 kademede "kusursuz" olabilir.
* **Sargı malzemesi sıcaklık düzeltmesini değiştirir** (Cu 234.5,
  Al 225).

Yani Faz 8.1'de künyeyi toplamak burada üçüncü kez karşılığını veriyor
(8.3'te gerilim sınıfı ve kağıt tipi, 8.5'te varlık ağırlığı).
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .. import database
from ..core import electrical, nameplate


def _context(transformer_id: str) -> Dict[str, object]:
    """Değerlendirme için gereken künye bilgisi."""
    record = database.get_transformer(transformer_id) or {}
    np = record.get("nameplate") or {}
    return {
        "nameplate": np,
        "winding_material": np.get("winding_material") or "Cu",
        "rated_turns_ratio": nameplate.rated_turns_ratio(np),
        "tap_changer_type": np.get("tap_changer_type"),
        "tap_min": np.get("tap_min"),
        "tap_max": np.get("tap_max"),
    }


def expected_ratio(transformer_id: str,
                   tap: Optional[int] = None) -> Optional[float]:
    """Beklenen sarım oranı — kademe verilmişse ona göre."""
    np = (database.get_transformer(transformer_id) or {}).get("nameplate") or {}
    if tap is None:
        return nameplate.rated_turns_ratio(np)
    return nameplate.turns_ratio_at_tap(np, int(tap))


def assess_test(transformer_id: str,
                test: Dict[str, object]) -> Dict[str, object]:
    """Tek bir elektriksel testi künye bağlamıyla değerlendirir."""
    ctx = _context(transformer_id)
    tap = test.get("tap_position")
    exp = expected_ratio(transformer_id,
                         int(tap) if tap is not None else None)

    result = electrical.assess(
        test,
        expected_ratio=exp,
        winding_material=str(ctx["winding_material"]),
    )
    result["test"] = test
    result["context"] = {
        "rated_turns_ratio": ctx["rated_turns_ratio"],
        "expected_ratio_at_tap": exp,
        "tap_position": tap,
        "winding_material": ctx["winding_material"],
        "tap_changer_type": ctx["tap_changer_type"],
    }
    return result


def _summaries(transformer_id: str,
               tests: List[Dict[str, object]]) -> List[Dict[str, object]]:
    """Her testin kısa hükmü — geçmiş listesi için."""
    rows: List[Dict[str, object]] = []
    for t in tests:
        a = assess_test(transformer_id, t)
        ttr = a["sections"]["turns_ratio"]
        rows.append({
            "id": t["id"],
            "tested_at": t["tested_at"],
            "tested_by": t.get("tested_by"),
            "notes": t.get("notes"),
            "overall": a["overall"],
            "problems": a["problems"],
            "sections_measured": a["measured_count"],
            "data_suspect": bool(ttr.get("data_suspect")),
            "voided": bool(t.get("voided_at")),
            "void_reason": t.get("void_reason"),
        })
    return rows


def history(transformer_id: str) -> Dict[str, object]:
    """Trafonun tüm elektriksel testleri + geçerli en sonun değerlendirmesi.

    Geçersiz işaretlenmiş kayıtlar listede GÖRÜNÜR (gerekçesiyle) ama
    hüküm üretmez. Gizlemek yanlış olurdu: "ölçüm yapılmadı" ile
    "yapıldı ama hatalıydı" farklı bilgilerdir.
    """
    tests = database.get_electrical_tests(transformer_id)
    if not tests:
        return {"available": False, "reason": "no_electrical_tests",
                "message": "Bu trafo için elektriksel test kaydı yok.",
                "tests": []}

    valid = [t for t in tests if not t.get("voided_at")]
    if not valid:
        return {"available": False, "reason": "all_voided",
                "message": "Bu trafonun tüm test kayıtları geçersiz "
                           "işaretlenmiş; hüküm verilebilecek ölçüm yok.",
                "tests": tests,
                "summaries": _summaries(transformer_id, tests)}

    latest = assess_test(transformer_id, valid[-1])

    # Her testin HÜKMÜ de dönüyor, yalnızca sonuncusunun değil. Panel
    # önce sadece son testi gösteriyordu ve kullanıcı girdiği bir testin
    # sonucunu bir daha göremiyordu — geçmiş, sahada tam olarak
    # karşılaştırma yapmak için tutulur.
    summaries = _summaries(transformer_id, tests)
    # Tam değerlendirmeler de id'ye göre dönüyor. Her test için ayrı
    # istek atmak yerine hepsi tek cevapta: değerlendirme zaten burada
    # hesaplanıyor (özet için), ikinci kez hesaplatmanın anlamı yok.
    assessments: Dict[int, Dict[str, object]] = {
        int(t["id"]): assess_test(transformer_id, t) for t in tests
    }

    # Sargı direnci dengesizliğinin ZAMAN İÇİNDEKİ seyri, tek bir
    # ölçümden daha bilgilendiricidir: %1.8 tek başına "iyi"dir, ama iki
    # yılda %0.4'ten %1.8'e çıkmışsa gelişen bir sorun vardır.
    imbalance_series: List[Dict[str, object]] = []
    for t in valid:
        section = electrical.assess_winding_resistance(
            {ph: t.get(f"rw_{ph.lower()}_ohm") for ph in electrical.PHASES},
            temp_c=t.get("winding_temp_c"),
        )
        if section.get("available"):
            imbalance_series.append({
                "tested_at": t["tested_at"],
                "imbalance_pct": section["imbalance_pct"],
            })

    return {
        "available": True,
        "n_tests": len(tests),
        "n_valid": len(valid),
        "latest_valid_id": valid[-1]["id"],
        "tests": tests,
        "latest_assessment": latest,
        "summaries": summaries,
        "assessments": assessments,
        "imbalance_series": imbalance_series,
    }


def electrical_card(transformer_id: str,
                    test: Optional[Dict[str, object]]) -> Dict[str, object]:
    """Filo kartına eklenecek kısa özet (test yoksa da güvenli)."""
    if not test:
        return {"has_electrical_test": False, "electrical_overall": None,
                "electrical_tested_at": None, "electrical_problems": []}

    assessment = assess_test(transformer_id, test)
    return {
        "has_electrical_test": True,
        "electrical_overall": assessment["overall"],
        "electrical_tested_at": test.get("tested_at"),
        "electrical_problems": assessment["problems"],
    }


def fleet_summary() -> Dict[str, object]:
    """Filo geneli elektriksel test durumu — her trafonun son testi."""
    latest = database.latest_electrical_tests()

    rows: List[Dict[str, object]] = []
    for tid, test in latest.items():
        assessment = assess_test(tid, test)
        ttr = assessment["sections"]["turns_ratio"]
        rows.append({
            "transformer_id": tid,
            "tested_at": test["tested_at"],
            "overall": assessment["overall"],
            "problems": assessment["problems"],
            "ttr_overall": ttr.get("overall") if ttr.get("available") else None,
            "sections_measured": assessment["measured_count"],
        })

    counts = {c: 0 for c in electrical.CONDITIONS}
    for r in rows:
        counts[str(r["overall"])] = counts.get(str(r["overall"]), 0) + 1

    # Hiç test edilmemişler ayrıca sayılır: elektriksel test seyrek
    # yapıldığı için "veri yok" burada istisna değil, KURALDIR — ve
    # bunu görünür kılmak gerekir.
    all_ids = {t["id"] for t in database.list_transformers()}

    return {
        "tested": len(rows),
        "never_tested": sorted(all_ids - set(latest)),
        "condition_counts": counts,
        "items": sorted(rows, key=lambda r: str(r["transformer_id"])),
    }
