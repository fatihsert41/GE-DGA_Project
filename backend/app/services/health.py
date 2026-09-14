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
from ..core import review as review_core
from . import electrical as electrical_service
from . import oil as oil_service
from . import components as component_service
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
             if review_core.is_usable(t)]
    oil = oil_service.oil_card(transformer_id, tests[-1] if tests else None)

    el_tests = [t for t in database.get_electrical_tests(transformer_id)
                if review_core.is_usable(t)]
    el = electrical_service.electrical_card(
        transformer_id, el_tests[-1] if el_tests else None)

    inspections = database.get_physical_inspections(transformer_id)
    phys = physical_service.physical_card(
        inspections[-1] if inspections else None)

    comp_tests = [t for t in database.get_component_tests(transformer_id)
                  if review_core.is_usable(t)]
    comp = component_service.component_card(
        transformer_id, comp_tests[-1] if comp_tests else None)

    cls = assets.get(record.get("asset_class"))
    result = health_index.compute(
        risk_condition=(latest_dga or {}).get("risk_condition"),
        oil_overall=oil.get("oil_overall"),
        paper=oil.get("paper"),
        electrical_overall=el.get("electrical_overall"),
        physical_overall=phys.get("physical_overall"),
        component_overall=comp.get("component_overall"),
        asset_weight=float(cls["weight"]),   # type: ignore[arg-type]
        # Onay bekleyen sonuç hesaba girer ama işaretlenir (Faz 12.2).
        unverified=review_core.unverified_dimensions({
            "oil": oil.get("oil_review_status"),
            "electrical": el.get("electrical_review_status"),
            "components": comp.get("component_review_status"),
        }),
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
            "component_tested_at": comp.get("component_tested_at"),
            "component_test_count": len(comp_tests),
        },
    }


def build_renewal_list(cards: list[Dict]) -> Dict[str, object]:
    """Saf hesap: HAZIR filo kartlarından yenileme listesini çıkarır.

    "Yenileme bütçesi hangi ünitelere gitmeli?" sorusunun cevabı —
    ACİLİYETE göre değil DURUMA göre sıralı.

    Neden ayrı ve saf? Önceden bu liste yalnızca ``fleet_health()`` içinde
    üretiliyordu ve o fonksiyon filoyu BAŞTAN hesaplıyordu. Yönetim ekranı
    hem ``/fleet/overview`` hem ``/health-index/fleet`` istediği için aynı
    filo her açılışta iki kez hesaplanıyordu. Artık ``build_overview``
    zaten elindeki kartlarla bu fonksiyonu çağırıyor; sıralama kuralı da
    tek yerde kalıyor.
    """
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

    return {"items": scored, "unknown": unknown}


def fleet_health() -> Dict[str, object]:
    """``/health-index/fleet`` uç noktası: yenileme listesi + filo özeti.

    Filo yalnızca BİR kez hesaplanır; istatistik ve liste aynı kartlardan
    gelir. Uç nokta API tüketicileri için duruyor, arayüz artık bu veriyi
    ``/fleet/overview`` içinden alıyor.
    """
    from . import fleet as fleet_service

    summary = fleet_service.overview()["summary"]
    return {
        "stats": summary["health"],
        **summary["renewal"],
        "dimensions": [health_index.DIMENSIONS[k]
                       for k in health_index.DIMENSION_ORDER],
    }
