"""Veritabanını demo bir trafo filosuyla doldurur.

Dış veri yok: her trafonun geçmişini sentetik "yaşlanma serisi"
üretecinden oluşturur, her örneğe tam tanıyı (ML + klasik + risk)
uygular ve SQLite'a kaydeder.

⚠ Buradaki künye bilgileri (üretici, seri no, tarih) TAMAMEN KURGUSALDIR.
Gerçek hiçbir trafoya ait değildir; yalnızca alanların nasıl doldurulacağını
ve hesapların nasıl çalıştığını göstermek için üretilmiştir. Gerilim
seviyeleri Türkiye şebekesine uygun seçilmiştir (400/154/34.5/6.3 kV).

Çalıştırma (backend/ klasöründen):  python -m app.ml.seed
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from .. import database
from ..core import assets, nameplate
from ..core.gases import GASES
from ..services.diagnosis import diagnose
from .synth import make_aging_series
from .synth_electrical import make_electrical_test
from .synth_oil import make_oil_test

# Demo filosu. Sözlük kullanılıyor çünkü alan sayısı arttıkça konumsal
# tuple okunmaz hale geliyordu ("bu 12 neydi?"). Sözlükte her değer
# anahtarıyla birlikte duruyor.
#
# Senaryo alanları:
#   scenario : hangi arızaya doğru kötüleşiyor ("Normal" = sağlıklı kalıyor)
#   months   : üretilecek ölçüm sayısı
#   keep     : serinin yalnızca ilk N ayını sakla (erken evre trafosu)
#   lag      : tüm seriyi N ay geçmişe kaydır (numunesi gecikmiş trafo)
FLEET = [
    {
        "id": "TR-01", "name": "Ana Merkez Trafosu",
        "location": "İstanbul-Avrupa", "asset_class": "LPT", "mva": 250.0,
        "scenario": "D2", "months": 12,
        "nameplate": {
            "manufacturer": "GE Vernova", "serial_no": "GV-250-0842",
            "year_made": 2008, "commissioned_at": "2009-04-17",
            "hv_kv": 400.0, "lv_kv": 154.0, "vector_group": "YNyn0",
            "cooling": "OFAF", "oil_volume_l": 65000.0,
            "winding_material": "Cu", "insulation_type": "tuk",
            "tap_changer_type": "OLTC", "tap_min": -8, "tap_max": 8,
            "tap_step_percent": 1.25,
            "notes": "Şebeke bağlantı noktası; yedeği yok.",
        },
    },
    {
        "id": "TR-02", "name": "Yük Merkezi 2",
        "location": "İstanbul-Anadolu", "asset_class": "LPT", "mva": 150.0,
        "scenario": "Normal", "months": 12,
        "nameplate": {
            "manufacturer": "Siemens Energy", "serial_no": "SE-150-3311",
            "year_made": 2015, "commissioned_at": "2015-11-02",
            "hv_kv": 154.0, "lv_kv": 34.5, "vector_group": "YNd11",
            "cooling": "ONAF", "oil_volume_l": 42000.0,
            "winding_material": "Cu", "insulation_type": "tuk",
            "tap_changer_type": "OLTC", "tap_min": -9, "tap_max": 9,
            "tap_step_percent": 1.25,
        },
    },
    {
        "id": "TR-03", "name": "OSB Besleme", "location": "Kocaeli",
        "asset_class": "LPT", "mva": 180.0, "scenario": "T3", "months": 10,
        "nameplate": {
            "manufacturer": "BEST A.Ş.", "serial_no": "BST-180-1074",
            "year_made": 2012, "commissioned_at": "2012-08-30",
            "hv_kv": 154.0, "lv_kv": 34.5, "vector_group": "YNd11",
            "cooling": "OFAF", "oil_volume_l": 48000.0,
            "winding_material": "Cu", "insulation_type": "tuk",
            "tap_changer_type": "OLTC", "tap_min": -9, "tap_max": 9,
            "tap_step_percent": 1.25,
            "notes": "Organize sanayi bölgesi, yüksek ve değişken yük.",
        },
    },
    {
        "id": "TR-04", "name": "Şehir Dağıtım", "location": "Bursa",
        "asset_class": "MPT", "mva": 50.0, "scenario": "T1", "months": 12,
        "nameplate": {
            "manufacturer": "BEST A.Ş.", "serial_no": "BST-050-0619",
            "year_made": 2006, "commissioned_at": "2006-06-12",
            "hv_kv": 154.0, "lv_kv": 34.5, "vector_group": "YNd11",
            "cooling": "ONAF", "oil_volume_l": 22000.0,
            "winding_material": "Cu", "insulation_type": "kraft",
            "tap_changer_type": "OLTC", "tap_min": -8, "tap_max": 8,
            "tap_step_percent": 1.25,
        },
    },
    {
        "id": "TR-05", "name": "Sahil GIS", "location": "İzmir",
        "asset_class": "MPT", "mva": 80.0, "scenario": "Normal", "months": 12,
        "nameplate": {
            "manufacturer": "Hitachi Energy", "serial_no": "HE-080-7725",
            "year_made": 2018, "commissioned_at": "2019-01-21",
            "hv_kv": 154.0, "lv_kv": 34.5, "vector_group": "YNd11",
            "cooling": "ONAF", "oil_volume_l": 28000.0,
            "winding_material": "Cu", "insulation_type": "tuk",
            "tap_changer_type": "OLTC", "tap_min": -9, "tap_max": 9,
            "tap_step_percent": 1.25,
            "notes": "Deniz kenarı; tuzlu nem etkisi izlenmeli.",
        },
    },
    {
        "id": "TR-06", "name": "Demiryolu Besleme", "location": "Ankara",
        "asset_class": "MPT", "mva": 25.0, "scenario": "PD", "months": 8,
        "lag": 14,
        "nameplate": {
            "manufacturer": "BEST A.Ş.", "serial_no": "BST-025-0288",
            "year_made": 2003, "commissioned_at": "2003-09-08",
            "hv_kv": 154.0, "lv_kv": 34.5, "vector_group": "YNd11",
            "cooling": "ONAN", "oil_volume_l": 14000.0,
            "winding_material": "Al", "insulation_type": "kraft",
            "tap_changer_type": "DETC", "tap_min": -2, "tap_max": 2,
            "tap_step_percent": 2.5,
            "notes": "Darbeli yük profili.",
        },
    },
    {
        "id": "TR-07", "name": "Sanayi Fider", "location": "Gebze",
        "asset_class": "MPT", "mva": 40.0, "scenario": "D1", "months": 11,
        "nameplate": {
            "manufacturer": "ABB", "serial_no": "AB-040-4460",
            "year_made": 1998, "commissioned_at": "1998-10-05",
            "hv_kv": 154.0, "lv_kv": 34.5, "vector_group": "YNd11",
            "cooling": "ONAN", "oil_volume_l": 18000.0,
            "winding_material": "Cu", "insulation_type": "kraft",
            "tap_changer_type": "OLTC", "tap_min": -8, "tap_max": 8,
            "tap_step_percent": 1.25,
            "notes": "Filonun en eski ünitelerinden.",
        },
    },
    {
        "id": "TR-08", "name": "Rüzgar Bağlantı", "location": "Çanakkale",
        "asset_class": "LPT", "mva": 120.0, "scenario": "T2", "months": 12,
        "nameplate": {
            "manufacturer": "GE Vernova", "serial_no": "GV-120-9013",
            "year_made": 2020, "commissioned_at": "2020-07-14",
            "hv_kv": 154.0, "lv_kv": 34.5, "vector_group": "YNd11",
            "cooling": "ONAF", "oil_volume_l": 38000.0,
            "winding_material": "Cu", "insulation_type": "tuk",
            "tap_changer_type": "OLTC", "tap_min": -9, "tap_max": 9,
            "tap_step_percent": 1.25,
            "notes": "RES bağlantısı; değişken üretim, sık yük değişimi.",
        },
    },
    {
        "id": "TR-09", "name": "Liman Besleme", "location": "Mersin",
        "asset_class": "SPT", "mva": 8.0, "scenario": "D1", "months": 12,
        "keep": 5, "lag": 26,
        "nameplate": {
            "manufacturer": "BEST A.Ş.", "serial_no": "BST-008-0132",
            "year_made": 1996, "commissioned_at": "1996-05-19",
            "hv_kv": 34.5, "lv_kv": 6.3, "vector_group": "Dyn11",
            "cooling": "ONAN", "oil_volume_l": 6500.0,
            "winding_material": "Al", "insulation_type": "kraft",
            "tap_changer_type": "DETC", "tap_min": -2, "tap_max": 2,
            "tap_step_percent": 2.5,
            "notes": "SPT hattı üretimden kalktı; yedek parça temini zor.",
        },
    },
    {
        # Faz 9.35 — HENÜZ SAHAYA GİTMEMİŞ ÜNİTE.
        #
        # Bu kayıt bir hatayı kanıtlamak için var: yaşam döngüsü
        # modellenmeden önce, fabrikada bekleyen böyle bir ünite
        # "hiç numune alınmamış" sayılıp numune alma iş emri
        # üretiyordu. Henüz enerjilenmemiş, yağında gaz üretmesi
        # fiziksel olarak mümkün olmayan bir trafo için.
        #
        # Ölçümü YOK ve olmamalı (months: 0).
        "id": "TR-10", "name": "Yeni Ünite — Sipariş 4471",
        "location": "Fabrika / Gebze", "asset_class": "LPT", "mva": 200.0,
        "scenario": "Normal", "months": 0,
        "lifecycle": "awaiting_transport",
        "lifecycle_note": "Fabrika testleri tamam; ağır nakliye ve vinç "
                          "planlaması bekleniyor.",
        "nameplate": {
            "manufacturer": "GE Vernova", "serial_no": "GV-200-1188",
            "year_made": 2026,
            "hv_kv": 154.0, "lv_kv": 34.5, "vector_group": "YNd11",
            "cooling": "OFAF", "oil_volume_l": 52000.0,
            "winding_material": "Cu", "insulation_type": "tuk",
            "tap_changer_type": "OLTC", "tap_min": -9, "tap_max": 9,
            "tap_step_percent": 1.25,
            "notes": "Müşteri teslimi bekleniyor; sahaya henüz sevk edilmedi.",
        },
    },
]


# Elektriksel test senaryoları (Faz 8.6). Rastgele DEĞİL, elle seçildi:
# her biri sistemin bir yeteneğini kanıtlıyor. Çoğunluk sağlıklı olmalı,
# yoksa demo inandırıcılığını yitirir.
#
# En önemli üçü:
#   TR-04  DGA "T1" (düşük sıcaklıkta ısınma) diyor, sargı direnci kademe
#          kontağında aşınma gösteriyor → İKİ BAĞIMSIZ KAYNAK AYNI ŞEYİ
#          SÖYLÜYOR. Tek kaynağın iki kez söylemesinden çok daha değerli.
#   TR-05  Yağı temiz, DGA'sı sakin, ama TTR'de tek fazda spir kaybı →
#          YAĞIN GÖREMEDİĞİ ARIZA. Bu fazın var oluş sebebi.
#   TR-02  Yalıtımı çok kuru; PI düşük görünüyor ama bu arıza DEĞİL.
#          Sistem bunu bilmeli, yoksa en sağlam trafoyu suçlar.
ELECTRICAL_SCENARIOS = {
    "TR-01": "healthy",
    "TR-02": "very_dry",           # tuzak: düşük PI ama arıza yok
    "TR-03": "healthy",
    "TR-04": "tap_wear",           # DGA'daki T1 ile örtüşür
    "TR-05": "shorted_turn",       # yağın göremediği arıza
    "TR-06": "wet_insulation",     # 2003 yapımı, kraft, darbeli yük
    "TR-07": "aged_insulation",    # filonun en eskisi (1998)
    "TR-08": "healthy",
    # TR-09 kasten YOK: hiç elektriksel testi olmayan varlık senaryosu.
    # Elektriksel test seyrek yapılır; "veri yok" istisna değil KURALDIR.
}


def _reset() -> None:
    """Tabloları oluştur ve eski demo kayıtları temizle (temiz başlangıç)."""
    database.init_db()
    with sqlite3.connect(database.DB_PATH) as conn:
        conn.execute("DELETE FROM lifecycle_events")
        conn.execute("DELETE FROM electrical_tests")
        conn.execute("DELETE FROM oil_tests")
        conn.execute("DELETE FROM measurements")
        conn.execute("DELETE FROM transformers")


def seed() -> None:
    _reset()
    total = 0

    for idx, unit in enumerate(FLEET):
        np_fields = unit.get("nameplate", {})
        database.upsert_transformer(
            unit["id"], unit["name"], unit["location"],
            asset_class=unit["asset_class"], mva=unit["mva"],
            **np_fields,
        )

        # Yaşam döngüsü durumu (Faz 9.35). Varsayılan "devrede".
        life = unit.get("lifecycle")
        if life and life != "in_service":
            database.set_lifecycle(
                unit["id"], life, unit.get("lifecycle_note"),
                changed_by={"employee_no": "10502", "name": "Demo Kurulum"})

        scenario = unit["scenario"]
        months = unit["months"]

        # Ölçümü olmayan varlık: fabrikada bekleyen ünite gibi.
        if months == 0:
            print(f"  {unit['id']} {unit['name']:<22} {unit['asset_class']} "
                  f"{unit['mva']:>6.0f}MVA  "
                  f"durum={life}  (olcum yok — henuz isletmede degil)")
            continue
        keep = unit.get("keep")
        lag = unit.get("lag", 0)

        # Bu trafonun aylık gaz geçmişini üret (senaryosuna doğru kötüleşir).
        df = make_aging_series(fault_class=scenario, months=months,
                               seed=idx + 1)
        if keep is not None:
            df = df.head(keep)      # erken evre: seriyi baştan kes
            months = keep

        # İlk ölçüm 'months' ay önce, sonuncusu bugün olacak şekilde tarihle.
        # 'lag' varsa tüm seri o kadar ay daha geriye kayar.
        start = datetime.now(timezone.utc) - timedelta(
            days=30 * (months - 1 + lag))

        for k, (_, row) in enumerate(df.iterrows()):
            gases = {g: float(row[g]) for g in GASES}
            result = diagnose(gases)               # ML + klasik + risk
            sampled_at = (start + timedelta(days=30 * k)).isoformat()
            database.save_measurement(unit["id"], gases, result,
                                      sampled_at=sampled_at)
            total += 1

        last = diagnose({g: float(df.iloc[-1][g]) for g in GASES})
        record = database.get_transformer(unit["id"]) or {}
        age = (record.get("derived") or {}).get("age_years")

        # --- Yağ kalitesi testleri (Faz 8.3) --------------------------
        # DGA'dan daha SEYREK alınır: laboratuvar testi pahalıdır ve
        # kağıt bozunması yavaş bir süreçtir. Yılda bir makul.
        np_fields = unit.get("nameplate", {})
        n_oil = max(1, min(4, int((age or 5) // 6)))
        for k in range(n_oil):
            # Geçmişe doğru: en eski test en düşük yaşta alınmış.
            years_ago = (n_oil - 1 - k) * 3
            test_age = max(0.5, (age or 5) - years_ago)
            values = make_oil_test(
                age_years=test_age,
                fault_class=scenario,
                insulation_type=str(np_fields.get("insulation_type", "kraft")),
                hv_kv=np_fields.get("hv_kv"),
                seed=idx * 100 + k,
            )
            sampled = (datetime.now(timezone.utc)
                       - timedelta(days=int(years_ago * 365.25)))
            database.save_oil_test(unit["id"], values,
                                   sampled_at=sampled.isoformat(),
                                   lab="Demo Laboratuvarı")

        # --- Elektriksel testler (Faz 8.6) ----------------------------
        # DGA'dan ÇOK daha seyrek: trafo enerjisizken yapılır, yani
        # planlı kesinti gerektirir. Tipik olarak devreye alma + büyük
        # bakım. Demo filoda son bir test yeterli.
        scenario_el = ELECTRICAL_SCENARIOS.get(unit["id"])
        if scenario_el:
            expected = nameplate.rated_turns_ratio(np_fields)
            if expected:
                values = make_electrical_test(
                    expected_ratio=expected,
                    scenario=scenario_el,
                    age_years=float(age or 10),
                    base_resistance_ohm=0.35 + 0.004 * float(unit["mva"]),
                    seed=idx * 200 + 7,
                )
                values["tap_position"] = 0
                tested = (datetime.now(timezone.utc)
                          - timedelta(days=int(180 + idx * 90)))
                database.save_electrical_test(
                    unit["id"], values, tested_at=tested.isoformat(),
                    tested_by="Demo Saha Ekibi")

        flag = " ⚠ uzman incelemesi" if last["review"]["needed"] else ""
        gecikme = f" ⏰ {lag} ay geçti" if lag else ""
        oncelik = assets.priority_score(last["risk"]["condition"],
                                        unit["asset_class"])
        print(f"  {unit['id']} {unit['name']:<22} {unit['asset_class']} "
              f"{unit['mva']:>6.0f}MVA {str(age):>5} yaş  "
              f"tanı={last['prediction']:<6} "
              f"risk={last['risk']['level_tr']:<7} "
              f"öncelik={oncelik:>4.2f}{flag}{gecikme}")

    from ..services import oil as oil_service
    fleet_oil = oil_service.fleet_summary()

    print("")
    print(f"Toplam {len(FLEET)} trafo, {total} DGA olcumu kaydedildi.")
    print(f"Yag kalitesi: {fleet_oil['tested']} trafo test edildi, "
          f"durum dagilimi {dict(fleet_oil['condition_counts'])}")
    from ..services import electrical as el_service
    fleet_el = el_service.fleet_summary()
    print(f"Elektriksel test: {fleet_el['tested']} trafo test edildi, "
          f"durum dagilimi {dict(fleet_el['condition_counts'])}")
    for r in fleet_el["items"]:
        if r["overall"] != "iyi":
            print(f"  {r['transformer_id']}  {r['overall']}: "
                  f"{'; '.join(r['problems'])}")
    if fleet_el["never_tested"]:
        print(f"  hic test edilmemis: {', '.join(fleet_el['never_tested'])}")

    print("En yasli kagitlar:")
    for r in fleet_oil["most_aged_paper"]:
        print(f"  {r['transformer_id']}  DP={r['dp_estimate']}  "
              f"({r['paper_band']}, omrunun "
              f"%{r['life_consumed_pct']:.0f}'i tuketilmis)")


if __name__ == "__main__":
    seed()
