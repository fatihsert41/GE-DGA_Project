"""Filo geneli özet (Faz 5.2).

database.latest_measurements() satırlarını dashboard'un beklediği iki
parçaya dönüştürür:
  * transformers - trafo başına tek kart verisi (son tanı + risk)
  * summary      - filo geneli sayımlar (risk ve arıza dağılımı)

Burada yeniden tahmin YAPILMAZ: tanı, ölçüm kaydedilirken zaten
services/diagnosis.py tarafından üretilip DB'ye yazılmıştır.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List, Optional

from .. import database
from ..core import assets, health_index, lifecycle, nameplate
from ..core.gases import (FAULT_FAMILY, FAULT_GROUP, FAULT_LABELS_TR,
                          SEVERE_FAULTS, total_combustible)
from ..core.risk import RISK_LEVELS_TR, RISK_ORDER
from . import electrical as electrical_service
from . import oil as oil_service
from . import components as component_service
from . import physical as physical_service
from .diagnosis import CONFIDENCE_THRESHOLD


def _days_since(iso: Optional[str]) -> Optional[int]:
    """Son ölçümün üstünden kaç gün geçti? Bozuk tarihte None döner."""
    if not iso:
        return None
    try:
        ts = datetime.fromisoformat(iso)
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return max(0, (datetime.now(timezone.utc) - ts).days)


def _to_card(row: Dict) -> Dict:
    """Tek bir DB satırını frontend'in göstereceği 'kart' sözlüğüne çevir."""
    gases = row.get("gases")
    has_data = gases is not None          # ölçümü olmayan trafo (LEFT JOIN)
    pred = row.get("prediction")
    level = row.get("risk_level")

    cls = assets.get(row.get("asset_class"))
    condition = row.get("risk_condition")
    days = _days_since(row.get("sampled_at"))
    # Numune aralığı sınıfa göre değişir: LPT 6 ay, MPT 12, SPT 24.
    interval_days = int(cls["sampling_months"]) * 30

    # Yaşam döngüsü durumu (Faz 9.35) — numune kuralından ÖNCE gelir.
    life = lifecycle.summary(row.get("lifecycle_status"))

    # DÖRT DURUM. Önceden üç vardı ve hepsi varlığın nerede olduğunu
    # görmezden geliyordu.
    #
    # ⚠ YAŞANAN HATA: fabrikada sevkiyat bekleyen bir ünite "hiç numune
    # alınmamış" sayılıp numune alma iş emri üretiyordu. Henüz
    # enerjilenmemiş, yağında gaz üretmesi fiziksel olarak mümkün
    # olmayan bir trafo için. Kural yanlış değildi; kurala verilen
    # varlık kümesi yanlıştı.
    #
    # Kural tek bir soru soruyor: bu varlık İZLENİYOR mu? Durumların
    # tek tek sayılmaması bilinçli — yeni bir durum eklendiğinde
    # buraya dokunmak gerekmesin diye (bkz. core/lifecycle.py).
    if not life["monitored"]:
        sampling_status = "not_monitored"
    elif days is None:
        sampling_status = "never_sampled"
    elif days > interval_days:
        sampling_status = "overdue"
    else:
        sampling_status = "current"

    return {
        "asset_class": cls["code"],
        "asset_class_name": cls["name_tr"],
        "asset_class_active": cls["active"],
        "mva": row.get("mva"),
        # Künye özeti (Faz 8.1). Tam künye /transformers/{id} adresinde;
        # kartta yalnızca bir bakışta gereken alanlar var.
        "manufacturer": row.get("manufacturer"),
        "voltage": (f"{row['hv_kv']:g}/{row['lv_kv']:g} kV"
                    if row.get("hv_kv") and row.get("lv_kv") else None),
        "cooling": row.get("cooling"),
        "age_years": nameplate.age_years({
            "commissioned_at": row.get("commissioned_at"),
            "year_made": row.get("year_made"),
        }),
        # Öncelik = IEEE kondisyonu × varlık ağırlığı. Açıklanabilir olsun
        # diye bileşenleri de gönderiliyor; arayüz formülü gösterebiliyor.
        "lifecycle": life,
        "lifecycle_status": life["code"],
        # Bakım servisinin (.NET) okuduğu DÜZ alanlar. İç içe nesneyi
        # ayrıştırmak yerine düz alan taşımak, servisler arası sınırda
        # daha dayanıklı: karşı taraf iç yapıyı bilmek zorunda kalmıyor.
        "lifecycle_phase": life["phase"],
        "lifecycle_monitored": life["monitored"],
        "lifecycle_changed_at": row.get("lifecycle_changed_at"),
        "priority": assets.priority_score(condition, cls["code"]),
        "asset_weight": cls["weight"],
        "sampling_months": cls["sampling_months"],
        "days_since_sample": days,
        "sampling_status": sampling_status,
        # never_sampled da bir gecikmedir: temel çizgi numunesi alınmamış.
        "sampling_overdue": sampling_status in ("overdue", "never_sampled"),
        "id": row["transformer_id"],
        "name": row["transformer_name"],
        "location": row["location"],
        "measurement_count": row["measurement_count"],
        "has_data": has_data,
        "last_sampled_at": row.get("sampled_at"),
        "prediction": pred,
        "prediction_label": FAULT_LABELS_TR.get(pred) if pred else None,
        "prediction_group": FAULT_GROUP.get(pred) if pred else None,
        "prediction_family": FAULT_FAMILY.get(pred) if pred else None,
        "confidence": row.get("confidence"),
        # Ölçüm kaydedilirken saklanan güvenden yeniden hesaplanır; eşik
        # değişirse eski kayıtlar da yeni eşiğe göre değerlendirilir.
        "needs_review": bool(has_data and (row.get("confidence") or 0.0)
                             < CONFIDENCE_THRESHOLD),
        "severe": bool(pred in SEVERE_FAULTS),
        "risk_level": level,
        "risk_level_tr": RISK_LEVELS_TR.get(level) if level else None,
        "risk_condition": row.get("risk_condition"),
        "tdcg": round(total_combustible(gases), 1) if has_data else None,
        "gases": gases,
    }


def _severity_key(card: Dict) -> tuple:
    """Sıralama: önce ÖNCELİK, sonra ham risk, sonra id.

    Ham riske göre sıralamak yanıltıcıdır: kritik durumdaki küçük bir ünite,
    ciddi arıza geliştiren bir LPT'nin önüne geçerdi. Öncelik skoru sonucu
    da hesaba katar. Eşitlikte id devreye girer, böylece sıra deterministik
    kalır ve kartlar her istekte aynı yerde durur.
    """
    return (-card.get("priority", 0.0),
            -RISK_ORDER.get(card["risk_level"], 0),
            card["id"])


def _lifecycle_distribution(cards: List[Dict]) -> Dict[str, int]:
    """Yaşam döngüsü durumlarına göre sayım (yalnızca dolu olanlar)."""
    counts: Dict[str, int] = {}
    for c in cards:
        code = c.get("lifecycle_status") or lifecycle.DEFAULT_STATE
        counts[code] = counts.get(code, 0) + 1
    return counts


def build_overview(rows: List[Dict],
                   oil_tests: Optional[Dict[str, Dict]] = None,
                   electrical_tests: Optional[Dict[str, Dict]] = None,
                   inspections: Optional[Dict[str, Dict]] = None,
                   component_tests: Optional[Dict[str, Dict]] = None) -> Dict:
    """Saf hesaplama: DB satırlarını özet + kart listesine çevirir.

    Veritabanına dokunmaz, bu yüzden sahte satırlarla test edilebilir.
    """
    oil_tests = oil_tests or {}
    electrical_tests = electrical_tests or {}
    inspections = inspections or {}
    component_tests = component_tests or {}
    cards: List[Dict] = []
    for r in rows:
        card = _to_card(r)
        # Yağ özeti karta eklenir; testi olmayan trafo için güvenli boş değer.
        card.update(oil_service.oil_card(card["id"],
                                         oil_tests.get(card["id"])))
        # Elektriksel test özeti (Faz 8.6). Çoğu trafoda YOKTUR ve bu
        # normaldir: testler enerjisizken yapılır.
        card.update(electrical_service.electrical_card(
            card["id"], electrical_tests.get(card["id"])))
        # Fiziksel gözlem özeti (Faz 9.5).
        card.update(physical_service.physical_card(
            inspections.get(card["id"])))
        # Buşing ve kademe değiştirici (Faz 9.4).
        card.update(component_service.component_card(
            card["id"], component_tests.get(card["id"])))
        # Sağlık endeksi (Faz 8.5/8.6): dört boyutu tek skorda birleştirir.
        # `priority` ACİLİYETİ ölçer (bugün kime koşayım), `health` DURUMU
        # (bu varlık genel olarak ne hâlde) — ikisi farklı sorulardır.
        card["health"] = health_index.compute(
            risk_condition=card.get("risk_condition"),
            oil_overall=card.get("oil_overall"),
            paper=card.pop("paper", None),
            electrical_overall=card.get("electrical_overall"),
            physical_overall=card.get("physical_overall"),
            component_overall=card.get("component_overall"),
            asset_weight=card.get("asset_weight"),
        )
        card["health_score"] = card["health"].get("score")
        card["health_band"] = card["health"].get("band")
        cards.append(card)
    cards.sort(key=_severity_key)

    measured = [c for c in cards if c["has_data"]]

    # Dağılımları SIFIRLA başlat: grafikte hiç 'critical' yoksa bile
    # anahtar var olsun ki frontend'in eksenleri/renkleri kaymasın.
    risk_distribution: Dict[str, int] = {lvl: 0 for lvl in RISK_LEVELS_TR}
    fault_distribution: Dict[str, int] = {}
    # Sınıf dağılımı ölçümsüz trafoları da sayar: filo envanteri tanıya
    # bağlı değildir.
    class_distribution: Dict[str, int] = {c: 0 for c in assets.CLASS_ORDER}
    for c in cards:
        class_distribution[c["asset_class"]] = (
            class_distribution.get(c["asset_class"], 0) + 1)
    for c in measured:
        risk_distribution[c["risk_level"]] += 1
        fault_distribution[c["prediction"]] = (
            fault_distribution.get(c["prediction"], 0) + 1
        )

    needs_attention = [c for c in measured
                       if c["risk_level"] in ("high", "critical")]

    return {
        "summary": {
            "total": len(cards),
            "with_data": len(measured),
            "total_measurements": sum(c["measurement_count"] for c in cards),
            "risk_distribution": risk_distribution,
            "fault_distribution": fault_distribution,
            "needs_attention": len(needs_attention),
            "attention_ids": [c["id"] for c in needs_attention],
            "needs_review": sum(1 for c in measured if c["needs_review"]),
            "class_distribution": class_distribution,
            "sampling_overdue": sum(1 for c in cards if c["sampling_overdue"]),
            "never_sampled": sum(1 for c in cards
                                 if c["sampling_status"] == "never_sampled"),
            # İzlenmeyen varlıklar (fabrikada, yolda, yedek, hizmet dışı)
            # ayrıca sayılır: filoda kaç ünitenin henüz işletmede
            # olmadığı, yönetim için ayrı bir bilgidir.
            "not_monitored": sum(1 for c in cards
                                 if c["sampling_status"] == "not_monitored"),
            "lifecycle_distribution": _lifecycle_distribution(cards),
            # Sağlık endeksi filo özeti. Ortalamanın yanında `unknown`
            # da veriliyor: kaç varlığın durumunu BİLMEDİĞİMİZ, ortalama
            # kadar önemli bir yönetim bilgisidir.
            "health": health_index.fleet_stats(
                [c["health_score"] for c in cards]),
        },
        "transformers": cards,
    }


def overview() -> Dict:
    """I/O katmanı: satırları DB'den çeker, hesabı build_overview'a bırakır."""
    return build_overview(database.latest_measurements(),
                          database.latest_oil_tests(),
                          database.latest_electrical_tests(),
                          database.latest_physical_inspections(),
                          database.latest_component_tests())
