"""Test onay akışının veritabanı tarafı. (Faz 12.2)

``core/review.py`` kuralları tutar (saf); bu modül onları veritabanına
ve test değerlendirme servislerine bağlar. Aynı ayrım sağlık endeksinde
(``core/health_index`` / ``services/health``) de var.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Tuple

from .. import database
from ..core import assets
from ..core import review as core_review
from . import components as component_service
from . import electrical as electrical_service
from . import oil as oil_service

_ASSESSORS: Dict[str, Callable[[str, Dict[str, object]], Dict[str, object]]] = {
    "oil": oil_service.assess_test,
    "electrical": electrical_service.assess_test,
    "components": component_service.assess_test,
}

# Kuyruk klasörü → hangi durumlar listelenir.
FOLDERS: Dict[str, List[str]] = {
    core_review.PENDING: [core_review.PENDING],
    core_review.RETEST: [core_review.RETEST],
    core_review.APPROVED: [core_review.APPROVED],
    core_review.REJECTED: [core_review.REJECTED],
    "all": [core_review.PENDING, core_review.RETEST,
            core_review.APPROVED, core_review.REJECTED],
}


def _table(kind: str) -> str:
    return str(core_review.KINDS[kind]["table"])


def classify(kind: str, transformer_id: str, test_id: int) -> Optional[str]:
    """Yeni (ya da henüz sınıflandırılmamış) bir testin onay durumunu belirler."""
    row = database.get_test_row(_table(kind), test_id)
    if row is None:
        return None
    assessment = _ASSESSORS[kind](transformer_id, row)
    status = core_review.initial_status(assessment.get("overall"))  # type: ignore[arg-type]
    database.set_review_status(_table(kind), test_id, status)
    return status


def backfill() -> int:
    """Onay sütunu eklenmeden ÖNCE kaydedilmiş testleri sınıflandırır.

    Uygulama açılışında çalışır ve yinelenebilir: yalnızca durumu boş
    (NULL) olan satırlara dokunur, ikinci çalıştırmada 0 döner. Böylece
    mevcut veritabanında sınır dışı çıkmış eski testler de kuyruğa düşer —
    özellik yalnızca bundan sonra girilen testlerde çalışsaydı demo
    filoda hiç görünmezdi.
    """
    count = 0
    for kind in core_review.KINDS:
        for row in database.tests_without_review_status(_table(kind)):
            classify(kind, str(row["transformer_id"]), int(row["id"]))  # type: ignore[arg-type]
            count += 1
    return count


def _days_since(iso: Optional[str]) -> Optional[int]:
    if not iso:
        return None
    try:
        ts = datetime.fromisoformat(str(iso))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - ts).days)


def _item(kind: str, row: Dict[str, object],
          transformers: Dict[str, Dict[str, object]]) -> Dict[str, object]:
    """Kuyruk satırı: testin kendisi + hükmü + onay bilgisi."""
    spec = core_review.KINDS[kind]
    tid = str(row["transformer_id"])
    if tid not in transformers:
        transformers[tid] = database.get_transformer(tid) or {}
    record = transformers[tid]
    assessment = _ASSESSORS[kind](tid, row)
    status = row.get("review_status")
    cls = assets.get(record.get("asset_class"))  # type: ignore[arg-type]

    return {
        "kind": kind,
        "kind_label": spec["label"],
        "test_id": row["id"],
        "transformer_id": tid,
        "transformer_name": record.get("name"),
        "asset_class": cls["code"],
        "asset_weight": cls["weight"],
        "tested_at": row.get(str(spec["date_field"])),
        "overall": assessment.get("overall"),
        "problems": assessment.get("problems") or [],
        "recorded_by_id": row.get("recorded_by_id"),
        "recorded_by_name": row.get("recorded_by_name"),
        "created_at": row.get("created_at"),
        "waiting_days": _days_since(row.get("created_at")),  # type: ignore[arg-type]
        "review_status": status,
        "review_status_label": core_review.STATUS_LABELS.get(str(status), "—"),
        "reviewed_at": row.get("reviewed_at"),
        "reviewed_by_id": row.get("reviewed_by_id"),
        "reviewed_by_name": row.get("reviewed_by_name"),
        "review_note": row.get("review_note"),
        "voided": bool(row.get("voided_at")),
    }


def queue(folder: str = core_review.PENDING) -> Dict[str, object]:
    """Onay kuyruğu — klasöre göre."""
    statuses = FOLDERS[folder]
    transformers: Dict[str, Dict[str, object]] = {}
    items: List[Dict[str, object]] = []
    for kind in core_review.KINDS:
        for row in database.tests_by_review_status(_table(kind), statuses):
            items.append(_item(kind, row, transformers))

    # Bekleyenler: önce SONUCU AĞIR varlık (LPT), sonra en uzun bekleyen.
    # Faz 6.6'daki öncelik mantığı: aynı gün giren iki testten LPT'ninki
    # önce değerlendirilmeli. Karara bağlanmışlar: en yeni karar üstte.
    pending = [i for i in items if core_review.is_unverified(i["review_status"])]  # type: ignore[arg-type]
    decided = [i for i in items if i not in pending]
    pending.sort(key=lambda i: (-float(i["asset_weight"]),  # type: ignore[arg-type]
                                str(i["created_at"] or "")))
    decided.sort(key=lambda i: str(i["reviewed_at"] or ""), reverse=True)

    return {
        "folder": folder,
        "items": pending + decided,
        "counts": database.review_counts(),
    }


def decide(kind: str, test_id: int, decision: str, note: Optional[str],
           reviewer: Dict[str, str]) -> Tuple[int, object]:
    """Mühendis kararını uygular. (HTTP kodu, gövde) döner."""
    if kind not in core_review.KINDS:
        return 404, f"Bilinmeyen test türü: {kind}"

    row = database.get_test_row(_table(kind), test_id)
    if row is None:
        return 404, f"Test bulunamadı: {kind}/{test_id}"

    problem = core_review.validate_decision(
        row, decision, note, reviewer.get("employee_no", ""))
    if problem:
        return problem

    status = core_review.DECISIONS[decision]
    applied = database.record_review_decision(
        _table(kind), test_id, status,
        note.strip() if note and note.strip() else None, reviewer)
    if not applied:
        # Koşullu güncelleme 0 satır etkiledi: biz kontrol ettikten sonra
        # başka bir mühendis karar verdi. İkinci kararı sessizce yazmak,
        # birincisini ezmek olurdu.
        return 409, "Bu teste az önce başka bir mühendis karar verdi."

    updated = database.get_test_row(_table(kind), test_id) or row
    return 200, {"ok": True, "item": _item(kind, updated, {})}
