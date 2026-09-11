"""Bileşen izleme: buşingler ve kademe değiştirici. — Faz 9.4

NEDEN AYRI BİR BOYUT?
---------------------
Şimdiye kadarki her ölçüt trafonun **aktif kısmını** (sargı, yağ, kağıt)
değerlendiriyordu. Ama saha istatistiklerinde trafo arızalarının önemli
bir kısmı aktif kısımdan değil, **eklentilerden** gelir:

* **Buşingler** — yüksek gerilimi tanktan dışarı taşıyan yalıtkanlar.
  İçlerinde kondansatör katmanları vardır; bir katman delindiğinde
  kalanlar üzerindeki gerilim artar ve arıza hızlanır. Ani ve şiddetli
  biter: buşing patlaması yangına yol açabilir.
* **Kademe değiştirici (OLTC)** — trafonun tek HAREKETLİ parçası.
  Hareketli olan aşınır. Kademeli trafolarda bakım gerektiren bileşenin
  başında gelir.

İKİ FARKLI ÖLÇÜT MANTIĞI
------------------------
Bu modülde iki ayrı yaklaşım bir arada, ve farkları öğreticidir:

**Buşingde ölçüt DEĞİŞİMDİR, mutlak değer değil.** Kapasitans (C1)
buşingin künyesinde yazar; ölçülen değerin künyeden sapması, bir
kondansatör katmanının delindiğini gösterir. %5 sapma, katmanların
%5'inin gitmesi demektir. Mutlak kapasitans tasarıma göre değişir, tek
başına bir şey söylemez — tıpkı sargı direncinde olduğu gibi (Faz 8.6).

**OLTC'de ölçüt KULLANIMDIR, durum değil.** Kontak aşınması işletme
sayısıyla ilerler. "Şu an iyi görünüyor" yeterli değildir; 80.000 kez
çalışmış bir mekanizma, iyi görünse bile revizyon zamanı gelmiştir.
Bu, takvime değil **sayaca** bağlı bir bakımdır.

STANDARTLAR
-----------
* IEEE C57.19.01 / C57.152 — buşing güç faktörü ve kapasitans
* IEC 60137 — buşing tanımları
* IEEE C57.131 / IEC 60214 — kademe değiştirici

⚠ Eşikler **konvansiyoneldir**; üretici kılavuzu esastır. Değerler tek
yerde toplandı ve değiştirilebilir tutuldu.
"""
from __future__ import annotations

from typing import Dict, List, Optional

PHASES = ("A", "B", "C")
CONDITIONS = ("iyi", "kabul", "kötü", "bilinmiyor")

# --- Buşing ---------------------------------------------------------------
# Güç faktörü (tan δ) — yalıtımın kayıp oranı. Yeni buşingde çok küçüktür.
BUSHING_PF_GOOD = 0.5       # %
BUSHING_PF_ACCEPT = 1.0

# Kapasitans sapması — ASIL ÖLÇÜT.
#
# C1, buşingin künyesinde yazar. Ölçülen değer künyeden saparsa bir
# kondansatör katmanı delinmiş demektir: %5 sapma, katmanların %5'inin
# kısa devre olması. Bu geri dönüşsüzdür ve hızlanarak ilerler — kalan
# katmanlar üzerindeki gerilim arttığı için bir sonraki delinme daha
# kolay olur.
BUSHING_CAP_GOOD = 2.0      # % sapma
BUSHING_CAP_ACCEPT = 5.0

# Bu sapmanın ötesi ölçüm/giriş hatası şüphesi doğurur (TTR'deki
# %10 kuralıyla aynı gerekçe: fiziksel olarak açıklanamayan büyüklük).
BUSHING_CAP_IMPLAUSIBLE = 25.0

# --- Kademe değiştirici ---------------------------------------------------
# Revizyon aralığı: işletme sayısı VE takvim. Hangisi önce dolarsa.
#
# Üreticiler tipik olarak 50.000-100.000 işletme ya da 6-7 yıl verir.
# Burada muhafazakâr uç seçildi; gerçek değer üretici kılavuzundadır.
OLTC_OPERATIONS_LIMIT = 50_000
OLTC_OPERATIONS_WARN = 40_000
OLTC_YEARS_LIMIT = 7.0
OLTC_YEARS_WARN = 6.0

# OLTC yağı ana tank yağından AYRIDIR ve çok daha hızlı kirlenir:
# kademe değişiminde oluşan ark, yağı doğrudan bozar. Bu yüzden
# eşikleri de ana tanktan farklı ve daha gevşektir.
OLTC_BDV_GOOD = 30.0        # kV
OLTC_BDV_ACCEPT = 20.0


def _num(value: object) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _worst(conditions: List[str]) -> str:
    known = [c for c in conditions if c != "bilinmiyor"]
    if not known:
        return "bilinmiyor"
    for level in ("kötü", "kabul"):
        if level in known:
            return level
    return "iyi"


# ---------------------------------------------------------------------------
# Buşingler
# ---------------------------------------------------------------------------

def assess_bushings(measured: Dict[str, object]) -> Dict[str, object]:
    """Üç fazın buşing güç faktörü ve kapasitansını değerlendirir.

    Beklenen alanlar (faz başına):
        bushing_a_pf_pct, bushing_a_cap_pf, bushing_a_cap_rated_pf
    """
    rows: List[Dict[str, object]] = []

    for ph in PHASES:
        low = ph.lower()
        pf = _num(measured.get(f"bushing_{low}_pf_pct"))
        cap = _num(measured.get(f"bushing_{low}_cap_pf"))
        rated = _num(measured.get(f"bushing_{low}_cap_rated_pf"))

        pf_condition = "bilinmiyor"
        if pf is not None:
            pf_condition = ("iyi" if pf <= BUSHING_PF_GOOD
                            else "kabul" if pf <= BUSHING_PF_ACCEPT
                            else "kötü")

        deviation = None
        cap_condition = "bilinmiyor"
        suspect = False
        if cap is not None and rated:
            deviation = (cap - rated) / rated * 100.0
            mag = abs(deviation)
            if mag > BUSHING_CAP_IMPLAUSIBLE:
                # TTR'deki imkânsız sapma kuralıyla aynı mantık: bu
                # büyüklük bir katman kaybıyla açıklanamaz.
                cap_condition = "kötü"
                suspect = True
            else:
                cap_condition = ("iyi" if mag <= BUSHING_CAP_GOOD
                                 else "kabul" if mag <= BUSHING_CAP_ACCEPT
                                 else "kötü")

        rows.append({
            "phase": ph,
            "pf_pct": pf,
            "pf_condition": pf_condition,
            "capacitance_pf": cap,
            "rated_pf": rated,
            "deviation_pct": round(deviation, 2) if deviation is not None else None,
            "cap_condition": cap_condition,
            "data_suspect": suspect,
            "condition": _worst([pf_condition, cap_condition]),
        })

    known = [r for r in rows if r["condition"] != "bilinmiyor"]
    if not known:
        return {"available": False, "reason": "Buşing ölçümü girilmemiş."}

    overall = _worst([str(r["condition"]) for r in rows])

    problems: List[str] = []
    for r in known:
        if r["cap_condition"] == "kötü" and r["deviation_pct"] is not None:
            if r["data_suspect"]:
                problems.append(
                    f"{r['phase']} buşingi kapasitans sapması "
                    f"%{abs(float(r['deviation_pct'])):.1f} — bu büyüklük bir "
                    f"katman kaybıyla açıklanamaz, ölçüm/giriş hatası olmalı")
            else:
                problems.append(
                    f"{r['phase']} buşingi kapasitans sapması "
                    f"%{abs(float(r['deviation_pct'])):.1f} "
                    f"(sınır %{BUSHING_CAP_GOOD}) — kondansatör katmanı "
                    f"delinmiş olabilir")
        if r["pf_condition"] == "kötü":
            problems.append(
                f"{r['phase']} buşingi güç faktörü %{r['pf_pct']} "
                f"(iyi sınırı %{BUSHING_PF_GOOD})")

    return {
        "available": True,
        "overall": overall,
        "phases": rows,
        "problems": problems,
        "data_suspect": any(r["data_suspect"] for r in rows),
        "standard": "IEEE C57.19.01 / C57.152",
        "meaning": "Kapasitans sapması bir kondansatör katmanının "
                   "delindiğini gösterir; kalan katmanların gerilimi "
                   "arttığı için süreç hızlanarak ilerler.",
    }


# ---------------------------------------------------------------------------
# Kademe değiştirici
# ---------------------------------------------------------------------------

def assess_oltc(measured: Dict[str, object],
                has_tap_changer: bool = True) -> Dict[str, object]:
    """Kademe değiştiricinin durumunu değerlendirir.

    Beklenen alanlar: oltc_operations, oltc_ops_since_overhaul,
    oltc_years_since_overhaul, oltc_oil_bdv_kv
    """
    if not has_tap_changer:
        return {"available": False,
                "reason": "Bu trafoda kademe değiştirici yok."}

    ops_since = _num(measured.get("oltc_ops_since_overhaul"))
    years_since = _num(measured.get("oltc_years_since_overhaul"))
    total_ops = _num(measured.get("oltc_operations"))
    bdv = _num(measured.get("oltc_oil_bdv_kv"))

    if ops_since is None and years_since is None and bdv is None:
        return {"available": False, "reason": "Kademe değiştirici verisi yok."}

    checks: List[Dict[str, object]] = []

    # 1) İşletme sayısı — ASIL ÖLÇÜT.
    #
    # Kontak aşınması takvimle değil KULLANIMLA ilerler. Az çalışan bir
    # OLTC yıllarca revizyonsuz kalabilir; çok çalışan biri iki yılda
    # sınırı doldurur.
    if ops_since is not None:
        condition = ("iyi" if ops_since < OLTC_OPERATIONS_WARN
                     else "kabul" if ops_since < OLTC_OPERATIONS_LIMIT
                     else "kötü")
        checks.append({
            "key": "operations",
            "label": "Revizyondan beri işletme",
            "value": int(ops_since),
            "unit": "işletme",
            "limit": OLTC_OPERATIONS_LIMIT,
            "condition": condition,
            "meaning": "Kontak aşınması takvimle değil kullanımla ilerler.",
        })

    # 2) Takvim — ikincil ama gerekli.
    #
    # Az çalışan bir OLTC'de bile yağ yaşlanır, contalar sertleşir,
    # mekanizma yağı özelliğini yitirir. Sayaç dolmasa da süre dolar.
    if years_since is not None:
        condition = ("iyi" if years_since < OLTC_YEARS_WARN
                     else "kabul" if years_since < OLTC_YEARS_LIMIT
                     else "kötü")
        checks.append({
            "key": "years",
            "label": "Revizyondan beri süre",
            "value": round(years_since, 1),
            "unit": "yıl",
            "limit": OLTC_YEARS_LIMIT,
            "condition": condition,
            "meaning": "Sayaç dolmasa da yağ yaşlanır, contalar sertleşir.",
        })

    # 3) OLTC yağı — ana tanktan AYRI ve çok daha hızlı bozulur.
    if bdv is not None:
        condition = ("iyi" if bdv >= OLTC_BDV_GOOD
                     else "kabul" if bdv >= OLTC_BDV_ACCEPT
                     else "kötü")
        checks.append({
            "key": "oil_bdv",
            "label": "Kademe yağı delinme gerilimi",
            "value": round(bdv, 1),
            "unit": "kV",
            "limit": OLTC_BDV_ACCEPT,
            "condition": condition,
            "meaning": "Kademe değişimindeki ark yağı doğrudan bozar; "
                       "ana tank yağından çok daha hızlı kirlenir.",
        })

    overall = _worst([str(c["condition"]) for c in checks])

    problems = [f"{c['label']}: {c['value']} {c['unit']} "
                f"(sınır {c['limit']})"
                for c in checks if c["condition"] == "kötü"]

    return {
        "available": True,
        "overall": overall,
        "checks": checks,
        "total_operations": int(total_ops) if total_ops is not None else None,
        "problems": problems,
        "standard": "IEEE C57.131 / IEC 60214",
        "meaning": "Kademe değiştirici trafonun tek HAREKETLİ parçasıdır; "
                   "hareketli olan aşınır.",
    }


# ---------------------------------------------------------------------------
# Bütün
# ---------------------------------------------------------------------------

def assess(test: Dict[str, object],
           has_tap_changer: bool = True) -> Dict[str, object]:
    """Bir bileşen testini bütün olarak değerlendirir."""
    bushings = assess_bushings(test)
    oltc = assess_oltc(test, has_tap_changer)

    sections = {"bushings": bushings, "oltc": oltc}

    conditions: List[str] = []
    problems: List[str] = []
    for section in sections.values():
        if not section.get("available"):
            continue
        conditions.append(str(section.get("overall") or "bilinmiyor"))
        problems.extend(list(section.get("problems") or []))

    return {
        "overall": _worst(conditions),
        "measured_count": len(conditions),
        "sections": sections,
        "problems": problems,
    }


def schema() -> Dict[str, object]:
    """Form ve açıklamalar için tanım."""
    return {
        "bushings": {
            "label": "Buşingler",
            "standard": "IEEE C57.19.01 / C57.152",
            "pf_good": BUSHING_PF_GOOD,
            "pf_accept": BUSHING_PF_ACCEPT,
            "cap_good": BUSHING_CAP_GOOD,
            "cap_accept": BUSHING_CAP_ACCEPT,
            "meaning": "Ölçüt DEĞİŞİMDİR: kapasitans künyeden saparsa bir "
                       "kondansatör katmanı delinmiştir. Mutlak değer "
                       "tasarıma göre değişir, tek başına bir şey söylemez.",
            "fields": [f"bushing_{p.lower()}_{s}"
                       for p in PHASES
                       for s in ("pf_pct", "cap_pf", "cap_rated_pf")],
        },
        "oltc": {
            "label": "Kademe değiştirici",
            "standard": "IEEE C57.131 / IEC 60214",
            "operations_limit": OLTC_OPERATIONS_LIMIT,
            "years_limit": OLTC_YEARS_LIMIT,
            "bdv_accept": OLTC_BDV_ACCEPT,
            "meaning": "Ölçüt KULLANIMDIR: kontak aşınması takvimle değil "
                       "işletme sayısıyla ilerler. 80.000 kez çalışmış bir "
                       "mekanizma, iyi görünse bile revizyon ister.",
            "fields": ["oltc_operations", "oltc_ops_since_overhaul",
                       "oltc_years_since_overhaul", "oltc_oil_bdv_kv"],
        },
    }
