"""Trafo şeması: hangi parça ne durumda? — Faz 9.6

NEDEN BACKEND'DE?
-----------------
Şema bir çizimdir, ama parçaların rengini belirleyen şey KURALDIR: "bu
buşing kötü mü?" sorusunun cevabı kapasitans sapmasından gelir, "bu
radyatör kötü mü?" sorusununki saha gözleminden. Bu kuralları arayüzde
tekrar yazmak, projede baştan beri kaçınılan hatayı yapardı: iki yerde
iki farklı gerçek.

Arayüz yalnızca çizer. Hangi parçanın hangi renkte olacağını ve
tıklanınca hangi sekmeye gidileceğini burası söyler.

NEDEN ŞİMDİ ANLAMLI?
--------------------
Faz 9'un başındaki analizde şema ertelenmişti: "bileşen verisi yoksa şema
boş bir çizim olur." Faz 9.4 (buşing/kademe) ve 9.5 (saha gözlemi)
tamamlandıktan sonra her parçanın arkasında gerçek bir ölçüm var.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from .. import database
from ..core import components as core_components
from ..core import physical as core_physical
from . import components as component_service
from . import oil as oil_service
from . import physical as physical_service

# Parça tanımları: şemada ne çizilecek, verisi nereden gelecek.
#
# ``tab`` alanı arayüzün hangi detay sekmesine gideceğini söyler —
# şemadan tıklayınca ölçümün kendisine ulaşılabilmeli, yoksa çizim
# dekordan ibaret kalır.
PARTS: List[Dict[str, str]] = [
    {"code": "bushing_a", "label": "A fazı buşingi", "tab": "components"},
    {"code": "bushing_b", "label": "B fazı buşingi", "tab": "components"},
    {"code": "bushing_c", "label": "C fazı buşingi", "tab": "components"},
    {"code": "windings", "label": "Sargılar (aktif kısım)", "tab": "measurements"},
    {"code": "paper", "label": "Kağıt yalıtım", "tab": "oil"},
    {"code": "oil", "label": "Yalıtım yağı", "tab": "oil"},
    {"code": "oltc", "label": "Kademe değiştirici", "tab": "components"},
    {"code": "cooling", "label": "Radyatörler ve fanlar", "tab": "inspection"},
    {"code": "conservator", "label": "Konservatör ve nem alıcı", "tab": "inspection"},
    {"code": "protection", "label": "Koruma tertibatı", "tab": "inspection"},
    {"code": "tank", "label": "Tank ve sızdırmazlık", "tab": "inspection"},
]

# DGA kondisyonu (1-4) -> parça durumu.
_DGA_CONDITION = {1: "iyi", 2: "kabul", 3: "kötü", 4: "kötü"}

# Saha gözlemi derecesi -> parça durumu.
_RATING = {"iyi": "iyi", "dikkat": "kabul", "kötü": "kötü",
           "bakılmadı": "bilinmiyor"}

# Kağıt bandı -> parça durumu.
_PAPER_BAND = {"sağlıklı": "iyi", "orta": "kabul",
               "ileri": "kötü", "ömür sonu": "kötü"}


def _part(code: str, condition: str, source: str,
          detail: Optional[str] = None) -> Dict[str, object]:
    spec = next(p for p in PARTS if p["code"] == code)
    return {
        "code": code,
        "label": spec["label"],
        "tab": spec["tab"],
        "condition": condition,
        # Hangi ölçümden geldiği HER ZAMAN yazılı. Renkli bir kutu
        # kendi başına bir iddiadır; iddianın kaynağı görünmeli.
        "source": source,
        "detail": detail,
    }


def _rating_of(inspection: Optional[Dict[str, object]], code: str) -> str:
    if not inspection:
        return "bakılmadı"
    obs = inspection.get("observations") or {}
    value = str(obs.get(code) or "bakılmadı")
    return value if value in core_physical.RATINGS else "bakılmadı"


def build(transformer_id: str) -> Dict[str, object]:
    """Bir trafonun şema verisini üretir."""
    record = database.get_transformer(transformer_id)
    if record is None:
        return {"found": False}

    # --- Kaynak ölçümler ------------------------------------------------
    measurements = database.get_measurements(transformer_id)
    latest_dga = measurements[-1] if measurements else None

    oil_tests = [t for t in database.get_oil_tests(transformer_id)
                 if not t.get("voided_at")]
    oil = oil_service.oil_card(transformer_id,
                               oil_tests[-1] if oil_tests else None)

    comp_tests = database.get_component_tests(transformer_id)
    comp = (component_service.assess_test(transformer_id, comp_tests[-1])
            if comp_tests else None)

    inspections = database.get_physical_inspections(transformer_id)
    inspection = inspections[-1] if inspections else None

    np = record.get("nameplate") or {}
    has_tap_changer = bool(np.get("tap_changer_type"))

    parts: List[Dict[str, object]] = []

    # --- Buşingler -------------------------------------------------------
    bushings = (comp or {}).get("sections", {}).get("bushings") if comp else None
    for ph in core_components.PHASES:
        code = f"bushing_{ph.lower()}"
        if bushings and bushings.get("available"):
            row = next((r for r in bushings["phases"] if r["phase"] == ph), None)
            if row and row["condition"] != "bilinmiyor":
                dev = row.get("deviation_pct")
                detail = (f"kapasitans sapması %{dev}" if dev is not None
                          else f"güç faktörü %{row.get('pf_pct')}")
                parts.append(_part(code, str(row["condition"]),
                                   "Buşing testi", detail))
                continue
        parts.append(_part(code, "bilinmiyor", "Buşing testi",
                           "ölçüm yok"))

    # --- Sargılar: DGA -----------------------------------------------------
    if latest_dga and latest_dga.get("risk_condition"):
        cond = int(latest_dga["risk_condition"])
        parts.append(_part("windings", _DGA_CONDITION.get(cond, "kabul"),
                           "DGA (çözünmüş gaz analizi)",
                           f"{latest_dga.get('prediction')} · "
                           f"IEEE kondisyon {cond}"))
    else:
        parts.append(_part("windings", "bilinmiyor", "DGA", "ölçüm yok"))

    # --- Kağıt -------------------------------------------------------------
    band = oil.get("paper_band")
    if band:
        parts.append(_part("paper", _PAPER_BAND.get(str(band), "kabul"),
                           "Furan → DP (Chendong)",
                           f"DP ≈ {oil.get('dp_estimate')} · tüketilen ömür "
                           f"%{oil.get('life_consumed_pct')}"))
    else:
        parts.append(_part("paper", "bilinmiyor", "Furan analizi",
                           "ölçüm yok"))

    # --- Yağ ---------------------------------------------------------------
    if oil.get("oil_overall"):
        parts.append(_part("oil", str(oil["oil_overall"]),
                           "Yağ kalitesi testi",
                           "nem, delinme gerilimi, asitlik, arayüzey gerilimi"))
    else:
        parts.append(_part("oil", "bilinmiyor", "Yağ kalitesi testi",
                           "ölçüm yok"))

    # --- Kademe değiştirici ------------------------------------------------
    oltc = (comp or {}).get("sections", {}).get("oltc") if comp else None
    if not has_tap_changer:
        parts.append(_part("oltc", "yok", "Künye",
                           "bu trafoda kademe değiştirici yok"))
    elif oltc and oltc.get("available"):
        detail = "; ".join(f"{c['label']} {c['value']} {c['unit']}"
                           for c in oltc["checks"])
        parts.append(_part("oltc", str(oltc["overall"]),
                           "Kademe değiştirici testi", detail))
    else:
        parts.append(_part("oltc", "bilinmiyor", "Kademe değiştirici testi",
                           "ölçüm yok"))

    # --- Saha gözleminden gelen parçalar ------------------------------------
    for code, item in (("cooling", "cooling"),
                       ("conservator", "silica_gel"),
                       ("protection", "protection"),
                       ("tank", "oil_leak")):
        rating = _rating_of(inspection, item)
        spec = core_physical.ITEMS[item]
        parts.append(_part(
            code, _RATING[rating], "Saha gözlemi",
            f"{spec['label']}: {core_physical.RATING_LABELS[rating].lower()}"))

    known = [p for p in parts if p["condition"] not in ("bilinmiyor", "yok")]
    bad = [p for p in known if p["condition"] == "kötü"]

    return {
        "found": True,
        "transformer_id": transformer_id,
        "name": record.get("name"),
        "parts": parts,
        "summary": {
            "total": len(parts),
            "known": len(known),
            "bad": len(bad),
            "bad_parts": [str(p["label"]) for p in bad],
        },
        "note": "Her parçanın rengi bir ÖLÇÜMDEN gelir; kaynağı parçanın "
                "yanında yazılıdır. Tıklayınca ilgili ölçüm sekmesi açılır.",
    }
