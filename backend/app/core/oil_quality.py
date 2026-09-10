"""Yağ kalitesi testleri ve kağıt yaşlanması. — Faz 8.3

DGA NEYİ SÖYLEMEZ?
-----------------
Çözünmüş gaz analizi **yağdaki arızayı** söyler: ark var mı, aşırı ısınma
var mı, hangi tip. Ama trafonun ömrünü belirleyen şey yağ değil, **kağıt
yalıtımdır** — ve DGA bunu göstermez.

Kağıt bozundukça mekanik dayanımını yitirir. Bir gün trafo, normal bir kısa
devre akımının mekanik kuvvetine dayanamaz ve sargı deforme olur. Yağ
değiştirilebilir; kağıt değiştirilemez. Trafonun ömrü, kağıdın ömrüdür.

Bu modül aynı yağ numunesinden ölçülen ama DGA'nın kapsamadığı parametreleri
ele alır ve en önemlisini hesaplar: **kağıdın polimerizasyon derecesi (DP)**.

STANDARTLAR
-----------
* Nem            IEC 60422 / IEC 60814
* Delinme (BDV)  IEC 60156
* Asitlik        IEC 62021
* Arayüzey ger.  ASTM D971
* Furan (2-FAL)  IEC 61198

⚠ Buradaki eşik değerleri **konvansiyoneldir ve yaklaşıktır**. Gerçek
uygulamada işletme kendi kabul kriterlerini belirler. Değerler tek yerde
toplandı ve değiştirilebilir tutuldu — `assets.py`'deki MVA bantlarında da
aynı yaklaşım izlenmişti.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

# --- Gerilim sınıfı: eşikler gerilime göre sıkılaşır ----------------------
# Yüksek gerilimde aynı nem miktarı çok daha tehlikelidir, çünkü elektrik
# alan şiddeti yüksektir.
VOLTAGE_CLASSES = ("<=72.5kV", "72.5-170kV", ">170kV")


def voltage_class(hv_kv: Optional[float]) -> str:
    """Künyedeki YG geriliminden sınıf çıkarır."""
    if hv_kv is None:
        return "72.5-170kV"          # makul orta varsayım
    if hv_kv <= 72.5:
        return "<=72.5kV"
    if hv_kv <= 170.0:
        return "72.5-170kV"
    return ">170kV"


# Sınır değerler: (iyi_ustu, kabul_ustu) — bu değerlerin ötesi "kötü".
# Yönlü: "lower_better" küçük olan iyidir, "higher_better" büyük olan iyi.
LIMITS: Dict[str, Dict[str, object]] = {
    "water_ppm": {
        "label": "Nem", "unit": "ppm", "direction": "lower_better",
        "standard": "IEC 60422 / 60814",
        "meaning": "Yalıtımda su; delinme dayanımını düşürür, kağıdı hızla "
                   "yaşlandırır.",
        "thresholds": {
            "<=72.5kV": (20.0, 30.0),
            "72.5-170kV": (15.0, 20.0),
            ">170kV": (10.0, 15.0),
        },
    },
    "bdv_kv": {
        "label": "Delinme gerilimi", "unit": "kV", "direction": "higher_better",
        "standard": "IEC 60156",
        "meaning": "Yağın dielektrik dayanımı. Nem ve partikül düşürür.",
        "thresholds": {
            "<=72.5kV": (50.0, 40.0),
            "72.5-170kV": (55.0, 47.0),
            ">170kV": (60.0, 50.0),
        },
    },
    "acidity_mgkoh_g": {
        "label": "Asitlik", "unit": "mg KOH/g", "direction": "lower_better",
        "standard": "IEC 62021",
        "meaning": "Yağın oksitlenmesi. Yüksek asitlik tortu oluşturur ve "
                   "soğutmayı bozar.",
        "thresholds": {
            "<=72.5kV": (0.10, 0.20),
            "72.5-170kV": (0.10, 0.15),
            ">170kV": (0.10, 0.15),
        },
    },
    "ift_mn_m": {
        "label": "Arayüzey gerilimi", "unit": "mN/m",
        "direction": "higher_better",
        "standard": "ASTM D971",
        "meaning": "Yağdaki polar bozunma ürünleri. Asitlikle birlikte "
                   "yorumlanır.",
        "thresholds": {
            "<=72.5kV": (28.0, 22.0),
            "72.5-170kV": (28.0, 22.0),
            ">170kV": (30.0, 24.0),
        },
    },
}

CONDITIONS = ("iyi", "kabul", "kötü", "bilinmiyor")

# --- Kağıt yaşlanması -----------------------------------------------------
# Chendong bağıntısı: log10(2FAL[mg/L]) = 1.51 - 0.0035 × DP
CHENDONG_A = 1.51
CHENDONG_B = 0.0035

DP_NEW = 1100          # yeni kağıt
DP_END_OF_LIFE = 200   # mekanik dayanım bitti kabul edilir

# Furan ölçüm alt sınırı; bunun altında "tespit edilemedi" sayılır.
FURAN_DETECTION_LIMIT = 0.01

DP_BANDS = [
    (700, "sağlıklı", "Kağıt yeni sayılır; belirgin bozunma yok."),
    (450, "orta", "Normal yaşlanma sürüyor; izlemeye devam."),
    (250, "ileri", "Belirgin bozunma; yenileme planlaması başlatılmalı."),
    (0, "ömür sonu", "Mekanik dayanım kritik; kısa devre kuvvetine "
                     "dayanmayabilir."),
]


def assess_parameter(name: str, value: Optional[float],
                     vclass: str) -> Dict[str, object]:
    """Tek bir yağ parametresini değerlendirir."""
    spec = LIMITS.get(name)
    if spec is None:
        return {"parameter": name, "condition": "bilinmiyor"}

    thresholds = spec["thresholds"][vclass]      # type: ignore[index]
    good, acceptable = thresholds

    if value is None:
        condition = "bilinmiyor"
    elif spec["direction"] == "lower_better":
        condition = ("iyi" if value <= good
                     else "kabul" if value <= acceptable else "kötü")
    else:
        condition = ("iyi" if value >= good
                     else "kabul" if value >= acceptable else "kötü")

    return {
        "parameter": name,
        "label": spec["label"],
        "unit": spec["unit"],
        "value": value,
        "condition": condition,
        "good_limit": good,
        "acceptable_limit": acceptable,
        "standard": spec["standard"],
        "meaning": spec["meaning"],
    }


def estimate_dp(furan_2fal_mgl: Optional[float],
                insulation_type: Optional[str] = None) -> Dict[str, object]:
    """Furan konsantrasyonundan kağıdın polimerizasyon derecesini kestirir.

    DP'yi doğrudan ölçmek için trafoyu açıp kağıt örneği almak gerekir.
    Furan ise aynı yağ numunesinden çıkar — bu yüzden değerlidir.

    ⚠ SINIR: Chendong bağıntısı **standart kraft kağıt** için türetilmiştir.
    Termal yükseltilmiş kağıtta (TUK) daha az furan üretilir, dolayısıyla
    bağıntı DP'yi olduğundan **yüksek** gösterir — yani trafoyu olduğundan
    genç sanırız. Künyedeki ``insulation_type`` alanı bu yüzden önemli:
    uyarı üretebilmek için gerekli. (Faz 8.1'de eklenmişti.)
    """
    if furan_2fal_mgl is None:
        return {"available": False, "reason": "furan ölçümü yok"}

    if furan_2fal_mgl < FURAN_DETECTION_LIMIT:
        # log10(0) tanımsız; ayrıca çok düşük furan "kağıt yeni" demektir.
        return {
            "available": True,
            "furan_2fal_mgl": furan_2fal_mgl,
            "dp_estimate": DP_NEW,
            "band": "sağlıklı",
            "note": "Furan tespit sınırının altında; kağıt yeni kabul edildi.",
            "life_consumed_pct": 0.0,
            "reliable": True,
            "warnings": [],
        }

    dp = (CHENDONG_A - math.log10(furan_2fal_mgl)) / CHENDONG_B
    dp = max(0.0, min(float(dp), 2000.0))   # fiziksel olmayan uçları kırp

    band, description = "ömür sonu", DP_BANDS[-1][2]
    for lower, name, desc in DP_BANDS:
        if dp >= lower:
            band, description = name, desc
            break

    # Tüketilen ömür: yeni kağıttan ömür sonuna kadar olan yolun ne kadarı?
    span = DP_NEW - DP_END_OF_LIFE
    consumed = (DP_NEW - dp) / span * 100.0
    consumed = max(0.0, min(consumed, 100.0))

    warnings: List[str] = []
    reliable = True
    if str(insulation_type or "").lower() == "tuk":
        reliable = False
        warnings.append(
            "Bu trafoda termal yükseltilmiş kağıt (TUK) var. Chendong "
            "bağıntısı standart kraft için türetildi; TUK daha az furan "
            "ürettiği için DP olduğundan YÜKSEK (trafo olduğundan genç) "
            "görünür. Sonuç iyimser kabul edilmeli.")

    return {
        "available": True,
        "furan_2fal_mgl": furan_2fal_mgl,
        "dp_estimate": round(dp),
        "band": band,
        "description": description,
        "life_consumed_pct": round(consumed, 1),
        "dp_new": DP_NEW,
        "dp_end_of_life": DP_END_OF_LIFE,
        "model": "Chendong (IEC 61198)",
        "reliable": reliable,
        "warnings": warnings,
    }


def assess(test: Dict[str, object], hv_kv: Optional[float] = None,
           insulation_type: Optional[str] = None) -> Dict[str, object]:
    """Bir yağ kalitesi testini bütün olarak değerlendirir."""
    vclass = voltage_class(hv_kv)

    parameters = [
        assess_parameter(name, _num(test.get(name)), vclass)
        for name in LIMITS
    ]

    paper = estimate_dp(_num(test.get("furan_2fal_mgl")), insulation_type)

    # Genel durum EN KÖTÜ parametreye göre belirlenir. Ortalama almak
    # yanıltıcı olurdu: üç iyi bir kötüyü gizleyemez, çünkü tek bir
    # parametrenin kötü olması trafoyu riske atmaya yeter.
    known = [p for p in parameters if p["condition"] != "bilinmiyor"]
    if not known:
        overall = "bilinmiyor"
    elif any(p["condition"] == "kötü" for p in known):
        overall = "kötü"
    elif any(p["condition"] == "kabul" for p in known):
        overall = "kabul"
    else:
        overall = "iyi"

    problems = [f"{p['label']}: {p['value']} {p['unit']} "
                f"(sınır {p['acceptable_limit']})"
                for p in known if p["condition"] == "kötü"]

    return {
        "voltage_class": vclass,
        "overall": overall,
        "parameters": parameters,
        "problems": problems,
        "measured_count": len(known),
        "paper": paper,
    }


def _num(value: object) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
