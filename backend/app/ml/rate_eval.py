"""Gaz üretim hızı ölçütünün katkısını ÖLÇER. — DENEY

Son çalıştırma (15 Eyl 2026): HÜKÜM "EKLEME" — 106 seride 0 erken
yakalama. Bkz. ``docs/DENEY-GAZ-URETIM-HIZI.md``.

NEDEN ÖNCE ÖLÇÜYORUZ?
---------------------
Faz 6.5'te "ML ve klasik ayrışıyor" kuralı eklenmek üzereydi; ölçüldü ve
ELENDİ (%45 tetikleniyordu ama tetiklendiğinde model daha doğruydu).
Faz 6.7'de sentetik üretecin "şiddet" bileşeni dağılımı gerçeğe en çok
yaklaştıran şeydi ama aktarıma EN ÇOK ZARAR verdi.

Ders aynı: **bir kuralın makul görünmesi, işe yaradığı anlamına gelmez.**
Bu betik iki soruyu ölçer:

1. Hız ölçütü kararı KAÇ VAKADA değiştiriyor? (değiştirmiyorsa gereksiz)
2. Arızayı mutlak derişimden KAÇ AY ÖNCE yakalıyor? (asıl iddia bu)

Çalıştırma (backend/ klasöründen):  python -m app.ml.rate_eval
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from ..core import rate as rate_core
from ..core import risk as risk_core
from ..core.gases import GASES
from .synth import make_aging_series

# Alarm eşiği: kondisyon 3 ve üstü "detaylı inceleme planla" demek.
ALARM_CONDITION = 3

FAULTS = ["PD", "D1", "D2", "T1", "T2", "T3"]
SEEDS = list(range(1, 21))      # arıza başına 20 seri
MONTHS = 18


def _series_rows(fault: str, seed: int) -> List[Dict[str, object]]:
    """Aylık ölçüm serisi üretir ve tarihlendirir."""
    df = make_aging_series(fault_class=fault, months=MONTHS, seed=seed)
    start = datetime.now(timezone.utc) - timedelta(days=30 * (MONTHS - 1))
    rows = []
    for k, (_, row) in enumerate(df.iterrows()):
        rows.append({
            "sampled_at": (start + timedelta(days=30 * k)).isoformat(),
            "gases": {g: float(row[g]) for g in GASES},
        })
    return rows


def _first_alarm_month(rows: List[Dict[str, object]],
                       use_rate: bool) -> Optional[int]:
    """Hangi ayda ilk kez alarm eşiğine ulaşıldı? Ulaşılmadıysa None.

    Her ay, O ANA KADARKİ ölçümlerle karar verilir — gerçek işletmede
    geleceği bilmediğimiz için. Tüm seriyi görüp geriye dönük hız
    hesaplamak, olmayan bir bilgiyi kullanmak olurdu.
    """
    for k in range(len(rows)):
        window = rows[:k + 1]
        gases = window[-1]["gases"]
        abs_cond = int(risk_core.assess(gases)["condition"])  # type: ignore[arg-type]

        if not use_rate:
            if abs_cond >= ALARM_CONDITION:
                return k
            continue

        rate_result = rate_core.assess(window)
        combined = rate_core.combine(abs_cond, rate_result)
        if (combined["condition"] or 0) >= ALARM_CONDITION:
            return k
    return None


def run() -> Dict[str, object]:
    print("Gaz uretim hizi olcutu — katki olcumu")
    print(f"  {len(FAULTS)} ariza x {len(SEEDS)} tohum = "
          f"{len(FAULTS) * len(SEEDS)} seri, {MONTHS} ay")
    print(f"  Alarm esigi: kondisyon >= {ALARM_CONDITION}")
    print("")

    per_fault: Dict[str, Dict[str, object]] = {}
    all_gains: List[int] = []
    only_rate = 0        # yalnızca hızın yakaladığı
    only_abs = 0         # yalnızca derişimin yakaladığı
    neither = 0

    for fault in FAULTS:
        gains: List[int] = []
        rate_only = 0
        for seed in SEEDS:
            rows = _series_rows(fault, seed)
            m_abs = _first_alarm_month(rows, use_rate=False)
            m_rate = _first_alarm_month(rows, use_rate=True)

            if m_abs is None and m_rate is None:
                neither += 1
            elif m_abs is None:
                rate_only += 1
                only_rate += 1
            elif m_rate is None:
                only_abs += 1
            else:
                gains.append(m_abs - m_rate)
                all_gains.append(m_abs - m_rate)

        earlier = [g for g in gains if g > 0]
        per_fault[fault] = {
            "median_gain_months": sorted(gains)[len(gains) // 2] if gains else None,
            "earlier_count": len(earlier),
            "same_count": len([g for g in gains if g == 0]),
            "later_count": len([g for g in gains if g < 0]),
            "rate_only_count": rate_only,
        }
        med = per_fault[fault]["median_gain_months"]
        print(f"  {fault:<4} ortanca kazanc {str(med):>4} ay   "
              f"daha erken {len(earlier):>2}/{len(SEEDS)}   "
              f"yalnizca hiz {rate_only:>2}")

    earlier_total = len([g for g in all_gains if g > 0])
    later_total = len([g for g in all_gains if g < 0])
    median_gain = sorted(all_gains)[len(all_gains) // 2] if all_gains else None

    print("")
    print("  TOPLAM")
    print(f"    ortanca kazanc          : {median_gain} ay")
    print(f"    daha ERKEN yakalanan    : {earlier_total}/{len(all_gains)}")
    print(f"    daha GEC yakalanan      : {later_total}/{len(all_gains)}")
    print(f"    yalnizca hizin gordugu  : {only_rate}")
    print(f"    yalnizca derisimin      : {only_abs}")
    print(f"    ikisinin de gormedigi   : {neither}")

    # --- YANLIŞ ALARM KONTROLÜ ------------------------------------------
    # Erken yakalamak tek başına iyi değildir: sağlıklı trafolarda da
    # alarm üretiyorsa ölçüt işe yaramaz. Faz 6.5'te elenen kural tam
    # olarak buna takılmıştı.
    false_abs = false_rate = 0
    for seed in SEEDS:
        rows = _series_rows("Normal", seed)
        if _first_alarm_month(rows, use_rate=False) is not None:
            false_abs += 1
        if _first_alarm_month(rows, use_rate=True) is not None:
            false_rate += 1

    print("")
    print(f"  YANLIS ALARM (saglikli trafo, {len(SEEDS)} seri)")
    print(f"    yalnizca derisim : {false_abs}/{len(SEEDS)}")
    print(f"    derisim + hiz    : {false_rate}/{len(SEEDS)}")

    verdict = ("EKLE" if (median_gain or 0) > 0 and false_rate <= false_abs + 2
               else "EKLEME")
    print("")
    print(f"  HUKUM: {verdict}")

    return {
        "per_fault": per_fault,
        "median_gain_months": median_gain,
        "earlier": earlier_total,
        "later": later_total,
        "only_rate": only_rate,
        "only_absolute": only_abs,
        "false_alarm_absolute": false_abs,
        "false_alarm_with_rate": false_rate,
        "verdict": verdict,
    }


if __name__ == "__main__":
    run()
