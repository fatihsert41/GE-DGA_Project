"""Model inceleme kuyruğunun veritabanı tarafı. (Faz 12.3)

``core/expert_label.py`` kuralları tutar (saf); bu modül onları ölçüm
kayıtlarına, klasik yöntemlere ve modele bağlar.
"""
from __future__ import annotations

import csv
import io
from typing import Dict, List, Optional, Set, Tuple

from .. import database
from ..core import assets
from ..core import expert_label as core_label
from ..core.classify import consensus
from ..core.gases import FAULT_LABELS_TR, GASES
from ..ml import predictor
from .diagnosis import CONFIDENCE_THRESHOLD

FOLDERS = ("pending", "labeled", "all")


def _latest_ids() -> Set[int]:
    """Her trafonun EN SON ölçümünün id'si — bugünkü kararı etkileyenler."""
    return {int(r["measurement_id"]) for r in database.latest_measurements()
            if r.get("measurement_id") is not None}


def _item(m: Dict[str, object], label: Optional[Dict[str, object]],
          latest_ids: Set[int],
          transformers: Dict[str, Dict[str, object]]) -> Dict[str, object]:
    tid = str(m["transformer_id"])
    if tid not in transformers:
        transformers[tid] = database.get_transformer(tid) or {}
    record = transformers[tid]
    cls = assets.get(record.get("asset_class"))  # type: ignore[arg-type]
    conf = m.get("confidence")
    pred = m.get("prediction")

    return {
        "measurement_id": m["id"],
        "transformer_id": tid,
        "transformer_name": record.get("name"),
        "asset_class": cls["code"],
        "asset_weight": cls["weight"],
        "sampled_at": m.get("sampled_at"),
        "model_prediction": pred,
        "model_prediction_tr": FAULT_LABELS_TR.get(str(pred), pred),
        "confidence": conf,
        "low_confidence": conf is not None and float(conf) < CONFIDENCE_THRESHOLD,  # type: ignore[arg-type]
        # Son ölçüm mü? Uzman kararı yalnızca SON ölçümde bugünkü bakım
        # kararını değiştirir; eskiler veri seti için değerlidir.
        "is_latest": int(m["id"]) in latest_ids,  # type: ignore[arg-type]
        "risk_level": m.get("risk_level"),
        "recorded_by_id": m.get("recorded_by_id"),
        "recorded_by_name": m.get("recorded_by_name"),
        "expert_label": label.get("expert_label") if label else None,
        "expert_label_tr": (core_label.LABELS_TR.get(str(label.get("expert_label")))
                            if label else None),
        "agrees": bool(label.get("agrees")) if label else None,
        "note": label.get("note") if label else None,
        "labeled_by_id": label.get("labeled_by_id") if label else None,
        "labeled_by_name": label.get("labeled_by_name") if label else None,
        "labeled_at": label.get("labeled_at") if label else None,
    }


def _pending(labels: Dict[int, Dict[str, object]]) -> List[Dict[str, object]]:
    return [m for m in database.low_confidence_measurements(CONFIDENCE_THRESHOLD)
            if int(m["id"]) not in labels]  # type: ignore[arg-type]


def queue(folder: str = "pending") -> Dict[str, object]:
    labels = database.expert_labels_by_measurement()
    latest_ids = _latest_ids()
    transformers: Dict[str, Dict[str, object]] = {}

    pending_rows = _pending(labels) if folder in ("pending", "all") else []
    labeled_rows = (database.measurements_by_ids(list(labels))
                    if folder in ("labeled", "all") else [])

    pending = [_item(m, None, latest_ids, transformers) for m in pending_rows]
    # Sıralama: önce trafonun SON ölçümü (bugünkü kararı etkiler), sonra
    # sonucu ağır varlık (LPT), sonra en yeni ölçüm. Python'un sıralaması
    # kararlı olduğu için önce ikincil ölçüte, sonra birincile göre dizilir.
    pending.sort(key=lambda i: str(i["sampled_at"] or ""), reverse=True)
    pending.sort(key=lambda i: (not i["is_latest"], -float(i["asset_weight"])))  # type: ignore[arg-type]

    labeled = [_item(m, labels.get(int(m["id"])), latest_ids, transformers)  # type: ignore[arg-type]
               for m in labeled_rows]
    labeled.sort(key=lambda i: str(i["labeled_at"] or ""), reverse=True)

    return {
        "folder": folder,
        "threshold": CONFIDENCE_THRESHOLD,
        "items": pending + labeled,
        "stats": stats(labels),
    }


def detail(measurement_id: int) -> Optional[Dict[str, object]]:
    """Mühendisin karar vermesi için gereken her şey."""
    m = database.get_measurement(measurement_id)
    if m is None:
        return None
    label = database.expert_label_for(measurement_id)
    gases = m["gases"]
    classical = consensus(gases)  # type: ignore[arg-type]

    # Güncel model: kayıttaki tahmin ESKİ bir model sürümünden gelmiş
    # olabilir. İkisini yan yana göstermek, "model değişince bu vaka ne
    # olurdu" sorusunu da cevaplar.
    current = None
    if predictor.is_ready():
        try:
            current = predictor.predict(gases)  # type: ignore[arg-type]
        except Exception:        # model dosyası bozuksa ekran yine açılsın
            current = None

    item = _item(m, label, _latest_ids(), {})
    return {
        **item,
        "gases": {g: gases.get(g) for g in GASES},  # type: ignore[union-attr]
        "classical": {
            "prediction": classical["prediction"],
            "confidence": classical["confidence"],
            "votes": classical["votes"],
        },
        "risk": classical["risk"],
        "current_model": current,
        "threshold": CONFIDENCE_THRESHOLD,
        "labels": [{"value": v, "label": core_label.LABELS_TR[v]}
                   for v in core_label.LABELS],
        "note_min_length": core_label.NOTE_MIN_LENGTH,
    }


def label(measurement_id: int, label_value: str, note: Optional[str],
          reviewer: Dict[str, str]) -> Tuple[int, object]:
    m = database.get_measurement(measurement_id)
    if m is None:
        return 404, f"Ölçüm bulunamadı: {measurement_id}"

    existing = database.expert_label_for(measurement_id)
    problem = core_label.validate_label(
        m, label_value, note, reviewer.get("employee_no", ""), existing)
    if problem:
        return problem

    clean_note = note.strip() if note and note.strip() else None
    saved = database.save_expert_label(m, label_value, clean_note, reviewer)
    if saved is None:
        # Benzersiz indeks ikinci kaydı reddetti: kontrol ile yazma arasında
        # başka bir mühendis etiketledi.
        return 409, "Bu ölçüm az önce başka bir mühendis tarafından etiketlendi."

    return 200, {"ok": True,
                 "item": _item(m, database.expert_label_for(measurement_id),
                               _latest_ids(), {})}


def stats(labels: Optional[Dict[int, Dict[str, object]]] = None) -> Dict[str, object]:
    labels = labels if labels is not None else database.expert_labels_by_measurement()
    result = core_label.agreement_stats(labels.values())
    result["pending"] = len(_pending(labels))
    result["threshold"] = CONFIDENCE_THRESHOLD
    return result


def dataset() -> List[Dict[str, object]]:
    """Uzman etiketli ölçümler — eğitim/değerlendirme verisi.

    "Belirlenemedi" etiketleri GİRMEZ: uzmanın emin olmadığı bir vakayı
    bir sınıfa yazmak, modele uydurulmuş bir cevap öğretmek olurdu.
    """
    rows: List[Dict[str, object]] = []
    for r in database.labeled_measurements():
        if not core_label.is_determined(r.get("expert_label")):  # type: ignore[arg-type]
            continue
        gases = r.get("gases") or {}
        rows.append({
            "measurement_id": r["measurement_id"],
            "transformer_id": r["transformer_id"],
            "sampled_at": r.get("sampled_at"),
            **{g: gases.get(g) for g in GASES},  # type: ignore[union-attr]
            "model_prediction": r.get("model_prediction"),
            "model_confidence": r.get("model_confidence"),
            "expert_label": r["expert_label"],
            "labeled_by_id": r.get("labeled_by_id"),
            "labeled_at": r.get("labeled_at"),
        })
    return rows


def dataset_csv() -> str:
    rows = dataset()
    columns = ["measurement_id", "transformer_id", "sampled_at", *GASES,
               "model_prediction", "model_confidence", "expert_label",
               "labeled_by_id", "labeled_at"]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()
