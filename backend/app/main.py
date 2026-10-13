from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.audio import (
    CONVERSION_VERSION,
    WavRejected,
    blob_path,
    compute_peaks,
    derivative_path,
    ffmpeg_version,
    peaks_path,
    playback_file,
    probe_wav,
    write_pcm16_derivative,
)
from app.config import Settings, load_settings
from app.db import asset_dict, connect, project_dict
from app.worker import AnalysisWorker


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message


class ErrorBody(BaseModel):
    error: str
    message: str


class Health(BaseModel):
    status: str
    database: str
    ffmpeg_version: str
    analysis: Literal["not_implemented"]


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class Project(BaseModel):
    id: str
    name: str
    mode: Literal["study"]
    created_at: str
    updated_at: str


class Asset(BaseModel):
    id: str
    sha256: str
    original_name: str
    byte_length: int
    duration_s: float
    sample_rate: int
    channels: int
    subtype: Literal["pcm_16", "pcm_24"]
    analysis_status: Literal["not_run"]
    playback_status: Literal["ready", "unavailable"]
    created_at: str


class ProjectDetail(Project):
    assets: list[Asset]


class UploadResult(BaseModel):
    cache: Literal["hit", "miss"]
    asset: Asset


class PeakBucket(BaseModel):
    min: float
    max: float


class Peaks(BaseModel):
    duration_s: float
    sample_rate: int
    channels: int
    method_id: str
    buckets: list[PeakBucket]


class Job(BaseModel):
    id: str
    asset_id: str
    status: Literal["queued", "running", "completed", "failed", "canceled"]
    created_at: str
    updated_at: str
    error: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _db(request: Request) -> sqlite3.Connection:
    return request.app.state.db


def _require_project(conn: sqlite3.Connection, project_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise AppError(404, "not_found", "Project not found.")
    return row


def _require_asset(conn: sqlite3.Connection, asset_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    if row is None:
        raise AppError(404, "not_found", "Asset not found.")
    return row


async def spool_upload(upload: UploadFile, dest: Path, max_bytes: int) -> tuple[str, int]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    hasher = hashlib.sha256()
    total = 0
    try:
        with dest.open("wb") as handle:
            while True:
                chunk = await upload.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise AppError(
                        413,
                        "too_large",
                        f"File exceeds the {max_bytes} byte upload limit.",
                    )
                hasher.update(chunk)
                handle.write(chunk)
        return hasher.hexdigest(), total
    except AppError:
        dest.unlink(missing_ok=True)
        raise
    except (ConnectionError, TimeoutError) as exc:
        dest.unlink(missing_ok=True)
        raise AppError(
            400, "upload_interrupted", "Upload interrupted. Temporary file removed."
        ) from exc
    except Exception:
        dest.unlink(missing_ok=True)
        raise


def _cache_peaks(data_root: Path, sha256: str, kind: str, source: Path) -> None:
    payload = compute_peaks(source)
    path = peaks_path(data_root, sha256, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _try_peaks(data_root: Path, sha256: str, kind: str, source: Path) -> None:
    try:
        _cache_peaks(data_root, sha256, kind, source)
    except (OSError, WavRejected, ValueError):
        return


def _prepare_playback(data_root: Path, sha256: str, source: Path, info) -> str:
    if info.subtype == "pcm_16":
        _try_peaks(data_root, sha256, "original", source)
        return "ready"
    dest = derivative_path(data_root, sha256)
    try:
        if not dest.is_file():
            write_pcm16_derivative(source, dest, info)
    except (OSError, RuntimeError, WavRejected):
        dest.unlink(missing_ok=True)
        dest.with_suffix(".partial.wav").unlink(missing_ok=True)
        return "unavailable"
    _try_peaks(data_root, sha256, CONVERSION_VERSION, dest)
    return "ready"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()
    settings.data_root.mkdir(parents=True, exist_ok=True)
    connection = connect(settings.database_path)
    app = FastAPI(title="Audio Reference Studio")
    app.state.settings = settings
    app.state.db = connection
    app.state.worker = AnalysisWorker(connection)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
        expose_headers=["Accept-Ranges", "Content-Range", "Content-Length"],
    )

    @app.exception_handler(AppError)
    async def app_error(_request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status, content={"error": exc.code, "message": exc.message}
        )

    @app.get("/api/health", response_model=Health)
    def health() -> Health:
        database = "ok"
        try:
            connection.execute("SELECT 1")
        except sqlite3.Error:
            database = "error"
        return Health(
            status="ok" if database == "ok" else "degraded",
            database=database,
            ffmpeg_version=ffmpeg_version(),
            analysis="not_implemented",
        )

    @app.post("/api/projects", response_model=Project)
    def create_project(body: ProjectCreate) -> dict:
        name = body.name.strip()
        if not name:
            raise AppError(400, "invalid_name", "Project name is required.")
        now = _now()
        project_id = str(uuid.uuid4())
        connection.execute(
            "INSERT INTO projects (id, name, mode, created_at, updated_at) VALUES (?, ?, 'study', ?, ?)",
            (project_id, name, now, now),
        )
        connection.commit()
        row = connection.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
        return project_dict(row)

    @app.get("/api/projects", response_model=list[Project])
    def list_projects() -> list[dict]:
        rows = connection.execute("SELECT * FROM projects ORDER BY created_at").fetchall()
        return [project_dict(row) for row in rows]

    @app.get("/api/projects/{project_id}", response_model=ProjectDetail)
    def get_project(project_id: str) -> dict:
        project = project_dict(_require_project(connection, project_id))
        rows = connection.execute(
            """
            SELECT assets.* FROM assets
            JOIN project_assets ON project_assets.asset_id = assets.id
            WHERE project_assets.project_id = ?
            ORDER BY project_assets.ordering, assets.created_at
            """,
            (project_id,),
        ).fetchall()
        project["assets"] = [asset_dict(row) for row in rows]
        return project

    @app.post("/api/projects/{project_id}/assets", response_model=UploadResult)
    async def upload_asset(project_id: str, file: UploadFile = File(...)) -> dict:  # noqa: B008
        _require_project(connection, project_id)
        original_name = file.filename or "untitled.wav"
        if len(original_name) > 255:
            raise AppError(400, "invalid_name", "File name is too long.")
        if not original_name.lower().endswith(".wav"):
            raise AppError(400, "not_wav", "Only WAV files are accepted.")
        tmp = settings.data_root / "tmp" / f"{uuid.uuid4().hex}.part"
        try:
            sha256, size = await spool_upload(file, tmp, settings.max_bytes)
            try:
                info = probe_wav(tmp)
            except WavRejected as exc:
                raise AppError(400, "invalid_wav", str(exc)) from exc
            if info.duration_s > settings.max_duration_s:
                raise AppError(
                    400,
                    "too_long",
                    f"Duration {info.duration_s:.2f}s exceeds the {settings.max_duration_s:g}s limit.",
                )
            existing = connection.execute(
                "SELECT * FROM assets WHERE sha256 = ?", (sha256,)
            ).fetchone()
            if existing is not None:
                asset = asset_dict(existing)
                cache: Literal["hit", "miss"] = "hit"
            else:
                target = blob_path(settings.data_root, sha256)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    tmp.unlink(missing_ok=True)
                else:
                    os.replace(tmp, target)
                playback_status = _prepare_playback(settings.data_root, sha256, target, info)
                asset_id = str(uuid.uuid4())
                created = _now()
                connection.execute(
                    """
                    INSERT INTO assets (
                      id, sha256, original_name, byte_length, duration_s, sample_rate, channels,
                      subtype, analysis_status, playback_status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'not_run', ?, ?)
                    """,
                    (
                        asset_id,
                        sha256,
                        original_name,
                        size,
                        info.duration_s,
                        info.sample_rate,
                        info.channels,
                        info.subtype,
                        playback_status,
                        created,
                    ),
                )
                connection.commit()
                asset = asset_dict(
                    connection.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
                )
                cache = "miss"
            order = connection.execute(
                "SELECT COALESCE(MAX(ordering), -1) + 1 FROM project_assets WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            connection.execute(
                """
                INSERT INTO project_assets (project_id, asset_id, ordering)
                VALUES (?, ?, ?)
                ON CONFLICT (project_id, asset_id) DO NOTHING
                """,
                (project_id, asset["id"], order),
            )
            connection.commit()
            return {"cache": cache, "asset": asset}
        finally:
            tmp.unlink(missing_ok=True)

    @app.get("/api/assets/{asset_id}", response_model=Asset)
    def get_asset(asset_id: str) -> dict:
        return asset_dict(_require_asset(connection, asset_id))

    @app.get("/api/assets/{asset_id}/stream")
    def stream_asset(asset_id: str) -> FileResponse:
        asset = _require_asset(connection, asset_id)
        path = playback_file(
            settings.data_root, asset["sha256"], asset["subtype"], asset["playback_status"]
        )
        if path is None:
            raise AppError(
                409,
                "playback_unavailable",
                "Playback is unavailable. The stored master was not modified and is not streamed.",
            )
        return FileResponse(path, media_type="audio/wav", filename="playback.wav")

    @app.get("/api/assets/{asset_id}/peaks", response_model=Peaks)
    def get_peaks(asset_id: str) -> dict:
        asset = _require_asset(connection, asset_id)
        path = playback_file(
            settings.data_root, asset["sha256"], asset["subtype"], asset["playback_status"]
        )
        if path is None:
            raise AppError(
                409,
                "peaks_unavailable",
                "Peaks are unavailable because playback audio was not produced.",
            )
        kind = "original" if asset["subtype"] == "pcm_16" else CONVERSION_VERSION
        cache = peaks_path(settings.data_root, asset["sha256"], kind)
        if not cache.is_file():
            try:
                _cache_peaks(settings.data_root, asset["sha256"], kind, path)
            except (OSError, WavRejected, ValueError) as exc:
                raise AppError(
                    409,
                    "peaks_unavailable",
                    "Peaks could not be read from the playback file.",
                ) from exc
        payload = json.loads(cache.read_text())
        return payload

    @app.post("/api/assets/{asset_id}/analyze", response_model=ErrorBody, status_code=501)
    def analyze(asset_id: str) -> JSONResponse:
        _require_asset(connection, asset_id)
        app.state.worker.run_available()
        return JSONResponse(
            status_code=501,
            content={
                "error": "not_implemented",
                "message": "Analysis is not implemented. No job was created.",
            },
        )

    @app.get("/api/jobs/{job_id}", response_model=Job)
    def get_job(job_id: str) -> dict:
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise AppError(404, "not_found", "No job with that id exists.")
        return {
            "id": row["id"],
            "asset_id": row["asset_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "error": row["error"],
        }

    return app
