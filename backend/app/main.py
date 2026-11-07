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
from fastapi.responses import FileResponse, JSONResponse, Response
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
from app.charts import KINDS, not_run
from app.config import Settings, load_settings
from app.db import asset_dict, connect, project_dict
from app.exports import ExportError, create_export, open_export
from app.lyric_charts import (
    LYRIC_KINDS,
    build_lyric_chart,
    load_stored_charts,
    summary_for,
)
from app.lyrics import (
    LYRIC_MAX_BYTES,
    LyricError,
    canonical_evidence,
    create_annotation,
    delete_annotation,
    delete_lyrics,
    list_annotations,
    load_document,
    lyric_kind,
    require_membership,
    source_bytes,
    store_upload,
    update_segment,
    verify_segment,
)
from app.measure import ALGORITHM_VERSION, PARAMS_HASH
from app.pipeline import analysis_dir, empty_registry, public_summary
from app.png import RENDERER_VERSION, rendered_png
from app.worker import AnalysisWorker


class AppError(Exception):
    def __init__(
        self, status: int, code: str, message: str, extra: dict | None = None
    ) -> None:
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra or {}


class ErrorBody(BaseModel):
    error: str
    message: str


class Health(BaseModel):
    status: str
    database: str
    ffmpeg_version: str
    analysis: Literal["available"]


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
    analysis_status: Literal["not_run", "queued", "running", "completed", "failed"]
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


class ChartLine(BaseModel):
    name: str
    unit: str
    x: list[float]
    y: list[float | None]


class ChartBar(BaseModel):
    label: str
    value: float


class ChartHeatmap(BaseModel):
    x: list[float]
    y: list[float]
    z: list[list[float]]


class ChartSeries(BaseModel):
    lines: list[ChartLine] = []
    bars: list[ChartBar] = []
    heatmap: ChartHeatmap | None = None


class AxisDefinitions(BaseModel):
    x: str = ""
    y: str = ""
    y_scale: Literal["linear", "log"] = "linear"


class ReviewMarker(BaseModel):
    time_s: float
    label: str
    kind: str = "event"
    value: str | None = None
    caveat: str | None = None


class SummaryItem(BaseModel):
    label: str
    value: str


class ChartSummary(BaseModel):
    chart_kind: str
    status: Literal["not_run", "ready", "not_available", "failed"]
    title: str
    evidence_class: str
    method_id: str
    method_version: str
    caveats: list[str]
    summary: list[SummaryItem]
    not_available_reason: str | None = None
    error: str | None = None
    data_url: str
    png_url: str | None = None


class ChartList(BaseModel):
    charts: list[ChartSummary]


class ChartDocument(BaseModel):
    model_config = {"extra": "allow"}
    chart_kind: str
    status: Literal["not_run", "ready", "not_available", "failed"]
    title: str
    evidence_class: str
    method_id: str
    method_version: str
    caveats: list[str]
    summary: list[SummaryItem]
    series: ChartSeries
    axis_definitions: AxisDefinitions
    review_markers: list[ReviewMarker]
    not_available_reason: str | None = None
    error: str | None = None


class Job(BaseModel):
    id: str
    asset_id: str
    status: Literal["queued", "running", "completed", "failed", "canceled"]
    created_at: str
    updated_at: str
    error: str | None = None


class LyricSegmentOut(BaseModel):
    id: str
    ordinal: int
    source_cue: str | None
    text: str
    start_s: float | None
    end_s: float | None
    timing_origin: Literal["unplaced", "subtitle_supplied", "manual_edit", "manual_verified"]
    artist_verified: bool
    note: str
    usable: bool


class LyricValidationOut(BaseModel):
    segment_id: str | None
    code: Literal[
        "overlap",
        "out_of_range",
        "empty_cue",
        "reversed_time",
        "malformed_time",
        "unparsed",
    ]
    detail: str


class LyricDocumentOut(BaseModel):
    id: str
    project_id: str
    asset_id: str
    upload_id: str
    source_kind: Literal["txt", "md", "srt"]
    source_sha256: str
    original_name: str
    revision: int
    segments: list[LyricSegmentOut]
    validation: list[LyricValidationOut]


class LyricSegmentUpdate(BaseModel):
    expected_revision: int = Field(ge=1)
    text: str | None = None
    start_s: float | None = None
    end_s: float | None = None
    note: str | None = None
    clear_timing: bool = False


class LyricVerify(BaseModel):
    expected_revision: int = Field(ge=1)
    verified: bool


class AnnotationIn(BaseModel):
    start_s: float
    end_s: float
    text: str = Field(min_length=1, max_length=2000)
    segment_id: str | None = None


class AnnotationOut(BaseModel):
    id: str
    project_id: str
    asset_id: str
    segment_id: str | None
    start_s: float
    end_s: float
    text: str
    created_at: str


class EvidenceRef(BaseModel):
    id: str
    evidence_class: str
    name: str
    interval_s: list[float] | None
    value: float | str | None
    unit: str | None
    method: str
    analysis_version: Literal["m1-v3"] | None
    lyric_document_id: str | None
    lyric_revision: int | None
    cites: list[str]
    caveat: str
    persisted: bool


class CanonicalEvidence(BaseModel):
    asset_id: str
    project_id: str
    analysis_version: Literal["m1-v3"] | None
    lyric_document_id: str | None
    lyric_revision: int | None
    records: list[EvidenceRef]


EvidenceClass = Literal[
    "measured",
    "estimated",
    "textual",
    "interpretive",
    "unknown",
    "not_applicable",
]


class LyricSeriesLine(BaseModel):
    name: str
    unit: str
    x: list[float]
    y: list[float | None]
    evidence_class: EvidenceClass
    evidence_id: str


class LyricSeriesBar(BaseModel):
    label: str
    value: float
    evidence_class: EvidenceClass
    evidence_id: str


class LyricRegion(BaseModel):
    evidence_id: str
    segment_id: str
    label: str
    start_s: float
    end_s: float
    evidence_class: Literal["textual"]


class LyricChartRow(BaseModel):
    evidence_id: str
    evidence_class: EvidenceClass
    kind: Literal["finding", "principle"]
    name: str
    value: str
    unit: str | None
    cites: list[str]
    caveat: str


class InsufficientPrinciple(BaseModel):
    code: Literal[
        "level_contrast",
        "written_repetition",
        "tempo",
        "melody",
        "section",
        "vocal",
        "emotion",
        "instrumentation",
    ]
    reason: str
    cites: list[str]


class LyricSeries(BaseModel):
    lines: list[LyricSeriesLine] = []
    bars: list[LyricSeriesBar] = []
    heatmap: ChartHeatmap | None = None


class ExportCreate(BaseModel):
    profile: Literal["technical", "lyricist", "combined"]
    lyrics: Literal["summarized", "included", "omitted"] = "summarized"


class ExportManifest(BaseModel):
    export_id: str
    project_id: str
    asset_id: str
    profile: Literal["technical", "lyricist", "combined"]
    lyrics_mode: Literal["summarized", "included", "omitted"]
    narrative: Literal["none"]
    source_sha256: str
    algorithm_version: str | None
    params_hash: str | None
    renderer_version: Literal["png-r1"]
    lyric_renderer_version: Literal["lyric-png-v1"] | None
    lyric_document_id: str | None
    lyric_revision: int | None
    lyric_source_sha256: str | None
    content_sha256: str
    created_at: str
    png_unavailable: list[str]
    files: list[str]


class LyricChartDocument(BaseModel):
    chart_kind: Literal["L01", "L02", "L03", "L04", "L05"]
    status: Literal["not_run", "ready", "not_available", "failed"]
    title: str
    evidence_class: EvidenceClass
    method_id: Literal["lyrics-v1"]
    method_version: Literal["lyrics-v1"]
    analysis_version: Literal["m1-v3"] | None
    lyric_document_id: str | None
    lyric_revision: int | None
    caveats: list[str]
    summary: list[SummaryItem]
    series: LyricSeries
    axis_definitions: AxisDefinitions
    review_markers: list[ReviewMarker]
    regions: list[LyricRegion]
    rows: list[LyricChartRow]
    insufficient: list[InsufficientPrinciple]
    not_available_reason: str | None = None
    error: str | None = None


def _lyric(exc: LyricError) -> AppError:
    return AppError(exc.status, exc.code, exc.message, exc.extra)


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
    app.state.worker = AnalysisWorker(connection, settings)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
        expose_headers=["Accept-Ranges", "Content-Range", "Content-Length"],
    )

    @app.exception_handler(AppError)
    async def app_error(_request: Request, exc: AppError) -> JSONResponse:
        content = {"error": exc.code, "message": exc.message}
        content.update(exc.extra)
        return JSONResponse(status_code=exc.status, content=content)

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
            analysis="available",
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

    def _job_dict(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "asset_id": row["asset_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "error": row["error"],
        }

    def _chart_file(asset: sqlite3.Row, kind: str) -> dict:
        if kind not in KINDS:
            raise AppError(404, "not_found", "Unknown chart.")
        path = analysis_dir(settings.data_root, asset["sha256"]) / f"{kind}.json"
        if not path.is_file():
            return not_run(kind)
        return json.loads(path.read_text())

    @app.post("/api/assets/{asset_id}/analyze", response_model=Job, status_code=202)
    def analyze(asset_id: str) -> dict:
        asset = _require_asset(connection, asset_id)
        now = _now()
        final = analysis_dir(settings.data_root, asset["sha256"])
        cached = connection.execute(
            """
            SELECT id FROM analysis_runs
            WHERE asset_id = ? AND algorithm_version = ? AND params_hash = ? AND status = 'completed'
            """,
            (asset_id, ALGORITHM_VERSION, PARAMS_HASH),
        ).fetchone()
        if cached is not None and (final / "metrics.json").is_file():
            job_id = str(uuid.uuid4())
            connection.execute(
                """
                INSERT INTO jobs (id, asset_id, status, created_at, updated_at, error)
                VALUES (?, ?, 'completed', ?, ?, NULL)
                """,
                (job_id, asset_id, now, now),
            )
            connection.execute(
                "UPDATE assets SET analysis_status = 'completed' WHERE id = ?",
                (asset_id,),
            )
            connection.commit()
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
            return _job_dict(row)
        active = connection.execute(
            """
            SELECT * FROM jobs
            WHERE asset_id = ? AND status IN ('queued', 'running')
            ORDER BY created_at DESC LIMIT 1
            """,
            (asset_id,),
        ).fetchone()
        if active is not None:
            return _job_dict(active)
        job_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO jobs (id, asset_id, status, created_at, updated_at, error)
            VALUES (?, ?, 'queued', ?, ?, NULL)
            """,
            (job_id, asset_id, now, now),
        )
        connection.execute(
            "UPDATE assets SET analysis_status = 'queued' WHERE id = ?",
            (asset_id,),
        )
        connection.commit()
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _job_dict(row)

    @app.get("/api/assets/{asset_id}/charts", response_model=ChartList)
    def list_charts(asset_id: str) -> dict:
        asset = _require_asset(connection, asset_id)
        final = analysis_dir(settings.data_root, asset["sha256"])
        if not (final / "metrics.json").is_file():
            return {"charts": empty_registry(asset_id)}
        charts = []
        for kind in KINDS:
            document = json.loads((final / f"{kind}.json").read_text())
            charts.append(public_summary(document, asset_id))
        return {"charts": charts}

    @app.get("/api/assets/{asset_id}/charts/{kind}/data", response_model=ChartDocument)
    def chart_data(asset_id: str, kind: str) -> dict:
        asset = _require_asset(connection, asset_id)
        document = _chart_file(asset, kind)
        if "series" not in document:
            document = {
                **document,
                "series": {"lines": [], "bars": [], "heatmap": None},
                "axis_definitions": {"x": "", "y": "", "y_scale": "linear"},
                "review_markers": [],
            }
        return document

    @app.get("/api/assets/{asset_id}/charts/{kind}/image")
    def chart_image(asset_id: str, kind: str) -> FileResponse:
        asset = _require_asset(connection, asset_id)
        if kind not in KINDS:
            raise AppError(404, "not_found", "Unknown chart.")
        path = rendered_png(analysis_dir(settings.data_root, asset["sha256"]), kind)
        if path is None:
            raise AppError(404, "png_unavailable", "No current PNG was written for this chart.")
        return FileResponse(
            path,
            media_type="image/png",
            headers={"X-Renderer-Version": RENDERER_VERSION, "Cache-Control": "no-cache"},
        )

    @app.get("/api/assets/{asset_id}/metrics")
    def metrics(asset_id: str) -> dict:
        asset = _require_asset(connection, asset_id)
        path = analysis_dir(settings.data_root, asset["sha256"]) / "metrics.json"
        if not path.is_file():
            raise AppError(404, "not_ready", "Analysis has not been run.")
        return json.loads(path.read_text())

    @app.get("/api/assets/{asset_id}/evidence")
    def evidence(asset_id: str) -> dict:
        asset = _require_asset(connection, asset_id)
        path = analysis_dir(settings.data_root, asset["sha256"]) / "evidence.json"
        if not path.is_file():
            raise AppError(404, "not_ready", "Analysis has not been run.")
        return json.loads(path.read_text())

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

    @app.post(
        "/api/projects/{project_id}/assets/{asset_id}/lyrics",
        response_model=LyricDocumentOut,
        status_code=201,
    )
    async def upload_lyrics(
        project_id: str,
        asset_id: str,
        file: UploadFile = File(...),  # noqa: B008
    ) -> dict:
        try:
            require_membership(connection, project_id, asset_id)
            lyric_kind(file.filename or "")
            tmp = settings.data_root / "tmp" / f"{uuid.uuid4().hex}.part"
            sha_ignored, _size = await spool_upload(file, tmp, LYRIC_MAX_BYTES)
            raw = tmp.read_bytes()
            tmp.unlink(missing_ok=True)
            del sha_ignored
            return store_upload(
                connection,
                settings.data_root,
                project_id,
                asset_id,
                file.filename or "",
                raw,
            )
        except LyricError as exc:
            raise _lyric(exc) from exc

    @app.get(
        "/api/projects/{project_id}/assets/{asset_id}/lyrics",
        response_model=LyricDocumentOut,
    )
    def get_lyrics(project_id: str, asset_id: str) -> dict:
        try:
            document = load_document(connection, project_id, asset_id)
        except LyricError as exc:
            raise _lyric(exc) from exc
        if document is None:
            raise AppError(404, "no_lyrics", "No lyric document is attached.")
        return document

    @app.get("/api/projects/{project_id}/assets/{asset_id}/lyrics/source")
    def lyric_source(project_id: str, asset_id: str) -> Response:
        try:
            body = source_bytes(connection, settings.data_root, project_id, asset_id)
        except LyricError as exc:
            raise _lyric(exc) from exc
        return Response(content=body, media_type="text/plain; charset=utf-8")

    @app.delete(
        "/api/projects/{project_id}/assets/{asset_id}/lyrics",
        status_code=204,
    )
    def remove_lyrics(project_id: str, asset_id: str) -> Response:
        try:
            delete_lyrics(connection, settings.data_root, project_id, asset_id)
        except LyricError as exc:
            raise _lyric(exc) from exc
        return Response(status_code=204)

    @app.put(
        "/api/projects/{project_id}/assets/{asset_id}/lyric-segments/{segment_id}",
        response_model=LyricDocumentOut,
    )
    def put_segment(
        project_id: str, asset_id: str, segment_id: str, body: LyricSegmentUpdate
    ) -> dict:
        try:
            return update_segment(
                connection,
                project_id,
                asset_id,
                segment_id,
                body.expected_revision,
                body.text,
                body.start_s,
                body.end_s,
                body.note,
                body.clear_timing,
            )
        except LyricError as exc:
            raise _lyric(exc) from exc

    @app.post(
        "/api/projects/{project_id}/assets/{asset_id}/lyric-segments/{segment_id}/verify",
        response_model=LyricDocumentOut,
    )
    def post_verify(
        project_id: str, asset_id: str, segment_id: str, body: LyricVerify
    ) -> dict:
        try:
            return verify_segment(
                connection,
                project_id,
                asset_id,
                segment_id,
                body.expected_revision,
                body.verified,
            )
        except LyricError as exc:
            raise _lyric(exc) from exc

    @app.get(
        "/api/projects/{project_id}/assets/{asset_id}/annotations",
        response_model=list[AnnotationOut],
    )
    def get_annotations(project_id: str, asset_id: str) -> list[dict]:
        try:
            return list_annotations(connection, project_id, asset_id)
        except LyricError as exc:
            raise _lyric(exc) from exc

    @app.post(
        "/api/projects/{project_id}/assets/{asset_id}/annotations",
        response_model=AnnotationOut,
        status_code=201,
    )
    def post_annotation(project_id: str, asset_id: str, body: AnnotationIn) -> dict:
        try:
            return create_annotation(
                connection,
                project_id,
                asset_id,
                body.start_s,
                body.end_s,
                body.text,
                body.segment_id,
            )
        except LyricError as exc:
            raise _lyric(exc) from exc

    @app.delete(
        "/api/projects/{project_id}/assets/{asset_id}/annotations/{annotation_id}",
        status_code=204,
    )
    def remove_annotation(project_id: str, asset_id: str, annotation_id: str) -> Response:
        try:
            delete_annotation(connection, project_id, asset_id, annotation_id)
        except LyricError as exc:
            raise _lyric(exc) from exc
        return Response(status_code=204)

    @app.get(
        "/api/projects/{project_id}/assets/{asset_id}/evidence",
        response_model=CanonicalEvidence,
    )
    def project_evidence(project_id: str, asset_id: str) -> dict:
        try:
            return canonical_evidence(connection, settings.data_root, project_id, asset_id)
        except LyricError as exc:
            raise _lyric(exc) from exc

    def _lyric_inputs(project_id: str, asset_id: str) -> tuple[dict, dict, dict | None]:
        try:
            asset = require_membership(connection, project_id, asset_id)
            bundle = canonical_evidence(connection, settings.data_root, project_id, asset_id)
            document = load_document(connection, project_id, asset_id)
        except LyricError as exc:
            raise _lyric(exc) from exc
        charts = load_stored_charts(settings.data_root, asset["sha256"])
        return bundle, charts, document

    @app.get(
        "/api/projects/{project_id}/assets/{asset_id}/lyric-charts",
        response_model=ChartList,
    )
    def lyric_chart_list(project_id: str, asset_id: str) -> dict:
        bundle, charts, document = _lyric_inputs(project_id, asset_id)
        built = [build_lyric_chart(kind, bundle, charts, document) for kind in LYRIC_KINDS]
        return {"charts": [summary_for(item, project_id, asset_id) for item in built]}

    @app.get(
        "/api/projects/{project_id}/assets/{asset_id}/lyric-charts/{kind}/data",
        response_model=LyricChartDocument,
    )
    def lyric_chart_data(project_id: str, asset_id: str, kind: str) -> dict:
        if kind not in LYRIC_KINDS:
            raise AppError(404, "not_found", "Unknown chart.")
        bundle, charts, document = _lyric_inputs(project_id, asset_id)
        return build_lyric_chart(kind, bundle, charts, document)

    @app.post(
        "/api/projects/{project_id}/assets/{asset_id}/exports",
        response_model=ExportManifest,
    )
    def create_recording_export(project_id: str, asset_id: str, body: ExportCreate) -> dict:
        try:
            return create_export(
                connection,
                settings.data_root,
                project_id,
                asset_id,
                body.profile,
                body.lyrics,
            )
        except LyricError as exc:
            raise _lyric(exc) from exc
        except ExportError as exc:
            raise AppError(exc.status, exc.code, exc.message) from exc

    @app.get("/api/projects/{project_id}/assets/{asset_id}/exports/{export_id}")
    def download_recording_export(
        project_id: str, asset_id: str, export_id: str
    ) -> FileResponse:
        try:
            path, profile = open_export(
                connection, settings.data_root, project_id, asset_id, export_id
            )
        except LyricError as exc:
            raise _lyric(exc) from exc
        except ExportError as exc:
            raise AppError(exc.status, exc.code, exc.message) from exc
        return FileResponse(
            path,
            media_type="application/zip",
            filename=f"{profile}-{export_id}.zip",
        )

    return app
