"""Klasik yöntemlerin kararlarını ML'e GİRDİ olarak veren hibrit özellikler.

Fikir borsadaki teknik indikatör mantığının aynısı: modele ham fiyat yerine
RSI/MACD gibi türetilmiş göstergeleri de vermek. Burada "gösterge" 50 yıllık
saha bilgisinin damıtılmış hâli olan klasik DGA yöntemleridir.

Model normalde sıfırdan başlar ve gaz oranlarından arıza tipini kendi
çıkarmaya çalışır. Hibrit yaklaşımda ise Duval'in, Rogers'ın ve IEC'nin
verdiği kararları hazır alır; üstüne yalnızca "bu kural şu durumda yanılıyor"
düzeltmesini öğrenir.

Neden ayrı modül? ``features.build_features`` canlı tahmin yolunda çalışır ve
hızlı olmalı; klasik yöntemleri her satır için koşturmak pahalıdır. Hibrit
özellikler yalnızca deney/eğitim hattında kullanılır.
"""
from __future__ import annotations

from typing import Dict, List

import pandas as pd

from ..core.classify import classical_methods
from ..core.gases import FAULT_CLASSES
from .features import CORE_FEATURE_NAMES, build_features

# Arıza sınıfı -> sayı. Ağaç modelleri metin kabul etmez.
# "DT" (Duval'in karışık bölgesi) ayrı bir kod; bilinmeyen/N/A ise -1.
_FAULT_CODE: Dict[str, int] = {c: i for i, c in enumerate(FAULT_CLASSES)}
_FAULT_CODE["DT"] = len(FAULT_CLASSES)

# Ham gaz adı -> sayı (key_gas hangi gazı baskın buldu).
_GAS_CODE: Dict[str, int] = {
    g: i for i, g in enumerate(["H2", "CH4", "C2H6", "C2H4", "C2H2", "CO", "CO2"])
}

INDICATOR_NAMES: List[str] = [
    # Duval üçgeninin koordinatları: toplamı 100 olduğu için ÖLÇEK BAĞIMSIZ.
    # 10 ppm'lik bir numune ile 10.000 ppm'lik numune aynı noktaya düşebilir;
    # arıza tipini belirleyen mutlak miktar değil, gazların birbirine oranıdır.
    "pct_CH4", "pct_C2H4", "pct_C2H2",
    # Dört yöntemin kararı (sınıf kodu).
    "duval_code", "rogers_code", "iec_code", "keygas_code",
    # Rogers'ın üç oranı için ürettiği ayrık kodlar.
    "rogers_r1", "rogers_r2", "rogers_r3",
    # Key Gas: hangi gaz baskın ve payı ne.
    "keygas_gas", "keygas_share",
    # Yöntemler ne kadar anlaşıyor? Düşükse vaka belirsizdir — modelin
    # "burada kurallara güvenme" diyebilmesi için bir güven göstergesi.
    "n_votes", "agreement",
]

HYBRID_FEATURE_NAMES: List[str] = [*CORE_FEATURE_NAMES, *INDICATOR_NAMES]


def _code(fault: object) -> int:
    return _FAULT_CODE.get(str(fault), -1)


def classical_indicators(g: Dict[str, float]) -> Dict[str, float]:
    """Tek bir ölçüm için klasik yöntem göstergelerini üretir."""
    m = classical_methods(g)

    duval = m["duval"]
    pct = duval.get("percentages", {}) or {}

    rogers = m["rogers"]
    r_codes = rogers.get("codes", {}) or {}

    keygas = m["key_gas"]

    # Oy birliği: dört yöntemin kaçı en çok tekrar eden kararda buluşuyor?
    votes = [_code(duval.get("zone")), _code(rogers.get("fault")),
             _code(m["iec"].get("fault")), _code(keygas.get("fault"))]
    valid = [v for v in votes if v >= 0]
    top = max((valid.count(v) for v in set(valid)), default=0)

    return {
        "pct_CH4": float(pct.get("CH4", 0.0)),
        "pct_C2H4": float(pct.get("C2H4", 0.0)),
        "pct_C2H2": float(pct.get("C2H2", 0.0)),
        "duval_code": float(_code(duval.get("zone"))),
        "rogers_code": float(_code(rogers.get("fault"))),
        "iec_code": float(_code(m["iec"].get("fault"))),
        "keygas_code": float(_code(keygas.get("fault"))),
        "rogers_r1": float(r_codes.get("C2H2/C2H4", -1)),
        "rogers_r2": float(r_codes.get("CH4/H2", -1)),
        "rogers_r3": float(r_codes.get("C2H4/C2H6", -1)),
        "keygas_gas": float(_GAS_CODE.get(str(keygas.get("key_gas")), -1)),
        "keygas_share": float(keygas.get("share", 0.0)),
        "n_votes": float(len(valid)),
        "agreement": float(top / len(valid)) if valid else 0.0,
    }


def build_hybrid_features(df: pd.DataFrame) -> pd.DataFrame:
    """Ham gaz DataFrame'i -> çekirdek özellikler + klasik göstergeler."""
    core = build_features(df, CORE_FEATURE_NAMES)
    ind = df.apply(lambda r: classical_indicators(r.to_dict()),
                   axis=1, result_type="expand")
    out = pd.concat([core.reset_index(drop=True),
                     ind[INDICATOR_NAMES].reset_index(drop=True)], axis=1)
    return out[HYBRID_FEATURE_NAMES]
