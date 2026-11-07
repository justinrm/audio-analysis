from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

MIGRATIONS = Path(__file__).resolve().parents[1] / "migrations"


def _migrate_v2(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executescript((MIGRATIONS / "002_analysis.sql").read_text())
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA user_version = 2")
    conn.commit()


class _Rows:
    """Rows already read while the connection lock was held."""

    def __init__(self, rows: list[sqlite3.Row]) -> None:
        self._rows = rows
        self._index = 0

    def fetchone(self) -> sqlite3.Row | None:
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def fetchall(self) -> list[sqlite3.Row]:
        rows = self._rows[self._index :]
        self._index = len(self._rows)
        return rows


class SerializedConnection(sqlite3.Connection):
    """One sqlite3 connection cannot run two statements at once.

    Sync endpoints share this connection from a thread pool. Overlapping
    execute() and fetchone() calls return None or a torn row, which the lyric
    reader reports as a 404 for a document that is stored.
    """

    # ponytail: one lock per statement. BEGIN can still interleave with another
    # request on this connection; hold the lock for the transaction if that shows up.

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._guard = threading.Lock()

    def execute(self, sql: str, parameters: object = ()) -> sqlite3.Cursor | _Rows:
        with self._guard:
            cursor = super().execute(sql, parameters)
            if cursor.description is None:
                return cursor
            return _Rows(cursor.fetchall())

    def executemany(self, sql: str, seq_of_parameters: object) -> sqlite3.Cursor:
        with self._guard:
            return super().executemany(sql, seq_of_parameters)

    def executescript(self, sql_script: str) -> sqlite3.Cursor:
        with self._guard:
            return super().executescript(sql_script)

    def commit(self) -> None:
        with self._guard:
            super().commit()

    def rollback(self) -> None:
        with self._guard:
            super().rollback()


def connect(database: Path) -> sqlite3.Connection:
    database.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(database, check_same_thread=False, factory=SerializedConnection)
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
        version = 2
    if version < 3:
        conn.executescript((MIGRATIONS / "003_lyrics.sql").read_text())
        conn.execute("PRAGMA user_version = 3")
        conn.commit()
        version = 3
    if version < 4:
        conn.executescript((MIGRATIONS / "004_exports.sql").read_text())
        conn.execute("PRAGMA user_version = 4")
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
