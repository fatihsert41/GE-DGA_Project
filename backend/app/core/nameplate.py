"""Trafo künyesi (nameplate): varlığın kalıcı kimlik ve tasarım bilgileri.

NEDEN BU MODÜL VAR
------------------
Şimdiye kadar bir trafo hakkında beş şey biliyorduk: id, ad, konum, sınıf,
MVA. Gerçek bir varlık kaydı çok daha zengindir ve **sonraki her tanı
modülü buna dayanır**:

* Sarım oranı testi (TTR) beklenen değeri **gerilim oranından ve bağlantı
  grubundan** hesaplar.
* Termal model (IEEE C57.91) **soğutma tipini** ister.
* Yaşlanma / kalan ömür hesabı **devreye alma tarihini** ister.
* Gaz ppm değerini mutlak gaz miktarına çevirmek **yağ hacmini** ister.

Yani künye süs değil, hesapların girdisi.

Bu modül saf Python'dur: sabitler, doğrulama ve türetilmiş büyüklükler.
Veritabanı ve HTTP bilmez.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional

# --- Soğutma tipleri (IEC 60076-2) ----------------------------------------
# Dört harf: [yağ ortamı][yağ dolaşımı][dış ortam][dış dolaşım]
#   O=mineral yağ, N=doğal dolaşım, A=hava, F=zorlamalı, D=yönlendirilmiş
# Termal modelin zaman sabitleri ve üs katsayıları bu tipe göre değişir.
COOLING_TYPES: Dict[str, str] = {
    "ONAN": "Doğal yağ, doğal hava (radyatör)",
    "ONAF": "Doğal yağ, fanlı hava",
    "OFAF": "Pompalı yağ, fanlı hava",
    "ODAF": "Yönlendirilmiş yağ, fanlı hava",
}

# --- Bağlantı grupları -----------------------------------------------------
# Harf: sargı bağlantısı (Y=yıldız, D=üçgen, Z=zikzak), büyük harf YG tarafı.
# N = nötr çıkışlı. Sayı = saat yönü faz kayması (×30°).
#
# TTR için kritik: faz-faz ölçümünde YILDIZ-ÜÇGEN kombinasyonu √3 çarpanı
# getirir. Beklenen oranı yanlış hesaplamak testi anlamsız kılar.
VECTOR_GROUPS: Dict[str, Dict[str, object]] = {
    "YNyn0": {"hv": "Y", "lv": "Y", "shift": 0, "phase_factor": 1.0},
    "YNd11": {"hv": "Y", "lv": "D", "shift": 11, "phase_factor": 3 ** 0.5},
    "YNd1": {"hv": "Y", "lv": "D", "shift": 1, "phase_factor": 3 ** 0.5},
    "Dyn11": {"hv": "D", "lv": "Y", "shift": 11, "phase_factor": 1 / 3 ** 0.5},
    "Dyn1": {"hv": "D", "lv": "Y", "shift": 1, "phase_factor": 1 / 3 ** 0.5},
    "Dd0": {"hv": "D", "lv": "D", "shift": 0, "phase_factor": 1.0},
}

WINDING_MATERIALS = ("Cu", "Al")

# Kağıt yalıtım tipi — kağıt yaşlanma hesabında (Faz 8.2) fark yaratır:
# termal yükseltilmiş kağıt daha yavaş bozunur ve furan bağıntısı sapar.
INSULATION_TYPES: Dict[str, str] = {
    "kraft": "Standart kraft kağıt",
    "tuk": "Termal yükseltilmiş kraft (TUK)",
}

TAP_CHANGER_TYPES: Dict[str, str] = {
    "OLTC": "Yük altında kademe değiştirici",
    "DETC": "Yüksüz kademe değiştirici",
    "none": "Kademe değiştirici yok",
}

# Anma sıcak nokta sıcaklığı (IEEE C57.91 referansı). Yaşlanma hesabında
# 110 °C'de normal ömür ≈ 180.000 saat kabul edilir.
DEFAULT_RATED_HOTSPOT_C = 110.0
DEFAULT_RATED_TOP_OIL_C = 95.0

# Yeni kağıdın polimerizasyon derecesi. 200'e düşünce kağıt ömrünü
# tamamlamış sayılır (Faz 8.2'de kullanılacak).
DP_NEW_PAPER = 1100
DP_END_OF_LIFE = 200


class NameplateError(ValueError):
    """Künye doğrulaması başarısız."""


def validate(np: Dict[str, object]) -> List[str]:
    """Künyeyi denetler ve sorun listesi döndürür (boşsa sorun yok).

    Hata FIRLATMAZ, listeler: bir künyede birden çok sorun olabilir ve
    kullanıcıya hepsini birden göstermek tek tek düzelttirmekten iyidir.
    """
    problems: List[str] = []

    hv = _num(np.get("hv_kv"))
    lv = _num(np.get("lv_kv"))
    if hv is not None and lv is not None and hv <= lv:
        problems.append(
            f"YG gerilimi ({hv} kV) AG geriliminden ({lv} kV) büyük olmalı.")

    cooling = np.get("cooling")
    if cooling and str(cooling) not in COOLING_TYPES:
        problems.append(f"Bilinmeyen soğutma tipi: {cooling}. "
                        f"Geçerli: {', '.join(COOLING_TYPES)}")

    vg = np.get("vector_group")
    if vg and str(vg) not in VECTOR_GROUPS:
        problems.append(f"Bilinmeyen bağlantı grubu: {vg}. "
                        f"Geçerli: {', '.join(VECTOR_GROUPS)}")

    wm = np.get("winding_material")
    if wm and str(wm) not in WINDING_MATERIALS:
        problems.append(f"Sargı malzemesi Cu veya Al olmalı: {wm}")

    ins = np.get("insulation_type")
    if ins and str(ins) not in INSULATION_TYPES:
        problems.append(f"Bilinmeyen yalıtım tipi: {ins}")

    tc = np.get("tap_changer_type")
    if tc and str(tc) not in TAP_CHANGER_TYPES:
        problems.append(f"Bilinmeyen kademe değiştirici tipi: {tc}")

    tmin = _num(np.get("tap_min"))
    tmax = _num(np.get("tap_max"))
    if tmin is not None and tmax is not None and tmin > tmax:
        problems.append(f"Kademe aralığı ters: {tmin} > {tmax}")

    year = np.get("year_made")
    if year is not None:
        y = _num(year)
        this_year = date.today().year
        if y is not None and not (1900 <= y <= this_year + 1):
            problems.append(f"Üretim yılı makul değil: {year}")

    for field in ("mva", "oil_volume_l"):
        v = _num(np.get(field))
        if v is not None and v <= 0:
            problems.append(f"{field} pozitif olmalı: {v}")

    return problems


def _num(value: object) -> Optional[float]:
    """Sayıya çevirir; çeviremezse None (doğrulama onu ayrıca yakalar)."""
    if value is None or value == "":
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _parse_date(value: object) -> Optional[date]:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return datetime.fromisoformat(str(value)[:10]).date()
    except ValueError:
        return None


def age_years(np: Dict[str, object], today: Optional[date] = None
              ) -> Optional[float]:
    """Devreye alma tarihinden bugüne kaç yıl geçti?

    Devreye alma tarihi yoksa üretim yılına düşer. Yaşlanma ve ömür
    hesaplarının girdisi.
    """
    today = today or date.today()
    commissioned = _parse_date(np.get("commissioned_at"))
    if commissioned is not None:
        return round((today - commissioned).days / 365.25, 1)

    year = _num(np.get("year_made"))
    if year is not None:
        return round(today.year - year, 1)
    return None


def rated_turns_ratio(np: Dict[str, object]) -> Optional[float]:
    """Anma sarım oranı — sarım oranı testinin (TTR) beklenen değeri.

    Faz-faz ölçümünde bağlantı grubu bir çarpan getirir: yıldız-üçgen
    kombinasyonlarında √3. Bu çarpanı atlamak testi anlamsız kılar —
    ölçüm "hatalı" görünür oysa trafo sağlamdır.
    """
    hv = _num(np.get("hv_kv"))
    lv = _num(np.get("lv_kv"))
    if hv is None or lv is None or lv <= 0:
        return None

    vg = VECTOR_GROUPS.get(str(np.get("vector_group") or ""), {})
    factor = float(vg.get("phase_factor", 1.0))  # type: ignore[arg-type]
    return round((hv / lv) * factor, 4)


def turns_ratio_at_tap(np: Dict[str, object], tap: int) -> Optional[float]:
    """Belirli bir kademe pozisyonundaki beklenen sarım oranı.

    Kademe değiştirici YG sargısının sarım sayısını değiştirir; her kademe
    tipik olarak ±%1.25 gerilim değişimi sağlar.
    """
    base = rated_turns_ratio(np)
    step = _num(np.get("tap_step_percent"))
    if base is None or step is None:
        return base
    return round(base * (1 + (tap * step) / 100.0), 4)


def summary(np: Dict[str, object]) -> Dict[str, object]:
    """Künyeden türetilen büyüklükler — tabloda saklanmaz, hesaplanır."""
    return {
        "age_years": age_years(np),
        "rated_turns_ratio": rated_turns_ratio(np),
        "cooling_label": COOLING_TYPES.get(str(np.get("cooling") or ""), None),
        "insulation_label": INSULATION_TYPES.get(
            str(np.get("insulation_type") or ""), None),
        "tap_changer_label": TAP_CHANGER_TYPES.get(
            str(np.get("tap_changer_type") or ""), None),
    }
