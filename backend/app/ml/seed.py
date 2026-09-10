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
from ..core import assets
from ..core.gases import GASES
from ..services.diagnosis import diagnose
from .synth import make_aging_series

# (id, ad, konum, sınıf, MVA, senaryo, ay sayısı, kaç ay saklanacak, gecikme)
#
# Son sütun (gecikme) tüm seriyi geçmişe kaydırır: "bu trafodan uzun süredir
# numune alınmamış" demektir. Gerçek filolarda ihmal edilen varlıklar olur ve
# sorunlar tam oralarda saklanır — TR-06 ve TR-09 bunu temsil ediyor.
#
# Sınıflar GE Vernova'nın hattına göre: LPT (Large) ve MPT (Medium) üretimde,
# SPT (Small) hattı kalktı ama saha üniteleri çalışmaya devam ediyor — TR-09
# bilinçli olarak öyle bir eski ünite.
#
# Dağılım öncelik mantığını GÖRÜNÜR kılacak şekilde seçildi: TR-03 yüksek
# riskli bir LPT (öncelik 3.0), TR-07 ise kritik riskli bir MPT (2.8). Yani
# ham riske göre TR-07 önde olurdu; varlık ağırlığı devreye girince TR-03
# öne geçiyor. Sahada da böyle davranılır.
# "Normal" senaryosu = sağlıklı kalan trafo; diğerleri o arızaya doğru kötüleşir.
#
# Son sütun (keep) serinin YALNIZCA ilk N ayını kaydeder: "yeni bozulmaya
# başlamış, imzası henüz oturmamış" trafoyu temsil eder. TR-09 bunun için
# var — model orada "Normal" diyor ama güveni düşük, yani uzman incelemesi
# uyarısı tetikleniyor. Gerçek bir filoda böyle belirsiz vakalar hep olur;
# demo filosunda da olmalı ki sistemin belirsizliği nasıl ele aldığı görünsün.
FLEET = [
    ("TR-01", "Ana Merkez Trafosu", "İstanbul-Avrupa",  "LPT", 250.0, "D2", 12, None, 0),
    ("TR-02", "Yük Merkezi 2",       "İstanbul-Anadolu", "LPT", 150.0, "Normal", 12, None, 0),
    ("TR-03", "OSB Besleme",         "Kocaeli",          "LPT", 180.0, "T3", 10, None, 0),
    ("TR-04", "Şehir Dağıtım",       "Bursa",            "MPT",  50.0, "T1", 12, None, 0),
    ("TR-05", "Sahil GIS",           "İzmir",            "MPT",  80.0, "Normal", 12, None, 0),
    ("TR-06", "Demiryolu Besleme",   "Ankara",           "MPT",  25.0, "PD", 8, None, 14),
    ("TR-07", "Sanayi Fider",        "Gebze",            "MPT",  40.0, "D1", 11, None, 0),
    ("TR-08", "Rüzgar Bağlantı",     "Çanakkale",        "LPT", 120.0, "T2", 12, None, 0),
    ("TR-09", "Liman Besleme",       "Mersin",           "SPT",   8.0, "D1", 12, 5, 26),
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
    for idx, (tid, name, location, cls, mva, scenario, months,
              keep, lag) in enumerate(FLEET):
        database.upsert_transformer(tid, name, location,
                                    asset_class=cls, mva=mva)

        # Bu trafonun aylık gaz geçmişini üret (senaryosuna doğru kötüleşir).
        df = make_aging_series(fault_class=scenario, months=months, seed=idx + 1)
        if keep is not None:
            df = df.head(keep)      # erken evre: seriyi baştan kes
            months = keep

        # İlk ölçüm 'months' ay önce, sonuncusu bugün olacak şekilde tarihle.
        # 'lag' varsa tüm seri o kadar ay daha geriye kayar: son numunenin
        # üstünden 'lag' ay geçmiş olur.
        start = datetime.now(timezone.utc) - timedelta(
            days=30 * (months - 1 + lag))
        for k, (_, row) in enumerate(df.iterrows()):
            gases = {g: float(row[g]) for g in GASES}
            result = diagnose(gases)               # ML + klasik + risk
            sampled_at = (start + timedelta(days=30 * k)).isoformat()
            database.save_measurement(tid, gases, result, sampled_at=sampled_at)
            total += 1

        last = diagnose({g: float(df.iloc[-1][g]) for g in GASES})
        flag = " ⚠ uzman incelemesi" if last["review"]["needed"] else ""
        oncelik = assets.priority_score(last["risk"]["condition"], cls)
        gecikme = f" ⏰ {lag} ay geçti" if lag else ""
        print(f"  {tid} {name:<22} {cls} {mva:>6.0f}MVA {scenario:<6} "
              f"tanı={last['prediction']:<6} risk={last['risk']['level_tr']:<7} "
              f"öncelik={oncelik:>4.2f}{flag}{gecikme}")

    print(f"\nToplam {len(FLEET)} trafo, {total} ölçüm kaydedildi.")


if __name__ == "__main__":
    seed()