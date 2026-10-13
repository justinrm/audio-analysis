"""One-at-a-time analysis worker.

The API enqueues jobs. This process claims them. A request handler must not
run the measurements. Start it with `python -m app.worker`.
"""

from __future__ import annotations

import shutil
import sqlite3
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.audio import blob_path
from app.config import Settings, load_settings
from app.db import connect
from app.measure import ALGORITHM_VERSION, PARAMS_HASH
from app.pipeline import analysis_dir, run_analysis


def _now() -> str:
    return datetime.now(UTC).isoformat()


class AnalysisWorker:
    def __init__(self, connection: sqlite3.Connection, settings: Settings) -> None:
        self._connection = connection
        self._settings = settings

    def recover_interrupted(self) -> int:
        now = _now()
        rows = self._connection.execute(
            "SELECT id, asset_id FROM jobs WHERE status = 'running'"
        ).fetchall()
        for row in rows:
            self._connection.execute(
                "UPDATE jobs SET status = 'failed', error = ?, updated_at = ? WHERE id = ?",
                ("interrupted", now, row["id"]),
            )
            self._connection.execute(
                """
                UPDATE assets SET analysis_status = 'failed'
                WHERE id = ? AND analysis_status = 'running'
                """,
                (row["asset_id"],),
            )
        self._connection.commit()
        return len(rows)

    def run_available(self) -> int:
        now = _now()
        self._connection.execute("BEGIN IMMEDIATE")
        row = self._connection.execute(
            """
            UPDATE jobs SET status = 'running', updated_at = ?
            WHERE id = (
              SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1
            )
            RETURNING id, asset_id
            """,
            (now,),
        ).fetchone()
        if row is None:
            self._connection.commit()
            return 0
        self._connection.execute(
            "UPDATE assets SET analysis_status = 'running' WHERE id = ?",
            (row["asset_id"],),
        )
        self._connection.commit()
        self._execute(row["id"], row["asset_id"])
        return 1

    def _execute(self, job_id: str, asset_id: str) -> None:
        asset = self._connection.execute(
            "SELECT * FROM assets WHERE id = ?", (asset_id,)
        ).fetchone()
        if asset is None:
            self._finish(job_id, None, "failed", "Asset disappeared before analysis.")
            return
        final = analysis_dir(self._settings.data_root, asset["sha256"])
        existing = self._connection.execute(
            """
            SELECT id, status FROM analysis_runs
            WHERE asset_id = ? AND algorithm_version = ? AND params_hash = ?
            """,
            (asset_id, ALGORITHM_VERSION, PARAMS_HASH),
        ).fetchone()
        if existing and existing["status"] == "completed" and (final / "metrics.json").is_file():
            self._finish(job_id, asset_id, "completed", None)
            return
        stage = final.parent / f".{ALGORITHM_VERSION}-{job_id}"
        try:
            if stage.exists():
                shutil.rmtree(stage)
            run_analysis(
                blob_path(self._settings.data_root, asset["sha256"]),
                stage,
                asset_id,
                asset["sha256"],
            )
            final.parent.mkdir(parents=True, exist_ok=True)
            if final.exists():
                shutil.rmtree(final)
            stage.rename(final)
            self._store_run(
                existing["id"] if existing else str(uuid.uuid4()),
                asset_id,
                final,
                "completed",
                None,
            )
            self._finish(job_id, asset_id, "completed", None)
        except Exception as exc:  # noqa: BLE001 - the worker has to record the failure and keep polling
            shutil.rmtree(stage, ignore_errors=True)
            message = f"{type(exc).__name__}: {exc}"[:300]
            if existing:
                self._store_run(existing["id"], asset_id, final, "failed", message)
            self._finish(job_id, asset_id, "failed", message)

    def _store_run(
        self, run_id: str, asset_id: str, final: Path, status: str, error: str | None
    ) -> None:
        now = _now()
        metrics = str(final / "metrics.json") if status == "completed" else None
        evidence = str(final / "evidence.json") if status == "completed" else None
        self._connection.execute(
            """
            INSERT INTO analysis_runs (
              id, asset_id, algorithm_version, params_hash, status, started_at, finished_at,
              error, metrics_path, evidence_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (asset_id, algorithm_version, params_hash) DO UPDATE SET
              status = excluded.status,
              finished_at = excluded.finished_at,
              error = excluded.error,
              metrics_path = excluded.metrics_path,
              evidence_path = excluded.evidence_path
            """,
            (
                run_id,
                asset_id,
                ALGORITHM_VERSION,
                PARAMS_HASH,
                status,
                now,
                now,
                error,
                metrics,
                evidence,
            ),
        )

    def _finish(self, job_id: str, asset_id: str | None, status: str, error: str | None) -> None:
        now = _now()
        self._connection.execute(
            "UPDATE jobs SET status = ?, error = ?, updated_at = ? WHERE id = ?",
            (status, error, now, job_id),
        )
        if asset_id is not None:
            self._connection.execute(
                "UPDATE assets SET analysis_status = ? WHERE id = ?",
                (status if status in {"completed", "failed"} else "running", asset_id),
            )
        self._connection.commit()


def main() -> None:
    settings = load_settings()
    connection = connect(settings.database_path)
    worker = AnalysisWorker(connection, settings)
    worker.recover_interrupted()
    while True:
        if worker.run_available() == 0:
            time.sleep(0.5)


if __name__ == "__main__":
    main()
