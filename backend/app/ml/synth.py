"""Standards-based synthetic DGA data generator.

The project intentionally uses no proprietary field data. Instead we
synthesise labelled samples whose gas signatures follow the fault
characteristics defined by IEC 60599 and the Duval triangle, then label
each sample by the fault class that generated it (unambiguous ground
truth). This is a defensible, reproducible substitute for scarce field
data and is documented as such in the report.

Two products:
* ``make_dataset``       - i.i.d. labelled samples for model training.
* ``make_aging_series``  - one transformer's gases evolving over time,
                            used by the trend / predictive-maintenance module.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from ..core.gases import GASES

# Per-class gas *signature*: (median ppm, log-normal sigma) for each gas.
# Chosen so that the resulting ratios land in the correct IEC/Duval region
# for that fault class. CO/CO2 track cellulose involvement.
_PROFILES: Dict[str, Dict[str, Tuple[float, float]]] = {
    "Normal": {
        "H2": (15, 0.5), "CH4": (10, 0.5), "C2H6": (8, 0.5),
        "C2H4": (6, 0.5), "C2H2": (0.3, 0.6), "CO": (250, 0.4),
        "CO2": (2000, 0.3),
    },
    "PD": {  # partial discharge: hydrogen dominant
        "H2": (400, 0.5), "CH4": (60, 0.5), "C2H6": (15, 0.5),
        "C2H4": (8, 0.5), "C2H2": (1, 0.7), "CO": (300, 0.4),
        "CO2": (2500, 0.3),
    },
    "D1": {  # low-energy discharge: acetylene present, low ethylene
        "H2": (180, 0.5), "CH4": (90, 0.5), "C2H6": (25, 0.5),
        "C2H4": (40, 0.5), "C2H2": (90, 0.5), "CO": (350, 0.4),
        "CO2": (2600, 0.3),
    },
    "D2": {  # high-energy arcing: high acetylene + ethylene
        "H2": (280, 0.5), "CH4": (120, 0.5), "C2H6": (40, 0.5),
        "C2H4": (220, 0.5), "C2H2": (240, 0.5), "CO": (500, 0.4),
        "CO2": (3200, 0.3),
    },
    "T1": {  # thermal <300C: methane/ethane, cellulose (CO) elevated
        "H2": (60, 0.5), "CH4": (140, 0.5), "C2H6": (110, 0.5),
        "C2H4": (30, 0.5), "C2H2": (0.5, 0.6), "CO": (700, 0.4),
        "CO2": (4500, 0.3),
    },
    "T2": {  # thermal 300-700C: ethylene rising
        "H2": (90, 0.5), "CH4": (150, 0.5), "C2H6": (90, 0.5),
        "C2H4": (180, 0.5), "C2H2": (1.5, 0.6), "CO": (500, 0.4),
        "CO2": (3500, 0.3),
    },
    "T3": {  # thermal >700C: ethylene dominant
        "H2": (120, 0.5), "CH4": (200, 0.5), "C2H6": (70, 0.5),
        "C2H4": (520, 0.5), "C2H2": (4, 0.6), "CO": (450, 0.4),
        "CO2": (3300, 0.3),
    },
}

# Relative prevalence of each class (mild imbalance, like the field).
_CLASS_WEIGHTS = {
    "Normal": 0.24, "PD": 0.12, "D1": 0.12, "D2": 0.13,
    "T1": 0.13, "T2": 0.13, "T3": 0.13,
}


# --- Gerçekçilik katmanı (Faz 6.7) ----------------------------------------
# Gerçek veriyle ölçüldü: saha verisinde sınıf içi değişim katsayısı 1.7-4.9,
# bizim üretecimizde 0.24-0.46 idi. Yani sentetik sınıflar gerçeklerden ~10
# kat DAR. Sebep: üreteç her arızayı tek bir şiddette üretiyordu; gerçekte
# aynı arıza başlangıç evresinden ileri evreye kadar çok farklı büyüklükte
# görünür ve asıl yayılım oradan gelir.
#
# ``realism`` 0.0 = eski davranış (geriye dönük uyumluluk, testler),
# 1.0 = tam gerçekçilik. Ara değerler etkiyi ölçeklendirir.

_SEVERITY_SIGMA = 1.15      # şiddet çarpanının log-normal genişliği
_INCIPIENT_P = 0.28         # "henüz başlangıç evresinde" olma olasılığı
_MIXED_P = 0.15             # iki arızanın birlikte bulunma olasılığı
_MEAS_SIGMA = 0.16          # laboratuvar ölçüm tekrarlanabilirliği
_LABEL_NOISE_P = 0.05       # uzmanın komşu sınıfla karıştırma olasılığı

# Uzmanların gerçekte karıştırdığı komşu sınıflar (etiket gürültüsü buraya
# sınırlı): deşarj enerjisi ve termal sıcaklık süreklidir, sınır keskin değil.
_NEIGHBOURS: Dict[str, List[str]] = {
    "PD": ["D1"], "D1": ["PD", "D2"], "D2": ["D1"],
    "T1": ["T2"], "T2": ["T1", "T3"], "T3": ["T2"],
    "Normal": ["T1"],
}


# ÖLÇÜLMÜŞ ÖN AYAR (Faz 6.7).
# Beş gerçekçilik bileşeni gerçek veri üzerinde tek tek denendi; sıfır atış
# (sentetik eğitim -> gerçek test) F1'ine etkileri:
#
#   başlangıç evresi   +0.066  ✅  tek gerçek kazanç
#   etiket gürültüsü   -0.008
#   ölçüm gürültüsü    -0.012  (tek başına nötr; başlangıçla birlikte artı)
#   karışık arıza      -0.063  ❌
#   şiddet             -0.096  ❌  en zararlısı
#
# Şiddetin zarar vermesi ilk bakışta şaşırtıcı: dağılımı gerçeğe benzeten
# bileşen oydu (sınıf içi değişkenliği 0.3'ten 2.5'e çıkarıyordu). Ama
# "dağılımı benzetmek" ile "aktarımı iyileştirmek" AYNI ŞEY DEĞİL: şiddet
# çarpanı düşük şiddetli arızaları Normal'e indiriyor, yüksek şiddetlileri
# uçuruyor ve model mutlak seviyeden öğrendiği her şeyi kaybediyor.
#
# Üç tohumla doğrulandı: F1 0.530 ±0.001 -> 0.578 ±0.003.
PRESET_FIELD_LIKE: Dict[str, float] = {
    "incipient": 1.0,     # arızaların bir kısmı başlangıç evresinde yakalanır
    "noise": 1.0,         # laboratuvar ölçüm tekrarlanabilirliği
    "severity": 0.0,
    "mixed": 0.0,
    "label_noise": 0.0,
}


def _blend(a: Dict[str, Tuple[float, float]],
           b: Dict[str, Tuple[float, float]],
           t: float) -> Dict[str, Tuple[float, float]]:
    """İki profilin medyanlarını t oranında karıştırır (sigma a'dan gelir)."""
    return {g: ((1 - t) * a[g][0] + t * b[g][0], a[g][1]) for g in GASES}


def _sample_gas(profile: Dict[str, Tuple[float, float]],
                rng: np.random.Generator,
                severity: float = 1.0,
                meas_sigma: float = 0.0) -> Dict[str, float]:
    out: Dict[str, float] = {}
    for gas in GASES:
        median, sigma = profile[gas]
        # log-normal keeps values positive and right-skewed like real DGA.
        value = float(rng.lognormal(mean=np.log(median), sigma=sigma))
        value *= severity
        if meas_sigma > 0:
            # Ölçüm gürültüsü: aynı numune iki kez ölçülse aynı çıkmaz.
            value *= float(rng.lognormal(mean=0.0, sigma=meas_sigma))
        out[gas] = round(max(value, 0.0), 2)
    return out


def make_dataset(n: int = 4000, seed: int = 42,
                 realism: float = 0.0,
                 *,
                 severity: Optional[float] = None,
                 incipient: Optional[float] = None,
                 mixed: Optional[float] = None,
                 noise: Optional[float] = None,
                 label_noise: Optional[float] = None) -> pd.DataFrame:
    """``n`` etiketli örnek üretir (sütunlar: gazlar + label).

    ``realism`` (0..1) saha verisine benzemeyi artıran dört etkiyi açar:

    * **Şiddet** — aynı arıza farklı yoğunluklarda görünür. Tüm gazlar ortak
      bir çarpanla ölçeklenir; oranlar korunur, büyüklük değişir. Gerçek
      verideki geniş yayılımın ana kaynağı budur.
    * **Başlangıç evresi** — arıza yeni gelişiyorsa imza Normal'e yakındır.
      Profil Normal'e doğru karıştırılır; sınıflar arası GRİ BÖLGE böyle
      oluşur. (Faz 6.5'te üretecin hiç belirsiz vaka üretemediğini görmüştük.)
    * **Karışık arıza** — sahada termal ve deşarj aynı trafoda bulunabilir.
      Baskın olan etiketi belirler, diğeri imzayı kirletir.
    * **Ölçüm ve etiket gürültüsü** — laboratuvar tekrarlanabilirliği ve
      uzmanların komşu sınıfları karıştırması.

    ``realism=0.0`` eski davranışı birebir korur; eski model ve testler
    etkilenmez.

    Dört etkinin her biri ayrıca ayarlanabilir (``severity``, ``incipient``,
    ``mixed``, ``noise``, ``label_noise``). Verilmezse ``realism`` kullanılır.
    Bu ayrım deneysel: hangi gerçekçilik boyutunun işe yaradığını tek tek
    ölçebilmek için var.
    """
    realism = float(np.clip(realism, 0.0, 1.0))
    lv = lambda x: realism if x is None else float(np.clip(x, 0.0, 1.0))
    k_sev, k_inc = lv(severity), lv(incipient)
    k_mix, k_noise, k_lbl = lv(mixed), lv(noise), lv(label_noise)
    rng = np.random.default_rng(seed)
    classes = list(_CLASS_WEIGHTS)
    weights = np.array([_CLASS_WEIGHTS[c] for c in classes])
    weights /= weights.sum()

    rows: List[Dict[str, float]] = []
    labels = rng.choice(classes, size=n, p=weights)
    for label in labels:
        profile = _PROFILES[label]

        # 1) Karışık arıza: farklı ailedeki bir sınıfla harmanla.
        if label != "Normal" and rng.random() < _MIXED_P * k_mix:
            other = str(rng.choice([c for c in classes
                                    if c not in ("Normal", label)]))
            profile = _blend(profile, _PROFILES[other],
                             float(rng.uniform(0.15, 0.40)))

        # 2) Başlangıç evresi: imza henüz Normal'e yakın.
        if label != "Normal" and rng.random() < _INCIPIENT_P * k_inc:
            profile = _blend(profile, _PROFILES["Normal"],
                             float(rng.uniform(0.35, 0.85)))

        # 3) Şiddet: ortak çarpan, oranları bozmadan büyüklüğü değiştirir.
        # Normal sınıfa UYGULANMAZ: sağlıklı bir trafonun "şiddeti" yoktur ve
        # normal numuneyi 10 katına çıkarıp hâlâ "Normal" demek etiketi
        # doğrudan bozar (ilk denemede sıfır atış F1'i 0.519'dan 0.423'e
        # düşüren hata buydu).
        severity = (1.0 if label == "Normal"
                    else float(rng.lognormal(0.0, _SEVERITY_SIGMA * k_sev)))

        row = _sample_gas(profile, rng, severity=severity,
                          meas_sigma=_MEAS_SIGMA * k_noise)

        # 4) Etiket gürültüsü: uzman komşu sınıfla karıştırmış olabilir.
        final = label
        if rng.random() < _LABEL_NOISE_P * k_lbl:
            final = str(rng.choice(_NEIGHBOURS.get(label, [label])))

        row["label"] = final
        rows.append(row)
    return pd.DataFrame(rows, columns=[*GASES, "label"])


def make_field_like_dataset(n: int = 4000, seed: int = 42) -> pd.DataFrame:
    """Gerçek veriye en iyi aktarılan yapılandırmayla veri üretir.

    ``PRESET_FIELD_LIKE`` ölçülerek seçildi (bkz. yukarıdaki not ve
    docs/FAZ6-GERCEK-VERI-BULGULARI.md). Sentetik test doğruluğu bir miktar
    düşer — çünkü üretilen veri artık daha zor — ama gerçek trafo
    ölçümlerine aktarım belirgin iyileşir.
    """
    return make_dataset(n=n, seed=seed, **PRESET_FIELD_LIKE)


def make_aging_series(fault_class: str = "T2", months: int = 24,
                      seed: int = 7) -> pd.DataFrame:
    """Simulate one transformer degrading toward ``fault_class`` over time.

    Gases start near-normal and ramp (with noise) toward the target fault
    signature, giving the trend module a realistic worsening curve.
    """
    rng = np.random.default_rng(seed)
    start = _PROFILES["Normal"]
    end = _PROFILES[fault_class]
    rows: List[Dict[str, float]] = []
    for m in range(months):
        # non-linear (accelerating) progression
        t = (m / max(months - 1, 1)) ** 1.6
        row: Dict[str, float] = {"month": m}
        for gas in GASES:
            base = (1 - t) * start[gas][0] + t * end[gas][0]
            noise = rng.lognormal(mean=0.0, sigma=0.18)
            row[gas] = round(float(base * noise), 2)
        rows.append(row)
    return pd.DataFrame(rows, columns=["month", *GASES])
