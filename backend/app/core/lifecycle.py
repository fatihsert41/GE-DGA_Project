"""Varlık yaşam döngüsü: trafo fabrikadan sahaya. — Faz 9.35

NEDEN GEREKLİ — yaşanan somut hata
----------------------------------
Şimdiye kadar sisteme **işletmedeki** trafo gözüyle bakıldı: sahada duran,
yağı alınan, ölçülen bir varlık. Ama GE Vernova bu trafoları **üretip
satıyor**; bir ünitenin hayatı fabrikada başlıyor ve sahaya varması aylar
sürüyor.

Bunu modellememenin bedeli görünürdü: **fabrikada sevkiyat bekleyen bir
ünite "numunesi gecikmiş" sayılıyordu.** Henüz enerjilenmemiş, yağında
gaz üretmesi fiziksel olarak mümkün olmayan bir trafo için numune alma
iş emri öneriliyordu. Kural yanlış değildi; kurala verilen varlık kümesi
yanlıştı.

TASARIM: DURUMLAR AYRINTILI, KURALLAR EVRE BAZLI
------------------------------------------------
On bir durum var ama hiçbir kural tek tek durumlara bakmaz; hepsi
**evreye** (`phase`) bakar:

    factory  — henüz fabrikada, enerjilenmemiş
    transit  — yolda ya da nakliye/vinç bekliyor
    field    — sahada; montajda, devreye alınıyor ya da devrede
    retired  — hizmet dışı ya da hurda

Böylece "vinç bekleniyor" ile "yolda" arasındaki fark operasyon için
görünür kalır, ama kural yazarken tek bir soru sorulur: *bu varlık
izlenmeli mi?* Yeni bir durum eklendiğinde kuralları tek tek gözden
geçirmek gerekmez — evresi belirlenir, kurallar kendiliğinden doğru
çalışır.

⚠ Durum geçişleri KURALLIDIR (.NET'teki ``WorkOrderTransitions`` gibi):
"Devrede" durumundan "Üretimde"ye dönülemez. Geçersiz geçişi engellemek,
yanlış veriyi sonradan düzeltmekten ucuzdur.
"""
from __future__ import annotations

from typing import Dict, List, Optional

# --- Evreler ---------------------------------------------------------------
PHASES: Dict[str, Dict[str, object]] = {
    "factory": {
        "code": "factory", "label_tr": "Fabrikada",
        "note": "Henüz enerjilenmedi; yağında arıza gazı beklenmez.",
    },
    "transit": {
        "code": "transit", "label_tr": "Sevkiyatta",
        "note": "Nakliye sürecinde. Mekanik darbe riski izlenir, "
                "gaz üretimi beklenmez.",
    },
    "field": {
        "code": "field", "label_tr": "Sahada",
        "note": "Saha kurulumunda ya da işletmede.",
    },
    "retired": {
        "code": "retired", "label_tr": "Hizmet dışı",
        "note": "İşletmede değil.",
    },
}

PHASE_ORDER: List[str] = ["factory", "transit", "field", "retired"]


# --- Durumlar --------------------------------------------------------------
# monitored : DGA numune takvimi bu durumda işler mi?
#
# Yalnızca "in_service" izlenir. Devreye alma sırasında da DGA alınır ama
# bu bir TEMEL ÇİZGİ ölçümüdür, periyodik takvim değil — gecikme sayacı
# işletilmemelidir.
STATES: Dict[str, Dict[str, object]] = {
    "manufacturing": {
        "code": "manufacturing", "label_tr": "Üretimde", "phase": "factory",
        "order": 10, "monitored": False,
        "description": "Sargı, montaj ve yağ dolumu sürüyor.",
    },
    "factory_testing": {
        "code": "factory_testing", "label_tr": "Fabrika testinde",
        "phase": "factory", "order": 20, "monitored": False,
        "description": "Rutin ve tip testleri (oran, direnç, yalıtım).",
    },
    "ready_to_ship": {
        "code": "ready_to_ship", "label_tr": "Sevkiyata hazır",
        "phase": "factory", "order": 30, "monitored": False,
        "description": "Testleri geçti; sevkiyat planı bekliyor.",
    },
    "awaiting_transport": {
        "code": "awaiting_transport", "label_tr": "Nakliye/vinç bekliyor",
        "phase": "transit", "order": 40, "monitored": False,
        "description": "Ağır nakliye ve vinç planlaması bekleniyor. "
                       "Büyük üniteler için haftalar sürebilir.",
    },
    "in_transit": {
        "code": "in_transit", "label_tr": "Yolda", "phase": "transit",
        "order": 50, "monitored": False,
        "description": "Sevk edildi; darbe kaydedici izleniyor.",
    },
    "on_site": {
        "code": "on_site", "label_tr": "Sahada — montajda", "phase": "field",
        "order": 60, "monitored": False,
        "description": "Teslim alındı; montaj ve bağlantı sürüyor.",
    },
    "commissioning": {
        "code": "commissioning", "label_tr": "Devreye alma",
        "phase": "field", "order": 70, "monitored": False,
        "description": "Devreye alma testleri ve TEMEL ÇİZGİ ölçümleri. "
                       "Bu aşamada alınan DGA, karşılaştırma noktasıdır.",
    },
    "in_service": {
        "code": "in_service", "label_tr": "Devrede", "phase": "field",
        "order": 80, "monitored": True,
        "description": "Yük altında çalışıyor. Periyodik numune takvimi "
                       "yalnızca bu durumda işler.",
    },
    "spare": {
        "code": "spare", "label_tr": "Yedek", "phase": "field",
        "order": 85, "monitored": False,
        "description": "Sahada ama enerjisiz; yedek ünite olarak bekliyor. "
                       "Kritik bir varlık arızalandığında devreye alınır.",
    },
    "out_of_service": {
        "code": "out_of_service", "label_tr": "Hizmet dışı",
        "phase": "retired", "order": 90, "monitored": False,
        "description": "Arıza, bakım ya da karar gereği devre dışı.",
    },
    "scrapped": {
        "code": "scrapped", "label_tr": "Hurda", "phase": "retired",
        "order": 100, "monitored": False,
        "description": "Ömrünü tamamladı; izleme kapsamı dışında.",
    },
}

DEFAULT_STATE = "in_service"

# --- İzinli geçişler -------------------------------------------------------
# Kurallı durum makinesi. "Devrede" durumundan "Üretimde"ye dönülemez.
#
# Geri yönlü bazı geçişler BİLİNÇLİ olarak açık:
#   in_service -> out_of_service -> in_service   (bakım sonrası dönüş)
#   commissioning -> on_site                     (test başarısız, sökülüyor)
#   in_service -> spare                          (yerine yenisi kondu)
TRANSITIONS: Dict[str, List[str]] = {
    "manufacturing": ["factory_testing", "scrapped"],
    "factory_testing": ["ready_to_ship", "manufacturing", "scrapped"],
    "ready_to_ship": ["awaiting_transport", "factory_testing"],
    "awaiting_transport": ["in_transit", "ready_to_ship"],
    "in_transit": ["on_site", "awaiting_transport"],
    "on_site": ["commissioning", "in_transit"],
    "commissioning": ["in_service", "on_site", "out_of_service"],
    "in_service": ["out_of_service", "spare", "scrapped"],
    "spare": ["in_service", "out_of_service", "scrapped"],
    "out_of_service": ["in_service", "commissioning", "spare", "scrapped"],
    "scrapped": [],          # uç durum: buradan çıkış yok
}


def get(code: Optional[str]) -> Dict[str, object]:
    """Durum tanımı; bilinmeyen kod varsayılana düşer."""
    return STATES.get(str(code or ""), STATES[DEFAULT_STATE])


def phase_of(code: Optional[str]) -> str:
    return str(get(code)["phase"])


def is_monitored(code: Optional[str]) -> bool:
    """Periyodik DGA numune takvimi bu durumda işler mi?

    Kuralların sorduğu TEK soru bu. Durum listesi büyüdükçe kurallara
    dokunmak gerekmemesinin sebebi.
    """
    return bool(get(code)["monitored"])


def can_transition(current: Optional[str], target: str) -> bool:
    return target in TRANSITIONS.get(str(current or DEFAULT_STATE), [])


def validate_transition(current: Optional[str], target: str) -> Optional[str]:
    """Geçiş geçerli mi? Geçerliyse None, değilse açıklama döner.

    İstisna fırlatmak yerine metin döndürüyor: geçersiz geçiş beklenen
    bir durumdur (kullanıcı yanlış seçebilir), istisnai değil.
    (``nameplate.validate`` da aynı deseni izliyor.)
    """
    if target not in STATES:
        return f"Bilinmeyen durum: {target}"

    cur = str(current or DEFAULT_STATE)
    if cur == target:
        return f"Varlık zaten '{STATES[target]['label_tr']}' durumunda."

    if not can_transition(cur, target):
        allowed = TRANSITIONS.get(cur, [])
        names = ", ".join(str(STATES[a]["label_tr"]) for a in allowed) or "yok"
        return (f"'{STATES[cur]['label_tr']}' durumundan "
                f"'{STATES[target]['label_tr']}' durumuna geçilemez. "
                f"İzinli geçişler: {names}.")
    return None


def summary(code: Optional[str]) -> Dict[str, object]:
    """Arayüzün göstereceği durum özeti."""
    state = get(code)
    phase = PHASES[str(state["phase"])]
    return {
        "code": state["code"],
        "label_tr": state["label_tr"],
        "description": state["description"],
        "phase": phase["code"],
        "phase_tr": phase["label_tr"],
        "phase_note": phase["note"],
        "monitored": state["monitored"],
        "next_states": [
            {"code": c, "label_tr": STATES[c]["label_tr"]}
            for c in TRANSITIONS.get(str(state["code"]), [])
        ],
    }


def ordered_states() -> List[Dict[str, object]]:
    """Durumlar, yaşam döngüsü sırasına göre."""
    return [summary(c) for c in
            sorted(STATES, key=lambda c: int(STATES[c]["order"]))]  # type: ignore[arg-type]
