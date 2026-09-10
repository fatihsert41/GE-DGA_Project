"""Veritabanını demo bir trafo filosuyla doldurur.

Dış veri yok: her trafonun geçmişini sentetik "yaşlanma serisi"
üretecinden oluşturur, her örneğe tam tanıyı (ML + klasik + risk)
uygular ve SQLite'a kaydeder. Filo dashboard'unun göstereceği veriyi
üretmek için kullanılır.

Çalıştırma (backend/ klasöründen):  python -m app.ml.seed
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from .. import database
from ..core.gases import GASES
from ..services.diagnosis import diagnose
from .synth import make_aging_series

# (id, ad, konum, hedef arıza senaryosu, ay sayısı, kaç ay saklanacak)
# "Normal" senaryosu = sağlıklı kalan trafo; diğerleri o arızaya doğru kötüleşir.
#
# Son sütun (keep) serinin YALNIZCA ilk N ayını kaydeder: "yeni bozulmaya
# başlamış, imzası henüz oturmamış" trafoyu temsil eder. TR-09 bunun için
# var — model orada "Normal" diyor ama güveni düşük, yani uzman incelemesi
# uyarısı tetikleniyor. Gerçek bir filoda böyle belirsiz vakalar hep olur;
# demo filosunda da olmalı ki sistemin belirsizliği nasıl ele aldığı görünsün.
FLEET = [
    ("TR-01", "Ana Merkez Trafosu", "İstanbul-Avrupa",  "D2", 12, None),
    ("TR-02", "Yük Merkezi 2",       "İstanbul-Anadolu", "Normal", 12, None),
    ("TR-03", "OSB Besleme",         "Kocaeli",          "T3", 10, None),
    ("TR-04", "Şehir Dağıtım",       "Bursa",            "T1", 12, None),
    ("TR-05", "Sahil GIS",           "İzmir",            "Normal", 12, None),
    ("TR-06", "Demiryolu Besleme",   "Ankara",           "PD", 8, None),
    ("TR-07", "Sanayi Fider",        "Gebze",            "D1", 11, None),
    ("TR-08", "Rüzgar Bağlantı",     "Çanakkale",        "T2", 12, None),
    ("TR-09", "Liman Besleme",       "Mersin",           "D1", 12, 5),
]


def _reset() -> None:
    """Tabloları oluştur ve eski demo kayıtları temizle (temiz başlangıç)."""
    database.init_db()
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute("DELETE FROM measurements")
        conn.execute("DELETE FROM transformers")


def seed() -> None:
    _reset()
    total = 0
    for idx, (tid, name, location, scenario, months, keep) in enumerate(FLEET):
        database.upsert_transformer(tid, name, location)

        # Bu trafonun aylık gaz geçmişini üret (senaryosuna doğru kötüleşir).
        df = make_aging_series(fault_class=scenario, months=months, seed=idx + 1)
        if keep is not None:
            df = df.head(keep)      # erken evre: seriyi baştan kes
            months = keep

        # İlk ölçüm 'months' ay önce, sonuncusu bugün olacak şekilde tarihle.
        start = datetime.now(timezone.utc) - timedelta(days=30 * (months - 1))
        for k, (_, row) in enumerate(df.iterrows()):
            gases = {g: float(row[g]) for g in GASES}
            result = diagnose(gases)               # ML + klasik + risk
            sampled_at = (start + timedelta(days=30 * k)).isoformat()
            database.save_measurement(tid, gases, result, sampled_at=sampled_at)
            total += 1

        last = diagnose({g: float(df.iloc[-1][g]) for g in GASES})
        flag = " ⚠ uzman incelemesi" if last["review"]["needed"] else ""
        print(f"  {tid} {name:<22} senaryo={scenario:<6} "
              f"son tanı={last['prediction']:<6} güven=%{last['confidence']*100:>3.0f} "
              f"risk={last['risk']['level_tr']}{flag}")

    print(f"\nToplam {len(FLEET)} trafo, {total} ölçüm kaydedildi.")


if __name__ == "__main__":
    seed()