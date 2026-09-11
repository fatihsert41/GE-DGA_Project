"""Lightweight SQLite persistence (no ORM needed for a demo).

Two tables:
* transformers  - one row per monitored asset.
* measurements  - one row per oil sample: the seven gases, the diagnosis
                  that was produced, risk level and a timestamp.
"""
from __future__ import annotations

import json
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

DB_PATH = Path(__file__).resolve().parents[1] / "dga.db"


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
                     diagnosis: Dict, sampled_at: Optional[str] = None) -> int:
    risk = diagnosis.get("risk", {})
    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO measurements
               (transformer_id, sampled_at, gases_json, prediction,
                confidence, risk_level, risk_condition)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                transformer_id,
                sampled_at or _now(),
                json.dumps({k: gases.get(k, 0.0) for k in GASES}),
                diagnosis.get("prediction"),
                diagnosis.get("confidence"),
                risk.get("level"),
                risk.get("condition"),
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
                  notes: Optional[str] = None) -> int:
    """Bir yağ kalitesi testi kaydeder ve id'sini döndürür."""
    known = {k: values.get(k) for k in OIL_TEST_FIELDS}
    columns = ["transformer_id", "sampled_at", *OIL_TEST_FIELDS,
               "lab", "notes", "created_at"]
    row = [transformer_id, _normalize_ts(sampled_at) or _now(),
           *[known[k] for k in OIL_TEST_FIELDS], lab, notes, _now()]

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
                         notes: Optional[str] = None) -> int:
    """Bir elektriksel test kaydeder ve id'sini döndürür."""
    known = {k: values.get(k) for k in ELECTRICAL_TEST_FIELDS}
    columns = ["transformer_id", "tested_at", *ELECTRICAL_TEST_FIELDS,
               "tested_by", "notes", "created_at"]
    row = [transformer_id, _normalize_ts(tested_at) or _now(),
           *[known[k] for k in ELECTRICAL_TEST_FIELDS],
           tested_by, notes, _now()]

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
            )
            SELECT * FROM ranked WHERE rn = 1
            """
        ).fetchall()
    return {r["transformer_id"]: dict(r) for r in rows}


def void_test(table: str, transformer_id: str, test_id: int,
              reason: str) -> bool:
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

    voided_at = _now() if reason else None
    with _connect() as conn:
        cur = conn.execute(
            f"""UPDATE {table} SET voided_at = ?, void_reason = ?
                WHERE id = ? AND transformer_id = ?""",
            (voided_at, reason or None, int(test_id), transformer_id),
        )
        return cur.rowcount > 0
