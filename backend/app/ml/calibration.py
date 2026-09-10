"""Güven değerinin ölçülmesi: eşik nereden geliyor? — Düzeltme P0-4

SORUN
-----
``CONFIDENCE_THRESHOLD = 0.90`` değeri Faz 6.4'te **gerçek veriyle eğitilmiş
bir XGBoost** modelinde ölçüldü. Ama ``/predict`` uç noktasına hizmet veren
model **sentetik veriyle eğitilmiş bir RandomForest** ve farklı bir özellik
seti kullanıyor (12'ye karşı 23 özellik, ortak olan yalnızca 9).

Yani "bu eşiğin altında doğruluk %54" cümlesi hizmet veren model için
KANITLANMAMIŞTI. Dış inceleme bunu haklı olarak P0 saydı.

ÇÖZÜM
-----
Eşik, hizmet veren modelin **kendi ayrılmış test kümesinde** ölçülür ve
sonuç modelin yanında saklanır. Böylece her tahmin, eşiğin hangi modelde,
hangi veride ve hangi kapsamada ölçüldüğünü söyleyebilir.

DÜRÜSTLÜK SINIRI
----------------
Bu ölçüm **sentetik** test kümesinde yapılır, çünkü hizmet veren model
yedi gaz ister ve elimizdeki gerçek veri beş gaz içerir — yani bu model
gerçek veride doğrudan sınanamaz. Sonuç bu yüzden ``domain: "synthetic"``
olarak etiketlenir. Sentetik alandaki kalibrasyon, gerçek dünya garantisi
değildir; sadece "kendi dağılımında ne kadar dürüst?" sorusunu yanıtlar.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence

import numpy as np

# Güven bantları. Alt sınırlar; üst sınır bir sonraki bandın altı.
DEFAULT_BINS: Sequence[float] = (0.0, 0.5, 0.7, 0.8, 0.9, 0.99, 1.01)

# Eşik seçiminde hedeflenen isabet. Bunun üstünde karar veren model,
# vakaların en az bu oranında haklı olmalı.
DEFAULT_TARGET_ACCURACY = 0.90

# Eşiğin anlamlı olması için en az bu kadar vakayı kapsaması gerekir.
# %10 kapsamayla %99 isabet tutturmak, sistemi neredeyse hiç karar
# vermez hale getirir.
MIN_COVERAGE = 0.50


def confidence_report(y_true: Sequence[str], y_pred: Sequence[str],
                      confidence: Sequence[float],
                      bins: Sequence[float] = DEFAULT_BINS
                      ) -> Dict[str, object]:
    """Model "%X eminim" derken gerçekten %X tutturuyor mu?

    Döndürülen ``ece`` (Expected Calibration Error), bantların ağırlıklı
    ortalama sapmasıdır: 0'a yakın = dürüst, 0.15 üstü = kötü.
    """
    y_true = list(y_true)
    y_pred = list(y_pred)
    conf = np.asarray(confidence, dtype=float)
    correct = np.array([t == p for t, p in zip(y_true, y_pred)])
    n = len(correct)

    rows: List[Dict[str, float]] = []
    ece = 0.0
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (conf >= lo) & (conf < hi)
        count = int(mask.sum())
        if count == 0:
            continue
        mean_conf = float(conf[mask].mean())
        accuracy = float(correct[mask].mean())
        ece += (count / n) * abs(mean_conf - accuracy)
        rows.append({
            "lower": round(float(lo), 3),
            "upper": round(float(hi), 3),
            "n": count,
            "mean_confidence": round(mean_conf, 4),
            "accuracy": round(accuracy, 4),
            # Pozitif = model kendini KÜÇÜMSÜYOR, negatif = FAZLA İDDİALI.
            "gap": round(accuracy - mean_conf, 4),
        })

    return {"bins": rows, "ece": round(ece, 4), "n": n}


def choose_threshold(y_true: Sequence[str], y_pred: Sequence[str],
                     confidence: Sequence[float],
                     target_accuracy: float = DEFAULT_TARGET_ACCURACY,
                     min_coverage: float = MIN_COVERAGE
                     ) -> Dict[str, object]:
    """Hedef isabeti sağlayan EN DÜŞÜK eşiği bulur.

    En düşük olanı seçiyoruz çünkü eşik yükseldikçe daha çok vaka uzmana
    devredilir; amaç isabeti sağlayan en geniş kapsamadır.

    Hiçbir eşik hedefi sağlayamıyorsa ``met=False`` döner ve en iyi
    bulunan aday raporlanır — sessizce çalışmayan bir eşik koymaktansa
    "sağlanamadı" demek doğrudur.
    """
    y_true = list(y_true)
    y_pred = list(y_pred)
    conf = np.asarray(confidence, dtype=float)
    correct = np.array([t == p for t, p in zip(y_true, y_pred)])
    n = len(correct)

    candidates: List[Dict[str, float]] = []
    for th in np.round(np.arange(0.50, 1.001, 0.01), 2):
        mask = conf >= th
        covered = int(mask.sum())
        if covered == 0:
            continue
        candidates.append({
            "threshold": float(th),
            "coverage": round(covered / n, 4),
            "n": covered,
            "accuracy": round(float(correct[mask].mean()), 4),
            # Eşiğin ALTINDA kalanların isabeti: eşik gerçekten zor
            # vakaları ayıklıyorsa bu belirgin düşük olmalı.
            "accuracy_below": (round(float(correct[~mask].mean()), 4)
                               if (~mask).any() else None),
        })

    ok = [c for c in candidates
          if c["accuracy"] >= target_accuracy and c["coverage"] >= min_coverage]

    if ok:
        chosen = min(ok, key=lambda c: c["threshold"])
        met = True
    else:
        # Hedefe en çok yaklaşan adayı bildir.
        chosen = max(candidates, key=lambda c: c["accuracy"]) if candidates \
            else {"threshold": 0.9, "coverage": 0.0, "n": 0,
                  "accuracy": 0.0, "accuracy_below": None}
        met = False

    return {
        "threshold": chosen["threshold"],
        "target_accuracy": target_accuracy,
        "met": met,
        "coverage": chosen["coverage"],
        "accuracy_above": chosen["accuracy"],
        "accuracy_below": chosen["accuracy_below"],
        "n_above": chosen["n"],
        "curve": candidates[::5],   # her 0.05'te bir örnek nokta
    }


def measure(y_true: Sequence[str], y_pred: Sequence[str],
            confidence: Sequence[float], model_name: str,
            domain: str, dataset: str,
            target_accuracy: float = DEFAULT_TARGET_ACCURACY
            ) -> Dict[str, object]:
    """Eşik + kalibrasyon ölçümünü KÖKENİYLE birlikte paketler.

    ``domain`` ve ``dataset`` alanları kritik: eşiğin hangi modelde ve
    hangi veride ölçüldüğü, eşiğin kendisi kadar önemlidir. Faz 6.4'teki
    hata tam olarak bu bilginin taşınmamasıydı.
    """
    threshold = choose_threshold(y_true, y_pred, confidence, target_accuracy)
    report = confidence_report(y_true, y_pred, confidence)

    return {
        "measured_on": {
            "model": model_name,
            "domain": domain,       # "synthetic" | "real"
            "dataset": dataset,
            "n_test": report["n"],
        },
        "threshold": threshold["threshold"],
        "target_met": threshold["met"],
        "coverage": threshold["coverage"],
        "accuracy_above": threshold["accuracy_above"],
        "accuracy_below": threshold["accuracy_below"],
        "ece": report["ece"],
        "calibrated": report["ece"] < 0.05,
        "bins": report["bins"],
        "curve": threshold["curve"],
    }


def summary_line(measurement: Optional[Dict[str, object]]) -> str:
    """Arayüzde ve API'de gösterilecek tek cümlelik köken açıklaması."""
    if not measurement:
        return ("Eşik bu model üzerinde ölçülmedi; varsayılan değer "
                "kullanılıyor.")

    m = measurement["measured_on"]
    domain_tr = {"synthetic": "sentetik", "real": "gerçek"}.get(
        str(m["domain"]), str(m["domain"]))
    return (f"Eşik {m['model']} modelinde, {domain_tr} veride ölçüldü "
            f"({m['n_test']} örnek). Üstünde doğruluk "
            f"%{float(measurement['accuracy_above']) * 100:.0f}, "
            f"kapsama %{float(measurement['coverage']) * 100:.0f}.")
