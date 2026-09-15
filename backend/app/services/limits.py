"""Varlığa özel eşiklerin veritabanı tarafı. (Faz 12.4)

``core/asset_limits.py`` kuralları tutar (saf); bu modül onları veritabanına
ve yağ değerlendirmesine bağlar. Aynı ayrım onay kuyruğunda
(``core/review`` / ``services/review``) da var.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Dict, List, Optional, Tuple

from .. import database
from ..core import asset_limits as core_limits
from ..core import oil_quality
from ..core import review as review_core

# Kuyruk klasörü → hangi durumlar listelenir (None = hepsi).
FOLDERS: Dict[str, Optional[List[str]]] = {
    core_limits.PENDING: [core_limits.PENDING],
    core_limits.ACTIVE: [core_limits.ACTIVE],
    "closed": [core_limits.REJECTED, core_limits.REVOKED, core_limits.EXPIRED],
    "all": None,
}


def today() -> date:
    """Takvim günü UTC'de: kayıt zaman damgaları da UTC tutuluyor."""
    return datetime.now(timezone.utc).date()


def expire() -> int:
    """Süresi dolan istisnaları kapatır; kaç kayıt kapandığını döner.

    Arka planda zamanlanmış bir iş YOK: süre kontrolü her okumada yapılır.
    Tek süreçli bir demo için bu yeterli ve daha önemlisi GÜVENLİ: zamanlayıcı
    çalışmasa bile süresi dolan istisna uygulanmaz, çünkü değerlendirme
    zaten tarih penceresine bakıyor (``core_limits.is_in_effect``). Bu
    fonksiyon yalnızca durum etiketini gerçeğe eşitler ve yeni öneriye
    yer açar.
    """
    return database.expire_limit_overrides(today().isoformat())


def _nameplate(transformer_id: str) -> Tuple[Optional[Dict], Dict]:
    record = database.get_transformer(transformer_id)
    return record, ((record or {}).get("nameplate") or {})


def _impact(row: Dict[str, object]) -> Optional[Dict[str, object]]:
    """Son geçerli yağ testi bu sınırlarla değerlendirilseydi ne olurdu?

    Onaylayan mühendisin asıl sorusu budur: "bu istisna neyi değiştirir?"
    Bir gevşetmenin şu an 'kötü' olan sonucu 'kabul'e çevirdiğini görmeden
    onaylamak, körlemesine onaylamaktır. Hesap VARSAYIMSALDIR: tarih
    penceresine bakılmaz, yalnızca sınırların etkisi gösterilir.
    """
    tid = str(row["transformer_id"])
    tests = [t for t in database.get_oil_tests(tid) if review_core.is_usable(t)]
    parameter = str(row["parameter"])
    if not tests:
        return None

    test = tests[-1]
    _, np = _nameplate(tid)
    kwargs = {"hv_kv": np.get("hv_kv"), "insulation_type": np.get("insulation_type")}
    standard = oil_quality.assess(test, **kwargs)  # type: ignore[arg-type]
    hypothetical = oil_quality.assess(test, overrides={parameter: row},  # type: ignore[arg-type]
                                      **kwargs)

    def param(result: Dict[str, object]) -> Dict[str, object]:
        return next(p for p in result["parameters"]  # type: ignore[union-attr]
                    if p["parameter"] == parameter)

    return {
        "test_id": test["id"],
        "sampled_at": test.get("sampled_at"),
        "value": param(standard).get("value"),
        "condition_standard": param(standard)["condition"],
        "condition_override": param(hypothetical)["condition"],
        "overall_standard": standard["overall"],
        "overall_override": hypothetical["overall"],
        "changes_verdict": standard["overall"] != hypothetical["overall"],
    }


def _item(row: Dict[str, object], names: Dict[str, Optional[str]]) -> Dict[str, object]:
    """Kuyruk satırı: kayıt + etiketler + trafo adı + etki önizlemesi."""
    item = core_limits.describe(row, today())
    tid = str(row["transformer_id"])
    if tid not in names:
        names[tid] = (database.get_transformer(tid) or {}).get("name")
    item["transformer_name"] = names[tid]
    item["impact"] = _impact(row)
    return item


def queue(folder: str = core_limits.PENDING) -> Dict[str, object]:
    """İstisna kuyruğu — klasöre göre."""
    expire()
    rows = database.list_limit_overrides(FOLDERS[folder])
    names: Dict[str, Optional[str]] = {}
    items = [_item(r, names) for r in rows]
    if folder == core_limits.PENDING:
        # Bekleyenler: en uzun bekleyen üstte.
        items.sort(key=lambda i: str(i.get("proposed_at") or ""))
    return {
        "folder": folder,
        "items": items,
        "counts": database.limit_override_counts(),
    }


def for_transformer(transformer_id: str) -> Optional[Dict[str, object]]:
    """Trafonun istisna geçmişi ve yürürlükteki istisnaları."""
    record, np = _nameplate(transformer_id)
    if record is None:
        return None
    expire()
    names: Dict[str, Optional[str]] = {transformer_id: record.get("name")}
    items = [_item(r, names)
             for r in database.list_limit_overrides(None, transformer_id)]
    vclass = oil_quality.voltage_class(np.get("hv_kv"))
    return {
        "transformer_id": transformer_id,
        # Öneri formu, istisnanın NEYİN yerine geçeceğini yazarken göstersin:
        # standart sınır trafonun gerilim sınıfına bağlı.
        "voltage_class": vclass,
        "standard_limits": {
            name: dict(zip(("good", "acceptable"),
                           core_limits.standard_limits(name, vclass)))
            for name in core_limits.OVERRIDABLE
        },
        "active": [i for i in items if i["status"] == core_limits.ACTIVE],
        "history": items,
    }


def propose(transformer_id: str, body: Dict[str, object],
            proposer: Dict[str, str]) -> Tuple[int, object]:
    """İstisna önerisi kaydeder. (HTTP kodu, gövde) döner."""
    record, np = _nameplate(transformer_id)
    if record is None:
        return 404, f"Trafo bulunamadı: {transformer_id}"

    expire()
    now = today()
    parameter = str(body.get("parameter") or "")
    vclass = oil_quality.voltage_class(np.get("hv_kv"))
    valid_from = body.get("valid_from") or now.isoformat()

    problem = core_limits.validate_proposal(
        parameter, body.get("good_limit"), body.get("acceptable_limit"),  # type: ignore[arg-type]
        vclass, valid_from, body.get("valid_until"),
        body.get("reason"), now)  # type: ignore[arg-type]
    if problem:
        return problem

    std_good, std_acceptable = core_limits.standard_limits(parameter, vclass)
    new_id = database.create_limit_override(transformer_id, {
        "parameter": parameter,
        "voltage_class": vclass,
        "good_limit": body["good_limit"],
        "acceptable_limit": body["acceptable_limit"],
        "standard_good_limit": std_good,
        "standard_acceptable_limit": std_acceptable,
        "valid_from": core_limits.parse_date(valid_from).isoformat(),        # type: ignore[union-attr]
        "valid_until": core_limits.parse_date(body["valid_until"]).isoformat(),  # type: ignore[union-attr]
        "reason": str(body["reason"]).strip(),
    }, proposer)

    if new_id is None:
        return 409, ("Bu trafoda bu parametre için zaten onay bekleyen ya da "
                     "yürürlükte bir istisna var. Önce onu sonuçlandırın ya "
                     "da geri çekin.")

    return 200, {"ok": True,
                 "item": _item(database.get_limit_override(new_id) or {}, {})}


def decide(override_id: int, decision: str, note: Optional[str],
           reviewer: Dict[str, str]) -> Tuple[int, object]:
    """Onayla / reddet. (HTTP kodu, gövde) döner."""
    expire()
    row = database.get_limit_override(override_id)
    if row is None:
        return 404, f"İstisna bulunamadı: {override_id}"

    problem = core_limits.validate_decision(
        row, decision, note, reviewer.get("employee_no", ""), today())
    if problem:
        return problem

    applied = database.decide_limit_override(
        override_id, core_limits.DECISIONS[decision],
        note.strip() if note and note.strip() else None, reviewer)
    if not applied:
        return 409, "Bu istisnaya az önce başka bir mühendis karar verdi."

    return 200, {"ok": True,
                 "item": _item(database.get_limit_override(override_id) or {}, {})}


def revoke(override_id: int, note: Optional[str],
           who: Dict[str, str]) -> Tuple[int, object]:
    """Yürürlükteki istisnayı geri çeker; standart eşik geri gelir."""
    expire()
    row = database.get_limit_override(override_id)
    if row is None:
        return 404, f"İstisna bulunamadı: {override_id}"

    problem = core_limits.validate_revoke(row, note)
    if problem:
        return problem

    applied = database.revoke_limit_override(override_id, str(note).strip(), who)
    if not applied:
        return 409, "Bu istisna az önce geri çekildi ya da süresi doldu."

    return 200, {"ok": True,
                 "item": _item(database.get_limit_override(override_id) or {}, {})}


def schema() -> Dict[str, object]:
    """Kurallar ve seçenekler — arayüz formu buradan beslenir."""
    return {
        "parameters": {
            name: {
                "label": oil_quality.LIMITS[name]["label"],
                "unit": oil_quality.LIMITS[name]["unit"],
                "direction": oil_quality.LIMITS[name]["direction"],
                "standard": oil_quality.LIMITS[name]["standard"],
                "thresholds": oil_quality.LIMITS[name]["thresholds"],
            }
            for name in core_limits.OVERRIDABLE
        },
        "not_overridable": core_limits.NOT_OVERRIDABLE,
        "voltage_classes": list(oil_quality.VOLTAGE_CLASSES),
        "statuses": core_limits.STATUS_LABELS,
        "decisions": list(core_limits.DECISIONS),
        "folders": list(FOLDERS),
        "reason_min_length": core_limits.REASON_MIN_LENGTH,
        "note_min_length": core_limits.NOTE_MIN_LENGTH,
        "max_duration_days": core_limits.MAX_DURATION_DAYS,
        "max_deviation_pct": round(core_limits.MAX_DEVIATION * 100),
    }
