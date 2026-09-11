"""Fiziksel saha gözlemi kontrol listesi. — Faz 9.5

NEDEN EN UCUZ KAZANÇ?
---------------------
Şimdiye kadar eklenen her boyut bir laboratuvar ya da ölçü aleti
gerektiriyordu: DGA gaz kromatografı, furan ayrı bir analiz, TTR ve tan δ
özel cihazlar. Bu boyut **hiçbir şey gerektirmiyor** — teknisyen zaten
sahada, gözü zaten orada.

Üstelik endüstriyel sağlık endeksi modellerinin gerçek bileşenlerinden
biri: DGA ve yağ analizinin yanında **fiziksel gözlem**, yük geçmişi ve
bakım geçmişi de sayılır. Bizim endeksimizde eksikti.

GÖZÜN GÖRDÜĞÜNÜ CİHAZ GÖREMEZ
-----------------------------
Bazı arızalar hiçbir ölçüme yansımadan önce gözle görülür:

* **Yağ kaçağı** — seviye düşerse sargı açığa çıkar. DGA bunu görmez;
  yağ seviyesi düşerken gaz derişimi bile ARTMIŞ görünebilir (aynı gaz,
  daha az yağ).
* **Tıkalı radyatör / durmuş fan** — sıcaklık yükselir, kağıt hızlanarak
  yaşlanır. DGA bunu ancak termal arıza gazı çıktığında görür; o zaman
  hasar zaten oluşmuştur.
* **Doymuş silikajel** — nem alıcı görevini bırakmıştır; yağa nem girer.
  Bir sonraki yağ testinde görülür, ama aylar sonra.
* **Buchholz / basınç tahliye tertibatı arızası** — koruma yok demektir.
  Hiçbir kimyasal ölçüme yansımaz.

⚠ SINIR: bu boyut **özneldir**. "Hafif korozyon" iki teknisyende iki
farklı sonuç verebilir. Bu yüzden sağlık endeksinde en düşük ağırlığı
alır (bkz. ``core/health_index.py``): değeri hassasiyetinde değil,
KAPSAMINDA — ucuz olduğu için sık yapılabilir ve başka hiçbir yöntemin
göremediğini görür.
"""
from __future__ import annotations

from typing import Dict, List, Optional

# Gözlem sonucu.
RATINGS = ("iyi", "dikkat", "kötü", "bakılmadı")

RATING_LABELS = {
    "iyi": "Sorun yok",
    "dikkat": "İzlenmeli",
    "kötü": "Müdahale gerekli",
    "bakılmadı": "Bakılmadı",
}

# --- Kontrol maddeleri ----------------------------------------------------
# critical : "kötü" çıktığında TEK BAŞINA genel hükmü kötü yapar mı?
#
# Ayrım önemli: boyanın dökülmesi ile Buchholz rölesinin çalışmaması aynı
# şey değildir. İkisini eşit saymak, ya boyayı abartmak ya koruma
# arızasını hafife almak olur.
ITEMS: Dict[str, Dict[str, object]] = {
    "oil_leak": {
        "code": "oil_leak", "label": "Yağ kaçağı",
        "critical": True, "group": "Sızdırmazlık",
        "meaning": "Kaçak sürerse yağ seviyesi düşer ve sargı açığa "
                   "çıkabilir. DGA bunu göremez; hatta yağ azalınca gaz "
                   "derişimi ARTMIŞ görünür.",
        "what_to_look": "Tank dibi, radyatör flanşları, vana ve conta "
                        "bölgeleri, buşing dibi.",
    },
    "oil_level": {
        "code": "oil_level", "label": "Yağ seviyesi göstergesi",
        "critical": True, "group": "Sızdırmazlık",
        "meaning": "Konservatör seviyesi sıcaklığa göre beklenen bantta "
                   "olmalı. Düşük seviye doğrudan yalıtım riskidir.",
        "what_to_look": "Konservatör göstergesi ve sıcaklık-seviye "
                        "eğrisiyle uyum.",
    },
    "silica_gel": {
        "code": "silica_gel", "label": "Silikajel (nem alıcı)",
        "critical": False, "group": "Nem kontrolü",
        "meaning": "Rengi dönmüşse nem tutma görevi bitmiştir; yağa nem "
                   "girmeye başlar. Yağ testinde aylar sonra görülür.",
        "what_to_look": "Renk (mavi/turuncu → pembe/beyaz), yağ kilidi "
                        "seviyesi.",
    },
    "cooling": {
        "code": "cooling", "label": "Radyatör ve fanlar",
        "critical": True, "group": "Soğutma",
        "meaning": "Tıkalı radyatör ya da durmuş fan sıcaklığı yükseltir; "
                   "kağıt hızlanarak yaşlanır. DGA bunu ancak termal arıza "
                   "gazı çıkınca görür — hasar o zaman oluşmuştur.",
        "what_to_look": "Kirlenme/tıkanma, fan çalışması, yağ pompası "
                        "sesi, radyatör yüzey sıcaklığı farkı.",
    },
    "bushings": {
        "code": "bushings", "label": "Buşingler (görsel)",
        "critical": True, "group": "Elektriksel",
        "meaning": "Çatlak, kirlenme, yağ sızıntısı ya da flaş izi. Trafo "
                   "arızalarının önemli bir kısmı buşing kaynaklıdır.",
        "what_to_look": "Porselen çatlağı, kaçak izi, yüzey kirliliği, "
                        "korona/flaş izleri.",
    },
    "protection": {
        "code": "protection", "label": "Koruma tertibatı",
        "critical": True, "group": "Elektriksel",
        "meaning": "Buchholz, basınç tahliye, sıcaklık rölesi. Arızalıysa "
                   "koruma YOK demektir ve hiçbir kimyasal ölçüme yansımaz.",
        "what_to_look": "Röle göstergeleri, test düğmesi tepkisi, gaz "
                        "birikimi, kablo bağlantıları.",
    },
    "grounding": {
        "code": "grounding", "label": "Topraklama",
        "critical": True, "group": "Elektriksel",
        "meaning": "Gevşek ya da korozyona uğramış topraklama, arıza "
                   "akımının yolunu bozar; personel güvenliği sorunudur.",
        "what_to_look": "Bağlantı sıkılığı, korozyon, kesit hasarı.",
    },
    "noise_vibration": {
        "code": "noise_vibration", "label": "Gürültü ve titreşim",
        "critical": False, "group": "Mekanik",
        "meaning": "Olağandışı uğultu gevşek sargı ya da çekirdek "
                   "sorununa işaret edebilir.",
        "what_to_look": "Ses seviyesi ve karakteri, tank titreşimi.",
    },
    "corrosion": {
        "code": "corrosion", "label": "Korozyon ve boya",
        "critical": False, "group": "Gövde",
        "meaning": "Uzun vadeli sızdırmazlık riski. Tek başına acil "
                   "değildir ama ihmalin göstergesidir.",
        "what_to_look": "Pas, boya kabarması, özellikle deniz kenarı "
                        "ve sanayi bölgelerinde.",
    },
    "tap_changer": {
        "code": "tap_changer", "label": "Kademe değiştirici (görsel)",
        "critical": False, "group": "Mekanik",
        "meaning": "Sayaç, yağ durumu, kaçak. Kontak aşınmasını sargı "
                   "direnci ölçer; bu gözlem onu tamamlar.",
        "what_to_look": "İşletme sayacı, yağ rengi/seviyesi, motor "
                        "mekanizma kutusu.",
    },
}

ITEM_ORDER: List[str] = list(ITEMS)

# Kaç kritik olmayan madde "kötü" olursa genel hüküm kötüye döner?
#
# Tek bir kozmetik bulgu acil değildir, ama üç tanesi birden ihmal
# edilmiş bir varlığın işaretidir.
NONCRITICAL_BAD_LIMIT = 3


def _rating(value: object) -> str:
    text = str(value or "").strip()
    return text if text in RATINGS else "bakılmadı"


def assess(observations: Dict[str, object]) -> Dict[str, object]:
    """Bir gözlem turunu değerlendirir.

    ``observations``: {"oil_leak": "iyi", "cooling": "kötü", ...}
    """
    rows: List[Dict[str, object]] = []
    for code in ITEM_ORDER:
        spec = ITEMS[code]
        rating = _rating(observations.get(code))
        rows.append({
            "code": code,
            "label": spec["label"],
            "group": spec["group"],
            "critical": spec["critical"],
            "rating": rating,
            "rating_label": RATING_LABELS[rating],
            "meaning": spec["meaning"],
            "what_to_look": spec["what_to_look"],
        })

    checked = [r for r in rows if r["rating"] != "bakılmadı"]
    if not checked:
        return {"available": False, "reason": "Hiçbir madde işaretlenmemiş.",
                "items": rows}

    critical_bad = [r for r in checked
                    if r["critical"] and r["rating"] == "kötü"]
    other_bad = [r for r in checked
                 if not r["critical"] and r["rating"] == "kötü"]
    watch = [r for r in checked if r["rating"] == "dikkat"]

    # Genel hüküm. "En kötü madde" kuralının nitelikli hâli: kritik bir
    # maddenin kötü olması tek başına yeter, kozmetik bulgular ise
    # birikince anlam kazanır.
    if critical_bad:
        overall = "kötü"
    elif len(other_bad) >= NONCRITICAL_BAD_LIMIT:
        overall = "kötü"
    elif other_bad or watch:
        overall = "kabul"
    else:
        overall = "iyi"

    problems = [f"{r['label']}: {r['rating_label'].lower()}"
                for r in critical_bad + other_bad]

    return {
        "available": True,
        "overall": overall,
        "items": rows,
        "checked_count": len(checked),
        "total_count": len(rows),
        "critical_findings": [str(r["label"]) for r in critical_bad],
        "watch_items": [str(r["label"]) for r in watch],
        "problems": problems,
        # Kapsama: kaç madde bakıldı? Yarısı boş bırakılmış bir tur,
        # "sorun yok" demeye yetmez.
        "coverage_pct": round(len(checked) / len(rows) * 100),
    }


def schema() -> Dict[str, object]:
    """Arayüzün form ve açıklamaları için tanım."""
    groups: Dict[str, List[Dict[str, object]]] = {}
    for code in ITEM_ORDER:
        spec = ITEMS[code]
        groups.setdefault(str(spec["group"]), []).append({
            "code": code,
            "label": spec["label"],
            "critical": spec["critical"],
            "meaning": spec["meaning"],
            "what_to_look": spec["what_to_look"],
        })

    return {
        "groups": [{"name": name, "items": items}
                   for name, items in groups.items()],
        "ratings": [{"code": r, "label": RATING_LABELS[r]} for r in RATINGS],
        "noncritical_bad_limit": NONCRITICAL_BAD_LIMIT,
        "note": "Kritik maddelerden biri 'müdahale gerekli' ise genel hüküm "
                "tek başına kötüye döner. Kritik olmayan bulgular ise "
                f"{NONCRITICAL_BAD_LIMIT} tanesi birikince anlam kazanır.",
    }
