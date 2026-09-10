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
from ..ml import calibration, predictor

# --- Güven eşiği: ÇALIŞMA NOKTASI vs ÖLÇÜM (düzeltme P0-4) ---------------
#
# Sistem bu eşiğin altında "emin değilim" der ve vakayı uzmana devreder.
#
# ⚠ Bu değerin kökeni Faz 6.4'te YANLIŞ kaydedilmişti: 0.90, gerçek veriyle
# eğitilmiş bir XGBoost modelinde ölçülmüştü ama hizmet veren model sentetik
# veriyle eğitilmiş bir RandomForest. Dış inceleme bunu haklı olarak P0
# saydı. Artık eşik hizmet veren modelin KENDİ test kümesinde ölçülüyor
# (ml/calibration.py) ve sonuç modelin yanında saklanıyor.
#
# ÖLÇÜM SONUCU (RandomForest, field_like sentetik, 1000 örnek):
#   ECE 0.021 -> model kendi alanında İYİ KALİBRE
#   %90 isabet için yeterli eşik: 0.50 (kapsama %98)
#
# ÇALIŞMA NOKTASI ise bilinçli olarak daha yüksek: 0.90.
# Neden ölçülenden yüksek? Çünkü ölçüm SENTETİK alanda yapıldı ve Faz 6'da
# bu modelin gerçek veriye aktarımının zayıf olduğunu ölçtük (F1 0.96 -> 0.58).
# Kendi dağılımında dürüst olmak, farklı bir dağılımda dürüst olmayı
# garanti etmez. Aradaki fark bir EMNİYET PAYIDIR ve saklanmıyor, cevapta
# gerekçesiyle birlikte bildiriliyor.
#
# 0.90'da sentetik alanda: kapsama %63, üstünde doğruluk %98.9, altında %76.
CONFIDENCE_THRESHOLD = 0.90

_SAFETY_MARGIN_REASON = (
    "Çalışma eşiği ölçülen eşikten yüksek tutuluyor: ölçüm sentetik alanda "
    "yapıldı ve bu modelin gerçek veriye aktarımı zayıf (Faz 6). Aradaki "
    "fark bilinçli bir emniyet payıdır."
)


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
    info = predictor.model_info()
    measurement = (info.get("threshold") or {}) if info.get("available") else {}

    reasons = []
    if confidence < CONFIDENCE_THRESHOLD:
        reasons.append(
            f"Model kararsız (güven %{confidence * 100:.0f}, "
            f"eşik %{CONFIDENCE_THRESHOLD * 100:.0f}).")

    return {
        "needed": bool(reasons),
        "reasons": reasons,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "severe": prediction in SEVERE_FAULTS,
        # KÖKEN: eşik nereden geliyor, hangi modelde ölçüldü, kalibre mi?
        # Bu blok olmadan "eşik 0.90" cümlesi denetlenemez bir iddiadır.
        "threshold_basis": {
            "operating": CONFIDENCE_THRESHOLD,
            "measured": measurement.get("threshold"),
            "measured_on": measurement.get("measured_on"),
            "ece": measurement.get("ece"),
            "calibrated": measurement.get("calibrated"),
            "explanation": calibration.summary_line(measurement or None),
            "safety_margin": (
                _SAFETY_MARGIN_REASON
                if measurement.get("threshold") is not None
                and float(measurement["threshold"]) < CONFIDENCE_THRESHOLD
                else None),
        },
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
        # Hangi model bu tanıyı üretti? Model değiştiğinde eski kayıtların
        # hangi sürümle üretildiği bilinmeli.
        "model_info": predictor.model_info(),
    }
