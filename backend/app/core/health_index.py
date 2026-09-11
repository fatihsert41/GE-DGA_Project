"""Sağlık Endeksi — üç boyutu tek 0-100 skora indirger. — Faz 8.5

NEDEN?
------
Elimizde artık trafonun durumunu anlatan ÜÇ ayrı ölçüt var ve üçü farklı
birimlerde konuşuyor:

* **DGA riski**      — IEEE C57.104 kondisyonu (1-4)
* **Yağ kalitesi**   — iyi / kabul / kötü (IEC 60422 ailesi)
* **Kağıt DP**       — tüketilen ömür yüzdesi (Chendong / IEC 61198)

Bir bakım planlamacısı bunlara ayrı ayrı bakıp "hangisine önce gideyim?"
sorusunu cevaplayamaz. Endüstrideki karşılığı **Health Index**'tir: her
boyut ortak bir 0-100 ölçeğine çevrilir, önem ağırlığıyla çarpılır ve
ortalaması alınır. Mevcut ``assets.priority_score`` (kondisyon × varlık
ağırlığı) bu fikrin tek boyutlu hâliydi; burada genelleştiriliyor.

ÜÇ TASARIM KARARI
-----------------
1. **Bilinmeyen boyut "sağlıklı" sayılmaz.** Yağ testi olmayan bir trafo,
   yağı iyi olan bir trafoyla aynı skoru alamaz. Bilinmeyen boyutlar
   ortalamadan ÇIKARILIR (ağırlık paydası küçülür) ve ``coverage`` alanı
   skorun ne kadar veriye dayandığını söyler. Ortalamaya 100 yazmak
   sessizce yalan söylemek olurdu.

2. **Kritik boyut tavanı.** Saf ağırlıklı ortalama, iki iyi boyutun bir
   kritik boyutu gizlemesine izin verir: yağı temiz, kağıdı yeni ama ark
   yapan bir trafo 70 puan alırdı. Bu yüzden herhangi bir boyut en kötü
   seviyesindeyse skor bir TAVANI aşamaz. (``oil_quality.assess`` de aynı
   gerekçeyle ortalama değil "en kötü parametre" mantığını kullanıyor.)

3. **Yaş ayrı bir boyut DEĞİL.** Endüstriyel HI formüllerinin çoğu yaşı
   ayrıca puanlar. Burada puanlanmıyor, çünkü yaşın trafoya asıl etkisi
   zaten kağıt DP'sinin içinde ölçülüyor — ikisini toplamak aynı şeyi iki
   kez saymak olur. Yaş yine de raporda bağlam olarak taşınıyor.

⚠ Ağırlıklar ve bantlar **konvansiyoneldir**; işletmeler kendi HI
formüllerini kullanır. Değerler tek yerde toplandı ve değiştirilebilir
tutuldu — ``assets.py`` ve ``oil_quality.py`` ile aynı yaklaşım.
"""
from __future__ import annotations

from typing import Dict, List, Optional

# --- Boyutlar ------------------------------------------------------------
# weight : önem ağırlığı (ortalamada çarpan)
#
# DGA en ağır: aktif, gelişmekte olan bir arızayı gösteren tek boyut o.
# Kağıt ikinci: bozunması GERİ DÖNÜŞSÜZ, trafonun ömrü kağıdın ömrüdür.
# Yağ en hafif: kötü yağ ciddidir ama yağ filtrelenebilir/değiştirilebilir.
DIMENSIONS: Dict[str, Dict[str, object]] = {
    "dga": {
        "key": "dga",
        "label": "DGA riski",
        "weight": 4.0,
        "source": "IEEE C57.104 kondisyonu",
        "meaning": "Yağda çözünmüş gazlardan okunan aktif arıza şiddeti.",
    },
    "paper": {
        "key": "paper",
        "label": "Kağıt yalıtım",
        "weight": 3.0,
        "source": "Furan → DP (Chendong, IEC 61198)",
        "meaning": "Tüketilen mekanik ömür. Geri dönüşü yoktur.",
    },
    "oil": {
        "key": "oil",
        "label": "Yağ kalitesi",
        "weight": 2.0,
        "source": "IEC 60422 / 60156 / 62021 / ASTM D971",
        "meaning": "Nem, delinme gerilimi, asitlik, arayüzey gerilimi.",
    },
}

DIMENSION_ORDER: List[str] = ["dga", "paper", "oil"]

# IEEE kondisyonu -> 0-100 puan. Doğrusal DEĞİL: 1'den 2'ye geçmek rutin
# bir uyarıdır, 3'ten 4'e geçmek acil müdahaledir. Puan da bunu yansıtmalı.
DGA_SCORES: Dict[int, float] = {1: 100.0, 2: 75.0, 3: 40.0, 4: 10.0}

# Yağ genel durumu -> 0-100 puan.
OIL_SCORES: Dict[str, float] = {"iyi": 100.0, "kabul": 65.0, "kötü": 25.0}

# Skor bandı: (alt_sınır, kod, etiket, eylem)
BANDS = [
    (85.0, "excellent", "Çok İyi", "Rutin izlemeye devam."),
    (70.0, "good", "İyi", "Normal işletme; planlı bakım takviminde kalsın."),
    (50.0, "fair", "Orta", "Yakın izleme; numune sıklığını artır."),
    (30.0, "poor", "Kötü", "Detaylı saha incelemesi planla."),
    (0.0, "critical", "Kritik", "Acil değerlendirme; yenileme seçeneğini aç."),
]

# Bir boyut en kötü seviyesindeyse toplam skorun aşamayacağı tavan.
# 45 seçildi çünkü bu değer "Orta" bandının altına, "Kötü" bandına düşürür:
# tek başına kritik bir boyut, trafoyu en azından incelemeye sokmalıdır.
CRITICAL_CAP = 45.0

# Bir boyutu "en kötü" sayma eşikleri.
DGA_CRITICAL_CONDITION = 4        # IEEE kondisyon 4
PAPER_CRITICAL_CONSUMED = 90.0    # tüketilen ömür %90 üstü
OIL_CRITICAL = "kötü"

# Kapsama (coverage) yorumları: skor kaç boyutun verisine dayanıyor?
COVERAGE_LABELS = {
    "full": "Üç boyutun üçü de ölçülü.",
    "partial": "Bazı boyutlarda ölçüm yok; skor eksik veriye dayanıyor.",
    "none": "Hiçbir boyutta ölçüm yok; sağlık endeksi hesaplanamaz.",
}


def _band(score: float) -> Dict[str, str]:
    for lower, code, label, action in BANDS:
        if score >= lower:
            return {"band": code, "band_tr": label, "action": action}
    # BANDS'in son elemanı 0.0 olduğu için buraya normalde düşülmez.
    return {"band": "critical", "band_tr": "Kritik", "action": BANDS[-1][3]}


def _dga_dimension(risk_condition: Optional[int]) -> Dict[str, object]:
    """DGA kondisyonunu (1-4) 0-100 puana çevirir."""
    if risk_condition is None:
        return {"available": False, "reason": "DGA ölçümü yok"}
    cond = int(risk_condition)
    return {
        "available": True,
        "score": DGA_SCORES.get(cond, 10.0),
        "detail": f"IEEE kondisyon {cond}",
        "raw": cond,
        "is_critical": cond >= DGA_CRITICAL_CONDITION,
    }


def _paper_dimension(paper: Optional[Dict[str, object]]) -> Dict[str, object]:
    """Kağıt DP'sini 0-100 puana çevirir.

    Dönüşüm doğrudan: puan = 100 − tüketilen ömür yüzdesi. Yani DP 1100
    (yeni kağıt) 100 puan, DP 200 (ömür sonu) 0 puan. Ara bir ölçek
    uydurmaya gerek yok, ``oil_quality.estimate_dp`` zaten bu yüzdeyi
    üretiyor ve anlamı arayüzde birebir gösterilebiliyor.
    """
    if not paper or not paper.get("available"):
        return {"available": False, "reason": "furan ölçümü yok"}

    consumed = paper.get("life_consumed_pct")
    if consumed is None:
        return {"available": False, "reason": "tüketilen ömür hesaplanamadı"}

    consumed = float(consumed)
    score = max(0.0, min(100.0, 100.0 - consumed))

    warnings: List[str] = []
    # TUK uyarısı boyut seviyesine taşınıyor: skoru DÜZELTMİYORUZ (ne kadar
    # düzelteceğimizi bilmiyoruz), ama skorun iyimser olduğunu söylüyoruz.
    if paper.get("reliable") is False:
        warnings.append(
            "Kağıt puanı İYİMSER olabilir: TUK kağıtta Chendong bağıntısı "
            "DP'yi olduğundan yüksek gösterir.")

    return {
        "available": True,
        "score": round(score, 1),
        "detail": f"DP ≈ {paper.get('dp_estimate')} · "
                  f"tüketilen ömür %{consumed:g}",
        "raw": paper.get("dp_estimate"),
        "is_critical": consumed >= PAPER_CRITICAL_CONSUMED,
        "warnings": warnings,
    }


def _oil_dimension(oil_overall: Optional[str]) -> Dict[str, object]:
    """Yağ genel durumunu 0-100 puana çevirir."""
    if not oil_overall or oil_overall == "bilinmiyor":
        return {"available": False, "reason": "yağ kalitesi testi yok"}
    return {
        "available": True,
        "score": OIL_SCORES.get(oil_overall, 65.0),
        "detail": f"Genel durum: {oil_overall}",
        "raw": oil_overall,
        "is_critical": oil_overall == OIL_CRITICAL,
    }


def compute(risk_condition: Optional[int] = None,
            oil_overall: Optional[str] = None,
            paper: Optional[Dict[str, object]] = None,
            asset_class: Optional[str] = None,
            asset_weight: Optional[float] = None) -> Dict[str, object]:
    """Sağlık endeksini hesaplar.

    Saf fonksiyon: veritabanına da HTTP'ye de dokunmaz, bu yüzden doğrudan
    test edilebilir (``WorkOrderPlanner``'da da aynı tercih yapılmıştı).

    Dönen sözlükte skorun yanında **nasıl oluştuğu** da var: her boyutun
    puanı, ağırlığı ve katkısı. Formül arayüzde satır satır gösterilebilmeli
    — projedeki kural: kara kutu yok.
    """
    dims = {
        "dga": _dga_dimension(risk_condition),
        "paper": _paper_dimension(paper),
        "oil": _oil_dimension(oil_overall),
    }

    rows: List[Dict[str, object]] = []
    total_weight = 0.0
    weighted_sum = 0.0
    critical_dims: List[str] = []
    warnings: List[str] = []

    for key in DIMENSION_ORDER:
        spec = DIMENSIONS[key]
        d = dims[key]
        weight = float(spec["weight"])  # type: ignore[arg-type]
        row: Dict[str, object] = {
            "key": key,
            "label": spec["label"],
            "weight": weight,
            "source": spec["source"],
            "meaning": spec["meaning"],
            "available": bool(d.get("available")),
        }
        if d.get("available"):
            score = float(d["score"])  # type: ignore[arg-type]
            total_weight += weight
            weighted_sum += weight * score
            row.update({
                "score": round(score, 1),
                "detail": d.get("detail"),
                "raw": d.get("raw"),
                "contribution": round(weight * score, 1),
            })
            if d.get("is_critical"):
                critical_dims.append(str(spec["label"]))
            warnings.extend(list(d.get("warnings") or []))
        else:
            row["reason"] = d.get("reason")
        rows.append(row)

    measured = [r for r in rows if r["available"]]
    all_weight = sum(float(DIMENSIONS[k]["weight"]) for k in DIMENSION_ORDER)  # type: ignore[arg-type]

    if not measured:
        return {
            "available": False,
            "reason": "no_data",
            "message": "Bu trafo için ne DGA ne yağ testi var; sağlık "
                       "endeksi hesaplanamaz.",
            "dimensions": rows,
            "coverage": {"level": "none", "measured": 0,
                         "total": len(DIMENSION_ORDER),
                         "weight_ratio": 0.0,
                         "note": COVERAGE_LABELS["none"]},
        }

    raw_score = weighted_sum / total_weight

    capped = False
    score = raw_score
    if critical_dims and score > CRITICAL_CAP:
        score = CRITICAL_CAP
        capped = True

    # Tek bir sayı, hikâyeyi gizler. TR-09 örneği: DGA'sı sakin, yağı kabul
    # edilebilir, ama kağıdının %82'si tüketilmiş — ortalama "orta" çıkıyor
    # ve asıl sorun görünmüyor. Bu yüzden skoru en çok aşağı çeken boyut
    # ayrıca bildiriliyor; arayüz skorun yanında onu yazar.
    weakest = min(measured, key=lambda r: float(r["score"]))  # type: ignore[arg-type]

    coverage_level = "full" if len(measured) == len(DIMENSION_ORDER) else "partial"
    if coverage_level == "partial":
        warnings.append(
            "Skor eksik veriye dayanıyor: " +
            ", ".join(str(r["label"]) for r in rows if not r["available"]) +
            " ölçülmemiş. Eksik boyut 'sağlıklı' sayılmadı, ortalamadan "
            "çıkarıldı.")

    result: Dict[str, object] = {
        "available": True,
        "score": round(score, 1),
        "raw_score": round(raw_score, 1),
        "capped": capped,
        "cap": CRITICAL_CAP if capped else None,
        "critical_dimensions": critical_dims,
        "weakest": {"key": weakest["key"], "label": weakest["label"],
                    "score": weakest["score"], "detail": weakest.get("detail")},
        "dimensions": rows,
        "formula": "Σ(ağırlık × puan) ÷ Σ(ağırlık)",
        "weight_sum": round(total_weight, 1),
        "weighted_sum": round(weighted_sum, 1),
        "coverage": {
            "level": coverage_level,
            "measured": len(measured),
            "total": len(DIMENSION_ORDER),
            "weight_ratio": round(total_weight / all_weight, 2),
            "note": COVERAGE_LABELS[coverage_level],
        },
        "warnings": warnings,
    }
    result.update(_band(score))

    # Varlık ağırlığıyla birleşik "yenileme önceliği". Filo sıralamasındaki
    # `priority` ACİLİYETİ ölçer (DGA kondisyonu × varlık ağırlığı); bu ise
    # DURUMU ölçer. İkisi farklı sorulara cevap verir: "bugün kime koşayım"
    # ile "bu yıl hangi ünitenin bütçesini ayırayım" aynı şey değildir.
    if asset_weight is not None or asset_class is not None:
        w = asset_weight
        if w is None:
            from . import assets as _assets       # döngüsel import olmasın
            w = _assets.weight(asset_class)
        result["renewal_priority"] = round((100.0 - score) / 100.0 * float(w), 3)
        result["asset_weight"] = float(w)

    return result


def fleet_stats(scores: List[Optional[float]]) -> Dict[str, object]:
    """Filo geneli sağlık özeti: ortalama ve bant dağılımı.

    ``None`` girdiler (endeksi hesaplanamayan trafolar) ortalamaya
    katılmaz ama ``unknown`` olarak sayılır — filoda kaç varlığın durumunu
    bilmediğimiz, ortalamanın kendisi kadar önemlidir.
    """
    known = [float(s) for s in scores if s is not None]
    distribution = {code: 0 for _, code, _, _ in BANDS}
    for s in known:
        distribution[_band(s)["band"]] += 1

    return {
        "scored": len(known),
        "unknown": len(scores) - len(known),
        "average": round(sum(known) / len(known), 1) if known else None,
        "worst": round(min(known), 1) if known else None,
        "band_distribution": distribution,
    }
