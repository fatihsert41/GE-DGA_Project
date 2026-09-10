"""Emniyet açısından anlamlı ölçütler. — Faz 6.4

NEDEN BU DOSYA VAR
------------------
"F1 = 0.78" bir bakım mühendisine hiçbir şey söylemez, üstelik yanıltıcıdır.
Yedi sınıflı F1, modelin T1 ile T2'yi karıştırmasını, D2'yi Normal sanmasıyla
AYNI ağırlıkta cezalandırır. Oysa sahada bu ikisi taban tabana zıttır:

* T1 yerine T2 demek  -> ikisi de "termal arıza var, incele". Sonuç aynı.
* D2 yerine Normal demek -> ark var ama "sorun yok" dedik. **Felaket.**

Bir emniyet sistemi şu sorularla ölçülür:

  1. **Kaçırma (false negative):** Arıza var, model "Normal" dedi mi?
     Bu tek başına en kritik sayıdır.
  2. **Aile doğruluğu:** Termal mi, deşarj mı? Yapılacak iş buna göre değişir.
  3. **Ciddi arıza yakalama:** D2 (ark) ve T3 (>700 °C) — acil olanlar.
  4. **Seçici tahmin:** Model emin değilse SUSUP uzmana devredebilir.
     Kararların %70'inde %95 isabet + %30'unda "uzman baksın", her karara
     %78 isabetten çok daha güvenli bir sistemdir.

Çalıştırma (backend/ klasöründen):
    python -m app.ml.safety_eval --real data/dga_china_2321.xlsx
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

from ..core.gases import FAULT_CLASSES, FAULT_FAMILY, SEVERE_FAULTS
from .experiments import _apply_log, _features
from .real_data import load_real_dataset, print_report
from .train import ARTIFACT_DIR, _candidate_models

try:
    from imblearn.over_sampling import SMOTE
    _HAS_SMOTE = True
except Exception:  # pragma: no cover
    _HAS_SMOTE = False

# Tek doğruluk kaynağı core/gases.py; burada yalnızca kısa ad veriliyor.
FAMILY = FAULT_FAMILY
SEVERE = SEVERE_FAULTS

_LABEL_TO_INT = {c: i for i, c in enumerate(FAULT_CLASSES)}


def _train_best(X_tr: pd.DataFrame, y_tr: List[str], seed: int = 42):
    """Ablasyonun kazananı: XGBoost + SMOTE dengelemesi."""
    y_int = [_LABEL_TO_INT[y] for y in y_tr]
    if _HAS_SMOTE:
        k = min(5, min(pd.Series(y_int).value_counts()) - 1)
        if k >= 1:
            X_tr, y_int = SMOTE(random_state=seed,
                                k_neighbors=k).fit_resample(X_tr, y_int)
    model = _candidate_models()["XGBoost"]
    model.fit(X_tr, y_int)
    return model


def _selective(y_true: List[str], y_pred: List[str], conf: np.ndarray
               ) -> List[Dict[str, float]]:
    """Güven eşiğine göre kapsama/isabet dengesi.

    "Seçici tahmin": model yalnızca güveni eşiğin üstündeyse karar verir,
    altındaysa vakayı uzmana devreder. Kapsama (coverage) düşerken isabet
    yükselir; emniyet kritik sistemlerin standart çalışma biçimidir.
    """
    rows = []
    for th in (0.0, 0.5, 0.6, 0.7, 0.8, 0.9):
        mask = conf >= th
        n = int(mask.sum())
        if n == 0:
            continue
        yt = [y for y, m in zip(y_true, mask) if m]
        yp = [y for y, m in zip(y_pred, mask) if m]
        rows.append({
            "threshold": th,
            "coverage": round(n / len(y_true), 3),
            "n": n,
            "accuracy": round(float(accuracy_score(yt, yp)), 4),
            "f1_macro": round(float(f1_score(yt, yp, average="macro",
                                             zero_division=0)), 4),
        })
    return rows


def evaluate(real_path: Path, seed: int = 42, test_size: float = 0.3
             ) -> Dict[str, object]:
    real, rep = load_real_dataset(real_path)
    print_report(rep)

    tr, te = train_test_split(real, test_size=test_size, random_state=seed,
                              stratify=real["label"])
    tr, te = tr.reset_index(drop=True), te.reset_index(drop=True)

    # Ablasyonun en iyi yapılandırması: hibrit özellikler + log ölçek.
    X_tr = _apply_log(_features(tr, hybrid=True))
    X_te = _apply_log(_features(te, hybrid=True))
    y_tr = tr["label"].tolist()
    y_true = te["label"].tolist()

    model = _train_best(X_tr, y_tr, seed)
    proba = model.predict_proba(X_te)
    y_pred = [FAULT_CLASSES[int(i)] for i in proba.argmax(axis=1)]
    conf = proba.max(axis=1)

    # --- 1. Kaçırma: arıza varken "Normal" demek ---
    faults = [(t, p) for t, p in zip(y_true, y_pred) if t != "Normal"]
    missed = [(t, p) for t, p in faults if p == "Normal"]
    normals = [(t, p) for t, p in zip(y_true, y_pred) if t == "Normal"]
    false_alarms = [(t, p) for t, p in normals if p != "Normal"]

    # --- 2. Aile doğruluğu ---
    fam_true = [FAMILY[t] for t in y_true]
    fam_pred = [FAMILY[p] for p in y_pred]

    # --- 3. Ciddi arızalar ---
    severe = [(t, p) for t, p in zip(y_true, y_pred) if t in SEVERE]
    severe_missed_normal = [(t, p) for t, p in severe if p == "Normal"]
    severe_caught_family = [(t, p) for t, p in severe
                            if FAMILY[p] == FAMILY[t]]

    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_train": len(tr), "n_test": len(te),
        "seven_class": {
            "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
            "f1_macro": round(float(f1_score(y_true, y_pred, average="macro",
                                             zero_division=0)), 4),
        },
        "fault_detection": {
            "n_faults": len(faults),
            "missed": len(missed),
            "miss_rate": round(len(missed) / max(1, len(faults)), 4),
            "recall": round(1 - len(missed) / max(1, len(faults)), 4),
            "n_normal": len(normals),
            "false_alarms": len(false_alarms),
            "false_alarm_rate": round(len(false_alarms) / max(1, len(normals)), 4),
            "missed_cases": sorted({t for t, _ in missed}),
        },
        "family": {
            "accuracy": round(float(accuracy_score(fam_true, fam_pred)), 4),
            "f1_macro": round(float(f1_score(fam_true, fam_pred,
                                             average="macro",
                                             zero_division=0)), 4),
        },
        "severe": {
            "n": len(severe),
            "declared_normal": len(severe_missed_normal),
            "family_correct": len(severe_caught_family),
            "family_recall": round(len(severe_caught_family) /
                                   max(1, len(severe)), 4),
        },
        "selective": _selective(y_true, y_pred, conf),
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    with open(ARTIFACT_DIR / "safety_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    return report


def _print(report: Dict[str, object]) -> None:
    sc = report["seven_class"]
    fd = report["fault_detection"]
    fam = report["family"]
    sv = report["severe"]

    print("\n" + "=" * 62)
    print("EMNİYET AÇISINDAN ANLAMLI ÖLÇÜTLER")
    print("=" * 62)

    print(f"\n0) Referans — yedi sınıflı tam isabet")
    print(f"   doğruluk {sc['accuracy']:.3f} · F1-makro {sc['f1_macro']:.3f}")

    print(f"\n1) ARIZA YAKALAMA (en kritik sayı)")
    print(f"   {fd['n_faults']} arızalı numunenin {fd['missed']} tanesine "
          f"'Normal' dendi")
    print(f"   kaçırma oranı  : %{100 * fd['miss_rate']:.1f}")
    print(f"   arıza duyarlılığı: %{100 * fd['recall']:.1f}")
    print(f"   yanlış alarm   : {fd['n_normal']} normal numunenin "
          f"{fd['false_alarms']}'i (%{100 * fd['false_alarm_rate']:.1f})")
    if fd["missed_cases"]:
        print(f"   kaçırılan sınıflar: {fd['missed_cases']}")

    print(f"\n2) ARIZA AİLESİ (Normal / Termal / Deşarj)")
    print(f"   doğruluk {fam['accuracy']:.3f} · F1-makro {fam['f1_macro']:.3f}")
    print("   yapılacak iş bu seviyede belirlenir")

    print(f"\n3) CİDDİ ARIZALAR (D2 ark, T3 >700 °C)")
    print(f"   {sv['n']} ciddi vakanın {sv['declared_normal']} tanesine "
          f"'Normal' dendi")
    print(f"   doğru aileye atanan: {sv['family_correct']}/{sv['n']} "
          f"(%{100 * sv['family_recall']:.1f})")

    print(f"\n4) SEÇİCİ TAHMİN — emin değilse uzmana devret")
    print(f"   {'eşik':>6}{'kapsama':>10}{'karar':>8}{'doğruluk':>11}"
          f"{'F1':>9}")
    for r in report["selective"]:
        print(f"   {r['threshold']:>6.1f}{100 * r['coverage']:>9.0f}%"
              f"{r['n']:>8}{r['accuracy']:>11.3f}{r['f1_macro']:>9.3f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--real", type=Path, required=True)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--test-size", type=float, default=0.3)
    args = ap.parse_args()

    report = evaluate(args.real, seed=args.seed, test_size=args.test_size)
    _print(report)
    print(f"\nRapor: {ARTIFACT_DIR / 'safety_report.json'}")


if __name__ == "__main__":
    main()
