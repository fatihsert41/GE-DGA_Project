"""Elektriksel testler: TTR, sargı direnci, yalıtım direnci/PI, tan δ.
— Faz 8.6

YAĞIN GÖRMEDİĞİ ARIZALAR
------------------------
Şimdiye kadarki her ölçüt yağdan okunuyordu: DGA gazları, nem, asitlik,
furan. Ama trafonun bazı arızaları yağa iz bırakmaz ya da çok geç bırakır:

* **Kısa devre olmuş spir** — sarım oranını bozar. Yağa iz bırakması için
  önce ısınıp gaz üretmesi gerekir; TTR ise aynı gün yakalar.
* **Kademe değiştirici kontak aşınması** — direnci artırır, gaz üretmez.
* **Yalıtımda nem/kirlenme** — yalıtım direncini düşürür.
* **Yalıtımın genel yaşlanması** — tan δ'yı büyütür.

Bu yüzden elektriksel testler DGA'nın rakibi değil, **bağımsız bir
duyusudur**. İki bağımsız kaynağın aynı şeyi söylemesi, tek kaynağın iki
kez söylemesinden çok daha değerlidir.

STANDARTLAR
-----------
* IEEE C57.12.00 / C57.12.90 — sarım oranı toleransı, ölçüm yöntemi
* IEEE C57.152 — saha testleri kılavuzu (direnç dengesizliği, PI)
* IEC 60076-1 — sarım oranı toleransı (±%0.5)

⚠ Eşikler **konvansiyoneldir ve yaklaşıktır**; işletmeler kendi kabul
kriterlerini kullanır. `assets.py` ve `oil_quality.py`'deki gibi tek yerde
toplandı ve değiştirilebilir tutuldu.

⚠ ÖNEMLİ SINIR: bu testler trafo **enerjisizken** yapılır. DGA gibi
işletme sırasında alınamaz; bu yüzden ölçümleri seyrektir (tipik olarak
devreye alma + büyük bakım). Sistem bunu bilir ve ölçümün yaşını raporlar.
"""
from __future__ import annotations

from typing import Dict, List, Optional

CONDITIONS = ("iyi", "kabul", "kötü", "bilinmiyor")

PHASES = ("A", "B", "C")

# --- 1) Sarım oranı (TTR) -------------------------------------------------
# IEEE C57.12.00 ve IEC 60076-1: ölçülen oran, hesaplanan oranın ±%0.5'i
# içinde olmalı. Bu tolerans DAR'dır; tek bir kısa devre spir bile 1000
# sarımlık bir sargıda %0.1 sapma yapar, yani test çok hassastır.
TTR_GOOD_PCT = 0.5        # bu sapmanın altı kabul edilir
TTR_ACCEPT_PCT = 1.0      # arası şüpheli, üstü arıza

# --- 2) Sargı direnci -----------------------------------------------------
# Fazlar arası dengesizlik: IEEE C57.152 %2'yi eşik alır. Mutlak değer
# değil DENGESİZLİK bakılır, çünkü mutlak direnç sıcaklığa ve tasarıma
# bağlıdır; üç faz ise aynı trafoda aynı koşuldadır.
RESISTANCE_GOOD_PCT = 2.0
RESISTANCE_ACCEPT_PCT = 3.0

# Sıcaklık düzeltme sabitleri (direnç-sıcaklık katsayısı).
# Bakır ve alüminyumun direnci sıcaklıkla farklı hızda artar; iki ölçümü
# düzeltmeden karşılaştırmak yanlış sonuç verir.
TEMP_CONSTANT = {"Cu": 234.5, "Al": 225.0}
REFERENCE_TEMP_C = 75.0   # sargı direnci için yaygın referans

# --- 3) Yalıtım direnci ve polarizasyon indeksi (PI) ----------------------
# PI = R(10 dakika) / R(1 dakika). Temiz ve kuru yalıtımda direnç zamanla
# YÜKSELİR (polarizasyon); nemli/kirli yalıtımda sabit kalır.
# Oranın güzelliği: mutlak değere ve sıcaklığa görece duyarsızdır.
PI_BANDS = [
    (4.0, "iyi", "Yalıtım kuru ve temiz."),
    (2.0, "iyi", "Kabul edilebilir polarizasyon; yalıtım sağlıklı."),
    (1.5, "kabul", "Şüpheli; nem veya kirlenme başlamış olabilir."),
    (1.0, "kötü", "Zayıf polarizasyon; nem/kirlenme kuvvetle muhtemel."),
    (0.0, "kötü", "Direnç zamanla artmıyor; yalıtım ıslak veya kirli."),
]

# IEEE C57.152: yalıtım direnci çok yüksekse (temiz, kuru, modern yalıtım)
# PI anlamını yitirir — pay da payda da çok büyük olduğu için oran
# gürültüye döner. Bu durumda PI'ya bakıp "kötü" demek HATA olur.
PI_MEANINGLESS_ABOVE_MOHM = 5000.0

# Yalıtım direnci sıcaklıkla ÜSTEL değişir: yaklaşık her 10 °C'de iki
# katına/yarısına. 20 °C'ye normalize edilir.
IR_REFERENCE_TEMP_C = 20.0

# --- 4) Kayıp faktörü (tan δ / güç faktörü) ------------------------------
# Yalıtımın ne kadarının ısıya dönüştüğünü ölçer. Yeni yalıtımda çok
# küçüktür; yaşlanma, nem ve kirlenme ile büyür. 20 °C'ye normalize edilir.
TAND_GOOD_PCT = 0.5
TAND_ACCEPT_PCT = 1.0


def _num(value: object) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _worst(conditions: List[str]) -> str:
    """Birden çok ölçütün genel hükmü = EN KÖTÜSÜ.

    Ortalama almak yanlış olurdu: bir fazın bozuk olması trafoyu riske
    atmaya yeter, diğer iki fazın iyiliği bunu telafi etmez.
    (`oil_quality.assess` de aynı mantıkla çalışıyor.)
    """
    known = [c for c in conditions if c != "bilinmiyor"]
    if not known:
        return "bilinmiyor"
    for level in ("kötü", "kabul"):
        if level in known:
            return level
    return "iyi"


# ---------------------------------------------------------------------------
# 1) Sarım oranı — TTR
# ---------------------------------------------------------------------------

def assess_turns_ratio(measured: Dict[str, Optional[float]],
                       expected: Optional[float],
                       tap: Optional[int] = None) -> Dict[str, object]:
    """Üç fazın ölçülen sarım oranını beklenen değerle karşılaştırır.

    ``expected`` künyeden gelir (``nameplate.rated_turns_ratio`` ya da
    kademeliyse ``turns_ratio_at_tap``). Bağlantı grubunun getirdiği √3
    çarpanı orada uygulanır — burada tekrar uygulanmaz, iki kez çarpmak
    sağlam trafoyu arızalı gösterirdi.
    """
    if expected is None or expected <= 0:
        return {"available": False,
                "reason": "Künyede gerilim/bağlantı grubu eksik; beklenen "
                          "oran hesaplanamıyor."}

    phases: List[Dict[str, object]] = []
    for ph in PHASES:
        value = _num(measured.get(ph))
        if value is None:
            phases.append({"phase": ph, "condition": "bilinmiyor",
                           "measured": None})
            continue
        deviation = (value - expected) / expected * 100.0
        mag = abs(deviation)
        condition = ("iyi" if mag <= TTR_GOOD_PCT
                     else "kabul" if mag <= TTR_ACCEPT_PCT else "kötü")
        phases.append({
            "phase": ph,
            "measured": value,
            "deviation_pct": round(deviation, 3),
            "condition": condition,
            # Sapmanın İŞARETİ tanı koydurur: ölçülen oran BÜYÜKSE alçak
            # gerilim sargısında spir kaybı, KÜÇÜKSE yüksek gerilim
            # sargısında spir kaybı düşünülür.
            "direction": ("yüksek" if deviation > 0 else
                          "düşük" if deviation < 0 else "tam"),
        })

    known = [p for p in phases if p["condition"] != "bilinmiyor"]
    if not known:
        # Beklenen oran hesaplanabiliyor ama ölçüm girilmemiş. "Hesap
        # yapılabilir" ile "ölçüm var" aynı şey değil; ikisini karıştırmak
        # boş bir bölümü "değerlendirildi" saydırırdı.
        return {"available": False,
                "reason": "Sarım oranı ölçümü girilmemiş.",
                "expected": expected}

    overall = _worst([str(p["condition"]) for p in phases])

    problems: List[str] = []
    for p in known:
        if p["condition"] != "iyi":
            problems.append(
                f"{p['phase']} fazı beklenenden %{abs(float(p['deviation_pct'])):.2f} "
                f"{p['direction']} (tolerans ±%{TTR_GOOD_PCT})")

    # Fazlar arası yayılım: üçü de aynı yönde kaymışsa bu genellikle
    # kademe pozisyonunun yanlış girilmesidir (ölçüm hatası), bir faz
    # ayrışmışsa o fazda gerçek bir sargı sorunu vardır. Ayrım önemli:
    # biri kağıt hatası, diğeri trafoyu devreden çıkarma sebebi.
    spread = None
    note = None
    if len(known) == len(PHASES):
        devs = [float(p["deviation_pct"]) for p in known]
        spread = round(max(devs) - min(devs), 3)
        if overall != "iyi" and spread <= TTR_GOOD_PCT:
            note = ("Üç faz da aynı yönde ve birbirine yakın sapıyor. Bu "
                    "genellikle sargı arızası değil, KADEME POZİSYONUNUN "
                    "yanlış girilmesidir. Kademeyi doğrulayıp tekrar "
                    "değerlendirin.")
        elif overall != "iyi":
            note = ("Fazlar birbirinden ayrışıyor; sapma tek fazda "
                    "yoğunlaşmış. Bu, o sargıda kısa devre olmuş spir "
                    "işaretidir ve tek başına devreden çıkarma sebebidir.")

    return {
        "available": True,
        "expected": expected,
        "tap": tap,
        "phases": phases,
        "overall": overall,
        "problems": problems,
        "spread_pct": spread,
        "note": note,
        "tolerance_pct": TTR_GOOD_PCT,
        "standard": "IEEE C57.12.00 / IEC 60076-1",
    }


# ---------------------------------------------------------------------------
# 2) Sargı direnci
# ---------------------------------------------------------------------------

def correct_resistance(resistance: float, measured_temp_c: float,
                       winding_material: Optional[str] = "Cu",
                       reference_temp_c: float = REFERENCE_TEMP_C) -> float:
    """Sargı direncini referans sıcaklığa çevirir.

    R2 = R1 × (T + t2) / (T + t1);  T = 234.5 (Cu) veya 225 (Al).

    Düzeltmeden karşılaştırmak yaygın bir saha hatasıdır: 20 °C'de ölçülen
    bir trafo ile 60 °C'de ölçülen aynı trafo, düzeltilmezse %15'ten fazla
    farklı görünür ve sağlam ünite "bozuk" sanılır.
    """
    T = TEMP_CONSTANT.get(str(winding_material or "Cu"), TEMP_CONSTANT["Cu"])
    return resistance * (T + reference_temp_c) / (T + measured_temp_c)


def assess_winding_resistance(
        measured: Dict[str, Optional[float]],
        temp_c: Optional[float] = None,
        winding_material: Optional[str] = "Cu") -> Dict[str, object]:
    """Üç fazın sargı direncini DENGESİZLİK üzerinden değerlendirir.

    Mutlak direnç tasarıma bağlıdır ve künyede yazmaz; ama üç faz aynı
    trafoda, aynı sıcaklıkta, aynı tasarımdadır — birbirlerinin doğal
    referansıdır. Bu yüzden ölçüt "kaç ohm" değil, "fazlar ne kadar
    ayrışıyor".
    """
    values = {ph: _num(measured.get(ph)) for ph in PHASES}
    known = {ph: v for ph, v in values.items() if v is not None and v > 0}

    if len(known) < 2:
        return {"available": False,
                "reason": "Dengesizlik için en az iki faz ölçümü gerekir."}

    corrected = dict(known)
    if temp_c is not None:
        corrected = {ph: correct_resistance(v, temp_c, winding_material)
                     for ph, v in known.items()}

    mean = sum(corrected.values()) / len(corrected)
    spread = max(corrected.values()) - min(corrected.values())
    imbalance = spread / mean * 100.0 if mean else 0.0

    condition = ("iyi" if imbalance <= RESISTANCE_GOOD_PCT
                 else "kabul" if imbalance <= RESISTANCE_ACCEPT_PCT
                 else "kötü")

    worst_phase = max(corrected, key=lambda p: abs(corrected[p] - mean))

    problems: List[str] = []
    if condition != "iyi":
        problems.append(
            f"Fazlar arası dengesizlik %{imbalance:.2f} "
            f"(sınır %{RESISTANCE_GOOD_PCT}); en çok sapan faz {worst_phase}.")

    return {
        "available": True,
        "measured": known,
        "corrected": {ph: round(v, 5) for ph, v in corrected.items()},
        "temp_c": temp_c,
        "reference_temp_c": REFERENCE_TEMP_C if temp_c is not None else None,
        "winding_material": winding_material,
        "mean_ohm": round(mean, 5),
        "imbalance_pct": round(imbalance, 2),
        "worst_phase": worst_phase,
        "condition": condition,
        "problems": problems,
        "limit_pct": RESISTANCE_GOOD_PCT,
        "standard": "IEEE C57.152",
        "meaning": "Yüksek dengesizlik: gevşek bağlantı, kademe "
                   "değiştirici kontak aşınması veya sargıda kopukluk.",
    }


# ---------------------------------------------------------------------------
# 3) Yalıtım direnci ve polarizasyon indeksi
# ---------------------------------------------------------------------------

def correct_insulation_resistance(resistance_mohm: float,
                                  temp_c: float) -> float:
    """Yalıtım direncini 20 °C'ye normalize eder (her 10 °C'de iki kat)."""
    return resistance_mohm * (2.0 ** ((temp_c - IR_REFERENCE_TEMP_C) / 10.0))


def assess_insulation(ir_1min_mohm: Optional[float],
                      ir_10min_mohm: Optional[float],
                      temp_c: Optional[float] = None) -> Dict[str, object]:
    """Yalıtım direnci ve polarizasyon indeksini değerlendirir.

    PI = R(10 dk) / R(1 dk). Temiz ve kuru yalıtımda direnç zamanla
    yükselir; nemli veya kirli yalıtımda sabit kalır. ORAN olduğu için
    mutlak değere ve sıcaklığa görece duyarsızdır — sahada sevilmesinin
    sebebi budur.
    """
    r1 = _num(ir_1min_mohm)
    r10 = _num(ir_10min_mohm)

    if r1 is None or r1 <= 0:
        return {"available": False,
                "reason": "1 dakikalık yalıtım direnci ölçümü yok."}

    r1_corrected = (correct_insulation_resistance(r1, temp_c)
                    if temp_c is not None else r1)

    if r10 is None or r10 <= 0:
        return {
            "available": True,
            "ir_1min_mohm": r1,
            "ir_1min_corrected": round(r1_corrected, 1),
            "pi": None,
            "condition": "bilinmiyor",
            "problems": [],
            "note": "PI için 10 dakikalık ölçüm de gerekir; tek ölçümle "
                    "yalıtımın kuruluğu hakkında hüküm verilemez.",
            "standard": "IEEE C57.152",
        }

    pi = r10 / r1

    condition, description = "kötü", PI_BANDS[-1][2]
    for lower, cond, desc in PI_BANDS:
        if pi >= lower:
            condition, description = cond, desc
            break

    warnings: List[str] = []
    # Çok yüksek dirençte PI anlamını yitirir; bunu bilmeden "kötü" demek
    # sağlam ve KURU bir trafoyu suçlamak olur.
    if r1_corrected > PI_MEANINGLESS_ABOVE_MOHM and condition != "iyi":
        condition = "iyi"
        warnings.append(
            f"Yalıtım direnci çok yüksek ({round(r1_corrected)} MΩ > "
            f"{PI_MEANINGLESS_ABOVE_MOHM:g} MΩ). IEEE C57.152'ye göre bu "
            "aralıkta PI anlamını yitirir; düşük PI burada arıza değil, "
            "ölçüm gürültüsüdür. Hüküm mutlak dirence göre verildi.")

    problems: List[str] = []
    if condition == "kötü":
        problems.append(f"Polarizasyon indeksi {pi:.2f} — {description}")

    return {
        "available": True,
        "ir_1min_mohm": r1,
        "ir_10min_mohm": r10,
        "ir_1min_corrected": round(r1_corrected, 1),
        "temp_c": temp_c,
        "pi": round(pi, 2),
        "condition": condition,
        "description": description,
        "problems": problems,
        "warnings": warnings,
        "standard": "IEEE C57.152",
    }


# ---------------------------------------------------------------------------
# 4) Kayıp faktörü (tan δ)
# ---------------------------------------------------------------------------

def assess_tan_delta(tan_delta_pct: Optional[float],
                     temp_c: Optional[float] = None) -> Dict[str, object]:
    """Yalıtımın kayıp faktörünü değerlendirir.

    tan δ, uygulanan gerilimin ne kadarının ısıya dönüştüğünü ölçer. Yeni
    yalıtımda çok küçüktür; nem, kirlenme ve yaşlanma ile büyür. DGA'dan
    farklı olarak **noktasal bir arızayı değil, yalıtımın genel durumunu**
    gösterir — bu yüzden ikisi birbirini tamamlar.
    """
    value = _num(tan_delta_pct)
    if value is None:
        return {"available": False, "reason": "tan δ ölçümü yok."}

    condition = ("iyi" if value <= TAND_GOOD_PCT
                 else "kabul" if value <= TAND_ACCEPT_PCT else "kötü")

    warnings: List[str] = []
    # Sıcaklık düzeltmesi tan δ için basit bir formülle yapılamaz
    # (yalıtım tipine bağlı ampirik tablolar gerekir). Uydurmak yerine
    # SINIRI SÖYLÜYORUZ — projedeki kural: bilmediğimizi bildiğimizi
    # göstermek, sessizce yanlış sayı üretmekten iyidir.
    if temp_c is not None and abs(temp_c - 20.0) > 5.0:
        warnings.append(
            f"Ölçüm {temp_c:g} °C'de yapılmış; eşikler 20 °C içindir. "
            "tan δ sıcaklıkla belirgin artar ve düzeltmesi yalıtım tipine "
            "bağlı ampirik tablolar gerektirir — bu sistem düzeltme "
            "UYGULAMAZ. Sonucu temkinli yorumlayın.")

    problems: List[str] = []
    if condition != "iyi":
        problems.append(f"tan δ %{value:g} (iyi sınırı %{TAND_GOOD_PCT})")

    return {
        "available": True,
        "tan_delta_pct": value,
        "temp_c": temp_c,
        "condition": condition,
        "problems": problems,
        "warnings": warnings,
        "good_limit": TAND_GOOD_PCT,
        "acceptable_limit": TAND_ACCEPT_PCT,
        "standard": "IEEE C57.152",
        "meaning": "Yalıtımın genel yaşlanma/nem durumu; noktasal arıza "
                   "değil, bütünün durumu.",
    }


# ---------------------------------------------------------------------------
# Bütün test
# ---------------------------------------------------------------------------

def assess(test: Dict[str, object],
           expected_ratio: Optional[float] = None,
           winding_material: Optional[str] = "Cu") -> Dict[str, object]:
    """Bir elektriksel test kaydını bütün olarak değerlendirir."""
    ttr = assess_turns_ratio(
        {ph: test.get(f"ttr_{ph.lower()}") for ph in PHASES},
        expected_ratio,
        tap=test.get("tap_position"),  # type: ignore[arg-type]
    )
    resistance = assess_winding_resistance(
        {ph: test.get(f"rw_{ph.lower()}_ohm") for ph in PHASES},
        temp_c=_num(test.get("winding_temp_c")),
        winding_material=winding_material,
    )
    insulation = assess_insulation(
        test.get("ir_1min_mohm"),      # type: ignore[arg-type]
        test.get("ir_10min_mohm"),     # type: ignore[arg-type]
        temp_c=_num(test.get("insulation_temp_c")),
    )
    tand = assess_tan_delta(
        test.get("tan_delta_pct"),     # type: ignore[arg-type]
        temp_c=_num(test.get("tan_delta_temp_c")),
    )

    sections = {"turns_ratio": ttr, "winding_resistance": resistance,
                "insulation": insulation, "tan_delta": tand}

    conditions = []
    problems: List[str] = []
    warnings: List[str] = []
    for name, s in sections.items():
        if not s.get("available"):
            continue
        cond = s.get("overall") or s.get("condition")
        conditions.append(str(cond or "bilinmiyor"))
        problems.extend(list(s.get("problems") or []))
        warnings.extend(list(s.get("warnings") or []))
        if s.get("note"):
            warnings.append(str(s["note"]))

    overall = _worst(conditions)

    return {
        "overall": overall,
        "measured_count": len(conditions),
        "sections": sections,
        "problems": problems,
        "warnings": warnings,
    }
