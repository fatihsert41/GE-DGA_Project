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

from .core.gases import GASES

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
                id         TEXT PRIMARY KEY,
                name       TEXT NOT NULL,
                location   TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
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


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_transformer(tid: str, name: str, location: str = "") -> None:
    with _connect() as conn:
        conn.execute(
            """INSERT INTO transformers (id, name, location, created_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET name=excluded.name,
                                             location=excluded.location""",
            (tid, name, location, _now()),
        )


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
