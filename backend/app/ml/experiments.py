"""Artırım (ablasyon) deneyi: hangi hamle ne kadar kazandırıyor? — Faz 6.3

Faz 6.2 iki ayrı problemi ortaya çıkardı:

  * **A düşük** (sentetik-eğitimli model gerçek veride F1 0.50): model yanlış
    dağılıma çalışmış.
  * **B tavanı** (gerçekle eğitilse bile 0.76): problemin kendi zorluğu +
    beş gaz kısıtı.

Bu betik üç hamleyi ÜST ÜSTE ekleyerek her birinin katkısını ayrı ayrı ölçer.
Ablasyon budur: tek tek ekle, her adımda ölç, farkı hamleye yaz.

  E0  çekirdek özellikler (5 gaz + 4 oran)          -> temel çizgi
  E1  + klasik indikatörler (Duval/Rogers/IEC/KeyGas kararları)
  E2  + sınıf dengeleme (SMOTE)                     -> T1 gibi az örnekli
                                                       sınıflar için
  E3  + logaritmik ölçek                            -> gazlar 0.0001..95650
                                                       ppm arasında değişiyor

Her yapılandırma iki senaryoda ölçülür (Faz 6.2 ile AYNI bölme, seed 42):
  A = sentetik eğitim -> gerçek test  (sıfır atış)
  B = gerçek eğitim   -> gerçek test  (üst sınır)

Çalıştırma (backend/ klasöründen):
    python -m app.ml.experiments --real data/dga_china_2321.xlsx
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split

from ..core.gases import FAULT_CLASSES
from .features import CORE_FEATURE_NAMES, build_features
from .hybrid import HYBRID_FEATURE_NAMES, build_hybrid_features
from .real_data import load_real_dataset, print_report
from .synth import make_dataset
from .train import ARTIFACT_DIR, _candidate_models

try:
    from imblearn.over_sampling import SMOTE
    _HAS_SMOTE = True
except Exception:  # pragma: no cover
    _HAS_SMOTE = False

# Ablasyon adımları: (ad, hibrit mi, dengeleme mi, log mu)
CONFIGS: List[Tuple[str, bool, bool, bool]] = [
    ("E0_cekirdek", False, False, False),
    ("E1_indikator", True, False, False),
    ("E2_dengeleme", True, True, False),
    ("E3_log", True, True, True),
]

_LABEL_TO_INT = {c: i for i, c in enumerate(FAULT_CLASSES)}


def _features(df: pd.DataFrame, hybrid: bool) -> pd.DataFrame:
    raw = df.drop(columns=["label"]) if "label" in df.columns else df
    if hybrid:
        return build_hybrid_features(raw)
    return build_features(raw, CORE_FEATURE_NAMES)


def _apply_log(X: pd.DataFrame) -> pd.DataFrame:
    """Gaz ve oran sütunlarına log1p uygular.

    Neden log1p, düz log değil? Veride 0 ppm ölçümler var ve log(0) tanımsız.
    log1p(x) = log(1+x), sıfırda 0 verir ve küçük değerlerde kararlıdır.

    Kod sütunlarına (duval_code gibi) DOKUNULMAZ: onlar kategori, büyüklük
    değil; logaritmaları anlamsız olurdu.
    """
    out = X.copy()
    for col in CORE_FEATURE_NAMES:
        if col in out.columns:
            out[col] = np.log1p(out[col].clip(lower=0))
    return out


def _fit_predict(X_train: pd.DataFrame, y_train: List[str],
                 X_test: pd.DataFrame, balance: bool,
                 seed: int = 42) -> Dict[str, List[str]]:
    y_int = [_LABEL_TO_INT[y] for y in y_train]

    if balance and _HAS_SMOTE:
        # SMOTE az örnekli sınıflar için sentetik komşular üretir.
        # SADECE eğitim setine uygulanır; test setine dokunmak hile olurdu.
        k = min(5, min(pd.Series(y_int).value_counts()) - 1)
        if k >= 1:
            X_train, y_int = SMOTE(random_state=seed,
                                   k_neighbors=k).fit_resample(X_train, y_int)

    preds: Dict[str, List[str]] = {}
    for name, model in _candidate_models().items():
        model.fit(X_train, y_int)
        preds[name] = [FAULT_CLASSES[int(i)] for i in model.predict(X_test)]
    return preds


def _score(y_true: List[str], y_pred: List[str]) -> Dict[str, float]:
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "f1_macro": round(float(f1_score(y_true, y_pred, average="macro",
                                         zero_division=0)), 4),
    }


def run(real_path: Path, n_synth: int = 4000, seed: int = 42,
        test_size: float = 0.3) -> Dict[str, object]:
    real, rep = load_real_dataset(real_path)
    print_report(rep)

    real_train, real_test = train_test_split(
        real, test_size=test_size, random_state=seed, stratify=real["label"])
    real_train = real_train.reset_index(drop=True)
    real_test = real_test.reset_index(drop=True)
    print(f"\n  katmanlı bölme: {len(real_train)} eğitim / {len(real_test)} test")

    synth = make_dataset(n=n_synth, seed=seed)

    y_synth = synth["label"].astype(str).tolist()
    y_real = real_train["label"].astype(str).tolist()
    y_test = real_test["label"].astype(str).tolist()

    rows: List[Dict[str, object]] = []
    per_class: Dict[str, object] = {}

    for cfg_name, hybrid, balance, use_log in CONFIGS:
        t0 = time.time()
        X_synth = _features(synth, hybrid)
        X_real = _features(real_train, hybrid)
        X_test = _features(real_test, hybrid)
        if use_log:
            X_synth, X_real, X_test = (_apply_log(X_synth), _apply_log(X_real),
                                       _apply_log(X_test))

        for scenario, X_tr, y_tr in (("A_sentetik", X_synth, y_synth),
                                     ("B_gercek", X_real, y_real)):
            for model, pred in _fit_predict(X_tr, y_tr, X_test, balance,
                                            seed).items():
                rows.append({"config": cfg_name, "scenario": scenario,
                             "model": model, **_score(y_test, pred)})
                # En iyi yapılandırmanın sınıf bazı raporu için sakla.
                per_class[f"{cfg_name}|{scenario}|{model}"] = pred

        print(f"  {cfg_name:<16} tamam ({time.time() - t0:.1f}s)")

    # Her (yapılandırma, senaryo) için en iyi modeli özetle.
    summary: Dict[str, Dict[str, object]] = {}
    for cfg_name, *_ in CONFIGS:
        for scenario in ("A_sentetik", "B_gercek"):
            hits = [r for r in rows if r["config"] == cfg_name
                    and r["scenario"] == scenario]
            summary[f"{cfg_name}|{scenario}"] = max(hits,
                                                    key=lambda r: r["f1_macro"])

    best = max(rows, key=lambda r: r["f1_macro"])
    best_key = f"{best['config']}|{best['scenario']}|{best['model']}"
    report = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "n_synthetic": n_synth,
        "n_real_train": len(real_train),
        "n_real_test": len(real_test),
        "source": rep,
        "configs": [c[0] for c in CONFIGS],
        "results": rows,
        "summary": summary,
        "best": best,
        "best_per_class": classification_report(
            y_test, per_class[best_key], labels=FAULT_CLASSES,
            output_dict=True, zero_division=0),
    }

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    with open(ARTIFACT_DIR / "ablation_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)
    return report


def _print_summary(report: Dict[str, object]) -> None:
    summary = report["summary"]
    print("\nHER ADIMIN KATKISI (her hücrede o yapılandırmanın en iyi modeli)")
    print(f"  {'YAPILANDIRMA':<16}{'A sıfır atış':>16}{'B gerçek eğitim':>18}")
    print("  " + "-" * 50)
    prev_a = prev_b = None
    for cfg in report["configs"]:
        a = summary[f"{cfg}|A_sentetik"]
        b = summary[f"{cfg}|B_gercek"]
        da = "" if prev_a is None else f" ({a['f1_macro'] - prev_a:+.3f})"
        db = "" if prev_b is None else f" ({b['f1_macro'] - prev_b:+.3f})"
        print(f"  {cfg:<16}{a['f1_macro']:>8.3f}{da:<8}{b['f1_macro']:>10.3f}{db:<8}")
        prev_a, prev_b = a["f1_macro"], b["f1_macro"]

    print("\n  (değerler F1-makro; parantez içi bir önceki adıma göre fark)")
    best = report["best"]
    print(f"\nEN İYİ: {best['config']} / {best['scenario']} / {best['model']}"
          f"  acc={best['accuracy']} f1={best['f1_macro']}")

    pc = report["best_per_class"]
    print("\nEN İYİNİN SINIF BAZINDA F1'İ")
    for cls in FAULT_CLASSES:
        d = pc.get(cls, {})
        n = int(d.get("support", 0))
        print(f"  {cls:<8}{d.get('f1-score', 0):>7.2f}   (n={n})")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--real", type=Path, required=True)
    ap.add_argument("--n-synth", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--test-size", type=float, default=0.3)
    args = ap.parse_args()

    report = run(args.real, n_synth=args.n_synth, seed=args.seed,
                 test_size=args.test_size)
    _print_summary(report)
    print(f"\nRapor: {ARTIFACT_DIR / 'ablation_report.json'}")


if __name__ == "__main__":
    main()
