from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def _migrate_v2(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript((MIGRATIONS / "002_analysis.sql").read_text())
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA user_version = 2")
    conn.commit()


def connect(database: Path) -> sqlite3.Connection:
    database.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    conn.execute("PRAGMA journal_mode = WAL")
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 1:
        conn.executescript((MIGRATIONS / "001_init.sql").read_text())
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
        version = 1
    if version < 2:
        _migrate_v2(conn)
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
