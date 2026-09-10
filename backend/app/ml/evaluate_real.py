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
from sklearn.model_selection import train_test_split

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
    "bench": ["*iec*", "*tc*10*", "*bench*", "*589*"],
    "real": ["*data*", "*dga*", "*real*"],
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


def evaluate(real_train: Optional[pd.DataFrame], real_test: pd.DataFrame,
             bench: Optional[pd.DataFrame] = None,
             meta: Optional[Dict[str, object]] = None,
             n_synth: int = 4000, seed: int = 42) -> Dict[str, object]:
    """Dört senaryoyu aynı gerçek test setinde ölçer.

    Veri yükleme/bölme işi ÇAĞIRANA aittir (bkz. main): böylece hem hazır
    bölünmüş veri setleri hem de tek dosyalık setler aynı fonksiyonu kullanır.
    """
    meta = meta or {}
    X_test, y_test = _xy(real_test)

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
        "n_real_train": (len(real_train) if real_train is not None else 0),
        "n_real_test": len(real_test),
        "data": meta,
        "results": sorted(rows, key=lambda r: -r["f1_macro"]),
        "best": best,
        "confusion_matrix": (
            confusion_matrix(y_test, best_pred, labels=FAULT_CLASSES).tolist()
            if best_pred else None),
        "classes": FAULT_CLASSES,
    }

    # Bağımsız ikinci test seti varsa onu da ayrıca ölç.
    if bench is not None and len(bench):
        X_b, y_b = _xy(bench)
        bench_rows = [
            {"scenario": "A_sentetik_egitim", "model": name, **_score(y_b, pred)}
            for name, pred in _fit_predict(X_synth, y_synth, X_b).items()
        ]
        bench_rows.append({"scenario": "D_klasik", "model": "Classical Consensus",
                           **_score(y_b, _classical_predict(bench))})
        report["benchmark"] = {"n": len(bench),
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


def _dedupe_against(df: pd.DataFrame, other: pd.DataFrame) -> Tuple[pd.DataFrame, int]:
    """``other`` içinde de bulunan ölçümleri ``df``den çıkarır.

    Derleme veri setleri aynı vakaları paylaşabilir. Eğitimde görülen bir
    satır "bağımsız" test setinde de varsa sonuç şişer — bu veri sızıntısıdır.
    """
    key = CORE_GASES
    seen = set(map(tuple, other[key].round(4).to_numpy()))
    mask = [tuple(r) not in seen for r in df[key].round(4).to_numpy()]
    return df[mask].reset_index(drop=True), int(len(df) - sum(mask))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--real", type=Path, default=None,
                    help="Tek dosyalık gerçek veri; katmanlı olarak bölünür.")
    ap.add_argument("--train", type=Path, default=None,
                    help="Hazır bölünmüş veri setinin eğitim dosyası.")
    ap.add_argument("--test", type=Path, default=None,
                    help="Hazır bölünmüş veri setinin test dosyası.")
    ap.add_argument("--bench", type=Path, default=None,
                    help="Bağımsız ikinci test seti (kesişimi otomatik atılır).")
    ap.add_argument("--test-size", type=float, default=0.3)
    ap.add_argument("--n-synth", type=int, default=4000)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    meta: Dict[str, object] = {}
    real_train = real_test = None

    if args.real is not None or (args.train is None and args.test is None
                                 and _guess_file("real") is not None):
        # --- Tek dosya: katmanlı böl ---
        path = args.real or _guess_file("real")
        df, rep = load_real_dataset(path)
        print_report(rep)
        meta["source"] = rep
        real_train, real_test = train_test_split(
            df, test_size=args.test_size, random_state=args.seed,
            stratify=df["label"])
        real_train = real_train.reset_index(drop=True)
        real_test = real_test.reset_index(drop=True)
        meta["split"] = {"mode": "stratified", "test_size": args.test_size,
                         "n_train": len(real_train), "n_test": len(real_test)}
        print(f"  katmanlı bölme: {len(real_train)} eğitim / "
              f"{len(real_test)} test")
    else:
        # --- Hazır bölünmüş veri seti ---
        test_path = args.test or _guess_file("test")
        if test_path is None:
            print("Gerçek veri bulunamadı. "
                  f"Dosyaları {DATA_DIR} klasörüne koy "
                  "(açıklama: backend/data/README.md) ya da --real / --test ver.")
            raise SystemExit(1)
        real_test, rep_test = load_real_dataset(test_path)
        print_report(rep_test)
        meta["test_file"] = rep_test

        train_path = args.train or _guess_file("train")
        if train_path is not None:
            real_train, rep_train = load_real_dataset(train_path)
            print_report(rep_train)
            meta["train_file"] = rep_train

    # --- Bağımsız ikinci test seti ---
    bench = None
    bench_path = args.bench or _guess_file("bench")
    if bench_path is not None:
        bench, rep_bench = load_real_dataset(bench_path)
        print_report(rep_bench)
        n_before = len(bench)
        for part in (real_train, real_test):
            if part is not None:
                bench, removed = _dedupe_against(bench, part)
        meta["bench_file"] = rep_bench
        meta["bench_overlap_removed"] = n_before - len(bench)
        print(f"  kesişim temizliği: {n_before} -> {len(bench)} "
              f"({n_before - len(bench)} satır ana veriyle ortaktı)")

    report = evaluate(real_train, real_test, bench, meta=meta,
                      n_synth=args.n_synth, seed=args.seed)

    _print_table(report["results"], "GERÇEK TEST SETİ")
    if "benchmark" in report:
        _print_table(report["benchmark"]["results"],
                     f"BAĞIMSIZ İKİNCİ TEST SETİ (n={report['benchmark']['n']})")
    print(f"Rapor: {ARTIFACT_DIR / 'real_data_report.json'}")


if __name__ == "__main__":
    main()
