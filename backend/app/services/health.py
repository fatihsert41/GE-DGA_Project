"""Tek trafonun sağlık endeksi. — Faz 8.5

``core/health_index.py`` saf hesaptır; bu modül onu veritabanına bağlar:
son DGA ölçümünü ve son yağ testini bulur, künyeden gereken bağlamı
(gerilim sınıfı, kağıt tipi) alır ve hesabı çekirdeğe devreder.

Ayrım bilinçli: hesap I/O bilmeyen bir yerde durursa test edilebilir kalır.
Aynı ayrım ``services/fleet.py`` (build_overview / overview) ve .NET
tarafındaki ``WorkOrderPlanner`` için de yapılmıştı.
"""
from __future__ import annotations

from typing import Dict

from .. import database
from ..core import assets, health_index
from . import electrical as electrical_service
from . import oil as oil_service
from . import physical as physical_service


def transformer_health(transformer_id: str) -> Dict[str, object]:
    """Bir trafonun sağlık endeksini bileşenleriyle döndürür."""
    record = database.get_transformer(transformer_id)
    if record is None:
        return {"found": False}

    measurements = database.get_measurements(transformer_id)
    latest_dga = measurements[-1] if measurements else None

    # Geçersiz işaretlenmiş kayıtlar ATLANIR. Bunu unutmak, hatalı
    # olduğunu bildiğimiz bir ölçümün skoru bozmasına izin vermek olurdu
    # — geçersiz işaretlemenin tüm amacı tam olarak bunu engellemek.
    tests = [t for t in database.get_oil_tests(transformer_id)
             if not t.get("voided_at")]
    oil = oil_service.oil_card(transformer_id, tests[-1] if tests else None)

    el_tests = [t for t in database.get_electrical_tests(transformer_id)
                if not t.get("voided_at")]
    el = electrical_service.electrical_card(
        transformer_id, el_tests[-1] if el_tests else None)

    inspections = database.get_physical_inspections(transformer_id)
    phys = physical_service.physical_card(
        inspections[-1] if inspections else None)

    cls = assets.get(record.get("asset_class"))
    result = health_index.compute(
        risk_condition=(latest_dga or {}).get("risk_condition"),
        oil_overall=oil.get("oil_overall"),
        paper=oil.get("paper"),
        electrical_overall=el.get("electrical_overall"),
        physical_overall=phys.get("physical_overall"),
        asset_weight=float(cls["weight"]),   # type: ignore[arg-type]
    )

    return {
        "found": True,
        "transformer_id": transformer_id,
        "name": record.get("name"),
        "asset_class": cls["code"],
        "asset_class_name": cls["name_tr"],
        "health": result,
        # Skorun hangi ölçümlere dayandığı: "ne zaman ölçüldü" sorusu,
        # skorun kendisi kadar önemlidir. Üç yıl önceki bir yağ testine
        # dayanan "iyi" ile geçen ayki "iyi" aynı şey değildir.
        "sources": {
            "dga_sampled_at": (latest_dga or {}).get("sampled_at"),
            "dga_prediction": (latest_dga or {}).get("prediction"),
            "oil_sampled_at": oil.get("oil_sampled_at"),
            "electrical_tested_at": el.get("electrical_tested_at"),
            "measurement_count": len(measurements),
            "oil_test_count": len(tests),
            "electrical_test_count": len(el_tests),
            "physical_inspected_at": phys.get("physical_inspected_at"),
            "inspection_count": len(inspections),
        },
    }


def fleet_health() -> Dict[str, object]:
    """Filo geneli sağlık listesi — en kötüden iyiye sıralı.

    Filo ekranı zaten her kartta skoru taşıyor; bu uç nokta "yenileme
    bütçesi hangi ünitelere gitmeli?" sorusunu tek listede cevaplamak
    için var ve ACİLİYETE göre değil DURUMA göre sıralar.
    """
    from . import fleet as fleet_service

    cards = fleet_service.overview()["transformers"]
    items = [
        {
            "transformer_id": c["id"],
            "name": c["name"],
            "asset_class": c["asset_class"],
            "score": c["health_score"],
            "band": c["health"].get("band"),
            "band_tr": c["health"].get("band_tr"),
            "coverage": c["health"].get("coverage", {}).get("level"),
            "critical_dimensions": c["health"].get("critical_dimensions", []),
            "renewal_priority": c["health"].get("renewal_priority"),
            # Ham skor da taşınıyor: tavan kuralı birden çok trafoyu aynı
            # değere (45.0) yığabiliyor ve sıralama bilgisi kayboluyor.
            # Tavan HÜKMÜ doğru — "bu trafo en azından incelenmeli" — ama
            # ikisi arasında hangisinin daha kötü durumda olduğunu ham
            # ortalama hâlâ biliyor.
            "raw_score": c["health"].get("raw_score"),
            "capped": c["health"].get("capped", False),
        }
        for c in cards
    ]

    # Skoru olmayanlar en SONA değil, ayrı bir kovaya: bilinmeyen durum
    # "iyi" de değildir "kötü" de. Listede görünsün ki gözden kaçmasın.
    scored = sorted([i for i in items if i["score"] is not None],
                    key=lambda i: (i["score"], i["raw_score"] or 0.0,
                                   i["transformer_id"]))
    unknown = sorted([i for i in items if i["score"] is None],
                     key=lambda i: str(i["transformer_id"]))

    return {
        "stats": health_index.fleet_stats([i["score"] for i in items]),
        "items": scored,
        "unknown": unknown,
        "dimensions": [health_index.DIMENSIONS[k]
                       for k in health_index.DIMENSION_ORDER],
    }
