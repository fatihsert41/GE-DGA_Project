"""Demo elektriksel test üreteci. — Faz 8.6

⚠ Tüm veri SENTETİKTİR (proje veri politikası).

YAĞ ÜRETECİNDEN FARKI
---------------------
``synth_oil.py`` fiziksel bağıntılardan rastgele üretiyordu (nem ↔ BDV
ters ilişkili vb.). Burada yaklaşım farklı: **senaryolar elle yazıldı.**

Sebep: elektriksel testlerin demo değeri "gerçekçi dağılım"da değil,
**hikâyede**. "Yağ temiz ama sargı direnci dengesiz" gibi bir vaka
rastgele üretimden çıkmaz; çıksa bile rastgele çıktığı için anlatamaz.
Her senaryo, sistemin bir yeteneğini kanıtlamak için var.

Ölçüm gürültüsü yine de eklenir — üç fazın kuruşu kuruşuna aynı çıkması
saha verisinde görülmez ve sahteliği ele verir.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np

# Senaryo -> ne göstermek istiyoruz.
#
#   healthy         : her şey normal (çoğunluk böyle olmalı)
#   shorted_turn    : tek fazda kısa devre spir — TTR yakalar, DGA görmez
#   tap_wear        : kademe kontak aşınması — sargı direnci dengesizliği
#   wet_insulation  : nem/kirlenme — düşük PI
#   aged_insulation : genel yaşlanma — yüksek tan δ
#   very_dry        : çok kuru yalıtım — PI düşük ama ANLAMSIZ (tuzak vakası)
SCENARIOS = ("healthy", "shorted_turn", "tap_wear", "wet_insulation",
             "aged_insulation", "very_dry")


def make_electrical_test(expected_ratio: float,
                         scenario: str = "healthy",
                         age_years: float = 10.0,
                         base_resistance_ohm: float = 0.5,
                         seed: Optional[int] = None) -> Dict[str, object]:
    """Bir elektriksel test kaydı üretir.

    ``expected_ratio`` künyeden hesaplanan beklenen sarım oranıdır; üretilen
    ölçümler bunun etrafında salınır.
    """
    rng = np.random.default_rng(seed)

    # --- Sarım oranı --------------------------------------------------
    # Sağlam bir trafoda ölçüm hatası ±%0.1 mertebesindedir; tolerans
    # ±%0.5 olduğu için bu rahatça içeride kalır.
    ttr = {ph: expected_ratio * float(rng.normal(1.0, 0.0008))
           for ph in ("a", "b", "c")}

    if scenario == "shorted_turn":
        # Tek fazda spir kaybı: o fazın oranı DÜŞER (AG sargısı sağlamken
        # YG sargısında spir kaybı olursa oran düşer). %1.4 sapma, bir
        # büyük trafoda birkaç spire karşılık gelir — az ama ölümcül.
        ttr["b"] = expected_ratio * 0.986

    # --- Sargı direnci ------------------------------------------------
    base = base_resistance_ohm
    rw = {ph: base * float(rng.normal(1.0, 0.003)) for ph in ("a", "b", "c")}

    if scenario == "tap_wear":
        # Kademe değiştirici kontağı aşınınca o fazın direnci ARTAR.
        # %4.5 dengesizlik: IEEE C57.152'nin %2 sınırının belirgin üstü.
        rw["a"] = base * 1.045

    winding_temp = float(rng.uniform(18.0, 42.0))

    # --- Yalıtım direnci ----------------------------------------------
    # Yaşla düşer; ama asıl belirleyici nem.
    ir_1min = max(150.0, 2500.0 * (0.97 ** age_years)
                  * float(rng.lognormal(0.0, 0.15)))
    pi_target = float(rng.uniform(2.2, 3.5))          # sağlıklı polarizasyon

    if scenario == "wet_insulation":
        pi_target = float(rng.uniform(1.05, 1.35))    # direnç zamanla artmıyor
        ir_1min *= 0.35
    elif scenario == "very_dry":
        # Tuzak vakası: direnç devasa, PI düşük görünüyor ama bu ARIZA
        # DEĞİL. IEEE C57.152 bu bölgede PI'nın anlamını yitirdiğini söyler.
        ir_1min = float(rng.uniform(12000.0, 25000.0))
        pi_target = float(rng.uniform(1.15, 1.45))

    ir_10min = ir_1min * pi_target

    # --- tan δ ---------------------------------------------------------
    tan_delta = 0.18 + 0.014 * age_years * float(rng.normal(1.0, 0.12))
    if scenario == "aged_insulation":
        tan_delta = float(rng.uniform(1.15, 1.6))
    tan_delta = max(0.05, tan_delta)

    return {
        "ttr_a": round(ttr["a"], 4),
        "ttr_b": round(ttr["b"], 4),
        "ttr_c": round(ttr["c"], 4),
        "rw_a_ohm": round(rw["a"], 5),
        "rw_b_ohm": round(rw["b"], 5),
        "rw_c_ohm": round(rw["c"], 5),
        "winding_temp_c": round(winding_temp, 1),
        "ir_1min_mohm": round(ir_1min, 1),
        "ir_10min_mohm": round(ir_10min, 1),
        "insulation_temp_c": round(float(rng.uniform(15.0, 30.0)), 1),
        "tan_delta_pct": round(tan_delta, 3),
        "tan_delta_temp_c": round(float(rng.uniform(18.0, 24.0)), 1),
    }
