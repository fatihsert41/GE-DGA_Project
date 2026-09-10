"""Model teşhisi: iyileştirme yollarından hangisi gerçekten açık? — Faz 6.9

Fikir üretmek kolay, hangi fikrin işe yarayacağını bilmek zor. Bu betik
iki soruyu ölçüyle cevaplar:

  1. **Öğrenme eğrisi** — daha çok veri hâlâ işe yarıyor mu, yoksa doyduk mu?
     Eğri düzleşmişse "veri toplayalım" demek boşuna; hâlâ yükseliyorsa
     model mimarisiyle uğraşmak boşuna.
  2. **Çapraz doğrulama** — tek bölmeden gelen skor şans eseri mi?
     Tek bölmeye bakıp "F1 0.78" demek, tek atışa bakıp nişancı hakkında
     hüküm vermek gibidir.

Bulgular ve yorumu: docs/FAZ6-IYILESTIRME-YOL-HARITASI.md

Çalıştırma (backend/ klasöründen):
    python -m app.ml.diagnostics
"""
from pathlib import Path
import numpy as np, pandas as pd
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.metrics import accuracy_score, f1_score
from ..core.gases import FAULT_CLASSES, FAULT_FAMILY
from .real_data import DATA_DIR, load_real_dataset
from .experiments import _apply_log, _features
from .safety_eval import _train_best

DATA_FILE = DATA_DIR / "dga_china_2321.xlsx"

def run() -> None:
    """Teşhisleri çalıştırır ve raporu yazdırır."""
    real, _ = load_real_dataset(DATA_FILE)
    X_all = _apply_log(_features(real, hybrid=True))
    y_all = real["label"].tolist()

    def fit_score(Xtr, ytr, Xte, yte, seed=42):
        m = _train_best(Xtr, ytr, seed)
        p = [FAULT_CLASSES[int(i)] for i in m.predict(Xte)]
        return (f1_score(yte, p, average="macro", zero_division=0),
                accuracy_score(yte, p), p)

    # --- 1. OGRENME EGRISI: daha cok veri ise yarar mi? ---
    print("=" * 68)
    print("1) OGRENME EGRISI  (gercek egitim verisinin yuzdesi -> F1)")
    print("=" * 68)
    tr_idx, te_idx = train_test_split(np.arange(len(real)), test_size=0.3,
                                      random_state=42, stratify=real["label"])
    Xte, yte = X_all.iloc[te_idx], [y_all[i] for i in te_idx]
    print(f"{'oran':>6}{'n':>7}{'F1 ort':>10}{'std':>8}")
    onceki = None
    for frac in (0.15, 0.3, 0.5, 0.75, 1.0):
        skorlar = []
        for s in (0, 1, 2):
            if frac < 1.0:
                sub, _ = train_test_split(tr_idx, train_size=frac, random_state=s,
                                          stratify=[y_all[i] for i in tr_idx])
            else:
                sub = tr_idx
            f1, _, _ = fit_score(X_all.iloc[sub], [y_all[i] for i in sub], Xte, yte)
            skorlar.append(f1)
        m, sd = np.mean(skorlar), np.std(skorlar)
        fark = "" if onceki is None else f"  ({m-onceki:+.3f})"
        print(f"{frac:>6.0%}{int(frac*len(tr_idx)):>7}{m:>10.3f}{sd:>8.3f}{fark}")
        onceki = m

    # --- 2. KARARLILIK: 0.78 ne kadar guvenilir bir sayi? ---
    print()
    print("=" * 68)
    print("2) 5 KATLI CAPRAZ DOGRULAMA  (tek bolmeye guvenmek yerine)")
    print("=" * 68)
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    f1s, accs, aile = [], [], []
    for tr, te in skf.split(X_all, y_all):
        f1, acc, p = fit_score(X_all.iloc[tr], [y_all[i] for i in tr],
                               X_all.iloc[te], [y_all[i] for i in te])
        f1s.append(f1); accs.append(acc)
        yt = [y_all[i] for i in te]
        aile.append(accuracy_score([FAULT_FAMILY[t] for t in yt],
                                   [FAULT_FAMILY[q] for q in p]))
    print(f"  F1-makro : {np.mean(f1s):.3f} ± {np.std(f1s):.3f}   "
          f"(katlar: {', '.join(f'{x:.3f}' for x in f1s)})")
    print(f"  Dogruluk : {np.mean(accs):.3f} ± {np.std(accs):.3f}")
    print(f"  Aile     : {np.mean(aile):.3f} ± {np.std(aile):.3f}")


if __name__ == "__main__":
    run()
