"""Album QC comparison from stored m1-v3 chart JSON.

This module does not decode a WAV, call measure.py, or write an analysis cache.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
import sqlite3
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import matplotlib.pyplot as plt
from pydantic import BaseModel, Field

from app.png import render_figure

COMPARISON_VERSION = "album-qc-v1"
REPORT_VERSION = "album-report-v1"

CAVEATS = [
    "Album order is a listening sequence, not a statement that the recordings form a released album.",
    "Values keep the unit and method stored for that recording. They are not normalized onto a common baseline.",
    "Loudness range is not crest factor. RMS is not loudness. Sample peak dBFS, FFmpeg dBTP, and 4× reconstructed dBTP are different measurements.",
    "Band-share distance is not timbral, musical, or creative similarity. The Welch PSD line is not overlaid.",
    "Pulse candidates are provisional onset-autocorrelation estimates, not a beat grid.",
    "A listening checkpoint is not an audible defect.",
    "Progress mode changes only the x coordinate. It does not resample the series.",
]
HASH_CAVEAT = "parameter hashes differ across included recordings"
DISAGREE_CAVEAT = "summary_metrics_disagree"

_SCALARS = (
    ("integrated_loudness", "LUFS", "Integrated loudness", "ffmpeg-ebur128", "T02"),
    ("loudness_range", "LU", "Loudness range", "ffmpeg-ebur128", "T02"),
    ("sample_peak", "dBFS", "Sample peak", "sample-peak", "T01"),
    ("rms", "dBFS", "Whole-file RMS", "rms", "T01"),
    ("crest_factor", "dB", "Crest factor", "crest", "T01"),
    ("ffmpeg_true_peak", "dBTP", "FFmpeg true peak", "ffmpeg-ebur128", "T02"),
    ("reconstructed_peak", "dBTP", "4x reconstructed peak", "4x-reconstructed-peak", "T10"),
    ("correlation", "ratio", "Whole-file correlation", "lr-correlation-1s", "T05"),
    ("side_mid", "dB", "Side/mid", "lr-correlation-1s", "T05"),
    ("mono_fold_down", "dB", "Mono fold-down change", "lr-correlation-1s", "T05"),
    ("sub_bass_correlation", "ratio", "Below 120 Hz correlation", "lr-correlation-1s", "T05"),
)
_STEREO = {"correlation", "side_mid", "mono_fold_down", "sub_bass_correlation"}
_SERIES = ("1 s RMS", "3 s short-term LUFS")


def summary_number(document: dict, label: str) -> float | None:
    if not isinstance(document, dict):
        return None
    for item in document.get("summary") or []:
        if item.get("label") != label or item.get("value") in {"undefined", "none"}:
            continue
        token = str(item["value"]).split()[0]
        try:
            value = float(token)
        except ValueError:
            return None
        if not math.isfinite(value):
            return None
        return value
    return None


def band_distance(left: list[dict], right: list[dict]) -> dict:
    result = {
        "status": "not_available",
        "reason": "no_bands",
        "value": None,
        "unit": "percentage points",
        "method_id": "band-share-l1-v1",
        "evidence_class": None,
    }
    if [item["label"] for item in left] != [item["label"] for item in right]:
        result["reason"] = "band_edges_differ"
        return result
    if not left:
        return result
    if any(item.get("value") is None for item in (*left, *right)):
        result["reason"] = "unavailable_value"
        return result
    total = sum(abs(a["value"] - b["value"]) for a, b in zip(left, right, strict=True))
    result["status"] = "ready"
    result["reason"] = None
    result["value"] = total / 2.0
    result["evidence_class"] = "measured"
    return result


def compare(tracks: list[dict], x_mode: str, *, project_id: str = "", name: str = "") -> dict:
    if x_mode not in {"seconds", "progress"}:
        raise ValueError("invalid_x")
    prepared = [_prepare(track, index, x_mode) for index, track in enumerate(tracks)]
    included = [track for track in prepared if track["included"]]
    caveats = list(CAVEATS)
    if any(item.get("metrics_value") is not None for track in included for item in track["scalars"]):
        caveats.append(DISAGREE_CAVEAT)
    hashes = {track.get("params_hash") for track in included}
    if len(hashes) > 1:
        caveats.append(HASH_CAVEAT)
    ready = len(included) >= 2
    pairs: list[dict] = []
    distances: list[dict] = []
    panel = _panel(included, x_mode, caveats) if ready else None
    if ready:
        for index, left in enumerate(included):
            for right in included[index + 1 :]:
                pairs.append(_pair(left, right))
                distances.append(
                    {
                        "left_asset_id": left["asset_id"],
                        "right_asset_id": right["asset_id"],
                        **band_distance(left["bands"], right["bands"]),
                    }
                )
    for track in prepared:
        track.pop("charts", None)
        track.pop("metrics", None)
        track.pop("_lines", None)
    return {
        "comparison_version": COMPARISON_VERSION,
        "project_id": project_id,
        "name": name,
        "status": "ready" if ready else "not_available",
        "not_available_reason": None if ready else "need_two_recordings",
        "x_mode": x_mode,
        "tracks": prepared,
        "pairs": pairs,
        "spectral_distances": distances,
        "panel": panel,
        "caveats": caveats,
    }


def _prepare(track: dict, ordering: int, x_mode: str) -> dict:
    charts = track.get("charts") or {}
    prepared = {
        "ordering": ordering,
        "asset_id": track.get("asset_id"),
        "original_name": track.get("original_name") or "",
        "sha256": track.get("sha256"),
        "duration_s": _finite_number(track.get("duration_s")),
        "sample_rate": track.get("sample_rate"),
        "channels": track.get("channels"),
        "analysis_status": track.get("analysis_status"),
        "playback_status": track.get("playback_status"),
        "algorithm_version": track.get("algorithm_version"),
        "params_hash": track.get("params_hash"),
        "included": bool(track.get("included")),
        "omit_reason": track.get("omit_reason"),
        "scalars": [],
        "bands": [],
        "below_20_hz": None,
        "pulse": [],
        "endings": _empty_endings(),
        "sample_peak_time_s": None,
        "caveats": [],
        "charts": charts,
        "metrics": track.get("metrics"),
    }
    if not prepared["included"]:
        return prepared
    prepared["scalars"] = [_scalar(prepared, spec) for spec in _SCALARS]
    prepared["bands"] = _bands(charts.get("T03"))
    prepared["below_20_hz"] = summary_number(charts.get("T03") or {}, "Below 20 Hz")
    prepared["pulse"] = _pulse(charts.get("T06"))
    prepared["endings"] = _endings(charts.get("T10"))
    prepared["sample_peak_time_s"] = summary_number(charts.get("T01") or {}, "Sample peak time")
    t02 = charts.get("T02") or {}
    prepared["caveats"] = [str(item) for item in (t02.get("caveats") or [])]
    prepared["_lines"] = _lines(prepared, x_mode)
    return prepared


def _scalar(track: dict, spec: tuple[str, str, str, str, str]) -> dict:
    name, unit, label, method, kind = spec
    charts = track["charts"]
    document = charts.get(kind) if isinstance(charts.get(kind), dict) else None
    evidence = "measured"
    value = None
    if name in _STEREO:
        evidence = _stereo_evidence(track, document)
        if evidence == "measured" and document is not None:
            value = summary_number(document, label)
    elif document is not None and document.get("status") == "ready":
        value = summary_number(document, label)
    else:
        evidence = "unknown"
    row = {
        "name": name,
        "unit": unit,
        "evidence_class": evidence,
        "value": value,
        "method_id": method,
        "metrics_value": None,
    }
    metrics = _metric(track, name)
    if value is not None and metrics is not None and abs(value - metrics) > 0.05:
        row["metrics_value"] = metrics
    return row


def _stereo_evidence(track: dict, document: dict | None) -> str:
    if track.get("channels") == 1:
        return "not_applicable"
    if document is None or document.get("status") != "ready":
        return "unknown"
    if document.get("evidence_class") == "not_applicable":
        return "unknown"
    return "measured"


def _metric(track: dict, name: str) -> float | None:
    metrics = track.get("metrics")
    if not isinstance(metrics, dict):
        return None
    if name == "integrated_loudness":
        loudness = metrics.get("loudness")
        if isinstance(loudness, dict) and "integrated_lufs" in loudness:
            return _finite_number(loudness.get("integrated_lufs"))
        return _finite_number(metrics.get("integrated_lufs"))
    key = {"sample_peak": "sample_peak_dbfs", "rms": "rms_dbfs"}.get(name)
    if key is None or key not in metrics:
        return None
    return _finite_number(metrics.get(key))


def _bands(document: dict | None) -> list[dict]:
    if not isinstance(document, dict):
        return []
    rows = []
    for item in ((document.get("series") or {}).get("bars") or []):
        label = item.get("label")
        if not isinstance(label, str):
            continue
        rows.append({"label": label, "value": _finite_number(item.get("value"))})
    return rows


def _pulse(document: dict | None) -> list[dict]:
    if not isinstance(document, dict) or document.get("status") != "ready":
        return []
    rows = []
    for item in ((document.get("series") or {}).get("bars") or []):
        rows.append(
            {
                "label": str(item.get("label") or ""),
                "value": _finite_number(item.get("value")),
                "evidence_class": "estimated",
            }
        )
    return rows


def _endings(document: dict | None) -> dict:
    if not isinstance(document, dict) or document.get("status") != "ready":
        return _empty_endings()
    silence = []
    for item in document.get("silence") or []:
        start = _finite_number(item.get("start_s"))
        end = _finite_number(item.get("end_s"))
        if start is None or end is None:
            continue
        silence.append({"start_s": start, "end_s": end})
    tails = []
    for item in ((document.get("series") or {}).get("bars") or []):
        tails.append({"label": str(item.get("label") or ""), "value": _finite_number(item.get("value"))})
    return {
        "endpoint": _summary_text(document, "Endpoint"),
        "tails": tails,
        "silence": silence,
        "rail_count": summary_number(document, "Full-scale samples"),
        "reconstructed_peak": summary_number(document, "4x reconstructed peak"),
        "reconstructed_peak_time_s": summary_number(document, "4x peak time"),
    }


def _empty_endings() -> dict:
    return {
        "endpoint": None,
        "tails": [],
        "silence": [],
        "rail_count": None,
        "reconstructed_peak": None,
        "reconstructed_peak_time_s": None,
    }


def _summary_text(document: dict, label: str) -> str | None:
    for item in document.get("summary") or []:
        if item.get("label") == label and item.get("value") not in {None, "undefined", "none"}:
            return str(item["value"])
    return None


def _lines(track: dict, x_mode: str) -> list[dict]:
    document = (track.get("charts") or {}).get("T02") or {}
    stored = {
        line.get("name"): line
        for line in ((document.get("series") or {}).get("lines") or [])
        if isinstance(line, dict)
    }
    copied = []
    for name in _SERIES:
        line = stored.get(name)
        if line is None:
            continue
        copied.append(_copy_line(track, line, x_mode, name))
    return copied


def _copy_line(track: dict, line: dict, x_mode: str, stored_name: str) -> dict:
    xs: list[float | None] = []
    ys: list[float | None] = []
    for x_value, y_value in zip(line.get("x") or [], line.get("y") or [], strict=False):
        if x_mode == "progress":
            xs.append(_progress(x_value, track.get("duration_s")))
        else:
            xs.append(_finite_number(x_value))
        ys.append(None if y_value is None else _finite_number(y_value))
    return {
        "name": f"{track['ordering'] + 1}. {track['original_name']} — {stored_name}",
        "unit": line.get("unit") or "",
        "x": xs,
        "y": ys,
    }


def _panel(tracks: list[dict], x_mode: str, caveats: list[str]) -> dict:
    lines = []
    for track in tracks:
        lines.extend(track.get("_lines") or [])
    return {
        "chart_kind": "T11",
        "status": "ready",
        "title": "Album comparison",
        "evidence_class": "measured",
        "method_id": "stored-m1-v3-series",
        "method_version": COMPARISON_VERSION,
        "caveats": caveats,
        "summary": [],
        "series": {"lines": lines, "bars": [], "heatmap": None},
        "axis_definitions": {
            "x": "Time (s)" if x_mode == "seconds" else "Progress (fraction of duration)",
            "y": "dBFS or LUFS",
            "y_scale": "linear",
        },
        "review_markers": [],
        "not_available_reason": None,
        "error": None,
    }


def _pair(left: dict, right: dict) -> dict:
    left_rows = {item["name"]: item for item in left["scalars"]}
    right_rows = {item["name"]: item for item in right["scalars"]}
    deltas = []
    for name, unit, _label, method, kind in _SCALARS:
        one = left_rows[name]
        other = right_rows[name]
        reason = None
        delta = None
        if one["value"] is None or other["value"] is None:
            reason = "missing_value"
        elif _stored_method(left, kind) != _stored_method(right, kind) or one["unit"] != other["unit"]:
            reason = "method_mismatch"
        else:
            delta = other["value"] - one["value"]
        deltas.append(
            {
                "name": name,
                "unit": _difference_unit(unit),
                "method_id": method,
                "delta": delta,
                "reason": reason,
            }
        )
    return {
        "left_asset_id": left["asset_id"],
        "right_asset_id": right["asset_id"],
        "deltas": deltas,
    }


def _difference_unit(unit: str) -> str:
    """A level difference is not the absolute unit. LUFS differs in LU. dBFS and dBTP differ in dB."""
    if unit == "LUFS":
        return "LU"
    if unit in {"dBFS", "dBTP"}:
        return "dB"
    return unit


def _stored_method(track: dict, kind: str) -> str:
    document = (track.get("charts") or {}).get(kind) or {}
    return str(document.get("method_id") or "")


def _progress(x_value: object, duration: object) -> float | None:
    x_number = _finite_number(x_value)
    duration_number = _finite_number(duration)
    if x_number is None or duration_number is None or duration_number <= 0:
        return None
    return x_number / duration_number


def _fmt(value: float | None, unit: str | None = None) -> str:
    if value is None:
        return "not stored"
    digits = {
        "LUFS": 1,
        "LU": 1,
        "dBFS": 2,
        "dB": 2,
        "dBTP": 2,
        "ratio": 3,
        "s": 3,
        "percentage points": 2,
    }.get(unit or "", 3)
    return f"{value:.{digits}f}"


def _count(value: float | None) -> str:
    if value is None:
        return "not stored"
    if float(value).is_integer():
        return str(int(value))
    return _fmt(value)


def _amount(value: float | None, unit: str) -> str:
    if value is None:
        return "not stored"
    return f"{_fmt(value, unit)} {unit}"


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    if not math.isfinite(number):
        return None
    return number


class AlbumError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message


class ScalarRecord(BaseModel):
    name: str
    unit: str
    evidence_class: str
    value: float | None
    method_id: str
    metrics_value: float | None = None


class BandRecord(BaseModel):
    label: str
    value: float | None


class PulseRecord(BaseModel):
    label: str
    value: float | None
    evidence_class: str


class SilenceRecord(BaseModel):
    start_s: float
    end_s: float


class TailRecord(BaseModel):
    label: str
    value: float | None


class EndingRecord(BaseModel):
    endpoint: str | None
    tails: list[TailRecord]
    silence: list[SilenceRecord]
    rail_count: float | None
    reconstructed_peak: float | None
    reconstructed_peak_time_s: float | None


class TrackRecord(BaseModel):
    ordering: int
    asset_id: str
    original_name: str
    sha256: str
    duration_s: float | None
    sample_rate: int | None
    channels: int | None
    analysis_status: str
    playback_status: str
    algorithm_version: str | None
    params_hash: str | None
    included: bool
    omit_reason: str | None
    scalars: list[ScalarRecord]
    bands: list[BandRecord]
    below_20_hz: float | None
    pulse: list[PulseRecord]
    endings: EndingRecord
    sample_peak_time_s: float | None
    caveats: list[str]


class DeltaRecord(BaseModel):
    name: str
    unit: str
    method_id: str
    delta: float | None
    reason: str | None


class PairRecord(BaseModel):
    left_asset_id: str
    right_asset_id: str
    deltas: list[DeltaRecord]


class DistanceRecord(BaseModel):
    left_asset_id: str
    right_asset_id: str
    status: str
    reason: str | None
    value: float | None
    unit: str
    method_id: str
    evidence_class: str | None = None


class SummaryRecord(BaseModel):
    label: str
    value: str


class AxisRecord(BaseModel):
    x: str = ""
    y: str = ""
    y_scale: str = "linear"


class AlbumChartLine(BaseModel):
    name: str
    unit: str
    x: list[float | None]
    y: list[float | None]


class AlbumChartBar(BaseModel):
    label: str
    value: float


class AlbumChartSeries(BaseModel):
    lines: list[AlbumChartLine] = Field(default_factory=list)
    bars: list[AlbumChartBar] = Field(default_factory=list)
    heatmap: None = None


class AlbumChart(BaseModel):
    chart_kind: str
    status: str
    title: str
    evidence_class: str
    method_id: str
    method_version: str
    caveats: list[str]
    summary: list[SummaryRecord]
    series: AlbumChartSeries
    axis_definitions: AxisRecord
    review_markers: list[dict] = Field(default_factory=list)
    not_available_reason: str | None = None
    error: str | None = None


class ComparisonDocument(BaseModel):
    comparison_version: str
    project_id: str
    name: str
    status: str
    not_available_reason: str | None
    x_mode: str
    tracks: list[TrackRecord]
    pairs: list[PairRecord]
    spectral_distances: list[DistanceRecord]
    panel: AlbumChart | None
    caveats: list[str]


class ReviewRecord(BaseModel):
    asset_id: str
    checkpoint_id: str
    status: str
    note: str
    value: float | None
    unit: str | None
    time_s: float | None
    fact: str


class AlbumExportManifest(BaseModel):
    export_id: str
    project_id: str
    comparison_version: str
    report_version: str
    content_sha256: str
    created_at: str
    files: list[str]


_READ_KINDS = ("T01", "T02", "T03", "T05", "T06", "T10")
_STATUSES = {"unchecked", "confirmed_issue", "intentional", "not_audible"}


def require_album(conn: sqlite3.Connection, project_id: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    if row is None:
        raise AlbumError(404, "not_found", "Project not found.")
    if row["mode"] != "album":
        raise AlbumError(404, "not_album", "That project is not an album.")
    return row


def add_member(conn: sqlite3.Connection, project_id: str, asset_id: str) -> dict:
    require_album(conn, project_id)
    asset = conn.execute("SELECT id FROM assets WHERE id = ?", (asset_id,)).fetchone()
    if asset is None:
        raise AlbumError(404, "unknown_asset", "That recording is not in the library.")
    existing = conn.execute(
        "SELECT 1 AS present FROM project_assets WHERE project_id = ? AND asset_id = ?",
        (project_id, asset_id),
    ).fetchone()
    if existing is not None:
        raise AlbumError(409, "already_member", "That recording is already in the album.")
    order = conn.execute(
        "SELECT COALESCE(MAX(ordering), -1) + 1 AS next_order FROM project_assets WHERE project_id = ?",
        (project_id,),
    ).fetchone()["next_order"]
    conn.execute(
        "INSERT INTO project_assets (project_id, asset_id, ordering) VALUES (?, ?, ?)",
        (project_id, asset_id, order),
    )
    conn.commit()
    return {"asset_id": asset_id, "ordering": order}


_KEPT_RECORDS = (
    ("lyric_documents", "a lyric document"),
    ("lyric_uploads", "a lyric upload"),
    ("annotations", "an annotation"),
    ("export_runs", "a published export"),
)


def _kept_records(conn: sqlite3.Connection, project_id: str, asset_id: str) -> list[str]:
    found = []
    for table, label in _KEPT_RECORDS:
        row = conn.execute(
            f"SELECT 1 AS present FROM {table} WHERE project_id = ? AND asset_id = ?",
            (project_id, asset_id),
        ).fetchone()
        if row is not None:
            found.append(label)
    return found


def remove_member(conn: sqlite3.Connection, project_id: str, asset_id: str) -> None:
    require_album(conn, project_id)
    existing = conn.execute(
        "SELECT 1 AS present FROM project_assets WHERE project_id = ? AND asset_id = ?",
        (project_id, asset_id),
    ).fetchone()
    if existing is None:
        raise AlbumError(404, "unknown_asset", "That recording is not in the album.")
    kept = _kept_records(conn, project_id, asset_id)
    if kept:
        raise AlbumError(
            409,
            "member_has_records",
            "This album link has " + " and ".join(kept) + ". Those records were kept.",
        )
    try:
        conn.execute(
            "DELETE FROM project_assets WHERE project_id = ? AND asset_id = ?",
            (project_id, asset_id),
        )
        conn.execute(
            "DELETE FROM album_reviews WHERE project_id = ? AND asset_id = ?",
            (project_id, asset_id),
        )
        rows = conn.execute(
            """
            SELECT asset_id FROM project_assets
            WHERE project_id = ?
            ORDER BY ordering, asset_id
            """,
            (project_id,),
        ).fetchall()
        for index, row in enumerate(rows):
            conn.execute(
                "UPDATE project_assets SET ordering = ? WHERE project_id = ? AND asset_id = ?",
                (index, project_id, row["asset_id"]),
            )
        conn.commit()
    except AlbumError:
        conn.rollback()
        raise
    except Exception as exc:
        conn.rollback()
        raise AlbumError(500, "member_not_removed", "The recording was not removed.") from exc


def reorder(conn: sqlite3.Connection, project_id: str, asset_ids: list[str]) -> dict:
    require_album(conn, project_id)
    current = [
        row["asset_id"]
        for row in conn.execute(
            "SELECT asset_id FROM project_assets WHERE project_id = ? ORDER BY ordering",
            (project_id,),
        ).fetchall()
    ]
    if len(asset_ids) != len(current) or sorted(asset_ids) != sorted(current):
        raise AlbumError(400, "invalid_order", "The order must list each album recording once.")
    for index, asset_id in enumerate(asset_ids):
        conn.execute(
            "UPDATE project_assets SET ordering = ? WHERE project_id = ? AND asset_id = ?",
            (index, project_id, asset_id),
        )
    conn.commit()
    return {"asset_ids": asset_ids}


def build_comparison(
    conn: sqlite3.Connection, data_root: Path, project_id: str, x_mode: str
) -> dict:
    project = require_album(conn, project_id)
    tracks = [_load_track(data_root, row) for row in _member_rows(conn, project_id)]
    return compare(tracks, x_mode, project_id=project["id"], name=project["name"])


def review_view(conn: sqlite3.Connection, data_root: Path, project_id: str) -> list[dict]:
    document = build_comparison(conn, data_root, project_id, "seconds")
    stored = {
        (row["asset_id"], row["checkpoint_id"]): row
        for row in conn.execute(
            "SELECT asset_id, checkpoint_id, status, note FROM album_reviews WHERE project_id = ?",
            (project_id,),
        ).fetchall()
    }
    view = []
    for item in _applicable(document):
        saved = stored.get((item["asset_id"], item["checkpoint_id"]))
        view.append(
            {
                **item,
                "status": saved["status"] if saved is not None else "unchecked",
                "note": saved["note"] if saved is not None else "",
            }
        )
    return view


def save_review(
    conn: sqlite3.Connection,
    data_root: Path,
    project_id: str,
    asset_id: str,
    checkpoint_id: str,
    status: str,
    note: str,
) -> dict:
    require_album(conn, project_id)
    if status not in _STATUSES:
        raise AlbumError(400, "invalid_status", "The listening status is not recognized.")
    if len(note) > 500:
        raise AlbumError(400, "invalid_note", "A listening note is at most 500 characters.")
    if asset_id != "":
        member = conn.execute(
            "SELECT 1 AS present FROM project_assets WHERE project_id = ? AND asset_id = ?",
            (project_id, asset_id),
        ).fetchone()
        if member is None:
            raise AlbumError(404, "unknown_asset", "That recording is not in the album.")
    current = review_view(conn, data_root, project_id)
    match = next(
        (item for item in current if item["asset_id"] == asset_id and item["checkpoint_id"] == checkpoint_id),
        None,
    )
    if match is None:
        raise AlbumError(400, "checkpoint_not_applicable", "That checkpoint does not apply to this album.")
    conn.execute(
        """
        INSERT INTO album_reviews (
          project_id, asset_id, checkpoint_id, status, note, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT (project_id, asset_id, checkpoint_id)
        DO UPDATE SET status = excluded.status, note = excluded.note, updated_at = excluded.updated_at
        """,
        (project_id, asset_id, checkpoint_id, status, note, datetime.now(UTC).isoformat()),
    )
    conn.commit()
    return next(
        item
        for item in review_view(conn, data_root, project_id)
        if item["asset_id"] == asset_id and item["checkpoint_id"] == checkpoint_id
    )


def _member_rows(conn: sqlite3.Connection, project_id: str) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT assets.*, project_assets.ordering AS album_ordering
        FROM assets
        JOIN project_assets ON project_assets.asset_id = assets.id
        WHERE project_assets.project_id = ?
        ORDER BY project_assets.ordering, assets.created_at
        """,
        (project_id,),
    ).fetchall()


def _load_track(data_root: Path, row: sqlite3.Row) -> dict:
    sha = row["sha256"]
    analysis = data_root / "analysis" / sha / "m1-v3"
    metrics = _read_json(analysis / "metrics.json")
    charts = {}
    for kind in _READ_KINDS:
        document = _read_json(analysis / f"{kind}.json")
        if document is not None:
            charts[kind] = document
    included, reason = _inclusion(row, metrics, charts)
    version = metrics.get("algorithm_version") if isinstance(metrics, dict) else None
    params = metrics.get("params_hash") if isinstance(metrics, dict) else None
    return {
        "asset_id": row["id"],
        "original_name": row["original_name"],
        "sha256": sha,
        "duration_s": row["duration_s"],
        "sample_rate": row["sample_rate"],
        "channels": row["channels"],
        "analysis_status": row["analysis_status"],
        "playback_status": row["playback_status"],
        "included": included,
        "omit_reason": reason,
        "algorithm_version": version,
        "params_hash": params,
        "metrics": metrics,
        "charts": charts,
    }


def _inclusion(row: sqlite3.Row, metrics: dict | None, charts: dict) -> tuple[bool, str | None]:
    if row["analysis_status"] != "completed":
        return False, "analysis_incomplete"
    if not isinstance(metrics, dict) or metrics.get("algorithm_version") != "m1-v3":
        return False, "unsupported_analysis_version"
    if any(kind not in charts for kind in ("T01", "T02", "T03")):
        return False, "chart_missing"
    return True, None


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _applicable(document: dict) -> list[dict]:
    rows = []
    for track in document["tracks"]:
        if not track["included"]:
            continue
        scalars = {item["name"]: item for item in track["scalars"]}
        peak = scalars["sample_peak"]
        rows.append(
            _checkpoint(
                track["asset_id"],
                "sample_peak",
                peak["value"],
                peak["unit"],
                track.get("sample_peak_time_s"),
                _timed("Sample peak", peak["value"], peak["unit"], track.get("sample_peak_time_s")),
            )
        )
        true_peak = scalars["ffmpeg_true_peak"]
        if true_peak["value"] is not None:
            rows.append(
                _checkpoint(
                    track["asset_id"],
                    "ffmpeg_true_peak",
                    true_peak["value"],
                    true_peak["unit"],
                    None,
                    _timed("FFmpeg true peak", true_peak["value"], true_peak["unit"], None),
                )
            )
        reconstructed = scalars["reconstructed_peak"]
        peak_time = track["endings"]["reconstructed_peak_time_s"]
        if reconstructed["value"] is not None:
            rows.append(
                _checkpoint(
                    track["asset_id"],
                    "reconstructed_peak",
                    reconstructed["value"],
                    reconstructed["unit"],
                    peak_time,
                    _timed("4x reconstructed peak", reconstructed["value"], reconstructed["unit"], peak_time),
                )
            )
        rail = track["endings"]["rail_count"]
        rows.append(
            _checkpoint(
                track["asset_id"],
                "full_scale_rail",
                rail,
                "samples",
                None,
                f"Full-scale sample count {_count(rail)}.",
            )
        )
        endpoint = track["endings"]["endpoint"]
        rows.append(
            _checkpoint(
                track["asset_id"],
                "endpoint",
                None,
                None,
                None,
                f"Endpoint {endpoint}.",
            )
        )
        tails = [item for item in track["endings"]["tails"] if item.get("value") is not None]
        if tails:
            tail = tails[-1]
            rows.append(
                _checkpoint(
                    track["asset_id"],
                    "tail_level",
                    tail["value"],
                    "dBFS",
                    None,
                    f"{tail['label']} {_amount(tail['value'], 'dBFS')}.",
                )
            )
        silence = track["endings"]["silence"]
        rows.append(
            _checkpoint(
                track["asset_id"],
                "subthreshold",
                float(len(silence)),
                "intervals",
                silence[0]["start_s"] if silence else None,
                "no sub-threshold interval stored"
                if not silence
                else f"{len(silence)} sub-threshold intervals stored.",
            )
        )
        if scalars["correlation"]["evidence_class"] == "measured":
            rows.append(
                _checkpoint(
                    track["asset_id"],
                    "mono_compatibility",
                    scalars["correlation"]["value"],
                    scalars["correlation"]["unit"],
                    None,
                    (
                        "Correlation "
                        f"{_fmt(scalars['correlation']['value'], 'ratio')}, mono fold-down "
                        f"{_amount(scalars['mono_fold_down']['value'], 'dB')}, below 120 Hz correlation "
                        f"{_fmt(scalars['sub_bass_correlation']['value'], 'ratio')}."
                    ),
                )
            )
    spread = _level_spread(document)
    if spread is not None:
        rows.append(spread)
    return rows


def _level_spread(document: dict) -> dict | None:
    values = []
    for track in document["tracks"]:
        if not track["included"]:
            continue
        for item in track["scalars"]:
            if item["name"] == "integrated_loudness" and item["value"] is not None:
                values.append(item["value"])
    if len(values) < 2:
        return None
    spread = max(values) - min(values)
    return _checkpoint(
        "",
        "level_spread",
        spread,
        "LU",
        None,
        f"Maximum integrated loudness minus minimum is {_amount(spread, 'LU')}.",
    )


def _checkpoint(
    asset_id: str,
    checkpoint_id: str,
    value: float | None,
    unit: str | None,
    time_s: float | None,
    fact: str,
) -> dict:
    return {
        "asset_id": asset_id,
        "checkpoint_id": checkpoint_id,
        "value": value,
        "unit": unit,
        "time_s": time_s,
        "fact": fact,
    }


def _timed(label: str, value: float | None, unit: str, time_s: float | None) -> str:
    if value is None:
        return f"{label} is not stored."
    text = f"{label} {_amount(value, unit)}".strip()
    if time_s is None:
        return f"{text}."
    return f"{text} at {_fmt(time_s, 's')} s."


_REPORT_HEADINGS = (
    "Album",
    "Order",
    "Level",
    "Spectrum",
    "Stereo",
    "Dynamics",
    "Rhythm",
    "Endings",
    "Listening review",
    "Methods",
    "Limitations",
)
_CONTENT_NAMES = ("album-report.md", "comparison.json")


def render_report(document: dict, reviews: list[dict]) -> str:
    sections = {
        "Album": _report_album(document),
        "Order": _report_order(document),
        "Level": _report_level(document),
        "Spectrum": _report_spectrum(document),
        "Stereo": _report_stereo(document),
        "Dynamics": _report_dynamics(document),
        "Rhythm": _report_rhythm(document),
        "Endings": _report_endings(document),
        "Listening review": _report_reviews(document, reviews),
        "Methods": _report_methods(),
        "Limitations": _report_limits(document),
    }
    return "".join(f"## {heading}\n\n{sections[heading].strip()}\n\n" for heading in _REPORT_HEADINGS)


def publish_album_export(conn: sqlite3.Connection, data_root: Path, project_id: str) -> dict:
    document = build_comparison(conn, data_root, project_id, "seconds")
    if document["status"] != "ready" or not document.get("panel"):
        raise AlbumError(400, "comparison_not_ready", "An album export needs two analyzed recordings.")
    reviews = review_view(conn, data_root, project_id)
    report = render_report(document, reviews).encode()
    comparison = _dumps(document)
    content = {"album-report.md": report, "comparison.json": comparison}
    content_hash = _content_sha256(content)
    try:
        png = _png_bytes(document["panel"])
    except AlbumError:
        raise
    except Exception as exc:
        raise AlbumError(500, "export_failed", "The album export was not published.") from exc
    export_id = str(uuid.uuid4())
    created = datetime.now(UTC).isoformat()
    manifest = {
        "export_id": export_id,
        "project_id": project_id,
        "comparison_version": COMPARISON_VERSION,
        "report_version": REPORT_VERSION,
        "content_sha256": content_hash,
        "created_at": created,
        "files": [
            "album-report.md",
            "charts/T11_album_comparison.png",
            "comparison.json",
            "manifest.json",
        ],
    }
    files = {
        **content,
        "charts/T11_album_comparison.png": png,
        "manifest.json": _dumps(manifest),
    }
    root = data_root / "exports"
    root.mkdir(parents=True, exist_ok=True)
    temp_zip = root / f".{export_id}.zip.tmp"
    final = root / f"{export_id}.zip"
    try:
        _zip_files(temp_zip, files)
        _validate_zip(temp_zip, manifest)
        if final.exists():
            raise AlbumError(500, "export_failed", "The album export was not published.")
        os.replace(temp_zip, final)
        try:
            conn.execute(
                """
                INSERT INTO album_export_runs (
                  id, project_id, comparison_version, report_version, content_sha256, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (export_id, project_id, COMPARISON_VERSION, REPORT_VERSION, content_hash, created),
            )
            conn.commit()
        except Exception:
            final.unlink(missing_ok=True)
            raise
    except AlbumError:
        raise
    except Exception as exc:
        raise AlbumError(500, "export_failed", "The album export was not published.") from exc
    finally:
        if temp_zip.exists():
            temp_zip.unlink()
    return manifest


def open_album_export(conn: sqlite3.Connection, data_root: Path, project_id: str, export_id: str) -> Path:
    require_album(conn, project_id)
    try:
        parsed = uuid.UUID(export_id)
    except ValueError:
        raise AlbumError(404, "not_found", "No album export with that id exists.") from None
    if str(parsed) != export_id:
        raise AlbumError(404, "not_found", "No album export with that id exists.")
    row = conn.execute(
        "SELECT id FROM album_export_runs WHERE id = ? AND project_id = ?",
        (export_id, project_id),
    ).fetchone()
    path = data_root / "exports" / f"{export_id}.zip"
    if row is None or not path.is_file():
        raise AlbumError(404, "not_found", "No album export with that id exists.")
    return path


def _png_bytes(panel: dict) -> bytes:
    figure = render_figure(panel)
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png")
    plt.close(figure)
    data = buffer.getvalue()
    if len(data) <= 32 or not data.startswith(b"\x89PNG\r\n\x1a\n") or b"IEND" not in data[-32:]:
        raise AlbumError(500, "export_failed", "The album figure was not published.")
    return data


def _dumps(payload: dict) -> bytes:
    return (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode()


def _content_sha256(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name in sorted(files):
        payload = files[name]
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(len(payload).to_bytes(8, "big"))
        digest.update(payload)
    return digest.hexdigest()


def _zip_files(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        for name in sorted(files):
            if name.startswith("/") or ".." in name.split("/") or name.endswith(".wav"):
                raise AlbumError(500, "export_failed", "The album export was not published.")
            info = zipfile.ZipInfo(filename=name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, files[name])


def _validate_zip(path: Path, manifest: dict) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if set(names) != set(manifest["files"]):
            raise AlbumError(500, "export_failed", "The album export was not published.")
        content: dict[str, bytes] = {}
        for name in names:
            if name.startswith("/") or ".." in name.split("/") or name.endswith(".wav"):
                raise AlbumError(500, "export_failed", "The album export was not published.")
            payload = archive.read(name)
            if name.endswith(".png") and (
                len(payload) <= 32 or not payload.startswith(b"\x89PNG\r\n\x1a\n") or b"IEND" not in payload[-32:]
            ):
                raise AlbumError(500, "export_failed", "The album export was not published.")
            if name in _CONTENT_NAMES:
                content[name] = payload
        if _content_sha256(content) != manifest["content_sha256"]:
            raise AlbumError(500, "export_failed", "The album export was not published.")


_MEASUREMENT_LABELS = {
    "integrated_loudness": "Integrated loudness",
    "loudness_range": "Loudness range",
    "sample_peak": "Sample peak",
    "rms": "Whole-file RMS",
    "crest_factor": "Crest factor",
    "ffmpeg_true_peak": "FFmpeg true peak",
    "reconstructed_peak": "4× reconstructed peak",
    "correlation": "Whole-file correlation",
    "side_mid": "Side/mid",
    "mono_fold_down": "Mono fold-down change",
    "sub_bass_correlation": "Correlation below 120 Hz",
}
_CHECKPOINT_LABELS = {
    "full_scale_rail": "Full-scale samples",
    "endpoint": "Endpoint",
    "tail_level": "Ending level",
    "subthreshold": "Sub-threshold intervals",
    "level_spread": "Loudness spread",
}
_STATUS_LABELS = {
    "unchecked": "Unchecked",
    "confirmed_issue": "Confirmed issue",
    "intentional": "Intentional",
    "not_audible": "Not audible",
}
_OMIT_LABELS = {
    "analysis_incomplete": "Analysis incomplete",
    "unsupported_analysis_version": "Unsupported analysis version",
    "chart_missing": "Required charts missing",
}
_EVIDENCE_LABELS = {
    "measured": "Measured",
    "estimated": "Estimated",
    "textual": "Textual",
    "interpretive": "Interpretive",
    "unknown": "Unknown",
    "not_applicable": "Not applicable",
}


def _measurement_label(name: str) -> str:
    return _MEASUREMENT_LABELS.get(name, name)


def _checkpoint_label(checkpoint_id: str) -> str:
    return _CHECKPOINT_LABELS.get(checkpoint_id, _measurement_label(checkpoint_id))


def _status_label(status: str) -> str:
    return _STATUS_LABELS.get(status, status)


def _omit_label(reason: str | None) -> str:
    if not reason:
        return "Not included"
    return _OMIT_LABELS.get(reason, reason)


def _evidence_label(evidence: str) -> str:
    return _EVIDENCE_LABELS.get(evidence, evidence)


def _report_album(document: dict) -> str:
    included = sum(1 for track in document["tracks"] if track["included"])
    return "\n".join(
        [
            f"Name: {document['name']}",
            f"Project: {document['project_id']}",
            f"Status: {document['status']}",
            f"Recordings: {len(document['tracks'])}",
            f"Included recordings: {included}",
            f"Comparison version: {document['comparison_version']}",
            f"Report version: {REPORT_VERSION}",
        ]
    )


def _report_order(document: dict) -> str:
    lines = []
    for track in document["tracks"]:
        reason = "Included" if track["included"] else _omit_label(track["omit_reason"])
        lines.append(
            f"{track['ordering'] + 1}. {track['original_name']} "
            f"sha256 {track['sha256']} {reason} {_fmt(_finite_number(track['duration_s']), 's')} s "
            f"{_count(_finite_number(track['sample_rate']))} Hz {_count(_finite_number(track['channels']))} ch"
        )
    return "\n".join(lines)


def _recording(document: dict, asset_id: str) -> str:
    if asset_id == "":
        return "Album"
    for track in document["tracks"]:
        if track["asset_id"] == asset_id:
            return f"{track['ordering'] + 1}. {track['original_name']}"
    return asset_id


def _report_level(document: dict) -> str:
    lines = [
        "Absolute integrated loudness is LUFS. Its difference is LU.",
        "Absolute sample peak and whole-file RMS are dBFS. Their differences are dB.",
        "Absolute FFmpeg true peak and the 4× reconstructed peak stay dBTP. A difference of one true-peak measurement is dB. Those two measurements are not subtracted from each other.",
        "A difference is the later recording minus the earlier recording.",
    ]
    for track in document["tracks"]:
        if not track["included"]:
            continue
        lines.append(_recording(document, track["asset_id"]))
        for item in track["scalars"]:
            if item["unit"] in {"LUFS", "LU", "dBFS", "dBTP"}:
                lines.append(
                    f"- {_measurement_label(item['name'])}: {_amount(item['value'], item['unit'])} "
                    f"({_evidence_label(item['evidence_class'])})"
                )
    for pair in document["pairs"]:
        later = _recording(document, pair["right_asset_id"])
        earlier = _recording(document, pair["left_asset_id"])
        for item in pair["deltas"]:
            if item["delta"] is None or item["unit"] not in {"LU", "dBFS", "dBTP", "dB"}:
                continue
            lines.append(
                f"- {later} minus {earlier}, {_measurement_label(item['name'])}: "
                f"{_amount(item['delta'], item['unit'])}"
            )
    return "\n".join(lines)


def _report_spectrum(document: dict) -> str:
    lines = [
        "Band-share distance uses stored T03 percentages. The Welch PSD line is not overlaid.",
        "The chart contract still calls for spectrum overlays. This report does not draw them.",
    ]
    for row in document["spectral_distances"]:
        shown = "not stored" if row["value"] is None else _amount(row["value"], row["unit"])
        lines.append(
            f"- {_recording(document, row['left_asset_id'])} to "
            f"{_recording(document, row['right_asset_id'])}: "
            f"{shown} {row['reason'] or row['status']}"
        )
    return "\n".join(lines)


def _report_stereo(document: dict) -> str:
    lines = []
    for track in document["tracks"]:
        if not track["included"]:
            continue
        for item in track["scalars"]:
            if item["name"] in {"correlation", "side_mid", "mono_fold_down", "sub_bass_correlation"}:
                lines.append(
                    f"- {_recording(document, track['asset_id'])} {_measurement_label(item['name'])}: "
                    f"{_amount(item['value'], item['unit'])} ({_evidence_label(item['evidence_class'])})"
                )
    return "\n".join(lines) or "No stereo scalars are stored."


def _report_dynamics(document: dict) -> str:
    lines = ["Loudness range is LU. Crest factor is dB. They are not subtracted."]
    for track in document["tracks"]:
        if not track["included"]:
            continue
        for item in track["scalars"]:
            if item["name"] in {"loudness_range", "crest_factor"}:
                lines.append(
                    f"- {_recording(document, track['asset_id'])} {_measurement_label(item['name'])}: "
                    f"{_amount(item['value'], item['unit'])}"
                )
    return "\n".join(lines)


def _report_rhythm(document: dict) -> str:
    lines = [
        "Pulse candidates are provisional onset-autocorrelation estimates, not a beat grid.",
        "Each score is normalized autocorrelation at that lag. It is not a probability and not a confirmed tempo.",
    ]
    for track in document["tracks"]:
        if not track["included"]:
            continue
        if not track["pulse"]:
            lines.append(f"- {_recording(document, track['asset_id'])}: no pulse candidate stored")
            continue
        for item in track["pulse"]:
            score = "not stored" if item["value"] is None else f"{_fmt(item['value'], 'ratio')} autocorrelation"
            lines.append(
                f"- {_recording(document, track['asset_id'])} {item['label']}: "
                f"{score} ({_evidence_label(item['evidence_class'])})"
            )
    return "\n".join(lines)


def _report_endings(document: dict) -> str:
    lines = ["4× reconstructed peak is not the FFmpeg true peak."]
    for track in document["tracks"]:
        if not track["included"]:
            continue
        ending = track["endings"]
        lines.append(
            f"- {_recording(document, track['asset_id'])} endpoint {ending['endpoint']}, "
            f"full-scale samples {_count(ending['rail_count'])}, "
            f"reconstructed peak {_amount(ending['reconstructed_peak'], 'dBTP')}, "
            f"sub-threshold intervals {len(ending['silence'])}"
        )
        for tail in ending["tails"]:
            lines.append(
                f"- {_recording(document, track['asset_id'])} {tail['label']}: {_amount(tail['value'], 'dBFS')}"
            )
    return "\n".join(lines)


def _report_reviews(document: dict, reviews: list[dict]) -> str:
    if not reviews:
        return "No listening checkpoint applies."
    lines = ["A listening status is a human attribution. The measurement text is unchanged by that status."]
    for item in reviews:
        note = f" Note: {item['note']}" if item["note"] else ""
        lines.append(
            f"- {_recording(document, item['asset_id'])}, {_checkpoint_label(item['checkpoint_id'])}: "
            f"{_status_label(item['status'])}. {item['fact']}{note}"
        )
    return "\n".join(lines)


def _report_methods() -> str:
    methods = [
        COMPARISON_VERSION,
        REPORT_VERSION,
        "band-share-l1-v1",
        "stored-m1-v3-series",
    ]
    methods.extend(spec[3] for spec in _SCALARS)
    return "\n".join(f"- {item}" for item in methods)


def _report_limits(document: dict) -> str:
    lines = list(document["caveats"])
    lines.append("The application did not listen to these recordings.")
    lines.append("PNG bytes are outside the content hash.")
    lines.append(
        "A crash after the ZIP is replaced and before the SQLite insert can leave an unlisted exports file."
    )
    lines.append("The chart contract's Welch PSD overlay remains deferred. No PSD samples were invented.")
    return "\n".join(f"- {line}" for line in lines)
