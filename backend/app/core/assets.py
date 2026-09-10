"""Varlık sınıfları: güç trafolarının büyüklük kategorileri.

GE Vernova'nın güç trafosu hattı **MPT** (Medium Power Transformer) ve
**LPT** (Large Power Transformer) olarak ayrılır. **SPT** (Small) hattı
üretimden kalkmıştır — ama sahadaki üniteler çalışmaya devam eder, bu
yüzden sistem onları hâlâ tanımak zorundadır. Üretimi biten bir ürünü
izleme kapsamı dışına atmak, filo yönetiminde klasik bir hatadır.

NEDEN SADECE ETİKET DEĞİL
-------------------------
Varlık sınıfı üç şeyi değiştirir:

1. **Numune alma sıklığı** — büyük üniteler daha sık örneklenir.
2. **Arızanın sonucu** — bir LPT genellikle şebeke bağlantı noktasındadır;
   arızası daha geniş bir alanı etkiler ve yedeklenmesi aylar sürer.
3. **Öncelik** — endüstride risk = olasılık × SONUÇ. Gaz analizi olasılığı
   verir; sonucu varlık sınıfı verir. İkisi çarpılmadan "önce hangisine
   bakayım?" sorusu doğru cevaplanamaz.

MVA aralıkları konvansiyoneldir; en yaygın eşik ABD DOE'nin LPT tanımıdır
(>= 100 MVA). Bu proje demo olduğu için değerler burada tek yerde toplandı
ve değiştirilebilir tutuldu.
"""
from __future__ import annotations

from typing import Dict, List, Optional

# Sınıf kodu -> tanım.
#   weight          : sonuç ağırlığı (öncelik hesabında çarpan)
#   sampling_months : önerilen numune aralığı (proje konvansiyonu, demo)
#   active          : ürün hattı hâlâ üretimde mi
ASSET_CLASSES: Dict[str, Dict[str, object]] = {
    "LPT": {
        "code": "LPT",
        "name": "Large Power Transformer",
        "name_tr": "Büyük Güç Trafosu",
        "mva_min": 100.0,
        "mva_max": None,
        "weight": 1.0,
        "sampling_months": 6,
        "active": True,
        "note": "Şebeke bağlantı noktası; yedeklenmesi aylar sürer.",
    },
    "MPT": {
        "code": "MPT",
        "name": "Medium Power Transformer",
        "name_tr": "Orta Güç Trafosu",
        "mva_min": 10.0,
        "mva_max": 100.0,
        "weight": 0.7,
        "sampling_months": 12,
        "active": True,
        "note": "Dağıtım ve endüstriyel besleme.",
    },
    "SPT": {
        "code": "SPT",
        "name": "Small Power Transformer",
        "name_tr": "Küçük Güç Trafosu",
        "mva_min": None,
        "mva_max": 10.0,
        "weight": 0.45,
        "sampling_months": 24,
        "active": False,          # ürün hattı kalktı, saha üniteleri sürüyor
        "note": "Ürün hattı sonlandırıldı; mevcut üniteler izlenmeye devam.",
    },
}

# Öncelik sıralamasında büyükten küçüğe.
CLASS_ORDER: List[str] = ["LPT", "MPT", "SPT"]

DEFAULT_CLASS = "MPT"


def classify_by_mva(mva: Optional[float]) -> str:
    """MVA değerinden sınıf çıkarır; bilinmiyorsa varsayılana düşer."""
    if mva is None:
        return DEFAULT_CLASS
    if mva >= 100.0:
        return "LPT"
    if mva >= 10.0:
        return "MPT"
    return "SPT"


def get(code: Optional[str]) -> Dict[str, object]:
    """Sınıf tanımını döndürür; bilinmeyen kod varsayılana düşer."""
    return ASSET_CLASSES.get(str(code or "").upper(),
                             ASSET_CLASSES[DEFAULT_CLASS])


def weight(code: Optional[str]) -> float:
    return float(get(code)["weight"])


def priority_score(risk_condition: Optional[int], code: Optional[str]) -> float:
    """Öncelik = IEEE kondisyonu × varlık ağırlığı.

    Kondisyon 1-4 arasıdır (gaz analizinden gelen "ne kadar acil"), ağırlık
    ise arızanın sonucunu ölçekler. Böylece kondisyon 3'teki bir LPT (3.0),
    kondisyon 4'teki bir SPT'nin (1.8) önüne geçer — sahada da böyle
    davranılır, çünkü ikisinin şebekeye etkisi aynı değildir.

    Formül bilinçli olarak basit ve AÇIKLANABİLİR tutuldu: arayüzde
    "kondisyon × ağırlık" diye gösterilebilmeli, kara kutu olmamalı.
    """
    return round(float(risk_condition or 0) * weight(code), 2)
