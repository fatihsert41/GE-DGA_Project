"""Gaz üretim hızı: IEEE C57.104 değişim hızı ölçütü. — DENEY

⛔ RAFA KALDIRILDI (15 Eyl 2026) — ürüne bağlı DEĞİL
---------------------------------------------------
Ölçüldü ve hiçbir kararı değiştirmediği görüldü (106 seride 0 erken
yakalama): sentetik serilerde en yüksek TDCG hızı ~2.5 ppm/gün, IEEE
1991 eşiği ise 10. Ayrıntı ve yeniden açma koşulları:
``docs/DENEY-GAZ-URETIM-HIZI.md``. Bu modülü bir yere bağlamadan önce
``python -m app.ml.rate_eval`` hükmü "EKLE" olmalı.

METODOLOJİK BOŞLUK
------------------
Sistem şimdiye kadar yalnızca **mutlak derişime** baktı: "H2 = 180 ppm".
Oysa IEEE C57.104'ün ölçütlerinden biri **değişim hızıdır**: "H2 ayda 40
ppm artıyor". İkisi çok farklı şeyler söyler:

    10 yıldır 180 ppm, sabit      → yüksek derişim, SIFIR hız
                                    eski ve kararlı bir arıza, acil değil
    3 ayda 40 → 180 ppm            → aynı derişim, ÇOK YÜKSEK hız
                                    gelişen bir arıza, acil

Sistem bu ikisini **aynı** değerlendiriyordu. Trend altyapısı
(``services/trend.py``) vardı ama yalnızca grafik çiziyordu; karara
girmiyordu.

STANDART DEĞERLERİ
------------------
IEEE C57.104 (1991) Tablo 3, toplam yanıcı gaz (TDCG) üretim hızını
kondisyon seviyelerine bağlar:

    Kondisyon 1   < 10 ppm/gün
    Kondisyon 2   10-30 ppm/gün
    Kondisyon 3   30-100 ppm/gün
    Kondisyon 4   > 100 ppm/gün

⚠ Bu eşikler **yeni** standartta (2019) revize edildi ve üretici/işletme
kendi değerlerini kullanabilir. Burada 1991 tablosu alındı çünkü yaygın
bilinen ve savunulabilir referans o; değerler tek yerde toplandı.

⚠ ÖNEMLİ SINIR — dürüstlük notu
-------------------------------
Bu modül **kural tabanlıdır, ML değildir.** Neden ML'e özellik olarak
eklenmedi? Çünkü ölçülemezdi: elimizdeki gerçek veri seti (2321 kayıt)
**tek noktalı** — aynı trafonun art arda ölçümleri yok, dolayısıyla hız
hesaplanamıyor. Faz 6.7'nin dersi buydu: *ölçülemeyen iyileştirme
eklenmez.* Standart tabanlı bir kuralın ise doğrulanması gerekmez;
dayanağı yayımlanmış bir tablo.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

from .gases import GASES, total_combustible

# IEEE C57.104 (1991) Tablo 3 — TDCG üretim hızı, ppm/gün.
TDCG_RATE_LIMITS = {
    "C1": 10.0,
    "C2": 30.0,
    "C3": 100.0,
}

# Hız hesabı için en az kaç ölçüm gerekir?
#
# İki nokta bir hız verir ama tek bir ölçüm hatası onu tamamen
# uydurabilir. Üç nokta, doğrusal uyumun ne kadar tutarlı olduğunu da
# söyler. (``services/trend.py`` de aynı eşiği kullanıyor.)
MIN_SAMPLES = 3

# Çok kısa aralıklarda hız gürültüye boğulur: bir haftada ölçülen iki
# numunenin farkı, laboratuvar saçılımından ayırt edilemez.
MIN_SPAN_DAYS = 20.0


def _parse(ts: object) -> Optional[datetime]:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts))
    except ValueError:
        return None


def _slope_per_day(points: List[tuple]) -> Optional[float]:
    """En küçük kareler eğimi (birim/gün). Nokta azsa None."""
    if len(points) < 2:
        return None

    n = len(points)
    mean_x = sum(p[0] for p in points) / n
    mean_y = sum(p[1] for p in points) / n

    denom = sum((p[0] - mean_x) ** 2 for p in points)
    if denom <= 0:
        return None

    num = sum((p[0] - mean_x) * (p[1] - mean_y) for p in points)
    return num / denom


def rate_condition(tdcg_rate_per_day: Optional[float]) -> Optional[int]:
    """TDCG üretim hızından IEEE kondisyonu (1-4)."""
    if tdcg_rate_per_day is None:
        return None
    # Negatif hız (gaz azalıyor — yağ değişimi ya da ölçüm saçılımı)
    # kondisyon 1 sayılır: azalan gaz arıza belirtisi değildir.
    if tdcg_rate_per_day < TDCG_RATE_LIMITS["C1"]:
        return 1
    if tdcg_rate_per_day < TDCG_RATE_LIMITS["C2"]:
        return 2
    if tdcg_rate_per_day < TDCG_RATE_LIMITS["C3"]:
        return 3
    return 4


def assess(measurements: List[Dict[str, object]]) -> Dict[str, object]:
    """Ölçüm serisinden gaz üretim hızını değerlendirir.

    ``measurements``: [{"sampled_at": ..., "gases": {...}}, ...]
    eskiden yeniye sıralı.
    """
    usable = []
    for m in measurements:
        ts = _parse(m.get("sampled_at"))
        gases = m.get("gases")
        if ts is not None and isinstance(gases, dict):
            usable.append((ts, gases))

    if len(usable) < MIN_SAMPLES:
        return {"available": False, "reason": "insufficient_history",
                "message": f"Hız hesabı için en az {MIN_SAMPLES} ölçüm "
                           f"gerekir; {len(usable)} var.",
                "n_samples": len(usable)}

    usable.sort(key=lambda p: p[0])
    t0 = usable[0][0]
    span_days = (usable[-1][0] - t0).total_seconds() / 86400.0

    if span_days < MIN_SPAN_DAYS:
        return {"available": False, "reason": "span_too_short",
                "message": "Ölçümler birbirine çok yakın; hesaplanan hız "
                           "laboratuvar saçılımından ayırt edilemez.",
                "span_days": round(span_days, 1)}

    # --- TDCG hızı: ASIL ölçüt --------------------------------------
    tdcg_points = [((ts - t0).total_seconds() / 86400.0,
                    total_combustible(gases)) for ts, gases in usable]
    tdcg_rate = _slope_per_day(tdcg_points)

    condition = rate_condition(tdcg_rate)

    # --- Gaz bazında hız: hangi gaz sürüklüyor? ---------------------
    per_gas: Dict[str, Dict[str, object]] = {}
    for gas in GASES:
        pts = [((ts - t0).total_seconds() / 86400.0, float(g.get(gas, 0.0)))
               for ts, g in usable]
        slope = _slope_per_day(pts)
        if slope is None:
            continue
        current = pts[-1][1]
        # Bağıl hız: "ayda %12 artıyor". Mutlak ppm/gün, düşük seviyeli
        # gazlarda (C2H2 gibi) küçük görünür ama oransal olarak
        # patlayıcı olabilir — ikisi birlikte okunmalı.
        relative = (slope * 30.0 / current * 100.0) if current > 1.0 else None
        per_gas[gas] = {
            "ppm_per_month": round(slope * 30.0, 2),
            "percent_per_month": round(relative, 1) if relative is not None else None,
            "current": round(current, 1),
        }

    rising = {g: d for g, d in per_gas.items()
              if float(d["ppm_per_month"]) > 0}  # type: ignore[arg-type]
    driver = max(rising, key=lambda g: float(per_gas[g]["ppm_per_month"])) \
        if rising else None

    return {
        "available": True,
        "n_samples": len(usable),
        "span_days": round(span_days, 1),
        "tdcg_current": round(tdcg_points[-1][1], 1),
        "tdcg_rate_per_day": round(tdcg_rate, 2) if tdcg_rate is not None else None,
        "tdcg_rate_per_month": round(tdcg_rate * 30.0, 1) if tdcg_rate is not None else None,
        "condition": condition,
        "driver_gas": driver,
        "per_gas": per_gas,
        "limits": TDCG_RATE_LIMITS,
        "standard": "IEEE C57.104 (1991) Tablo 3",
    }


def combine(absolute_condition: Optional[int],
            rate_result: Dict[str, object]) -> Dict[str, object]:
    """Mutlak derişim ve hız kondisyonlarını birleştirir.

    Kural: **ikisinin KÖTÜSÜ alınır.** Neden ortalama değil?

    İki ölçüt farklı soruları cevaplıyor ve ikisi de tek başına yeterli
    bir alarm sebebidir:

    * Yüksek derişim + sıfır hız → eski, kararlı bir arıza. Yine de
      yüksek derişim izlenmeli.
    * Düşük derişim + yüksek hız → yeni başlamış ama hızla gelişen bir
      arıza. Derişim henüz düşük diye beklemek, arızayı büyütmek olur.

    Ortalama almak ikinci durumu gizlerdi — ki bu ölçütün eklenme
    sebebi tam olarak odur.
    """
    rate_cond = rate_result.get("condition") if rate_result.get("available") else None
    abs_cond = absolute_condition

    if abs_cond is None and rate_cond is None:
        return {"condition": None, "basis": "veri yok"}

    if rate_cond is None:
        return {"condition": abs_cond, "basis": "yalnızca derişim",
                "absolute_condition": abs_cond, "rate_condition": None}

    if abs_cond is None:
        return {"condition": rate_cond, "basis": "yalnızca hız",
                "absolute_condition": None, "rate_condition": rate_cond}

    combined = max(abs_cond, rate_cond)
    if rate_cond > abs_cond:
        basis = "hız (derişimden daha acil)"
    elif abs_cond > rate_cond:
        basis = "derişim (hız sakin)"
    else:
        basis = "ikisi de aynı"

    return {
        "condition": combined,
        "basis": basis,
        "absolute_condition": abs_cond,
        "rate_condition": rate_cond,
        # Hızın kararı DEĞİŞTİRDİĞİ durum ayrıca işaretleniyor: bu
        # ölçütün ürüne kattığı değerin ölçüsü.
        "rate_escalated": rate_cond > abs_cond,
    }
