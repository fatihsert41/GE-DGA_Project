"""Lightweight SQLite persistence (no ORM needed for a demo).

Two tables:
* transformers  - one row per monitored asset.
* measurements  - one row per oil sample: the seven gases, the diagnosis
                  that was produced, risk level and a timestamp.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from .core import assets, nameplate
from .core.gases import GASES

# Künye sütunları: (ad, SQLite tipi). Tek yerde tutuluyor ki tablo
# oluşturma, göç ve okuma hep aynı listeye baksın.
NAMEPLATE_COLUMNS = [
    ("manufacturer", "TEXT"),
    ("serial_no", "TEXT"),
    ("year_made", "INTEGER"),
    ("commissioned_at", "TEXT"),
    ("hv_kv", "REAL"),
    ("lv_kv", "REAL"),
    ("vector_group", "TEXT"),
    ("cooling", "TEXT"),
    ("oil_volume_l", "REAL"),
    ("winding_material", "TEXT"),
    ("insulation_type", "TEXT"),
    ("tap_changer_type", "TEXT"),
    ("tap_min", "INTEGER"),
    ("tap_max", "INTEGER"),
    ("tap_step_percent", "REAL"),
    ("rated_hotspot_c", "REAL"),
    ("rated_top_oil_c", "REAL"),
    ("notes", "TEXT"),
]
NAMEPLATE_FIELDS = [name for name, _ in NAMEPLATE_COLUMNS]

# Varsayılan: backend/dga.db (yerel çalışma). Docker'da veritabanı imajın
# içinde değil kalıcı birimde durmalı; TRANSFORMERAI_DB_PATH ile verilir
# (backend/Dockerfile: /data/dga.db).
DB_PATH = Path(os.environ.get("TRANSFORMERAI_DB_PATH")
               or Path(__file__).resolve().parents[1] / "dga.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transformers (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                location    TEXT,
                asset_class TEXT NOT NULL DEFAULT 'MPT',
                mva         REAL,
                created_at  TEXT NOT NULL
            )
            """
        )
        # Şemayı önceki sürümden kalan veritabanlarına da taşı.
        _ensure_column(conn, "transformers", "asset_class",
                       "TEXT NOT NULL DEFAULT 'MPT'")
        _ensure_column(conn, "transformers", "mva", "REAL")
        # Künye alanları (Faz 8.1). Hepsi opsiyonel: eski kayıtlar
        # bozulmadan yaşamaya devam eder, künye sonradan doldurulabilir.
        for col, coltype in NAMEPLATE_COLUMNS:
            _ensure_column(conn, "transformers", col, coltype)

        _init_oil_tests(conn)
        _init_electrical_tests(conn)
        # Geçersiz işaretleme sütunları (Faz 8.6). Hatalı bir ölçüm
        # SİLİNMEZ, geçersiz işaretlenir: denetim izi korunur, ama kayıt
        # hüküm üretmez. Endüstride yapılan da budur — bir test raporu
        # yanlış çıktığında rapor imha edilmez, "void" damgası vurulur.
        for table in ("oil_tests", "electrical_tests"):
            _ensure_column(conn, table, "voided_at", "TEXT")
            _ensure_column(conn, table, "void_reason", "TEXT")

        _normalize_existing_timestamps(conn)
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS measurements (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                transformer_id TEXT NOT NULL,
                sampled_at     TEXT NOT NULL,
                gases_json     TEXT NOT NULL,
                prediction     TEXT,
                confidence     REAL,
                risk_level     TEXT,
                risk_condition INTEGER,
                FOREIGN KEY (transformer_id) REFERENCES transformers(id)
            )
            """
        )

        # Bileşen testleri: buşing + kademe değiştirici (Faz 9.4).
        # Sütun tercih edildi (JSON değil): değerler SAYISAL ve zamanla
        # karşılaştırılıyor — kapasitans sapmasının seyri, işletme
        # sayacının artışı. Fiziksel gözlemde JSON seçilmişti çünkü orada
        # değerler kategorik ve bütün olarak okunuyor.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS component_tests (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                transformer_id TEXT NOT NULL,
                tested_at      TEXT NOT NULL,
                bushing_a_pf_pct        REAL,
                bushing_a_cap_pf        REAL,
                bushing_a_cap_rated_pf  REAL,
                bushing_b_pf_pct        REAL,
                bushing_b_cap_pf        REAL,
                bushing_b_cap_rated_pf  REAL,
                bushing_c_pf_pct        REAL,
                bushing_c_cap_pf        REAL,
                bushing_c_cap_rated_pf  REAL,
                oltc_operations             INTEGER,
                oltc_ops_since_overhaul     INTEGER,
                oltc_years_since_overhaul   REAL,
                oltc_oil_bdv_kv             REAL,
                notes          TEXT,
                created_at     TEXT NOT NULL,
                recorded_by_id   TEXT,
                recorded_by_name TEXT,
                FOREIGN KEY (transformer_id) REFERENCES transformers(id)
            )
            """
        )
        conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_component_transformer
               ON component_tests(transformer_id, tested_at DESC)"""
        )

        # Fiziksel gözlem turları (Faz 9.5). Maddeler JSON olarak
        # saklanıyor: liste zamanla değişebilir ve her madde için ayrı
        # sütun açmak şemayı kırılgan yapardı. Yağ/elektriksel testlerde
        # sütun tercih edildi çünkü orada alanlar SAYISAL ve sorgulanıyor;
        # burada değerler kategorik ve bütün olarak okunuyor.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS physical_inspections (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                transformer_id  TEXT NOT NULL,
                inspected_at    TEXT NOT NULL,
                observations_json TEXT NOT NULL,
                notes           TEXT,
                created_at      TEXT NOT NULL,
                recorded_by_id   TEXT,
                recorded_by_name TEXT,
                FOREIGN KEY (transformer_id) REFERENCES transformers(id)
            )
            """
        )
        conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_physical_transformer
               ON physical_inspections(transformer_id, inspected_at DESC)"""
        )

        # Yaşam döngüsü (Faz 9.35). Varsayılan "devrede", çünkü mevcut
        # kayıtların tamamı işletmedeki varlıklar; yeni eklenenler
        # açıkça durum belirtir.
        _ensure_column(conn, "transformers", "lifecycle_status",
                       "TEXT NOT NULL DEFAULT 'in_service'")
        _ensure_column(conn, "transformers", "lifecycle_changed_at", "TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS lifecycle_events (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                transformer_id TEXT NOT NULL,
                from_status    TEXT,
                to_status      TEXT NOT NULL,
                note           TEXT,
                changed_at     TEXT NOT NULL,
                changed_by_id   TEXT,
                changed_by_name TEXT,
                FOREIGN KEY (transformer_id) REFERENCES transformers(id)
            )
            """
        )
        conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_lifecycle_transformer
               ON lifecycle_events(transformer_id, changed_at DESC)"""
        )

        # Kimlik sütunları (Faz 9.0c). Her kayıt "kim girdi" bilgisini
        # TAŞIR ve bu bilgi ANLIK GÖRÜNTÜDÜR: sicil no yanında ad da
        # saklanır. Neden? Personel işten ayrılsa, soyadı değişse ya da
        # kaydı kaldırılsa bile üç yıl önceki ölçümün kim tarafından
        # yapıldığı okunabilir kalmalı. Bu, "kayıt silinmez, geçersiz
        # işaretlenir" kararıyla aynı ilkenin devamı: geçmiş, bugünün
        # durumuna göre yeniden yazılmaz.
        for table in ("oil_tests", "electrical_tests", "measurements"):
            _ensure_column(conn, table, "recorded_by_id", "TEXT")
            _ensure_column(conn, table, "recorded_by_name", "TEXT")
        for table in ("oil_tests", "electrical_tests"):
            _ensure_column(conn, table, "voided_by_id", "TEXT")
            _ensure_column(conn, table, "voided_by_name", "TEXT")

        # Mühendislik onay sütunları (Faz 12.2). ``review_status`` BOŞ
        # (NULL) başlar, "onay gerekmiyor" değil: bu sütundan önce
        # kaydedilmiş testlerin hükmü henüz değerlendirilmedi. Açılışta
        # services/review.backfill() onları bir kez sınıflandırır.
        for table in REVIEW_TABLES:
            for col in ("review_status", "reviewed_at", "reviewed_by_id",
                        "reviewed_by_name", "review_note"):
                _ensure_column(conn, table, col, "TEXT")

        # Uzman etiketleri (Faz 12.3). Ayrı tablo, ölçüme sütun DEĞİL:
        # etiket ölçümün değil, ölçüm hakkındaki İNSAN KARARININ kaydıdır ve
        # kendi sahibi, zamanı, gerekçesi vardır. measurement_id BENZERSİZ:
        # bir ölçüme tek uzman kararı — iki mühendis aynı anda etiketlerse
        # veritabanı ikincisini reddeder.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expert_labels (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                measurement_id   INTEGER NOT NULL UNIQUE,
                transformer_id   TEXT NOT NULL,
                model_prediction TEXT,
                model_confidence REAL,
                expert_label     TEXT NOT NULL,
                agrees           INTEGER NOT NULL,
                note             TEXT,
                labeled_at       TEXT NOT NULL,
                labeled_by_id    TEXT,
                labeled_by_name  TEXT,
                FOREIGN KEY (measurement_id) REFERENCES measurements(id)
            )
            """
        )
        conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_expert_labels_transformer
               ON expert_labels(transformer_id)"""
        )

        # Varlığa özel eşikler (Faz 12.4). Standart sınırlar da kayda
        # KOPYALANIR (standard_*): kod içindeki standart ileride değişse
        # bile, istisnanın neyin yerine geçtiği geçmişte okunabilmeli.
        # Kayıt silinmez; reddedilen, geri çekilen ve süresi dolan
        # istisnalar durum alanıyla ayrılır.
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS limit_overrides (
                id                        INTEGER PRIMARY KEY AUTOINCREMENT,
                transformer_id            TEXT NOT NULL,
                parameter                 TEXT NOT NULL,
                voltage_class             TEXT NOT NULL,
                good_limit                REAL NOT NULL,
                acceptable_limit          REAL NOT NULL,
                standard_good_limit       REAL NOT NULL,
                standard_acceptable_limit REAL NOT NULL,
                valid_from                TEXT NOT NULL,
                valid_until               TEXT NOT NULL,
                reason                    TEXT NOT NULL,
                status                    TEXT NOT NULL,
                proposed_at               TEXT NOT NULL,
                proposed_by_id            TEXT,
                proposed_by_name          TEXT,
                decided_at                TEXT,
                decided_by_id             TEXT,
                decided_by_name           TEXT,
                decision_note             TEXT,
                revoked_at                TEXT,
                revoked_by_id             TEXT,
                revoked_by_name           TEXT,
                revoke_note               TEXT
            )
            """
        )
        # KISMİ benzersiz indeks: bir trafonun bir parametresi için aynı anda
        # yalnızca BİR açık (bekleyen ya da yürürlükte) istisna olabilir.
        # Kapanmış kayıtlar sınırsız birikebilir. Kontrol veritabanında, çünkü
        # iki mühendis aynı anda öneri gönderirse uygulama katmanındaki
        # kontrol ikisini de geçirirdi (Faz 12.2'deki yarışla aynı ders).
        conn.execute(
            """CREATE UNIQUE INDEX IF NOT EXISTS uq_limit_overrides_open
               ON limit_overrides(transformer_id, parameter)
               WHERE status IN ('pending', 'active')"""
        )
        conn.execute(
            """CREATE INDEX IF NOT EXISTS idx_limit_overrides_transformer
               ON limit_overrides(transformer_id)"""
        )



# Mühendislik onay akışına giren tablolar (Faz 12.2). Tablo adı SQL'e
# metin olarak girdiği için yalnızca bu listedekiler kabul edilir.
REVIEW_TABLES = ("oil_tests", "electrical_tests", "component_tests")

# Yağ kalitesi testi sütunları. DGA ölçümünden AYRI bir tablo:
# farklı laboratuvar testleri, farklı sıklık, farklı birimler. Aynı tabloya
# sıkıştırmak her satırın yarısını boş bırakırdı.
OIL_TEST_FIELDS = [
    "water_ppm", "bdv_kv", "acidity_mgkoh_g", "ift_mn_m",
    "furan_2fal_mgl", "color_astm",
]

# Elektriksel test sütunları (Faz 8.6). ``tap_position`` ölçüm değil
# BAĞLAMDIR: beklenen sarım oranı kademeye göre değişir, kademeyi bilmeden
# TTR sonucu yorumlanamaz.
# Bileşen testi sütunları (Faz 9.4).
COMPONENT_TEST_FIELDS = [
    *[f"bushing_{p}_{s}" for p in ("a", "b", "c")
      for s in ("pf_pct", "cap_pf", "cap_rated_pf")],
    "oltc_operations", "oltc_ops_since_overhaul",
    "oltc_years_since_overhaul", "oltc_oil_bdv_kv",
]

ELECTRICAL_TEST_FIELDS = [
    "tap_position",
    "ttr_a", "ttr_b", "ttr_c",
    "rw_a_ohm", "rw_b_ohm", "rw_c_ohm", "winding_temp_c",
    "ir_1min_mohm", "ir_10min_mohm", "insulation_temp_c",
    "tan_delta_pct", "tan_delta_temp_c",
]


def _ensure_column(conn: sqlite3.Connection, table: str, column: str,
                   ddl: str) -> None:
    """Sütun yoksa ekler; varsa hiçbir şey yapmaz (yinelenebilir göç).

    SQLite'ta "ADD COLUMN IF NOT EXISTS" yoktur, bu yüzden önce mevcut
    sütunlar okunur. Bu olmadan yeni bir alan eklediğimizde eski
    veritabanları açılırken çökerdi — kullanıcının dga.db dosyasını silmesi
    gerekirdi ve geçmiş ölçümler kaybolurdu.
    """
    cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


def _init_oil_tests(conn: sqlite3.Connection) -> None:
    """Yağ kalitesi testleri tablosu (Faz 8.3)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS oil_tests (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            transformer_id TEXT NOT NULL,
            sampled_at     TEXT NOT NULL,
            water_ppm      REAL,
            bdv_kv         REAL,
            acidity_mgkoh_g REAL,
            ift_mn_m       REAL,
            furan_2fal_mgl REAL,
            color_astm     REAL,
            lab            TEXT,
            notes          TEXT,
            created_at     TEXT NOT NULL,
            FOREIGN KEY (transformer_id) REFERENCES transformers(id)
        )
        """
    )
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_oil_tests_transformer
           ON oil_tests(transformer_id, sampled_at DESC)"""
    )


def _init_electrical_tests(conn: sqlite3.Connection) -> None:
    """Elektriksel test tablosu (Faz 8.6).

    Yağ testlerinden AYRI bir tablo, çünkü bu testler farklı bir dünyaya
    ait: trafo **enerjisizken** yapılırlar, sıklıkları çok daha düşüktür
    (devreye alma + büyük bakım) ve birimleri tamamen farklıdır. Aynı
    tabloya sıkıştırmak her satırın yarısını boş bırakırdı.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS electrical_tests (
            id                 INTEGER PRIMARY KEY AUTOINCREMENT,
            transformer_id     TEXT NOT NULL,
            tested_at          TEXT NOT NULL,
            tap_position       INTEGER,
            ttr_a              REAL,
            ttr_b              REAL,
            ttr_c              REAL,
            rw_a_ohm           REAL,
            rw_b_ohm           REAL,
            rw_c_ohm           REAL,
            winding_temp_c     REAL,
            ir_1min_mohm       REAL,
            ir_10min_mohm      REAL,
            insulation_temp_c  REAL,
            tan_delta_pct      REAL,
            tan_delta_temp_c   REAL,
            tested_by          TEXT,
            notes              TEXT,
            created_at         TEXT NOT NULL,
            FOREIGN KEY (transformer_id) REFERENCES transformers(id)
        )
        """
    )
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_electrical_tests_transformer
           ON electrical_tests(transformer_id, tested_at DESC)"""
    )


def _normalize_existing_timestamps(conn: sqlite3.Connection) -> None:
    """Eski kayıtlardaki tarih-only damgaları düzeltir (yinelenebilir göç).

    ``_ensure_column`` ile aynı felsefe: kullanıcının veritabanını silmesi
    gerekmesin. Bu göç olmadan, hatanın bulunmasından ÖNCE girilmiş
    kayıtlar yanlış sıralanmaya devam ederdi.
    """
    for table, column in (("oil_tests", "sampled_at"),
                          ("electrical_tests", "tested_at")):
        conn.execute(
            f"""UPDATE {table} SET {column} = {column} || 'T00:00:00+00:00'
                WHERE length({column}) = 10""")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_ts(value: Optional[str]) -> Optional[str]:
    """Tarih girişini sıralanabilir bir ISO zaman damgasına çevirir.

    ⚠ YAŞANAN HATA: Tarihler METİN olarak saklanıp metin olarak
    sıralanıyor (SQLite'ta tarih tipi yok). Arayüzdeki ``<input
    type="date">`` "2026-09-11" gönderir; otomatik kayıtlar ise
    "2026-09-11T08:00:00+00:00" biçimindedir. Metin karşılaştırmasında

        "2026-09-11" < "2026-09-11T08:00:00+00:00"

    olduğu için, AYNI GÜN elle tarih girilerek kaydedilen yeni bir test
    eski testin ARKASINA düşüyor ve "en son test" olarak seçilmiyordu.
    Kullanıcı yeni testini kaydediyor ama ekranda eskisini görüyordu.

    Çözüm: yalnızca tarih verilmişse o tarihe ŞU ANKİ saat eklenir.
    Gün başına (T00:00) sabitlemek yetmezdi: aynı gün girilen yeni bir
    test, o gün otomatik kaydedilmiş bir testin yine arkasına düşerdi.
    Şimdiki saati kullanmak, aynı güne girilen testleri doğal olarak
    giriş sırasına dizer; geçmiş tarihli testler ise yine kendi gününde
    kalır.
    """
    if not value:
        return None
    text = str(value).strip()
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        clock = datetime.now(timezone.utc).strftime("%H:%M:%S")
        return f"{text}T{clock}+00:00"
    return text


def upsert_transformer(tid: str, name: str, location: str = "",
                       asset_class: str = assets.DEFAULT_CLASS,
                       mva: Optional[float] = None,
                       **np_fields: object) -> None:
    """Trafoyu ekler veya günceller; künye alanları isteğe bağlıdır.

    ``**np_fields`` ile künye alanları geçilebilir (manufacturer, hv_kv ...).
    Bilinmeyen alan adları sessizce yok sayılır — dışarıdan gelen fazladan
    anahtar yüzünden kayıt kaybetmek istemeyiz.
    """
    code = str(assets.get(asset_class)["code"])

    # Yalnızca tanıdığımız künye alanlarını al.
    np_values = {k: np_fields.get(k) for k in NAMEPLATE_FIELDS
                 if k in np_fields}

    columns = ["id", "name", "location", "asset_class", "mva", "created_at"]
    values = [tid, name, location, code, mva, _now()]
    for key, value in np_values.items():
        columns.append(key)
        values.append(value)

    placeholders = ", ".join("?" for _ in columns)
    # created_at güncellemede korunur: kaydın ilk oluşturulma zamanıdır.
    updates = ", ".join(f"{c}=excluded.{c}" for c in columns
                        if c not in ("id", "created_at"))

    with _connect() as conn:
        conn.execute(
            f"""INSERT INTO transformers ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT(id) DO UPDATE SET {updates}""",
            values,
        )


def ensure_transformer(tid: str, name: Optional[str] = None) -> bool:
    """Trafo kaydı YOKSA oluşturur; VARSA hiçbir alanına dokunmaz.

    Neden ayrı bir fonksiyon? ``upsert_transformer`` adı gereği "varsa
    güncelle" demek ve verilmeyen alanları varsayılana düşürüyor. Ölçüm
    kaydetme yolunda bu yıkıcı: tek bir /predict çağrısı trafonun konumunu
    siliyor, varlık sınıfını MPT'ye düşürüyor ve gücünü boşaltıyordu.
    Öncelik skoru varlık sınıfına bağlı olduğu için kritik bir trafonun
    önceliği sessizce 4.00'ten 2.80'e iniyordu.

    Ölçüm eklemek varlık kaydını DÜZENLEMEK değildir. İki işi ayırmak
    gerekiyordu.

    Returns:
        Yeni kayıt oluşturulduysa True, kayıt zaten varsa False.
    """
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO transformers (id, name, location, asset_class,
                                         created_at)
               VALUES (?, ?, '', ?, ?)
               ON CONFLICT(id) DO NOTHING""",
            (tid, name or tid, assets.DEFAULT_CLASS, _now()),
        )
        return cur.rowcount > 0


def update_nameplate(tid: str, fields: Dict[str, object]) -> Optional[Dict]:
    """Var olan bir trafonun künyesini günceller.

    Sadece GÖNDERİLEN alanları değiştirir; gönderilmeyenler olduğu gibi
    kalır. Tam kaydı üzerine yazsaydık, arayüzde bir alanı boş bırakmak
    veritabanındaki değeri silerdi.
    """
    known = {k: v for k, v in fields.items() if k in NAMEPLATE_FIELDS}
    if not known:
        return get_transformer(tid)

    assignments = ", ".join(f"{k}=?" for k in known)
    with _connect() as conn:
        cur = conn.execute(
            f"UPDATE transformers SET {assignments} WHERE id = ?",
            [*known.values(), tid],
        )
        if cur.rowcount == 0:
            return None
    return get_transformer(tid)


def get_transformer(tid: str) -> Optional[Dict]:
    """Tek trafo: künyesi ve türetilmiş büyüklükleriyle."""
    with _connect() as conn:
        row = conn.execute("SELECT * FROM transformers WHERE id = ?",
                           (tid,)).fetchone()
    if row is None:
        return None

    record = dict(row)
    record["nameplate"] = {k: record.get(k) for k in NAMEPLATE_FIELDS}
    record["derived"] = nameplate.summary(record["nameplate"])
    return record


def list_transformers() -> List[Dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM transformers ORDER BY id").fetchall()
        return [dict(r) for r in rows]


def save_measurement(transformer_id: str, gases: Dict[str, float],
                     diagnosis: Dict, sampled_at: Optional[str] = None,
                     recorded_by: Optional[Dict[str, str]] = None) -> int:
    """DGA ölçümünü tanısıyla kaydeder.

    ``recorded_by`` (Faz 12.3): sütun Faz 9.0c'de eklenmişti ama DGA
    ölçümlerinde hiç doldurulmuyordu. Uzman etiketindeki dört göz kuralı
    "ölçümü kim girdi" bilgisine dayandığı için artık saklanıyor.
    """
    risk = diagnosis.get("risk", {})
    rec = recorded_by or {}
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO measurements
               (transformer_id, sampled_at, gases_json, prediction,
                confidence, risk_level, risk_condition,
                recorded_by_id, recorded_by_name)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                transformer_id,
                sampled_at or _now(),
                json.dumps({k: gases.get(k, 0.0) for k in GASES}),
                diagnosis.get("prediction"),
                diagnosis.get("confidence"),
                risk.get("level"),
                risk.get("condition"),
                rec.get("employee_no"),
                rec.get("name"),
            ),
        )
        return int(cur.lastrowid)


def get_measurements(transformer_id: str) -> List[Dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM measurements WHERE transformer_id = ?
               ORDER BY sampled_at ASC""",
            (transformer_id,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["gases"] = json.loads(d.pop("gases_json"))
        out.append(d)
    return out


# ---------------------------------------------------------------------------
# Yağ kalitesi testleri (Faz 8.3)
# ---------------------------------------------------------------------------

def save_oil_test(transformer_id: str, values: Dict[str, object],
                  sampled_at: Optional[str] = None,
                  lab: Optional[str] = None,
                  notes: Optional[str] = None,
                  recorded_by: Optional[Dict[str, str]] = None) -> int:
    """Bir yağ kalitesi testi kaydeder ve id'sini döndürür."""
    rec = recorded_by or {}
    known = {k: values.get(k) for k in OIL_TEST_FIELDS}
    columns = ["transformer_id", "sampled_at", *OIL_TEST_FIELDS,
               "lab", "notes", "created_at",
               "recorded_by_id", "recorded_by_name"]
    row = [transformer_id, _normalize_ts(sampled_at) or _now(),
           *[known[k] for k in OIL_TEST_FIELDS], lab, notes, _now(),
           rec.get("employee_no"), rec.get("name")]

    with _connect() as conn:
        cur = conn.execute(
            f"""INSERT INTO oil_tests ({", ".join(columns)})
                VALUES ({", ".join("?" for _ in columns)})""",
            row,
        )
        return int(cur.lastrowid)


def get_oil_tests(transformer_id: str) -> List[Dict]:
    """Bir trafonun tüm yağ testleri, eskiden yeniye."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM oil_tests WHERE transformer_id = ?
               ORDER BY sampled_at ASC, id ASC""",
            (transformer_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def latest_oil_tests() -> Dict[str, Dict]:
    """Her trafonun EN SON yağ testi — filo görünümü için.

    Faz 5.2'deki ``latest_measurements`` ile aynı desen: pencere fonksiyonu
    ile trafo başına tek satır.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            WITH ranked AS (
                SELECT o.*,
                       ROW_NUMBER() OVER (
                           PARTITION BY o.transformer_id
                           ORDER BY o.sampled_at DESC, o.id DESC
                       ) AS rn
                FROM oil_tests o
                WHERE o.voided_at IS NULL
                  -- Faz 12.2: mühendisin reddettiği ölçüm "son test" olamaz.
                  AND COALESCE(o.review_status, '') <> 'rejected'
            )
            SELECT * FROM ranked WHERE rn = 1
            """
        ).fetchall()
    return {r["transformer_id"]: dict(r) for r in rows}


def recent_measurements(limit: int = 20) -> List[Dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT m.*, t.name AS transformer_name
               FROM measurements m JOIN transformers t
                 ON m.transformer_id = t.id
               ORDER BY m.sampled_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["gases"] = json.loads(d.pop("gases_json"))
        out.append(d)
    return out

def latest_measurements() -> List[Dict]:
    """Her trafonun EN SON ölçümü — filo dashboard'unun ana sorgusu.

    Hiç ölçümü olmayan trafolar da listede döner (ölçüm alanları None).
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            WITH ranked AS (
                SELECT m.*,
                       ROW_NUMBER() OVER (
                           PARTITION BY m.transformer_id
                           ORDER BY m.sampled_at DESC, m.id DESC
                       ) AS rn
                FROM measurements m
            )
            SELECT t.id       AS transformer_id,
                   t.name     AS transformer_name,
                   t.location AS location,
                   t.asset_class AS asset_class,
                   t.mva AS mva,
                   t.manufacturer AS manufacturer,
                   t.hv_kv AS hv_kv,
                   t.lv_kv AS lv_kv,
                   t.cooling AS cooling,
                   t.commissioned_at AS commissioned_at,
                   t.year_made AS year_made,
                   t.lifecycle_status AS lifecycle_status,
                   t.lifecycle_changed_at AS lifecycle_changed_at,
                   r.id       AS measurement_id,
                   r.sampled_at,
                   r.gases_json,
                   r.prediction,
                   r.confidence,
                   r.risk_level,
                   r.risk_condition,
                   (SELECT COUNT(*) FROM measurements m2
                     WHERE m2.transformer_id = t.id) AS measurement_count
            FROM transformers t
            LEFT JOIN ranked r
                   ON r.transformer_id = t.id AND r.rn = 1
            ORDER BY t.id
            """
        ).fetchall()

    out = []
    for r in rows:
        d = dict(r)
        raw = d.pop("gases_json")
        d["gases"] = json.loads(raw) if raw else None
        out.append(d)
    return out



# ---------------------------------------------------------------------------
# Elektriksel testler (Faz 8.6)
# ---------------------------------------------------------------------------

def save_electrical_test(transformer_id: str, values: Dict[str, object],
                         tested_at: Optional[str] = None,
                         tested_by: Optional[str] = None,
                         notes: Optional[str] = None,
                         recorded_by: Optional[Dict[str, str]] = None) -> int:
    """Bir elektriksel test kaydeder ve id'sini döndürür.

    ``recorded_by``: {"employee_no": ..., "name": ...} — kaydı sisteme
    giren kişi. ``tested_by`` ondan FARKLI olabilir: testi sahada başkası
    yapmış, kaydı ofiste bir başkası girmiş olabilir. İkisini ayrı tutmak
    gerçek iş akışına uygundur.
    """
    rec = recorded_by or {}
    known = {k: values.get(k) for k in ELECTRICAL_TEST_FIELDS}
    columns = ["transformer_id", "tested_at", *ELECTRICAL_TEST_FIELDS,
               "tested_by", "notes", "created_at",
               "recorded_by_id", "recorded_by_name"]
    row = [transformer_id, _normalize_ts(tested_at) or _now(),
           *[known[k] for k in ELECTRICAL_TEST_FIELDS],
           tested_by, notes, _now(),
           rec.get("employee_no"), rec.get("name")]

    with _connect() as conn:
        cur = conn.execute(
            f"""INSERT INTO electrical_tests ({", ".join(columns)})
                VALUES ({", ".join("?" for _ in columns)})""",
            row,
        )
        return int(cur.lastrowid)


def get_electrical_tests(transformer_id: str) -> List[Dict]:
    """Bir trafonun tüm elektriksel testleri, eskiden yeniye."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM electrical_tests WHERE transformer_id = ?
               ORDER BY tested_at ASC, id ASC""",
            (transformer_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def latest_electrical_tests() -> Dict[str, Dict]:
    """Her trafonun EN SON elektriksel testi — filo görünümü için.

    ``latest_measurements`` ve ``latest_oil_tests`` ile aynı desen:
    pencere fonksiyonu ile trafo başına tek satır.
    """
    with _connect() as conn:
        rows = conn.execute(
            """
            WITH ranked AS (
                SELECT e.*,
                       ROW_NUMBER() OVER (
                           PARTITION BY e.transformer_id
                           ORDER BY e.tested_at DESC, e.id DESC
                       ) AS rn
                FROM electrical_tests e
                WHERE e.voided_at IS NULL
                  AND COALESCE(e.review_status, '') <> 'rejected'
            )
            SELECT * FROM ranked WHERE rn = 1
            """
        ).fetchall()
    return {r["transformer_id"]: dict(r) for r in rows}


def void_test(table: str, transformer_id: str, test_id: int,
              reason: str,
              voided_by: Optional[Dict[str, str]] = None) -> bool:
    """Bir test kaydını GEÇERSİZ işaretler (silmez).

    NEDEN SİLMİYORUZ
    ----------------
    Ölçüm kayıtları bir varlığın geçmişidir ve denetlenebilir olmalıdır.
    Sahada hatalı çıkan bir test raporu imha edilmez; üzerine "geçersiz"
    damgası vurulur, gerekçesi yazılır ve dosyada kalır. Sebebi pratik:
    "bu ölçüm neden yapılmadı?" ile "yapıldı ama hatalıydı" farklı
    şeylerdir ve ikincisi bilgi taşır — aynı hata tekrarlanıyorsa bunu
    ancak kayıtlar gösterir.

    Geçersiz kayıtlar geçmişte GÖRÜNÜR (gerekçesiyle) ama:
      * "son test" seçilirken atlanır,
      * hüküm ve sağlık endeksi hesabına girmez.

    Geri alınabilir: ``reason`` boş verilirse işaret kaldırılır.
    """
    if table not in ("oil_tests", "electrical_tests"):
        raise ValueError(f"Bilinmeyen tablo: {table}")

    rec = voided_by or {}
    voided_at = _now() if reason else None
    with _connect() as conn:
        cur = conn.execute(
            f"""UPDATE {table}
                SET voided_at = ?, void_reason = ?,
                    voided_by_id = ?, voided_by_name = ?
                WHERE id = ? AND transformer_id = ?""",
            (voided_at, reason or None,
             rec.get("employee_no") if reason else None,
             rec.get("name") if reason else None,
             int(test_id), transformer_id),
        )
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# Yaşam döngüsü (Faz 9.35)
# ---------------------------------------------------------------------------

def set_lifecycle(transformer_id: str, to_status: str,
                  note: Optional[str] = None,
                  changed_by: Optional[Dict[str, str]] = None) -> Optional[Dict]:
    """Durumu değiştirir ve geçişi geçmişe yazar.

    Geçerlilik kontrolü BURADA DEĞİL, çağıran katmanda yapılır
    (``core/lifecycle.validate_transition``): kural saf modülde durur,
    veritabanı yalnızca yazar. Aynı ayrım künye doğrulamasında da var.
    """
    rec = changed_by or {}
    with _connect() as conn:
        row = conn.execute(
            "SELECT lifecycle_status FROM transformers WHERE id = ?",
            (transformer_id,)).fetchone()
        if row is None:
            return None

        now = _now()
        conn.execute(
            """UPDATE transformers
               SET lifecycle_status = ?, lifecycle_changed_at = ?
               WHERE id = ?""",
            (to_status, now, transformer_id))
        conn.execute(
            """INSERT INTO lifecycle_events
               (transformer_id, from_status, to_status, note, changed_at,
                changed_by_id, changed_by_name)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (transformer_id, row["lifecycle_status"], to_status, note, now,
             rec.get("employee_no"), rec.get("name")))

    return get_transformer(transformer_id)


def get_lifecycle_events(transformer_id: str) -> List[Dict]:
    """Durum geçişi geçmişi, eskiden yeniye.

    Geçmiş SİLİNMEZ: "bu ünite ne zaman devreye alındı, ne zaman hizmet
    dışı kaldı" sorusu varlık yönetiminin temel sorularından biridir.
    """
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM lifecycle_events WHERE transformer_id = ?
               ORDER BY changed_at ASC, id ASC""",
            (transformer_id,)).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Fiziksel gözlem (Faz 9.5)
# ---------------------------------------------------------------------------

def save_physical_inspection(transformer_id: str,
                             observations: Dict[str, object],
                             inspected_at: Optional[str] = None,
                             notes: Optional[str] = None,
                             recorded_by: Optional[Dict[str, str]] = None
                             ) -> int:
    """Bir gözlem turunu kaydeder."""
    rec = recorded_by or {}
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO physical_inspections
               (transformer_id, inspected_at, observations_json, notes,
                created_at, recorded_by_id, recorded_by_name)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (transformer_id, _normalize_ts(inspected_at) or _now(),
             json.dumps(observations, ensure_ascii=False), notes, _now(),
             rec.get("employee_no"), rec.get("name")),
        )
        return int(cur.lastrowid)


def get_physical_inspections(transformer_id: str) -> List[Dict]:
    """Bir trafonun gözlem turları, eskiden yeniye."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM physical_inspections WHERE transformer_id = ?
               ORDER BY inspected_at ASC, id ASC""",
            (transformer_id,)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["observations"] = json.loads(d.pop("observations_json"))
        out.append(d)
    return out


def latest_physical_inspections() -> Dict[str, Dict]:
    """Her trafonun EN SON gözlem turu — filo görünümü için."""
    with _connect() as conn:
        rows = conn.execute(
            """
            WITH ranked AS (
                SELECT p.*,
                       ROW_NUMBER() OVER (
                           PARTITION BY p.transformer_id
                           ORDER BY p.inspected_at DESC, p.id DESC
                       ) AS rn
                FROM physical_inspections p
            )
            SELECT * FROM ranked WHERE rn = 1
            """
        ).fetchall()
    out = {}
    for r in rows:
        d = dict(r)
        d["observations"] = json.loads(d.pop("observations_json"))
        out[d["transformer_id"]] = d
    return out


# ---------------------------------------------------------------------------
# Bileşen testleri (Faz 9.4)
# ---------------------------------------------------------------------------

def save_component_test(transformer_id: str, values: Dict[str, object],
                        tested_at: Optional[str] = None,
                        notes: Optional[str] = None,
                        recorded_by: Optional[Dict[str, str]] = None) -> int:
    """Bir buşing/OLTC testini kaydeder."""
    rec = recorded_by or {}
    known = {k: values.get(k) for k in COMPONENT_TEST_FIELDS}
    columns = ["transformer_id", "tested_at", *COMPONENT_TEST_FIELDS,
               "notes", "created_at", "recorded_by_id", "recorded_by_name"]
    row = [transformer_id, _normalize_ts(tested_at) or _now(),
           *[known[k] for k in COMPONENT_TEST_FIELDS],
           notes, _now(), rec.get("employee_no"), rec.get("name")]

    with _connect() as conn:
        cur = conn.execute(
            f"""INSERT INTO component_tests ({", ".join(columns)})
                VALUES ({", ".join("?" for _ in columns)})""",
            row,
        )
        return int(cur.lastrowid)


def get_component_tests(transformer_id: str) -> List[Dict]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM component_tests WHERE transformer_id = ?
               ORDER BY tested_at ASC, id ASC""",
            (transformer_id,)).fetchall()
    return [dict(r) for r in rows]


def latest_component_tests() -> Dict[str, Dict]:
    with _connect() as conn:
        rows = conn.execute(
            """
            WITH ranked AS (
                SELECT c.*,
                       ROW_NUMBER() OVER (
                           PARTITION BY c.transformer_id
                           ORDER BY c.tested_at DESC, c.id DESC
                       ) AS rn
                FROM component_tests c
                WHERE COALESCE(c.review_status, '') <> 'rejected'
            )
            SELECT * FROM ranked WHERE rn = 1
            """
        ).fetchall()
    return {r["transformer_id"]: dict(r) for r in rows}


# ---------------------------------------------------------------------------
# Mühendislik onay akışı (Faz 12.2)
# ---------------------------------------------------------------------------

def _review_table(table: str) -> str:
    """Tablo adını beyaz listeden geçirir.

    Tablo adı SQL parametresi olarak verilemez (yalnızca değerler
    verilebilir), metin olarak sorguya girer. Kullanıcıdan gelen bir
    değerin buraya ulaşması SQL enjeksiyonu demektir; bu yüzden liste
    dışındaki her ad reddedilir.
    """
    if table not in REVIEW_TABLES:
        raise ValueError(f"Onay akışında olmayan tablo: {table}")
    return table


def get_test_row(table: str, test_id: int) -> Optional[Dict]:
    """Tek bir test satırı (onay alanlarıyla)."""
    with _connect() as conn:
        row = conn.execute(
            f"SELECT * FROM {_review_table(table)} WHERE id = ?",
            (int(test_id),)).fetchone()
    return dict(row) if row else None


def set_review_status(table: str, test_id: int, status: str) -> None:
    """İlk sınıflandırma: onay gerekiyor mu, gerekmiyor mu."""
    with _connect() as conn:
        conn.execute(
            f"UPDATE {_review_table(table)} SET review_status = ? WHERE id = ?",
            (status, int(test_id)))


def tests_without_review_status(table: str) -> List[Dict]:
    """Henüz sınıflandırılmamış (onay sütunundan önce girilmiş) testler."""
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM {_review_table(table)} WHERE review_status IS NULL"
        ).fetchall()
    return [dict(r) for r in rows]


def tests_by_review_status(table: str, statuses: List[str]) -> List[Dict]:
    """Verilen onay durumlarındaki testler."""
    if not statuses:
        return []
    marks = ", ".join("?" for _ in statuses)
    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT * FROM {_review_table(table)}
                WHERE review_status IN ({marks})
                ORDER BY created_at ASC, id ASC""",
            tuple(statuses)).fetchall()
    return [dict(r) for r in rows]


def record_review_decision(table: str, test_id: int, status: str,
                           note: Optional[str],
                           reviewer: Dict[str, str]) -> bool:
    """Mühendis kararını yazar. Karar YALNIZCA bekleyen teste yazılır.

    ``WHERE review_status = 'pending'`` koşulu bilinçli: iki mühendis aynı
    anda karar verirse ikisi de kontrolü geçebilir, ama veritabanı yalnızca
    birincisini yazar — ikincinin güncellemesi 0 satır etkiler ve
    ``False`` döner. Kontrolü sadece uygulama katmanında yapmak bu
    yarışı yakalayamazdı (iş emri sıra numarasındaki çakışmayla aynı ders).
    """
    with _connect() as conn:
        cur = conn.execute(
            f"""UPDATE {_review_table(table)}
                SET review_status = ?, reviewed_at = ?, reviewed_by_id = ?,
                    reviewed_by_name = ?, review_note = ?
                WHERE id = ? AND review_status = 'pending'""",
            (status, _now(), reviewer.get("employee_no"),
             reviewer.get("name"), note, int(test_id)))
        return cur.rowcount > 0


def review_counts() -> Dict[str, int]:
    """Onay durumlarına göre filo geneli sayım."""
    counts: Dict[str, int] = {}
    with _connect() as conn:
        for table in REVIEW_TABLES:
            for row in conn.execute(
                    f"""SELECT review_status, COUNT(*) AS n FROM {table}
                        WHERE review_status IS NOT NULL
                        GROUP BY review_status""").fetchall():
                key = row["review_status"]
                counts[key] = counts.get(key, 0) + int(row["n"])
    return counts


# ---------------------------------------------------------------------------
# Uzman etiketleri — model inceleme (Faz 12.3)
# ---------------------------------------------------------------------------

def _measurement_dict(row: sqlite3.Row) -> Dict:
    d = dict(row)
    d["gases"] = json.loads(d.pop("gases_json"))
    return d


def get_measurement(measurement_id: int) -> Optional[Dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM measurements WHERE id = ?",
                           (int(measurement_id),)).fetchone()
    return _measurement_dict(row) if row else None


def measurements_by_ids(ids: List[int]) -> List[Dict]:
    if not ids:
        return []
    marks = ", ".join("?" for _ in ids)
    with _connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM measurements WHERE id IN ({marks})",
            tuple(int(i) for i in ids)).fetchall()
    return [_measurement_dict(r) for r in rows]


def low_confidence_measurements(threshold: float) -> List[Dict]:
    """Model güveni eşiğin altında kalan ölçümler, yeniden eskiye."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM measurements
               WHERE confidence IS NOT NULL AND confidence < ?
               ORDER BY sampled_at DESC, id DESC""",
            (float(threshold),)).fetchall()
    return [_measurement_dict(r) for r in rows]


def save_expert_label(measurement: Dict, label: str, note: Optional[str],
                      reviewer: Dict[str, str]) -> Optional[int]:
    """Uzman kararını yazar; ölçüm zaten etiketliyse None.

    Modelin tahmini ve güveni etikete KOPYALANIR (anlık görüntü): ölçüm
    ileride yeni bir modelle yeniden tanılansa bile "uzman hangi tahmine
    itiraz etti" sorusu cevaplanabilir kalmalı.
    """
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO expert_labels
                   (measurement_id, transformer_id, model_prediction,
                    model_confidence, expert_label, agrees, note,
                    labeled_at, labeled_by_id, labeled_by_name)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (int(measurement["id"]), measurement["transformer_id"],
                 measurement.get("prediction"), measurement.get("confidence"),
                 label, int(label == measurement.get("prediction")), note,
                 _now(), reviewer.get("employee_no"), reviewer.get("name")))
            return int(cur.lastrowid)
    except sqlite3.IntegrityError:
        return None


def expert_label_for(measurement_id: int) -> Optional[Dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM expert_labels WHERE measurement_id = ?",
                           (int(measurement_id),)).fetchone()
    return dict(row) if row else None


def expert_labels_by_measurement() -> Dict[int, Dict]:
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM expert_labels").fetchall()
    return {int(r["measurement_id"]): dict(r) for r in rows}


def labeled_measurements() -> List[Dict]:
    """Etiketler + ölçüm gazları — veri seti dışa aktarımı için."""
    with _connect() as conn:
        rows = conn.execute(
            """SELECT l.*, m.sampled_at, m.gases_json
               FROM expert_labels l JOIN measurements m ON m.id = l.measurement_id
               ORDER BY l.labeled_at ASC, l.id ASC""").fetchall()
    return [_measurement_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# Varlığa özel eşikler — mühendislik istisnası (Faz 12.4)
# ---------------------------------------------------------------------------

def create_limit_override(transformer_id: str, values: Dict[str, object],
                          proposer: Dict[str, str]) -> Optional[int]:
    """İstisna önerisi kaydeder ve id'sini döner.

    Aynı trafo ve parametre için açık (bekleyen/yürürlükte) bir istisna
    varsa kısmi benzersiz indeks eklemeyi reddeder ve ``None`` döner.
    """
    try:
        with _connect() as conn:
            cur = conn.execute(
                """INSERT INTO limit_overrides (
                       transformer_id, parameter, voltage_class,
                       good_limit, acceptable_limit,
                       standard_good_limit, standard_acceptable_limit,
                       valid_from, valid_until, reason, status,
                       proposed_at, proposed_by_id, proposed_by_name)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)""",
                (transformer_id, values["parameter"], values["voltage_class"],
                 float(values["good_limit"]),               # type: ignore[arg-type]
                 float(values["acceptable_limit"]),         # type: ignore[arg-type]
                 float(values["standard_good_limit"]),      # type: ignore[arg-type]
                 float(values["standard_acceptable_limit"]),  # type: ignore[arg-type]
                 values["valid_from"], values["valid_until"], values["reason"],
                 _now(), proposer.get("employee_no"), proposer.get("name")))
            return int(cur.lastrowid)
    except sqlite3.IntegrityError:
        return None


def get_limit_override(override_id: int) -> Optional[Dict]:
    with _connect() as conn:
        row = conn.execute("SELECT * FROM limit_overrides WHERE id = ?",
                           (int(override_id),)).fetchone()
    return dict(row) if row else None


def list_limit_overrides(statuses: Optional[List[str]] = None,
                         transformer_id: Optional[str] = None) -> List[Dict]:
    """İstisnalar — en yeni öneri üstte. Filtreler isteğe bağlı."""
    clauses: List[str] = []
    params: List[object] = []
    if statuses:
        clauses.append(f"status IN ({', '.join('?' for _ in statuses)})")
        params.extend(statuses)
    if transformer_id:
        clauses.append("transformer_id = ?")
        params.append(transformer_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with _connect() as conn:
        rows = conn.execute(
            f"""SELECT * FROM limit_overrides {where}
                ORDER BY proposed_at DESC, id DESC""", tuple(params)).fetchall()
    return [dict(r) for r in rows]


def active_limit_overrides(transformer_id: str) -> List[Dict]:
    """Trafonun yürürlükteki istisnaları (tarih penceresi çağıranda)."""
    return list_limit_overrides(["active"], transformer_id)


def decide_limit_override(override_id: int, status: str, note: Optional[str],
                          reviewer: Dict[str, str]) -> bool:
    """Onay/ret yazar. YALNIZCA bekleyen kayda yazılır (yarışta False)."""
    with _connect() as conn:
        cur = conn.execute(
            """UPDATE limit_overrides
               SET status = ?, decided_at = ?, decided_by_id = ?,
                   decided_by_name = ?, decision_note = ?
               WHERE id = ? AND status = 'pending'""",
            (status, _now(), reviewer.get("employee_no"), reviewer.get("name"),
             note, int(override_id)))
        return cur.rowcount > 0


def revoke_limit_override(override_id: int, note: str,
                          who: Dict[str, str]) -> bool:
    """Geri çekme yazar. YALNIZCA yürürlükteki kayda yazılır."""
    with _connect() as conn:
        cur = conn.execute(
            """UPDATE limit_overrides
               SET status = 'revoked', revoked_at = ?, revoked_by_id = ?,
                   revoked_by_name = ?, revoke_note = ?
               WHERE id = ? AND status = 'active'""",
            (_now(), who.get("employee_no"), who.get("name"), note,
             int(override_id)))
        return cur.rowcount > 0


def expire_limit_overrides(today_iso: str) -> int:
    """Bitiş tarihi geçmiş açık istisnaları 'expired' yapar.

    Bekleyenler de kapanır: süresi onay beklerken dolan bir öneri artık
    onaylanamaz, ama açık kaldığı sürece aynı parametreye yeni öneriyi
    engellerdi.
    """
    with _connect() as conn:
        cur = conn.execute(
            """UPDATE limit_overrides SET status = 'expired'
               WHERE status IN ('pending', 'active') AND valid_until < ?""",
            (today_iso,))
        return cur.rowcount


def limit_override_counts() -> Dict[str, int]:
    with _connect() as conn:
        rows = conn.execute(
            """SELECT status, COUNT(*) AS n FROM limit_overrides
               GROUP BY status""").fetchall()
    return {r["status"]: int(r["n"]) for r in rows}
