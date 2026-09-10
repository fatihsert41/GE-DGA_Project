"""Gerçek veri seti yükleyicisinin şema/etiket eşlemesi (Faz 6).

Testler gerçek veri dosyasına BAĞIMLI DEĞİL: her test kendi geçici
dosyasını üretir. Böylece veri seti indirilmemiş bir makinede de çalışır.
"""
from __future__ import annotations

import pandas as pd
import pytest

from app.ml.features import CORE_FEATURE_NAMES, CORE_GASES, build_features
from app.ml.real_data import load_real_dataset, map_label


def _write(tmp_path, rows, name="veri.csv"):
    path = tmp_path / name
    df = pd.DataFrame(rows)
    if path.suffix == ".xlsx":
        df.to_excel(path, index=False)
    else:
        df.to_csv(path, index=False)
    return path


def test_column_aliases_and_label_formats(tmp_path):
    """Farklı sütun adları ve karışık etiket biçimleri tek şemaya iner."""
    path = _write(tmp_path, [
        {"Hydrogen": 20, "CH4 (ppm)": 10, "Ethane": 8, "C2H4": 6,
         "Acetylene": 0.3, "Fault Type": 0},              # tam sayı etiket
        {"Hydrogen": 280, "CH4 (ppm)": 120, "Ethane": 40, "C2H4": 220,
         "Acetylene": 240, "Fault Type": "Arcing"},        # metin eşanlamlı
        {"Hydrogen": 120, "CH4 (ppm)": 200, "Ethane": 70, "C2H4": 520,
         "Acetylene": 4, "Fault Type": "T3"},              # doğrudan sınıf adı
    ])
    df, report = load_real_dataset(path)

    assert list(df.columns) == [*CORE_GASES, "label"]
    assert df["label"].tolist() == ["Normal", "D2", "T3"]
    assert report["rows_in"] == 3 and report["rows_out"] == 3
    assert report["column_mapping"]["Hydrogen"] == "H2"


def test_bad_rows_are_dropped_and_counted(tmp_path):
    """Bozuk satırlar sessizce geçmez: atılır ve raporda sayılır."""
    good = {"H2": 60, "CH4": 12, "C2H6": 9, "C2H4": 7, "C2H2": 2, "label": "D1"}
    path = _write(tmp_path, [
        good,
        {**good, "H2": -5},                     # negatif konsantrasyon
        {**good, "CH4": "yok"},                 # sayısal değil
        {**good, "label": "???"},               # çevrilemeyen etiket
        {"H2": 0, "CH4": 0, "C2H6": 0, "C2H4": 0, "C2H2": 0, "label": "PD"},
    ])
    df, report = load_real_dataset(path)

    assert len(df) == 1 and df["label"].iloc[0] == "D1"
    assert report["dropped"]["negatif_deger"] == 1
    assert report["dropped"]["gaz_sayisal_degil"] == 1
    assert report["dropped"]["etiket_cevrilemedi"] == 1
    assert report["dropped"]["tamami_sifir"] == 1


def test_missing_gas_column_raises_with_helpful_message(tmp_path):
    """Eksik gaz sütununda sessizce sıfır uydurmak yerine hata verilir."""
    path = _write(tmp_path, [{"H2": 10, "CH4": 5, "C2H4": 3,
                              "C2H2": 1, "label": 0}])   # C2H6 yok
    with pytest.raises(ValueError, match="C2H6"):
        load_real_dataset(path)


def test_int_order_is_configurable(tmp_path):
    """Sayısal etiket sırası veri setine göre değiştirilebilmeli."""
    assert map_label(1, ["Normal", "PD", "D1"]) == "PD"
    assert map_label(1, ["Normal", "T3", "D1"]) == "T3"
    assert map_label(9, ["Normal", "PD"]) is None          # sıra dışı


def test_xlsx_is_readable_and_feeds_core_features(tmp_path):
    """Excel okunabiliyor ve çıktı doğrudan 5 gazlı özellik hattına giriyor."""
    path = _write(tmp_path, [
        {"H2": 20, "CH4": 10, "C2H6": 8, "C2H4": 6, "C2H2": 0.3, "label": 0},
        {"H2": 280, "CH4": 120, "C2H6": 40, "C2H4": 220, "C2H2": 240, "label": 3},
    ], name="veri.xlsx")
    df, _ = load_real_dataset(path)

    feats = build_features(df.drop(columns=["label"]), CORE_FEATURE_NAMES)
    assert list(feats.columns) == CORE_FEATURE_NAMES
    assert len(feats) == 2
    assert not feats.isnull().any().any()


def test_chinese_labels_are_mapped(tmp_path):
    """Çince etiketli veri setleri (Çin şebeke verisi) tanınmalı."""
    path = _write(tmp_path, [
        {"H2": 20, "CH4": 10, "C2H6": 8, "C2H4": 6, "C2H2": 0.3,
         "故障类型": "正常"},
        {"H2": 1458, "CH4": 9, "C2H6": 1812, "C2H4": 0.1, "C2H2": 0.1,
         "故障类型": "局部放电"},
        {"H2": 120, "CH4": 200, "C2H6": 70, "C2H4": 520, "C2H2": 4,
         "故障类型": "高温过热"},
    ])
    df, report = load_real_dataset(path)
    assert df["label"].tolist() == ["Normal", "PD", "T3"]
    assert report["column_mapping"]["故障类型"] == "label"


def test_duplicate_measurements_are_removed(tmp_path):
    """Birebir aynı ölçüm atılır: eğitim/test bölmesinde sızıntı yapardı."""
    row = {"H2": 60, "CH4": 12, "C2H6": 9, "C2H4": 7, "C2H2": 2, "label": "D1"}
    path = _write(tmp_path, [row, dict(row), dict(row),
                             {**row, "H2": 61}])
    df, report = load_real_dataset(path)
    assert len(df) == 2
    assert report["dropped"]["tekrar_eden"] == 2

    kept, _ = load_real_dataset(path, drop_duplicates=False)
    assert len(kept) == 4          # kapatılabilir olmalı
