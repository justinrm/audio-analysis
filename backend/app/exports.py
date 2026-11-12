"""Deterministic Technical, Lyricist, and Combined ZIP snapshots.

Exports copy stored evidence. They do not decode a WAV, remeasure, or rewrite
the analysis cache. The ZIP is replaced into exports/{id}.zip before the
SQLite row is inserted. A crash between those two steps can leave an unlisted
exports/{id}.zip. That file is not a successful export. A failed insert deletes
it when the process is still alive.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from app.charts import KINDS, not_run
from app.lyric_charts import LYRIC_KINDS, build_lyric_chart, load_stored_charts
from app.lyric_png import LYRIC_RENDERER_VERSION, write_lyric_png

BRIEF_TEMPLATE_VERSION = "lyric-brief-v2"
_OBSERVATION_CAP = 8
_REPEAT_CAP = 5
_CONTRAST_CAP = 3
_CLASS_ORDER = {
    "measured": 0,
    "estimated": 1,
    "textual": 2,
    "interpretive": 3,
    "unknown": 4,
    "not_applicable": 5,
}
from app.lyrics import LyricError, canonical_evidence, load_document, require_membership
from app.png import RENDERER_VERSION, rendered_png

_G3 = (
    "Stored T03 power remains labeled dB, not dB/Hz. "
    "This package does not relabel that measurement."
)
_G6 = (
    "Technical PNGs in a new package are png-r2 copies. "
    "Stored bar series are drawn on a separate panel from line series. "
    "Historical png-r1 files stay on disk and are not copied."
)


class ExportError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        self.status = status
        self.code = code
        self.message = message


def create_export(
    conn: sqlite3.Connection,
    data_root: Path,
    project_id: str,
    asset_id: str,
    profile: str,
    lyrics_mode: str,
) -> dict:
    temp_dir: Path | None = None
    temp_zip: Path | None = None
    try:
        asset = require_membership(conn, project_id, asset_id)
        export_id = str(uuid.uuid4())
        root = data_root / "exports"
        root.mkdir(parents=True, exist_ok=True)
        temp_dir = root / f".{export_id}.tmp"
        temp_zip = root / f".{export_id}.zip.tmp"
        final = root / f"{export_id}.zip"
        files, manifest = _assemble(
            conn,
            data_root,
            project_id,
            asset_id,
            asset,
            export_id,
            profile,
            lyrics_mode,
            temp_dir,
        )
        _zip_files(temp_zip, files)
        _validate(temp_zip, manifest)
        if final.exists():
            raise ExportError(500, "export_failed", "The export was not published.")
        os.replace(temp_zip, final)
        try:
            _insert_run(conn, manifest)
        except Exception:
            final.unlink(missing_ok=True)
            raise
        return manifest
    except (LyricError, ExportError):
        raise
    except Exception as exc:
        raise ExportError(500, "export_failed", "The export was not published.") from exc
    finally:
        if temp_dir is not None:
            shutil.rmtree(temp_dir, ignore_errors=True)
        if temp_zip is not None and temp_zip.exists():
            temp_zip.unlink()


def open_export(
    conn: sqlite3.Connection,
    data_root: Path,
    project_id: str,
    asset_id: str,
    export_id: str,
) -> tuple[Path, str]:
    try:
        parsed = uuid.UUID(export_id)
    except ValueError:
        raise ExportError(404, "not_found", "No export with that id exists.") from None
    if str(parsed) != export_id:
        raise ExportError(404, "not_found", "No export with that id exists.")
    require_membership(conn, project_id, asset_id)
    row = conn.execute(
        """
        SELECT profile FROM export_runs
        WHERE id = ? AND project_id = ? AND asset_id = ?
        """,
        (export_id, project_id, asset_id),
    ).fetchone()
    if row is None:
        raise ExportError(404, "not_found", "No export with that id exists.")
    path = data_root / "exports" / f"{export_id}.zip"
    if not path.is_file():
        raise ExportError(404, "not_found", "No export with that id exists.")
    return path, row["profile"]


def _insert_run(conn: sqlite3.Connection, manifest: dict) -> None:
    conn.execute(
        """
        INSERT INTO export_runs (
          id, project_id, asset_id, profile, lyrics_mode, lyric_revision,
          source_sha256, algorithm_version, params_hash, content_sha256, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            manifest["export_id"],
            manifest["project_id"],
            manifest["asset_id"],
            manifest["profile"],
            manifest["lyrics_mode"],
            manifest["lyric_revision"],
            manifest["source_sha256"],
            manifest["algorithm_version"],
            manifest["params_hash"],
            manifest["content_sha256"],
            manifest["created_at"],
        ),
    )
    conn.commit()


def _assemble(
    conn: sqlite3.Connection,
    data_root: Path,
    project_id: str,
    asset_id: str,
    asset: sqlite3.Row,
    export_id: str,
    profile: str,
    lyrics_mode: str,
    temp_dir: Path,
) -> tuple[dict[str, bytes], dict]:
    sha = asset["sha256"]
    analysis = data_root / "analysis" / sha / "m1-v3"
    metrics = _json_file(analysis / "metrics.json")
    files: dict[str, bytes] = {}
    png_unavailable: list[str] = []
    if profile in {"technical", "combined"}:
        chart_files, png_unavailable = _technical_charts(analysis)
        files.update(chart_files)
        metrics_bytes = _copy_or_dump(analysis / "metrics.json", _absent_metrics(sha))
        if profile == "technical":
            files["technical/metrics.json"] = metrics_bytes
            files["technical/evidence.json"] = _copy_or_dump(
                analysis / "evidence.json", {"status": "not_run", "records": []}
            )
        else:
            files["metrics.json"] = metrics_bytes
    document = None
    bundle = None
    if profile in {"lyricist", "combined"}:
        document = load_document(conn, project_id, asset_id)
        if document is None:
            raise LyricError(409, "no_lyrics", "No lyric document is attached.")
        bundle = canonical_evidence(conn, data_root, project_id, asset_id)
        if (
            bundle.get("lyric_document_id") != document["id"]
            or bundle.get("lyric_revision") != document["revision"]
        ):
            raise ExportError(
                409,
                "lyric_conflict",
                "The lyric document changed during export. Try again.",
            )
        stored = load_stored_charts(data_root, sha)
        built = [build_lyric_chart(kind, bundle, stored, document) for kind in LYRIC_KINDS]
        evidence = _redact_evidence(bundle, lyrics_mode)
        charts = [_redact_chart(chart, lyrics_mode, evidence) for chart in built]
        evidence_name = "evidence.json" if profile == "combined" else "lyricist/evidence.json"
        files[evidence_name] = _dumps(evidence)
        for chart in charts:
            kind = chart["chart_kind"]
            files[f"lyricist/charts/{kind}.json"] = _dumps(chart)
            png_path = temp_dir / "lyricist" / "charts" / f"{kind}.png"
            write_lyric_png(png_path, chart)
            files[f"lyricist/charts/{kind}.png"] = png_path.read_bytes()
        files["lyricist/brief.md"] = _brief(
            sha, metrics, document, lyrics_mode, charts, evidence
        ).encode()
        files["lyricist/README.md"] = _lyric_readme(sha, metrics, document, lyrics_mode).encode()
    if profile == "technical":
        files["technical/README.md"] = _technical_readme(sha, metrics, None, lyrics_mode).encode()
    elif profile == "combined":
        files["technical/README.md"] = _technical_readme(sha, metrics, document, lyrics_mode).encode()
        files["README.md"] = _combined_readme(sha, metrics, document, lyrics_mode).encode()
    created_at = datetime.now(UTC).isoformat()
    manifest_name = "manifest.json" if profile == "combined" else f"{profile}/manifest.json"
    content = {name: payload for name, payload in files.items() if _is_content(name)}
    manifest = {
        "export_id": export_id,
        "project_id": project_id,
        "asset_id": asset_id,
        "profile": profile,
        "lyrics_mode": lyrics_mode,
        "narrative": "none",
        "source_sha256": sha,
        "algorithm_version": None if metrics is None else metrics.get("algorithm_version"),
        "params_hash": None if metrics is None else metrics.get("params_hash"),
        "renderer_version": RENDERER_VERSION,
        "lyric_renderer_version": None if document is None else LYRIC_RENDERER_VERSION,
        "brief_template_version": None if document is None else BRIEF_TEMPLATE_VERSION,
        "lyric_document_id": None if document is None else document["id"],
        "lyric_revision": None if document is None else document["revision"],
        "lyric_source_sha256": None if document is None else document["source_sha256"],
        "content_sha256": _content_sha256(content),
        "created_at": created_at,
        "png_unavailable": png_unavailable,
        "files": sorted([*files.keys(), manifest_name]),
    }
    files[manifest_name] = _dumps(manifest)
    return files, manifest


def _technical_charts(analysis: Path) -> tuple[dict[str, bytes], list[str]]:
    files: dict[str, bytes] = {}
    missing: list[str] = []
    for kind in KINDS:
        path = analysis / f"{kind}.json"
        if path.is_file():
            files[f"technical/charts/{kind}.json"] = path.read_bytes()
        else:
            files[f"technical/charts/{kind}.json"] = _dumps(not_run(kind))
        png = rendered_png(analysis, kind)
        if png is None:
            missing.append(kind)
        else:
            files[f"technical/charts/{kind}.png"] = png.read_bytes()
    return files, missing


def _redact_evidence(bundle: dict, mode: str) -> dict:
    if mode == "included":
        return json.loads(json.dumps(bundle))
    records = []
    for record in bundle.get("records") or []:
        kind = _record_kind(str(record.get("id") or ""))
        if mode == "omitted" and kind in {"line", "repeat"}:
            continue
        copied = dict(record)
        if kind == "line":
            copied["value"] = None
        elif kind == "repeat":
            copied["name"] = "written_repetition"
        records.append(copied)
    return {**bundle, "records": records}


def _redact_chart(chart: dict, mode: str, evidence: dict) -> dict:
    copied = json.loads(json.dumps(chart))
    if mode == "included":
        return copied
    for index, region in enumerate(copied.get("regions") or []):
        region["label"] = f"Line {index + 1}"
    known = {item.get("id") for item in evidence.get("records") or []}
    rows = []
    for row in copied.get("rows") or []:
        kind = _record_kind(str(row.get("evidence_id") or ""))
        if mode == "omitted" and kind in {"line", "repeat"}:
            continue
        if kind == "line":
            row["value"] = ""
        elif kind == "repeat":
            row["name"] = "written_repetition"
        cites = row.get("cites") or []
        if cites and any(cite not in known for cite in cites):
            continue
        rows.append(row)
    copied["rows"] = rows
    return copied


def _record_kind(evidence_id: str) -> str:
    if evidence_id.startswith("ly:repeat:"):
        return "repeat"
    if evidence_id.startswith(("ly:density:", "ly:level:", "ly:lufs:", "ly:principle:")):
        return "other"
    if evidence_id.startswith("ly:"):
        return "line"
    return "other"


def _brief(
    sha: str,
    metrics: dict | None,
    document: dict,
    mode: str,
    charts: list[dict],
    evidence: dict,
) -> str:
    by_kind = {chart["chart_kind"]: chart for chart in charts}
    records = [item for item in evidence.get("records") or [] if item.get("id")]
    known = {item["id"] for item in records}
    lines = [
        "# Lyricist reference brief",
        "",
        "## Reference identity and provenance",
        f"Recording source SHA-256: `{sha}`",
        f"Analysis version: {_version(metrics)}",
        f"Parameter hash: {_params(metrics)}",
        f"Lyric document: `{document['id']}` revision {document['revision']}",
        f"Lyric source SHA-256: `{document['source_sha256']}`",
        f"Lyric renderer: {LYRIC_RENDERER_VERSION}.",
        f"Brief template: {BRIEF_TEMPLATE_VERSION}.",
        f"Lyric method: lyrics-v1. Technical renderer: {RENDERER_VERSION}. Narrative: none.",
        f"Lyric text mode: {mode}.",
        (
            "Timing comes from this lyric revision. "
            "Subtitle-supplied times are not artist confirmation. "
            "This package does not estimate singing or alignment."
        ),
    ]
    lines.extend(_provenance_lines(by_kind.get("L02")))
    lines.extend(["", "## What the available evidence establishes"])
    observations = _observations(records)
    shown = observations[:_OBSERVATION_CAP]
    lines.append(
        f"Showing {len(shown)} of {len(observations)} highlightable records. "
        "Rule: measured, then estimated, then textual summary records, "
        f"at most {_OBSERVATION_CAP}, ordered by evidence class then evidence id. "
        "Individual lyric lines are not listed in this section. "
        "Complete records are in evidence.json."
    )
    if not shown:
        lines.append("No stored technical or summary evidence is available for this revision.")
    for item in shown:
        lines.append(_observation_line(item, mode))
        caveat = item.get("caveat")
        if caveat and not _leaks_lyric(str(caveat), item, mode):
            lines.append(f"  Caveat: {caveat}")
    lines.extend(["", "## Written phrasing and repetition"])
    lines.append(
        "Word counts are written tokens, not vocal delivery or breaths. "
        "Spectral similarity is not textual repetition, a melody, or a hook."
    )
    if mode == "omitted":
        lines.append("Original lyric lines and repetition strings are omitted.")
    elif mode == "summarized":
        lines.append("Counts and citation ids are kept. Original lyric lines are not included.")
    else:
        lines.append("Original lyric lines for this mode are in evidence.json and the section below.")
    lines.extend(_summary_only(by_kind.get("L02")))
    repeats = _repeat_rows(by_kind.get("L04"))
    repeat_shown = repeats[:_REPEAT_CAP]
    lines.append(
        f"Showing {len(repeat_shown)} of {len(repeats)} written-repetition rows, "
        "the first rows in stored order. Complete rows are in lyricist/charts/L04.json."
    )
    for row in repeat_shown:
        lines.append(_safe_row(row, mode, known))
    lines.extend(["", "## Energy and contrast"])
    lines.append(
        "Energy values are stored full-mix measurements. They are not singing intensity, "
        "vocal performance, or emotion. dBFS and LUFS are different measurements."
    )
    lines.extend(_summary_only(by_kind.get("L03"), skip_contrast=True))
    contrasts = _contrasts(by_kind.get("L03"))
    contrast_shown = contrasts[:_CONTRAST_CAP]
    lines.append(
        f"Showing {len(contrast_shown)} of {len(contrasts)} consecutive full-mix RMS contrasts, "
        "the largest absolute differences first. "
        "Every interval mean remains in lyricist/charts/L03.json."
    )
    for value in contrast_shown:
        lines.append(f"- {value}")
    lines.extend(["", "## Transferable creative principles"])
    lines.append(
        "Principles are interpretive templates gated on stored evidence. "
        "They are not a listening impression."
    )
    principles = _principle_rows(by_kind.get("L05"))
    if not principles:
        lines.append("No lyrics-v1 principle met its evidence gate.")
    for row in principles:
        lines.append(_safe_row(row, mode, known))
    lines.extend(["", "## What this package cannot determine"])
    insufficient = (by_kind.get("L05") or {}).get("insufficient") or []
    if not insufficient:
        lines.extend(
            [
                "- Singing performance and vocal delivery.",
                "- Verified tempo or groove.",
                "- Melody or hook identity.",
                "- Instrumentation.",
                "- Emotional response.",
                "- Verified song sections.",
            ]
        )
    for item in insufficient:
        cites = [
            cite
            for cite in item.get("cites") or []
            if cite in known
        ]
        suffix = f" Citations: {', '.join(f'`{cite}`' for cite in cites)}." if cites else ""
        lines.append(f"- {item.get('code')}: {item.get('reason')}{suffix}")
    lines.extend(["", "## Detailed evidence references"])
    for kind in LYRIC_KINDS:
        chart = by_kind.get(kind)
        status = "missing" if chart is None else chart.get("status")
        lines.append(f"- {kind}: {status}. JSON and PNG: `lyricist/charts/{kind}.json`.")
    lines.append("Complete structured evidence: evidence.json.")
    if mode == "included":
        lyric_lines = [item for item in records if item.get("name") == "lyric_line"]
        lines.append(f"Original lyric lines in this mode: {len(lyric_lines)}.")
        for item in lyric_lines:
            lines.append(f"- `{item['id']}`: {item.get('value')}")
    lines.extend(
        [
            "This brief uses stored evidence and lyrics-v1 templates only.",
            _G3,
            _G6,
            "",
        ]
    )
    return "\n".join(lines)


def _provenance_lines(chart: dict | None) -> list[str]:
    if not chart:
        return ["Lyric timing counts are unavailable."]
    kept = []
    for item in chart.get("summary") or []:
        label = str(item.get("label") or "")
        if label in {"Supplied timing", "Manually edited", "Manually verified", "Unavailable timing"}:
            kept.append(f"{label}: {item.get('value')}.")
    return kept or ["Lyric timing counts are unavailable."]


def _observations(records: list[dict]) -> list[dict]:
    chosen = []
    for item in records:
        evidence_id = str(item.get("id") or "")
        if _record_kind(evidence_id) == "line":
            continue
        if not evidence_id.startswith(("ev:", "ly:")):
            continue
        chosen.append(item)
    chosen.sort(
        key=lambda item: (
            _CLASS_ORDER.get(str(item.get("evidence_class")), 9),
            str(item["id"]),
        )
    )
    return chosen


def _observation_line(item: dict, mode: str) -> str:
    evidence_id = str(item["id"])
    name = _public_repeat_name(item, mode)
    value = item.get("value")
    if value is None or (mode != "included" and _record_kind(evidence_id) == "line"):
        shown = "stored series"
    else:
        shown = f"{value} {item.get('unit') or ''}".strip()
    return (
        f"- `{evidence_id}` ({item.get('evidence_class')}): {name} — {shown}."
    )


def _summary_only(chart: dict | None, skip_contrast: bool = False) -> list[str]:
    if not chart:
        return ["Chart unavailable."]
    lines = [f"{chart['chart_kind']} status: {chart['status']}."]
    reason = chart.get("not_available_reason")
    if reason:
        lines.append(str(reason))
    for item in chart.get("summary") or []:
        if skip_contrast and item.get("label") == "Contrast":
            continue
        if str(item.get("label") or "").startswith("Stored "):
            continue
        lines.append(f"- {item.get('label')}: {item.get('value')}")
    for caveat in chart.get("caveats") or []:
        lines.append(f"Caveat: {caveat}")
    return lines


def _contrasts(chart: dict | None) -> list[str]:
    found = []
    for item in (chart or {}).get("summary") or []:
        if item.get("label") != "Contrast":
            continue
        value = str(item.get("value") or "")
        found.append((_contrast_magnitude(value), value))
    found.sort(key=lambda item: (-item[0], item[1]))
    return [value for _magnitude, value in found]


def _contrast_magnitude(value: str) -> float:
    marker = "differ by "
    if marker not in value:
        return 0.0
    number = value.split(marker, 1)[1].split(" dB", 1)[0]
    try:
        return abs(float(number))
    except ValueError:
        return 0.0


def _repeat_rows(chart: dict | None) -> list[dict]:
    rows = []
    for row in (chart or {}).get("rows") or []:
        if str(row.get("evidence_id") or "").startswith("ly:repeat:"):
            rows.append(row)
    return rows


def _principle_rows(chart: dict | None) -> list[dict]:
    return [row for row in (chart or {}).get("rows") or [] if row.get("kind") == "principle"]


def _safe_row(row: dict, mode: str, known: set[str]) -> str:
    cites = [cite for cite in row.get("cites") or [] if cite in known]
    suffix = f" Citations: {', '.join(f'`{cite}`' for cite in cites)}." if cites else ""
    name = _public_repeat_name(row, mode)
    evidence_id = str(row.get("evidence_id") or "")
    value = row.get("value") or ""
    if mode != "included" and _record_kind(evidence_id) == "line":
        value = ""
    label = f"`{evidence_id}`" if evidence_id in known else evidence_id
    return f"- {label} ({row.get('evidence_class')}): {name} {value}{suffix}".rstrip()


def _public_repeat_name(row: dict, mode: str) -> str:
    evidence_id = str(row.get("evidence_id") or row.get("id") or "")
    if mode != "included" and evidence_id.startswith(
        ("ly:repeat:", "ly:principle:written-repetition:")
    ):
        return "written_repetition"
    return str(row.get("name") or "")


def _leaks_lyric(caveat: str, item: dict, mode: str) -> bool:
    if mode == "included":
        return False
    value = item.get("value")
    return isinstance(value, str) and value and value in caveat


def _technical_readme(sha: str, metrics: dict | None, document: dict | None, mode: str) -> str:
    revision = "none" if document is None else str(document["revision"])
    return "\n".join(
        [
            "# Technical analysis package",
            "",
            "This folder is a snapshot of stored technical evidence.",
            "The export did not decode the WAV and did not remeasure.",
            f"Source SHA-256: {sha}",
            f"Method: {_version(metrics)}",
            f"Parameter hash: {_params(metrics)}",
            f"Technical renderer: {RENDERER_VERSION}",
            f"Lyric revision: {revision}",
            f"Lyric text mode: {mode}",
            "",
            f"PNG files are copies of valid {RENDERER_VERSION} artifacts.",
            "A chart listed as png_unavailable in the manifest has JSON and no current PNG.",
            "Legacy PNGs are not included.",
            _G3,
            _G6,
            "",
        ]
    )


def _lyric_readme(sha: str, metrics: dict | None, document: dict, mode: str) -> str:
    return "\n".join(
        [
            "# Lyricist reference package",
            "",
            "L01–L05 are drawings of the stored lyric-chart documents.",
            "They do not estimate singing, alignment, emotion, or instrumentation.",
            f"Source SHA-256: {sha}",
            f"Method: {_version(metrics)}",
            "Lyric method: lyrics-v1",
            f"Lyric renderer: {LYRIC_RENDERER_VERSION}",
            f"Brief template: {BRIEF_TEMPLATE_VERSION}",
            f"Lyric document: {document['id']} revision {document['revision']}",
            f"Lyric source SHA-256: {document['source_sha256']}",
            f"Lyric text mode: {mode}",
            "",
            _G3,
            _G6,
            "",
        ]
    )


def _combined_readme(sha: str, metrics: dict | None, document: dict, mode: str) -> str:
    return "\n".join(
        [
            "# Combined reference package",
            "",
            "Technical charts are under technical/charts/.",
            "Lyric charts and the reference brief are under lyricist/.",
            "metrics.json and evidence.json appear once, at the root of this ZIP.",
            "The WAV is not included.",
            f"Source SHA-256: {sha}",
            f"Method: {_version(metrics)}",
            f"Technical renderer: {RENDERER_VERSION}",
            f"Lyric renderer: {LYRIC_RENDERER_VERSION}",
            f"Brief template: {BRIEF_TEMPLATE_VERSION}",
            f"Lyric document: {document['id']} revision {document['revision']}",
            f"Lyric text mode: {mode}",
            "",
            _G3,
            _G6,
            "",
        ]
    )


def _version(metrics: dict | None) -> str:
    if metrics and metrics.get("algorithm_version"):
        return str(metrics["algorithm_version"])
    return "not run"


def _params(metrics: dict | None) -> str:
    if metrics and metrics.get("params_hash"):
        return str(metrics["params_hash"])
    return "none"


def _absent_metrics(sha: str) -> dict:
    return {
        "status": "not_run",
        "sha256": sha,
        "algorithm_version": None,
        "params_hash": None,
        "charts": {kind: "not_run" for kind in KINDS},
    }


def _json_file(path: Path) -> dict | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    return payload if isinstance(payload, dict) else None


def _copy_or_dump(path: Path, fallback: dict) -> bytes:
    if path.is_file():
        return path.read_bytes()
    return _dumps(fallback)


def _dumps(payload: dict) -> bytes:
    return (json.dumps(payload, indent=2, allow_nan=False) + "\n").encode()


def _is_content(name: str) -> bool:
    base = name.rsplit("/", 1)[-1]
    if base in {"metrics.json", "evidence.json", "brief.md"}:
        return True
    return "/charts/" in f"/{name}" and name.endswith(".json")


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
            if name.startswith("/") or ".." in name.split("/"):
                raise ExportError(500, "export_failed", "The export was not published.")
            info = zipfile.ZipInfo(filename=name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, files[name])


def _validate(path: Path, manifest: dict) -> None:
    required = _required(manifest["profile"])
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if set(names) != set(manifest["files"]):
            raise ExportError(500, "export_failed", "The export was not published.")
        content: dict[str, bytes] = {}
        for name in names:
            if name.startswith("/") or ".." in name.split("/") or name.endswith(".wav"):
                raise ExportError(500, "export_failed", "The export was not published.")
            data = archive.read(name)
            if name.endswith(".png") and not _png(data):
                raise ExportError(500, "export_failed", "The export was not published.")
            if _is_content(name):
                content[name] = data
        if any(name not in names for name in required):
            raise ExportError(500, "export_failed", "The export was not published.")
        if _content_sha256(content) != manifest["content_sha256"]:
            raise ExportError(500, "export_failed", "The export was not published.")


def _required(profile: str) -> list[str]:
    technical = [f"technical/charts/{kind}.json" for kind in KINDS]
    lyric = [f"lyricist/charts/{kind}.json" for kind in LYRIC_KINDS]
    lyric += [f"lyricist/charts/{kind}.png" for kind in LYRIC_KINDS]
    if profile == "technical":
        return [
            "technical/README.md",
            "technical/manifest.json",
            "technical/metrics.json",
            "technical/evidence.json",
            *technical,
        ]
    if profile == "lyricist":
        return [
            "lyricist/README.md",
            "lyricist/brief.md",
            "lyricist/manifest.json",
            "lyricist/evidence.json",
            *lyric,
        ]
    return [
        "README.md",
        "manifest.json",
        "metrics.json",
        "evidence.json",
        "technical/README.md",
        "lyricist/README.md",
        "lyricist/brief.md",
        *technical,
        *lyric,
    ]


def _png(data: bytes) -> bool:
    return len(data) > 32 and data.startswith(b"\x89PNG\r\n\x1a\n") and b"IEND" in data[-32:]
