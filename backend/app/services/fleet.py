"""Filo geneli özet (Faz 5.2).

database.latest_measurements() satırlarını dashboard'un beklediği iki
parçaya dönüştürür:
  * transformers - trafo başına tek kart verisi (son tanı + risk)
  * summary      - filo geneli sayımlar (risk ve arıza dağılımı)

Burada yeniden tahmin YAPILMAZ: tanı, ölçüm kaydedilirken zaten
services/diagnosis.py tarafından üretilip DB'ye yazılmıştır.
"""
from __future__ import annotations

from typing import Dict, List

from .. import database
from ..core.gases import (FAULT_FAMILY, FAULT_GROUP, FAULT_LABELS_TR,
                          SEVERE_FAULTS, total_combustible)
from ..core.risk import RISK_LEVELS_TR, RISK_ORDER
from .diagnosis import CONFIDENCE_THRESHOLD


def _to_card(row: Dict) -> Dict:
    """Tek bir DB satırını frontend'in göstereceği 'kart' sözlüğüne çevir."""
    gases = row.get("gases")
    has_data = gases is not None          # ölçümü olmayan trafo (LEFT JOIN)
    pred = row.get("prediction")
    level = row.get("risk_level")

    return {
        "id": row["transformer_id"],
        "name": row["transformer_name"],
        "location": row["location"],
        "measurement_count": row["measurement_count"],
        "has_data": has_data,
        "last_sampled_at": row.get("sampled_at"),
        "prediction": pred,
        "prediction_label": FAULT_LABELS_TR.get(pred) if pred else None,
        "prediction_group": FAULT_GROUP.get(pred) if pred else None,
        "prediction_family": FAULT_FAMILY.get(pred) if pred else None,
        "confidence": row.get("confidence"),
        # Ölçüm kaydedilirken saklanan güvenden yeniden hesaplanır; eşik
        # değişirse eski kayıtlar da yeni eşiğe göre değerlendirilir.
        "needs_review": bool(has_data and (row.get("confidence") or 0.0)
                             < CONFIDENCE_THRESHOLD),
        "severe": bool(pred in SEVERE_FAULTS),
        "risk_level": level,
        "risk_level_tr": RISK_LEVELS_TR.get(level) if level else None,
        "risk_condition": row.get("risk_condition"),
        "tdcg": round(total_combustible(gases), 1) if has_data else None,
        "gases": gases,
    }


def _severity_key(card: Dict) -> tuple:
    """En riskli trafo en üstte; eşitlik durumunda id'ye göre alfabetik."""
    return (-RISK_ORDER.get(card["risk_level"], 0), card["id"])


def build_overview(rows: List[Dict]) -> Dict:
    """Saf hesaplama: DB satırlarını özet + kart listesine çevirir.

    Veritabanına dokunmaz, bu yüzden sahte satırlarla test edilebilir.
    """
    cards: List[Dict] = [_to_card(r) for r in rows]
    cards.sort(key=_severity_key)

    measured = [c for c in cards if c["has_data"]]

    # Dağılımları SIFIRLA başlat: grafikte hiç 'critical' yoksa bile
    # anahtar var olsun ki frontend'in eksenleri/renkleri kaymasın.
    risk_distribution: Dict[str, int] = {lvl: 0 for lvl in RISK_LEVELS_TR}
    fault_distribution: Dict[str, int] = {}
    for c in measured:
        risk_distribution[c["risk_level"]] += 1
        fault_distribution[c["prediction"]] = (
            fault_distribution.get(c["prediction"], 0) + 1
        )

    needs_attention = [c for c in measured
                       if c["risk_level"] in ("high", "critical")]

    return {
        "summary": {
            "total": len(cards),
            "with_data": len(measured),
            "total_measurements": sum(c["measurement_count"] for c in cards),
            "risk_distribution": risk_distribution,
            "fault_distribution": fault_distribution,
            "needs_attention": len(needs_attention),
            "attention_ids": [c["id"] for c in needs_attention],
            "needs_review": sum(1 for c in measured if c["needs_review"]),
        },
        "transformers": cards,
    }


def overview() -> Dict:
    """I/O katmanı: satırları DB'den çeker, hesabı build_overview'a bırakır."""
    return build_overview(database.latest_measurements())
