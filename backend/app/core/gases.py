"""Fundamental DGA constants: the seven key gases, fault taxonomy, safe
ratios, and IEEE C57.104 concentration thresholds.

References
---------
* IEC 60599:2015  - Ratio-based interpretation of dissolved gases.
* IEEE C57.104-2008 - Condition-based concentration limits (Table 1).
* M. Duval, "A review of faults detectable by gas-in-oil analysis in
  transformers", IEEE Electrical Insulation Magazine, 2002.
"""
from __future__ import annotations

from typing import Dict

# --- The seven diagnostic gases (keys used everywhere in the codebase) ---
GASES = ["H2", "CH4", "C2H6", "C2H4", "C2H2", "CO", "CO2"]

GAS_LABELS_TR: Dict[str, str] = {
    "H2": "Hidrojen",
    "CH4": "Metan",
    "C2H6": "Etan",
    "C2H4": "Etilen",
    "C2H2": "Asetilen",
    "CO": "Karbonmonoksit",
    "CO2": "Karbondioksit",
}

# --- Fault taxonomy (IEC 60599) ---
# PD  : partial discharge
# D1  : low-energy discharge (sparking)
# D2  : high-energy discharge (arcing)
# T1  : thermal fault  < 300 C
# T2  : thermal fault  300-700 C
# T3  : thermal fault  > 700 C
# Normal : no active fault
# DT  : indeterminate / mixed (only used internally by classical methods)
FAULT_CLASSES = ["Normal", "PD", "D1", "D2", "T1", "T2", "T3"]

FAULT_LABELS_TR: Dict[str, str] = {
    "Normal": "Normal (arıza yok)",
    "PD": "Kısmi Deşarj",
    "D1": "Düşük Enerjili Deşarj",
    "D2": "Yüksek Enerjili Deşarj (Ark)",
    "T1": "Termal Arıza (< 300 °C)",
    "T2": "Termal Arıza (300-700 °C)",
    "T3": "Termal Arıza (> 700 °C)",
    "DT": "Belirsiz / Karışık",
}

# Coarse grouping used by the dashboard's simplified view.
FAULT_GROUP: Dict[str, str] = {
    "Normal": "Normal",
    "PD": "Deşarj",
    "D1": "Deşarj",
    "D2": "Ark",
    "T1": "Termal",
    "T2": "Termal",
    "T3": "Termal",
    "DT": "Belirsiz",
}

# --- Eylem seviyesi (Faz 6.4) ---------------------------------------------
# FAULT_GROUP arayüzün etiketi içindir ve Ark'ı ayrı gösterir. Bakım kararı
# ise üç aileden birine indirger: ne yapılacağı bu seviyede belirlenir.
# Model T1 yerine T2 derse ekip yine "termal arıza, incele" der — sonuç aynı.
# Ama Deşarj yerine Normal derse iş değişir. Ölçüm de burada yapılır.
FAULT_FAMILY: Dict[str, str] = {
    "Normal": "Normal",
    "PD": "Deşarj", "D1": "Deşarj", "D2": "Deşarj",
    "T1": "Termal", "T2": "Termal", "T3": "Termal",
    "DT": "Belirsiz",
}

# Acil müdahale gerektiren sınıflar: yüksek enerjili ark ve >700 °C ısınma.
SEVERE_FAULTS = {"D2", "T3"}

# --- IEEE C57.104-2008 Condition 1 upper limits (ppm) ---
# A gas above its limit is flagged; the count of exceedances drives the
# condition level (1-4) used for the risk badge.
IEEE_CONDITION1_PPM: Dict[str, float] = {
    "H2": 100.0,
    "CH4": 120.0,
    "C2H6": 65.0,
    "C2H4": 50.0,
    "C2H2": 35.0,
    "CO": 350.0,
    "CO2": 2500.0,
}

# Total Dissolved Combustible Gas condition thresholds (ppm), IEEE C57.104.
TDCG_LIMITS = {"C1": 720.0, "C2": 1920.0, "C3": 4630.0}
COMBUSTIBLE = ["H2", "CH4", "C2H6", "C2H4", "C2H2", "CO"]

_EPS = 1e-9  # guards divisions when a gas reads exactly zero


def total_combustible(g: Dict[str, float]) -> float:
    """TDCG - sum of the six combustible gases (excludes CO2)."""
    return float(sum(g.get(k, 0.0) for k in COMBUSTIBLE))


def safe_ratio(numerator: float, denominator: float) -> float:
    """Ratio that never divides by zero (denominator floored at _EPS)."""
    return float(numerator) / (float(denominator) + _EPS)


def key_ratios(g: Dict[str, float]) -> Dict[str, float]:
    """The five ratios that feed Rogers / IEC / Doernenburg logic."""
    return {
        "C2H2/C2H4": safe_ratio(g.get("C2H2", 0.0), g.get("C2H4", 0.0)),
        "CH4/H2": safe_ratio(g.get("CH4", 0.0), g.get("H2", 0.0)),
        "C2H4/C2H6": safe_ratio(g.get("C2H4", 0.0), g.get("C2H6", 0.0)),
        "C2H6/CH4": safe_ratio(g.get("C2H6", 0.0), g.get("CH4", 0.0)),
        "CO2/CO": safe_ratio(g.get("CO2", 0.0), g.get("CO", 0.0)),
    }
