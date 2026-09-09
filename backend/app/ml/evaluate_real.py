"""Sentetik veriyle eğitilen modeli GERÇEK veride sınar. — Faz 6

Projenin en kritik sorusu şu: "IEC 60599 imzalarına göre ürettiğim sentetik
veriyle eğitilen model, gerçek trafolardan alınmış ölçümlerde de çalışıyor
mu?" Bu betik onu ölçer ve dört senaryoyu aynı test setinde karşılaştırır:

  A. Sentetik-eğitimli  -> gerçek test   (SIFIR ATIŞ / zero-shot)
  B. Gerçek-eğitimli    -> gerçek test   (üst sınır: aynı dağılım)
  C. Karma eğitim       -> gerçek test   (sentetik veri işe yarıyor mu?)
  D. Klasik konsensüs   -> gerçek test   (öğrenmesiz temel çizgi)

A ile B arasındaki fark "alan kayması" (domain shift) demektir. C, A'dan
iyiyse sentetik veri gerçek veriyi zenginleştiriyor demektir; C, B'den
kötüyse sentetik veri gürültü katıyordur. İkisi de yayımlanabilir bir bulgu.

TÜM deneyler beş gazlı çekirdek özellik setiyle yapılır
(``features.CORE_FEATURE_NAMES``): açık veri setlerinde CO/CO2 yoktur, bu
yüzden yedi gazlı modelle karşılaştırma adil olmaz.

Çalıştırma (backend/ klasöründen):
    python -m app.ml.evaluate_real
    python -m app.ml.evaluate_real --train data/DGA_train.xlsx \
        --test data/DGA_test_unseen.xlsx --bench data/IEC_TC_10_data.xlsx
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score

from ..core.classify import consensus
from ..core.gases import FAULT_CLASSES
from .features import CORE_FEATURE_NAMES, CORE_GASES, build_features
from .real_data import DATA_DIR, load_real_dataset, print_report
from .synth import make_dataset
# Aday modeller train.py ile AYNI olmalı ki karşılaştırma anlamlı olsun.
from .train import ARTIFACT_DIR, _candidate_models

# data/ klasöründe dosya adı verilmediğinde aranacak kalıplar.
_GUESS = {
    "train": ["*train*"],
    "test": ["*test*", "*unseen*"],
    "bench": ["*iec*", "*tc*10*", "*bench*"],
}


def _guess_file(kind: str) -> Optional[Path]:
    if not DATA_DIR.exists():
        return None
    for pattern in _GUESS[kind]:
        hits = sorted(p for p in DATA_DIR.glob(pattern)
                      if p.suffix.lower() in (".xlsx", ".xls", ".csv"))
        if hits:
            return hits[0]
    return None


def _xy(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """Temiz veri çerçevesi -> (çekirdek özellikler, etiket listesi)."""
    X = build_features(df.drop(columns=["label"]), CORE_FEATURE_NAMES)
    return X, df["label"].astype(str).tolist()


def _score(y_true: List[str], y_pred: List[str]) -> Dict[str, float]:
    return {
        "accuracy": round(float(accuracy_score(y_true, y_pred)), 4),
        "f1_macro": round(float(f1_score(y_true, y_pred, average="macro",
                                         zero_division=0)), 4),
    }


def _fit_predict(X_train: pd.DataFrame, y_train: List[str],
                 X_test: pd.DataFrame) -> Dict[str, List[str]]:
    """Her aday modeli eğitip test setindeki tahminlerini döndürür."""
    label_to_int = {c: i for i, c in enumerate(FAULT_CLASSES)}
    y_int = [label_to_int[y] for y in y_train]

    preds: Dict[str, List[str]] = {}
    for name, model in _candidate_models().items():
        model.fit(X_train, y_int)
        preds[name] = [FAULT_CLASSES[int(i)] for i in model.predict(X_test)]
    return preds


def _classical_predict(df: pd.DataFrame) -> List[str]:
    """Klasik konsensüs; CO/CO2 bilinmediği için 0 verilir.

    NOT: key_gas yönteminin CO baskınlığı dalı bu yüzden devre dışı kalır.
    Duval, Rogers ve IEC oran yöntemleri beş gazla tam çalışır.
    """
    out: List[str] = []
    for _, row in df.iterrows():
        g = {k: float(row[k]) for k in CORE_GASES}
        g["CO"] = 0.0
        g["CO2"] = 0.0
        out.append(str(consensus(g)["prediction"]))
    return out


def evaluate(train_path: Optional[Path], test_path: Path,
             bench_path: Optional[Path] = None,
             n_synth: int = 4000, seed: int = 42) -> Dict[str, object]:
    # --- Gerçek veri ---
    real_test, rep_test = load_real_dataset(test_path)
    print_report(rep_test)
    X_test, y_test = _xy(real_test)

    real_train, rep_train = (None, None)
    if train_path is not None:
        real_train, rep_train = load_real_dataset(train_path)
        print_report(rep_train)

    # --- Sentetik veri, aynı çekirdek özellik setinde ---
    synth = make_dataset(n=n_synth, seed=seed)
    X_synth = build_features(synth.drop(columns=["label"]), CORE_FEATURE_NAMES)
    y_synth = synth["label"].astype(str).tolist()

    rows: List[Dict[str, object]] = []

    def add(scenario: str, model: str, note: str, scores: Dict[str, float]):
        rows.append({"scenario": scenario, "model": model, "note": note, **scores})

    # A. Sentetik -> gerçek (sıfır atış)
    t0 = time.time()
    for name, pred in _fit_predict(X_synth, y_synth, X_test).items():
        add("A_sentetik_egitim", name, "sıfır atış: gerçek veriyi hiç görmedi",
            _score(y_test, pred))
    print(f"  [A] tamam ({time.time() - t0:.1f}s)")

    # B ve C yalnızca gerçek eğitim seti varsa
    if real_train is not None:
        X_real, y_real = _xy(real_train)

        t0 = time.time()
        for name, pred in _fit_predict(X_real, y_real, X_test).items():
            add("B_gercek_egitim", name, "aynı dağılım: pratik üst sınır",
                _score(y_test, pred))
        print(f"  [B] tamam ({time.time() - t0:.1f}s)")

        X_mix = pd.concat([X_synth, X_real], ignore_index=True)
        y_mix = y_synth + y_real
        t0 = time.time()
        for name, pred in _fit_predict(X_mix, y_mix, X_test).items():
            add("C_karma_egitim", name, "sentetik + gerçek birlikte",
                _score(y_test, pred))
        print(f"  [C] tamam ({time.time() - t0:.1f}s)")

    # D. Klasik konsensüs (eğitimsiz)
    add("D_klasik", "Classical Consensus",
        "eğitimsiz; CO/CO2=0 olduğu için key_gas kısmen devre dışı",
        _score(y_test, _classical_predict(real_test)))

    # Karışıklık matrisi: en iyi ML senaryosu için
    best = max((r for r in rows if r["scenario"] != "D_klasik"),
               key=lambda r: r["f1_macro"])
    best_pred = None
    if best["scenario"] == "A_sentetik_egitim":
        best_pred = _fit_predict(X_synth, y_synth, X_test)[best["model"]]
    elif real_train is not None:
        X_real, y_real = _xy(real_train)
        if best["scenario"] == "B_gercek_egitim":
            best_pred = _fit_predict(X_real, y_real, X_test)[best["model"]]
        else:
            best_pred = _fit_predict(
                pd.concat([X_synth, X_real], ignore_index=True),
                y_synth + y_real, X_test)[best["model"]]

    report: Dict[str, object] = {
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "feature_set": CORE_FEATURE_NAMES,
        "n_synthetic": n_synth,
        "test_file": rep_test,
        "train_file": rep_train,
        "results": sorted(rows, key=lambda r: -r["f1_macro"]),
        "best": best,
        "confusion_matrix": (
            confusion_matrix(y_test, best_pred, labels=FAULT_CLASSES).tolist()
            if best_pred else None),
        "classes": FAULT_CLASSES,
    }

    # IEC TC 10 karşılaştırma seti varsa onu da ayrıca ölç.
    if bench_path is not None:
        bench, rep_bench = load_real_dataset(bench_path)
        print_report(rep_bench)
        X_b, y_b = _xy(bench)
        bench_rows = [
            {"scenario": "A_sentetik_egitim", "model": name, **_score(y_b, pred)}
            for name, pred in _fit_predict(X_synth, y_synth, X_b).items()
        ]
        bench_rows.append({"scenario": "D_klasik", "model": "Classical Consensus",
                           **_score(y_b, _classical_predict(bench))})
        report["benchmark"] = {"file": rep_bench,
                               "results": sorted(bench_rows,
                                                 key=lambda r: -r["f1_macro"])}

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    with open(ARTIFACT_DIR / "real_data_report.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False)

    return report


def _print_table(rows: List[Dict[str, object]], title: str) -> None:
    print(f"\n{title}")
    print(f"  {'SENARYO':<20}{'MODEL':<16}{'DOĞRULUK':>10}{'F1-MAKRO':>10}")
    print("  " + "-" * 56)
    for r in rows:
        print(f"  {r['scenario']:<20}{r['model']:<16}"
              f"{r['accuracy']:>10.4f}{r['f1_macro']:>10.4f}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--train", type=Path, default=None)
    ap.add_argument("--test", type=Path, default=None)
    ap.add_argument("--bench", type=Path, default=None)
    ap.add_argument("--n-synth", type=int, default=4000)
    args = ap.parse_args()

    test = args.test or _guess_file("test")
    if test is None:
        print("Gerçek test verisi bulunamadı.\n"
              f"Dosyaları {DATA_DIR} klasörüne koy "
              "(açıklama: backend/data/README.md) ya da --test ile yol ver.")
        raise SystemExit(1)

    report = evaluate(args.train or _guess_file("train"), test,
                      args.bench or _guess_file("bench"),
                      n_synth=args.n_synth)

    _print_table(report["results"], "GERÇEK TEST SETİ")
    if "benchmark" in report:
        _print_table(report["benchmark"]["results"], "IEC TC 10 KARŞILAŞTIRMA SETİ")
    print(f"\nRapor: {ARTIFACT_DIR / 'real_data_report.json'}")


if __name__ == "__main__":
    main()
