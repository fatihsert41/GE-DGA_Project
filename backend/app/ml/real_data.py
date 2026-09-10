"""Gerçek (açık kaynak) DGA veri setlerini projenin şemasına çevirir. — Faz 6

Neden ayrı bir modül? Çünkü dışarıdan gelen veri hiçbir zaman bizim
beklediğimiz biçimde değildir:

* Sütun adları değişir: ``H2``, ``h2``, ``Hydrogen``, ``H2 (ppm)`` ...
* Etiketler bazen metin (``PD``, ``D1``), bazen tam sayı (``0..6``) olur.
* Gaz seti beş gazdır: CO ve CO2 **yoktur** (bkz. features.CORE_GASES).

Bu modül tek bir iş yapar: ne gelirse gelsin, çıktı olarak
``[H2, CH4, C2H6, C2H4, C2H2, label]`` sütunlu temiz bir DataFrame ve
neyin nasıl eşlendiğini anlatan bir rapor üretir. Sessizce tahmin
yürütmez; emin olamadığı satırı atar ve raporda söyler.

Kullanım (backend/ klasöründen):
    python -m app.ml.real_data data/DGA_train.xlsx
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

from ..core.gases import FAULT_CLASSES
from .features import CORE_GASES

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# --- Sütun adı eşlemesi ---------------------------------------------------
# Anahtarlar sadeleştirilmiş hâldir: küçük harf, harf-rakam dışı her şey atılmış.
# Yani "C2H4 (ppm)" -> "c2h4ppm" -> aşağıdaki listede aranır.
_COLUMN_ALIASES: Dict[str, str] = {
    "h2": "H2", "hydrogen": "H2", "h2ppm": "H2",
    "ch4": "CH4", "methane": "CH4", "ch4ppm": "CH4",
    "c2h6": "C2H6", "ethane": "C2H6", "c2h6ppm": "C2H6",
    "c2h4": "C2H4", "ethylene": "C2H4", "ethene": "C2H4", "c2h4ppm": "C2H4",
    "c2h2": "C2H2", "acetylene": "C2H2", "ethyne": "C2H2", "c2h2ppm": "C2H2",
    "co": "CO", "carbonmonoxide": "CO",
    "co2": "CO2", "carbondioxide": "CO2",
    "label": "label", "class": "label", "fault": "label",
    "faulttype": "label", "faultclass": "label", "type": "label",
    "target": "label", "y": "label", "code": "label",
    "故障类型": "label",        # Çince: "arıza türü"
}

# --- Etiket eşlemesi ------------------------------------------------------
# Metin etiketlerin bilinen yazımları -> bizim yedi sınıfımız.
_LABEL_ALIASES: Dict[str, str] = {
    "normal": "Normal", "nofault": "Normal", "healthy": "Normal", "n": "Normal",
    "pd": "PD", "partialdischarge": "PD", "corona": "PD",
    "d1": "D1", "lowenergydischarge": "D1", "dischargelowenergy": "D1",
    "sparking": "D1",
    "d2": "D2", "highenergydischarge": "D2", "dischargehighenergy": "D2",
    "arcing": "D2", "arc": "D2",
    "t1": "T1", "thermalfaultbelow300": "T1", "lowtemperatureoverheating": "T1",
    "t2": "T2", "thermalfault300700": "T2", "mediumtemperatureoverheating": "T2",
    "t3": "T3", "thermalfaultabove700": "T3", "hightemperatureoverheating": "T3",

    # Çince etiketler: Çin şebeke verisi bu terimlerle yayımlanıyor.
    "正常": "Normal",          # normal
    "局部放电": "PD",           # kısmi deşarj
    "低能放电": "D1",           # düşük enerjili deşarj
    "火花放电": "D1",           # kıvılcım deşarjı
    "高能放电": "D2",           # yüksek enerjili deşarj
    "电弧放电": "D2",           # ark deşarjı
    "低温过热": "T1",           # düşük sıcaklıkta aşırı ısınma (<300 °C)
    "中温过热": "T2",           # orta sıcaklıkta aşırı ısınma (300-700 °C)
    "中低温过热": "T2",         # düşük-orta sıcaklık
    "高温过热": "T3",           # yüksek sıcaklıkta aşırı ısınma (>700 °C)
}

# Sayısal etiketler için VARSAYILAN sıra. Veri seti bunu belgelemiyorsa
# kesin bilinemez; bu yüzden değiştirilebilir ve rapor her zaman dağılımı
# yazdırır — dağılım mantıksızsa (ör. %90'ı tek sınıf) sıra yanlıştır.
DEFAULT_INT_ORDER: List[str] = list(FAULT_CLASSES)  # 0=Normal,1=PD,...,6=T3


def _simplify(name: object) -> str:
    r"""'C2H4 (ppm)' -> 'c2h4ppm'. Eşleme tablosunun aradığı biçim.

    Boşluk, noktalama ve alt çizgi atılır; harf/rakam kalır. ``\W`` yerine
    ``[\W_]`` kullanılıyor çünkü ``\w`` alt çizgiyi de harf sayar.
    Unicode korunur: Çince etiketli veri setleri var (``局部放电`` gibi),
    ASCII'ye indirgeseydik hepsi boş dizeye dönerdi.
    """
    return re.sub(r"[\W_]", "", str(name).lower(), flags=re.UNICODE)


def load_table(path: Path) -> pd.DataFrame:
    """.xlsx / .xls / .csv ayrımını tek yerde yapar."""
    suffix = path.suffix.lower()
    if suffix in (".xlsx", ".xls"):
        return pd.read_excel(path)
    if suffix in (".csv", ".txt"):
        return pd.read_csv(path)
    raise ValueError(f"Desteklenmeyen dosya türü: {suffix}")


def map_columns(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, str]]:
    """Sütun adlarını bizim şemamıza çevirir; eşlemeyi de döndürür."""
    mapping: Dict[str, str] = {}
    for col in df.columns:
        target = _COLUMN_ALIASES.get(_simplify(col))
        if target:
            mapping[str(col)] = target
    return df.rename(columns=mapping), mapping


def map_label(value: object, int_order: List[str]) -> Optional[str]:
    """Tek bir etiketi bizim sınıf adımıza çevirir; çeviremezse None."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    # Tam sayı etiket (0..6). "3.0" gibi float gelmesi de yaygın.
    if isinstance(value, (int, float)) and float(value).is_integer():
        idx = int(value)
        return int_order[idx] if 0 <= idx < len(int_order) else None

    key = _simplify(value)
    if key in _LABEL_ALIASES:
        return _LABEL_ALIASES[key]
    if key.isdigit():                       # metin olarak yazılmış sayı
        idx = int(key)
        return int_order[idx] if 0 <= idx < len(int_order) else None
    return None


def load_real_dataset(path: Path,
                      int_order: Optional[List[str]] = None,
                      drop_duplicates: bool = True
                      ) -> Tuple[pd.DataFrame, Dict[str, object]]:
    """Bir gerçek veri seti dosyasını yükler ve temizler.

    Döndürür: (temiz DataFrame, rapor). DataFrame sütunları
    ``CORE_GASES + ['label']``; rapor ne bulunduğunu ve ne atıldığını anlatır.
    """
    int_order = int_order or DEFAULT_INT_ORDER
    raw = load_table(path)
    df, colmap = map_columns(raw)

    missing = [g for g in CORE_GASES if g not in df.columns]
    if missing:
        raise ValueError(
            f"{path.name}: şu gaz sütunları bulunamadı: {missing}. "
            f"Dosyadaki sütunlar: {list(raw.columns)}")
    if "label" not in df.columns:
        raise ValueError(
            f"{path.name}: etiket sütunu bulunamadı. "
            f"Dosyadaki sütunlar: {list(raw.columns)}")

    n_in = len(df)
    out = df[[*CORE_GASES, "label"]].copy()

    # Gazlar sayısal olmalı; olmayan hücreler NaN'a döner ve satır atılır.
    for g in CORE_GASES:
        out[g] = pd.to_numeric(out[g], errors="coerce")

    out["label"] = out["label"].map(lambda v: map_label(v, int_order))

    unmapped = int(out["label"].isna().sum())
    nan_gas = int(out[CORE_GASES].isna().any(axis=1).sum())
    out = out.dropna()

    # Negatif konsantrasyon fiziksel olarak imkânsız.
    negative = int((out[CORE_GASES] < 0).any(axis=1).sum())
    out = out[(out[CORE_GASES] >= 0).all(axis=1)]

    # Tamamı sıfır olan satır ölçüm değil, boş kayıttır.
    all_zero = int((out[CORE_GASES].sum(axis=1) == 0).sum())
    out = out[out[CORE_GASES].sum(axis=1) > 0]

    # Birebir aynı ölçümler: derleme veri setlerinde aynı vaka birden çok
    # kaynaktan girdiği için sık görülür. Temizlenmezse rastgele bölmede
    # aynı satır hem eğitime hem teste düşer; model ezberler ve doğruluk
    # yapay olarak şişer (veri sızıntısı).
    duplicates = int(out.duplicated(subset=CORE_GASES).sum())
    if drop_duplicates:
        out = out.drop_duplicates(subset=CORE_GASES)

    out = out.reset_index(drop=True)
    report = {
        "file": path.name,
        "rows_in": n_in,
        "rows_out": len(out),
        "column_mapping": colmap,
        "dropped": {
            "etiket_cevrilemedi": unmapped,
            "gaz_sayisal_degil": nan_gas,
            "negatif_deger": negative,
            "tamami_sifir": all_zero,
            "tekrar_eden": duplicates if drop_duplicates else 0,
        },
        "duplicates_found": duplicates,
        "class_counts": out["label"].value_counts().to_dict(),
        "missing_classes": [c for c in FAULT_CLASSES
                            if c not in set(out["label"])],
    }
    return out, report


def print_report(report: Dict[str, object]) -> None:
    print(f"\n=== {report['file']} ===")
    print(f"  satır: {report['rows_in']} -> {report['rows_out']}")
    print(f"  sütun eşlemesi: {report['column_mapping']}")
    dropped = {k: v for k, v in report["dropped"].items() if v}
    print(f"  atılan: {dropped or 'yok'}")
    print("  sınıf dağılımı:")
    for cls in FAULT_CLASSES:
        n = report["class_counts"].get(cls, 0)
        bar = "#" * min(40, n)
        print(f"    {cls:<7}{n:>5}  {bar}")
    if report["missing_classes"]:
        print(f"  ⚠ veri setinde hiç olmayan sınıflar: "
              f"{report['missing_classes']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print(f"\nAranan klasör: {DATA_DIR}")
        if DATA_DIR.exists():
            found = [p.name for p in DATA_DIR.iterdir() if p.is_file()]
            print(f"İçindekiler: {found or '(boş)'}")
        else:
            print("Klasör henüz yok.")
        raise SystemExit(1)

    for arg in sys.argv[1:]:
        p = Path(arg)
        if not p.is_absolute():
            p = Path.cwd() / p
        df, rep = load_real_dataset(p)
        print_report(rep)
        print(df.head())
