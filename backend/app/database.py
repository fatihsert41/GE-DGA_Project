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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


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

