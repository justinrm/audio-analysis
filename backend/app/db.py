from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "001_init.sql"


def connect(database: Path) -> sqlite3.Connection:
    database.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 1:
        conn.executescript(MIGRATION.read_text())
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
    return conn


def asset_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "sha256": row["sha256"],
        "original_name": row["original_name"],
        "byte_length": row["byte_length"],
        "duration_s": row["duration_s"],
        "sample_rate": row["sample_rate"],
        "channels": row["channels"],
        "subtype": row["subtype"],
        "analysis_status": row["analysis_status"],
        "playback_status": row["playback_status"],
        "created_at": row["created_at"],
    }


def project_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "mode": row["mode"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
