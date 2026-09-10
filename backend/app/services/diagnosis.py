"""Orchestrates a full diagnosis for one gas reading.

Combines the ML prediction (when a model is trained) with the classical
consensus and the IEEE risk assessment into a single response object used
by the /predict endpoint and by persistence.
"""
from __future__ import annotations

from typing import Dict

from ..core import risk
from ..core.classify import consensus
from ..core.gases import (FAULT_FAMILY, FAULT_GROUP, FAULT_LABELS_TR,
                          SEVERE_FAULTS)
from ..ml import predictor

# Bu eşiğin altında model "emin değilim" sayılır ve vaka uzmana devredilir.
# Değer keyfi değil: gerçek veri üzerinde ölçüldü (Faz 6.4, safety_eval.py).
# Güven >= 0.90 olan vakalarda doğruluk 0.851'den 0.913'e çıkıyor; bunun
# bedeli vakaların ~%16'sını insana devretmek. Kaçırılan hata fark edilmeyen
# hatadır; devredilen vaka ise zaten uzman gözüne gidiyor.
CONFIDENCE_THRESHOLD = 0.90


def _review(prediction: str, confidence: float) -> Dict[str, object]:
    """Bu tanı insan gözü ister mi?

    Tek ölçüt modelin kendi güveni — ve bu seçim ölçülerek yapıldı.
    Gerçek test setinde (n=592, genel doğruluk %85):

    * güven < 0.90 olan vakalar: tetiklenme %16, o vakalarda doğruluk **%54**
      (tetiklenmeyenlerde %91). Yani eşik gerçekten zor vakaları ayıklıyor.

    İlk tasarımda "ML ve klasik yöntemler ayrışıyor" da bir tetikleyiciydi.
    Ölçünce ELENDİ: %45 tetikleniyor ve tetiklendiğinde modelin doğruluğu
    **%92** (tetiklenmediğinde %80). Yani ayrışma modelin değil, klasik
    motorun zayıflığını gösteriyor — üstelik her şeyi işaretleyen bir uyarı
    hiçbir şeyi işaretlememekle aynıdır (alarm yorgunluğu).

    Ciddi arıza (D2/T3) ayrı bir kavramdır: belirsizlik değil ACİLİYET
    bildirir, bu yüzden ``severe`` alanında ayrı taşınır.
    """
    reasons = []
    if confidence < CONFIDENCE_THRESHOLD:
        reasons.append(
            f"Model kararsız (güven %{confidence * 100:.0f}, "
            f"eşik %{CONFIDENCE_THRESHOLD * 100:.0f}). "
            f"Bu güven aralığındaki tahminlerin doğruluğu belirgin düşük.")

    return {
        "needed": bool(reasons),
        "reasons": reasons,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "severe": prediction in SEVERE_FAULTS,
    }


def diagnose(gases: Dict[str, float]) -> Dict[str, object]:
    classical = consensus(gases)
    risk_info = classical["risk"]

    if predictor.is_ready():
        ml = predictor.predict(gases)
        prediction = ml["prediction"]
        confidence = ml["confidence"]
        source = "ml"
    else:  # graceful fallback before training
        ml = None
        prediction = classical["prediction"]
        confidence = classical["confidence"]
        source = "classical"

    agreement = (ml is not None
                 and ml["prediction"] == classical["prediction"])

    return {
        "prediction": prediction,
        "prediction_label": FAULT_LABELS_TR.get(prediction, prediction),
        "prediction_group": FAULT_GROUP.get(prediction, "Belirsiz"),
        # Aile = eylem seviyesi. Mühendisin ilk bakacağı şey alt tip değil,
        # "termal mi deşarj mı" sorusudur; yapılacak iş buna göre belirlenir.
        "prediction_family": FAULT_FAMILY.get(prediction, "Belirsiz"),
        "confidence": confidence,
        "source": source,
        "ml": ml,
        "classical": {
            "prediction": classical["prediction"],
            "confidence": classical["confidence"],
            "votes": classical["votes"],
        },
        "agreement": agreement,
        "risk": risk_info,
        "review": _review(prediction, float(confidence or 0.0)),
    }
