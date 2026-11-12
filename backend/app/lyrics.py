"""Lyric documents, revisions, and the read-only evidence bundle.

Audio measurements stay in analysis/{sha256}/m1-v3. This module only reads those files.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

ANALYSIS_VERSION = "m1-v3"
LYRIC_MAX_BYTES = 1_048_576
_KINDS = {"txt": "txt", "md": "md", "srt": "srt"}
_TIME_LINE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})"
)
_RMS_CAVEAT = (
    "10*log10 of the mean of 10^(stored dBFS/10) for the T02 1 s RMS frames "
    "inside the written interval. Each stored frame has equal weight. "
    "A short trailing frame is already absent from T02. "
    "Power at the m1-v3 floor stays at that floor. "
    "Not a new WAV measurement, and not vocal energy."
)
_LUFS_CAVEAT = (
    "Arithmetic mean of the stored 3 s short-term LUFS samples inside the written interval. "
    "LUFS is not mean-square power. Not a new WAV measurement, and not vocal energy."
)


class LyricError(Exception):
    def __init__(
        self, status: int, code: str, message: str, extra: dict | None = None
    ) -> None:
        self.status = status
        self.code = code
        self.message = message
        self.extra = extra or {}


def word_count(text: str) -> int:
    count = 0
    for line in text.splitlines() or [""]:
        stripped = line.lstrip()
        marks = 0
        while marks < len(stripped) and stripped[marks] == "#":
            marks += 1
        if marks:
            stripped = stripped[marks:].lstrip()
        stripped = stripped.strip("*_")
        count += sum(1 for token in stripped.split() if any(ch.isalnum() for ch in token))
    return count


def usable(start_s: float | None, end_s: float | None, duration_s: float) -> bool:
    if start_s is None or end_s is None or not start_s < end_s:
        return False
    if not (math.isfinite(start_s) and math.isfinite(end_s)):
        return False
    return start_s >= -0.001 and end_s <= duration_s + 0.001


def lyric_kind(original_name: str) -> str:
    suffix = Path(original_name).suffix.lower().lstrip(".")
    kind = _KINDS.get(suffix)
    if kind is None:
        raise LyricError(
            415,
            "unsupported_lyrics",
            "Lyric files must end in .txt, .md, or .srt.",
        )
    return kind


def require_membership(conn: sqlite3.Connection, project_id: str, asset_id: str) -> sqlite3.Row:
    project = conn.execute("SELECT mode FROM projects WHERE id = ?", (project_id,)).fetchone()
    if project is None:
        raise LyricError(404, "not_found", "Project not found.")
    if project["mode"] != "study":
        raise LyricError(400, "not_study", "Lyrics and recording exports belong to a study.")
    row = conn.execute(
        """
        SELECT assets.* FROM assets
        JOIN project_assets ON project_assets.asset_id = assets.id
        WHERE project_assets.project_id = ? AND project_assets.asset_id = ?
        """,
        (project_id, asset_id),
    ).fetchone()
    if row is None:
        raise LyricError(404, "not_in_project", "That recording is not in this project.")
    return row


def store_upload(
    conn: sqlite3.Connection,
    data_root: Path,
    project_id: str,
    asset_id: str,
    original_name: str,
    raw: bytes,
) -> dict:
    asset = require_membership(conn, project_id, asset_id)
    kind = lyric_kind(original_name)
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise LyricError(422, "not_utf8", "Lyric text must be UTF-8.") from exc
    sha = hashlib.sha256(raw).hexdigest()
    # ponytail: orphan lyrics/{sha256} if the process dies after rename and before commit. Same bytes reuse the file.
    _write_file(data_root, sha, raw)
    segments, findings = _parse(text, kind, float(asset["duration_s"]))
    now = _now()
    upload_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    named = Path(original_name).name[:255] or f"lyrics.{kind}"
    _begin(conn)
    try:
        conn.execute(
            """
            INSERT INTO lyric_files (sha256, byte_length, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(sha256) DO NOTHING
            """,
            (sha, len(raw), now),
        )
        conn.execute(
            """
            INSERT INTO lyric_uploads (
              id, project_id, asset_id, file_sha256, source_kind, original_name, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (upload_id, project_id, asset_id, sha, kind, named, now),
        )
        conn.execute(
            """
            UPDATE lyric_documents SET is_current = 0
            WHERE project_id = ? AND asset_id = ? AND is_current = 1
            """,
            (project_id, asset_id),
        )
        conn.execute(
            """
            INSERT INTO lyric_documents (
              id, upload_id, project_id, asset_id, revision, is_current, created_at
            ) VALUES (?, ?, ?, ?, 1, 1, ?)
            """,
            (document_id, upload_id, project_id, asset_id, now),
        )
        for ordinal, segment in enumerate(segments):
            segment_id = str(uuid.uuid4())
            segment["id"] = segment_id
            _insert_segment(conn, document_id, ordinal, segment, 1)
        for finding in findings:
            ordinal = finding.get("ordinal")
            segment_id = segments[ordinal]["id"] if ordinal is not None else None
            conn.execute(
                """
                INSERT INTO lyric_validation (document_id, segment_id, code, detail)
                VALUES (?, ?, ?, ?)
                """,
                (document_id, segment_id, finding["code"], finding["detail"]),
            )
        _insert_overlaps(conn, document_id, segments, float(asset["duration_s"]))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return _require_document(conn, project_id, asset_id, float(asset["duration_s"]))


def load_document(
    conn: sqlite3.Connection, project_id: str, asset_id: str
) -> dict | None:
    asset = require_membership(conn, project_id, asset_id)
    return _document(conn, project_id, asset_id, float(asset["duration_s"]))


def source_bytes(
    conn: sqlite3.Connection, data_root: Path, project_id: str, asset_id: str
) -> bytes:
    asset = require_membership(conn, project_id, asset_id)
    row = _current_row(conn, project_id, asset_id)
    if row is None:
        raise LyricError(404, "no_lyrics", "No lyric document is attached.")
    path = data_root / "lyrics" / row["file_sha256"]
    if not path.is_file():
        raise LyricError(404, "source_missing", "The original lyric file is missing.")
    del asset
    return path.read_bytes()


def delete_lyrics(
    conn: sqlite3.Connection, data_root: Path, project_id: str, asset_id: str
) -> None:
    require_membership(conn, project_id, asset_id)
    _begin(conn)
    doomed: list[Path] = []
    try:
        hashes = [
            row["file_sha256"]
            for row in conn.execute(
                """
                SELECT file_sha256 FROM lyric_uploads
                WHERE project_id = ? AND asset_id = ?
                """,
                (project_id, asset_id),
            ).fetchall()
        ]
        if not hashes:
            raise LyricError(404, "no_lyrics", "No lyric document is attached.")
        conn.execute(
            "DELETE FROM lyric_documents WHERE project_id = ? AND asset_id = ?",
            (project_id, asset_id),
        )
        conn.execute(
            "DELETE FROM lyric_uploads WHERE project_id = ? AND asset_id = ?",
            (project_id, asset_id),
        )
        doomed = _unreferenced(conn, data_root, hashes)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    for path in doomed:
        path.unlink(missing_ok=True)


def update_segment(
    conn: sqlite3.Connection,
    project_id: str,
    asset_id: str,
    segment_id: str,
    expected_revision: int,
    text: str | None,
    start_s: float | None,
    end_s: float | None,
    note: str | None,
    clear_timing: bool,
) -> dict:
    asset = require_membership(conn, project_id, asset_id)
    if text is None and note is None and start_s is None and end_s is None and not clear_timing:
        raise LyricError(422, "empty_edit", "The edit did not change text, timing, or the note.")
    if (start_s is None) != (end_s is None):
        raise LyricError(422, "interval_not_usable", _interval_message())
    duration = float(asset["duration_s"])
    if start_s is not None and not usable(start_s, end_s, duration):
        raise LyricError(422, "interval_not_usable", _interval_message())
    _begin(conn)
    try:
        segment, revision = _lock_segment(conn, project_id, asset_id, segment_id, expected_revision)
        new_text = segment["text"] if text is None else text
        new_note = segment["note"] if note is None else note
        if clear_timing:
            new_start, new_end = None, None
        elif start_s is not None:
            new_start, new_end = start_s, end_s
        else:
            new_start, new_end = segment["start_s"], segment["end_s"]
        origin, verified = _after_edit(
            segment, new_text, new_start, new_end, clear_timing or start_s is not None, duration
        )
        _write_segment(
            conn,
            segment,
            revision + 1,
            new_text,
            new_start,
            new_end,
            origin,
            verified,
            new_note,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return _require_document(conn, project_id, asset_id, duration)


def verify_segment(
    conn: sqlite3.Connection,
    project_id: str,
    asset_id: str,
    segment_id: str,
    expected_revision: int,
    verified: bool,
) -> dict:
    asset = require_membership(conn, project_id, asset_id)
    duration = float(asset["duration_s"])
    _begin(conn)
    try:
        segment, revision = _lock_segment(conn, project_id, asset_id, segment_id, expected_revision)
        origin = segment["timing_origin"]
        flag = int(segment["artist_verified"])
        start_s, end_s = segment["start_s"], segment["end_s"]
        changed = False
        if verified:
            if origin == "manual_verified":
                conn.rollback()
                return _require_document(conn, project_id, asset_id, duration)
            if not usable(start_s, end_s, duration):
                raise LyricError(422, "interval_not_usable", _interval_message())
            origin, flag, changed = "manual_verified", 1, True
        elif origin == "manual_verified":
            origin = "manual_edit" if usable(start_s, end_s, duration) else "unplaced"
            flag = 0
            changed = True
        if not changed:
            conn.rollback()
            return _require_document(conn, project_id, asset_id, duration)
        _write_segment(
            conn,
            segment,
            revision + 1,
            segment["text"],
            start_s,
            end_s,
            origin,
            flag,
            segment["note"],
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return _require_document(conn, project_id, asset_id, duration)


def list_annotations(conn: sqlite3.Connection, project_id: str, asset_id: str) -> list[dict]:
    require_membership(conn, project_id, asset_id)
    rows = conn.execute(
        """
        SELECT * FROM annotations
        WHERE project_id = ? AND asset_id = ?
        ORDER BY created_at, id
        """,
        (project_id, asset_id),
    ).fetchall()
    return [_annotation(row) for row in rows]


def create_annotation(
    conn: sqlite3.Connection,
    project_id: str,
    asset_id: str,
    start_s: float,
    end_s: float,
    text: str,
    segment_id: str | None,
) -> dict:
    asset = require_membership(conn, project_id, asset_id)
    duration = float(asset["duration_s"])
    if not (
        math.isfinite(start_s)
        and math.isfinite(end_s)
        and end_s > start_s
        and start_s >= -0.001
        and end_s <= duration + 0.001
    ):
        raise LyricError(422, "interval_not_usable", _interval_message())
    now = _now()
    note_id = str(uuid.uuid4())
    _begin(conn)
    try:
        if segment_id is not None and _current_segment(conn, project_id, asset_id, segment_id) is None:
            raise LyricError(404, "not_current", "That line is not on the current lyric document.")
        conn.execute(
            """
            INSERT INTO annotations (
              id, project_id, asset_id, segment_id, start_s, end_s, text, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (note_id, project_id, asset_id, segment_id, start_s, end_s, text, now),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    row = conn.execute("SELECT * FROM annotations WHERE id = ?", (note_id,)).fetchone()
    return _annotation(row)


def delete_annotation(
    conn: sqlite3.Connection, project_id: str, asset_id: str, annotation_id: str
) -> None:
    require_membership(conn, project_id, asset_id)
    _begin(conn)
    try:
        deleted = conn.execute(
            """
            DELETE FROM annotations
            WHERE id = ? AND project_id = ? AND asset_id = ?
            """,
            (annotation_id, project_id, asset_id),
        ).rowcount
        if not deleted:
            raise LyricError(404, "not_found", "No note with that id exists.")
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def canonical_evidence(
    conn: sqlite3.Connection, data_root: Path, project_id: str, asset_id: str
) -> dict:
    asset = require_membership(conn, project_id, asset_id)
    duration = float(asset["duration_s"])
    document = _document(conn, project_id, asset_id, duration)
    persisted, have_file = _persisted_records(data_root, asset["sha256"])
    charts = {
        kind: _ready_chart(data_root, asset["sha256"], kind) for kind in ("T02", "T08", "T09")
    }
    derived = _derived_records(charts)
    lyric_records: list[dict] = []
    if document is not None:
        lyric_records = _lyric_records(document, charts.get("T02"))
    version = ANALYSIS_VERSION if have_file or derived else None
    return {
        "asset_id": asset_id,
        "project_id": project_id,
        "analysis_version": version,
        "lyric_document_id": None if document is None else document["id"],
        "lyric_revision": None if document is None else document["revision"],
        "records": persisted + derived + lyric_records,
    }


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _begin(conn: sqlite3.Connection) -> None:
    conn.execute("BEGIN IMMEDIATE")


def _interval_message() -> str:
    return "The interval needs a start before its end, inside the recording."


def _write_file(data_root: Path, sha256: str, raw: bytes) -> None:
    dest = data_root / "lyrics" / sha256
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file():
        return
    partial = dest.with_name(sha256 + ".partial")
    partial.write_bytes(raw)
    os.replace(partial, dest)


def _parse(text: str, kind: str, duration_s: float) -> tuple[list[dict], list[dict]]:
    if kind == "srt":
        return _parse_srt(text, duration_s)
    segments = []
    for line in text.splitlines():
        if not line.strip():
            continue
        segments.append(_segment(line, None, None, "unplaced", None))
    return segments, []


def _parse_srt(text: str, duration_s: float) -> tuple[list[dict], list[dict]]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return [], [{"ordinal": None, "code": "unparsed", "detail": "no SRT cues"}]
    segments = []
    findings = []
    for block in re.split(r"\n[ \t]*\n", normalized):
        lines = block.split("\n")
        index = 0
        source_cue = None
        if lines and re.fullmatch(r"\d+", lines[0].strip()):
            source_cue = lines[0].strip()
            index = 1
        stamp = lines[index].strip() if index < len(lines) else ""
        match = _TIME_LINE.fullmatch(stamp)
        body = lines[index + 1 :] if match else lines[index:]
        cue_text = "\n".join(body)
        ordinal = len(segments)
        if match is None:
            segments.append(_segment(cue_text, None, None, "unplaced", source_cue))
            findings.append(
                {
                    "ordinal": ordinal,
                    "code": "malformed_time",
                    "detail": stamp[:200] or cue_text[:200],
                }
            )
        else:
            start_s = _stamp(*match.group(1, 2, 3, 4))
            end_s = _stamp(*match.group(5, 6, 7, 8))
            segments.append(_segment(cue_text, start_s, end_s, "subtitle_supplied", source_cue))
            if end_s <= start_s:
                relation = "==" if end_s == start_s else ">"
                findings.append(
                    {
                        "ordinal": ordinal,
                        "code": "reversed_time",
                        "detail": f"{start_s:.3f} {relation} {end_s:.3f}",
                    }
                )
            elif start_s < -0.001 or end_s > duration_s + 0.001:
                findings.append(
                    {
                        "ordinal": ordinal,
                        "code": "out_of_range",
                        "detail": f"{start_s:.3f},{end_s:.3f} outside [0, {duration_s:.3f}]",
                    }
                )
        if not cue_text.strip():
            findings.append({"ordinal": ordinal, "code": "empty_cue", "detail": "empty cue"})
    return segments, findings


def _stamp(hours: str, minutes: str, seconds: str, millis: str) -> float:
    return ((int(hours) * 60 + int(minutes)) * 60 + int(seconds)) + int(millis) / 1000


def _segment(
    text: str,
    start_s: float | None,
    end_s: float | None,
    origin: str,
    source_cue: str | None,
) -> dict:
    return {
        "text": text,
        "start_s": start_s,
        "end_s": end_s,
        "timing_origin": origin,
        "source_cue": source_cue,
        "note": "",
    }


def _insert_segment(
    conn: sqlite3.Connection, document_id: str, ordinal: int, segment: dict, revision: int
) -> None:
    conn.execute(
        """
        INSERT INTO lyric_segments (
          id, document_id, ordinal, source_cue, text, start_s, end_s,
          timing_origin, artist_verified, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (
            segment["id"],
            document_id,
            ordinal,
            segment["source_cue"],
            segment["text"],
            segment["start_s"],
            segment["end_s"],
            segment["timing_origin"],
            segment["note"],
        ),
    )
    conn.execute(
        """
        INSERT INTO lyric_segment_revisions (
          segment_id, document_revision, text, start_s, end_s,
          timing_origin, artist_verified, note
        ) VALUES (?, ?, ?, ?, ?, ?, 0, ?)
        """,
        (
            segment["id"],
            revision,
            segment["text"],
            segment["start_s"],
            segment["end_s"],
            segment["timing_origin"],
            segment["note"],
        ),
    )


def _insert_overlaps(
    conn: sqlite3.Connection, document_id: str, segments: list[dict], duration_s: float
) -> None:
    usable_rows = [
        segment
        for segment in segments
        if usable(segment["start_s"], segment["end_s"], duration_s)
    ]
    for index, left in enumerate(usable_rows):
        for right in usable_rows[index + 1 :]:
            if left["start_s"] < right["end_s"] and right["start_s"] < left["end_s"]:
                for segment, other in ((left, right), (right, left)):
                    conn.execute(
                        """
                        INSERT INTO lyric_validation (document_id, segment_id, code, detail)
                        VALUES (?, ?, 'overlap', ?)
                        """,
                        (
                            document_id,
                            segment["id"],
                            f"{segment['id']} overlaps {other['id']}",
                        ),
                    )


def _current_row(conn: sqlite3.Connection, project_id: str, asset_id: str) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT lyric_documents.*, lyric_uploads.source_kind, lyric_uploads.file_sha256,
               lyric_uploads.original_name
        FROM lyric_documents
        JOIN lyric_uploads ON lyric_uploads.id = lyric_documents.upload_id
        WHERE lyric_documents.project_id = ? AND lyric_documents.asset_id = ?
          AND lyric_documents.is_current = 1
        """,
        (project_id, asset_id),
    ).fetchone()


def _document(
    conn: sqlite3.Connection, project_id: str, asset_id: str, duration_s: float
) -> dict | None:
    row = _current_row(conn, project_id, asset_id)
    if row is None:
        return None
    segments = conn.execute(
        """
        SELECT * FROM lyric_segments WHERE document_id = ? ORDER BY ordinal
        """,
        (row["id"],),
    ).fetchall()
    validation = conn.execute(
        """
        SELECT segment_id, code, detail FROM lyric_validation
        WHERE document_id = ? ORDER BY id
        """,
        (row["id"],),
    ).fetchall()
    return {
        "id": row["id"],
        "project_id": project_id,
        "asset_id": asset_id,
        "upload_id": row["upload_id"],
        "source_kind": row["source_kind"],
        "source_sha256": row["file_sha256"],
        "original_name": row["original_name"],
        "revision": row["revision"],
        "segments": [_segment_out(segment, duration_s) for segment in segments],
        "validation": [
            {"segment_id": item["segment_id"], "code": item["code"], "detail": item["detail"]}
            for item in validation
        ],
    }


def _require_document(
    conn: sqlite3.Connection, project_id: str, asset_id: str, duration_s: float
) -> dict:
    document = _document(conn, project_id, asset_id, duration_s)
    if document is None:
        raise LyricError(404, "no_lyrics", "No lyric document is attached.")
    return document


def _segment_out(row: sqlite3.Row, duration_s: float) -> dict:
    return {
        "id": row["id"],
        "ordinal": row["ordinal"],
        "source_cue": row["source_cue"],
        "text": row["text"],
        "start_s": row["start_s"],
        "end_s": row["end_s"],
        "timing_origin": row["timing_origin"],
        "artist_verified": bool(row["artist_verified"]),
        "note": row["note"],
        "usable": usable(row["start_s"], row["end_s"], duration_s),
    }


def _lock_segment(
    conn: sqlite3.Connection,
    project_id: str,
    asset_id: str,
    segment_id: str,
    expected_revision: int,
) -> tuple[sqlite3.Row, int]:
    current = _current_row(conn, project_id, asset_id)
    segment = _current_segment(conn, project_id, asset_id, segment_id)
    if current is None or segment is None or segment["document_id"] != current["id"]:
        raise LyricError(404, "not_current", "That line is not on the current lyric document.")
    if current["revision"] != expected_revision:
        raise LyricError(
            409,
            "stale_revision",
            "The lyric document changed.",
            {"current_revision": current["revision"]},
        )
    return segment, int(current["revision"])


def _current_segment(
    conn: sqlite3.Connection, project_id: str, asset_id: str, segment_id: str
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT lyric_segments.* FROM lyric_segments
        JOIN lyric_documents ON lyric_documents.id = lyric_segments.document_id
        WHERE lyric_segments.id = ? AND lyric_documents.project_id = ?
          AND lyric_documents.asset_id = ? AND lyric_documents.is_current = 1
        """,
        (segment_id, project_id, asset_id),
    ).fetchone()


def _after_edit(
    segment: sqlite3.Row,
    new_text: str,
    new_start: float | None,
    new_end: float | None,
    times_touched: bool,
    duration_s: float,
) -> tuple[str, int]:
    origin = segment["timing_origin"]
    if new_start is None:
        if times_touched:
            return "unplaced", 0
    elif times_touched:
        return "manual_edit", 0
    if new_text != segment["text"] and usable(new_start, new_end, duration_s):
        return "manual_edit", 0
    if new_text != segment["text"]:
        return origin, 0
    return origin, int(segment["artist_verified"])


def _write_segment(
    conn: sqlite3.Connection,
    segment: sqlite3.Row,
    revision: int,
    text: str,
    start_s: float | None,
    end_s: float | None,
    origin: str,
    verified: int,
    note: str,
) -> None:
    conn.execute(
        """
        UPDATE lyric_segments
        SET text = ?, start_s = ?, end_s = ?, timing_origin = ?, artist_verified = ?, note = ?
        WHERE id = ?
        """,
        (text, start_s, end_s, origin, verified, note, segment["id"]),
    )
    conn.execute(
        """
        INSERT INTO lyric_segment_revisions (
          segment_id, document_revision, text, start_s, end_s,
          timing_origin, artist_verified, note
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (segment["id"], revision, text, start_s, end_s, origin, verified, note),
    )
    conn.execute(
        "UPDATE lyric_documents SET revision = ? WHERE id = ?",
        (revision, segment["document_id"]),
    )


def _unreferenced(conn: sqlite3.Connection, data_root: Path, hashes: list[str]) -> list[Path]:
    doomed = []
    for sha in dict.fromkeys(hashes):
        left = conn.execute(
            "SELECT 1 FROM lyric_uploads WHERE file_sha256 = ?", (sha,)
        ).fetchone()
        if left is None:
            conn.execute("DELETE FROM lyric_files WHERE sha256 = ?", (sha,))
            doomed.append(data_root / "lyrics" / sha)
    return doomed


def _annotation(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "asset_id": row["asset_id"],
        "segment_id": row["segment_id"],
        "start_s": row["start_s"],
        "end_s": row["end_s"],
        "text": row["text"],
        "created_at": row["created_at"],
    }


def _normalize(text: str) -> str:
    kept = [ch for ch in text.casefold() if ch.isalnum() or ch.isspace()]
    return " ".join("".join(kept).split())


def _persisted_records(data_root: Path, sha256: str) -> tuple[list[dict], bool]:
    path = data_root / "analysis" / sha256 / ANALYSIS_VERSION / "evidence.json"
    if not path.is_file():
        return [], False
    payload = json.loads(path.read_text())
    if payload.get("algorithm_version") != ANALYSIS_VERSION:
        return [], False
    records = []
    for item in payload.get("records") or []:
        if not item.get("id"):
            continue
        records.append(
            {
                "id": item["id"],
                "evidence_class": item.get("kind") or "unknown",
                "name": item.get("name") or item["id"],
                "interval_s": item.get("interval_s"),
                "value": item.get("value"),
                "unit": item.get("unit"),
                "method": item.get("method") or "",
                "analysis_version": ANALYSIS_VERSION,
                "lyric_document_id": None,
                "lyric_revision": None,
                "cites": [],
                "caveat": item.get("caveat") or "",
                "persisted": True,
            }
        )
    return records, True


def _ready_chart(data_root: Path, sha256: str, kind: str) -> dict | None:
    path = data_root / "analysis" / sha256 / ANALYSIS_VERSION / f"{kind}.json"
    if not path.is_file():
        return None
    document = json.loads(path.read_text())
    if document.get("status") != "ready" or document.get("method_version") != ANALYSIS_VERSION:
        return None
    return document


def _derived_records(charts: dict[str, dict | None]) -> list[dict]:
    records = []
    t02 = charts.get("T02")
    if t02 is not None:
        for name, evidence_id in (
            ("1 s RMS", "ev:t02:rms-1s"),
            ("3 s short-term LUFS", "ev:t02:short-term-lufs"),
        ):
            line = _line(t02, name)
            if line is not None:
                records.append(_view(evidence_id, "measured", name, line.get("unit"), t02))
        if (t02.get("series") or {}).get("bars"):
            records.append(_view("ev:t02:windows", "measured", "analysis windows", "dB", t02))
    if charts.get("T08") is not None:
        records.append(
            _view(
                "ev:t08:provisional-change",
                "estimated",
                "provisional_change",
                None,
                charts["T08"],
            )
        )
    if charts.get("T09") is not None:
        records.append(
            _view("ev:t09:similarity", "estimated", "spectral similarity", None, charts["T09"])
        )
    return records


def _view(evidence_id: str, evidence_class: str, name: str, unit: str | None, chart: dict) -> dict:
    return {
        "id": evidence_id,
        "evidence_class": evidence_class,
        "name": name,
        "interval_s": None,
        "value": None,
        "unit": unit,
        "method": chart.get("method_id") or "",
        "analysis_version": ANALYSIS_VERSION,
        "lyric_document_id": None,
        "lyric_revision": None,
        "cites": [],
        "caveat": "Stored chart series. Not recomputed.",
        "persisted": False,
    }


def _line(document: dict, name: str) -> dict | None:
    for line in (document.get("series") or {}).get("lines") or []:
        if line.get("name") == name and len(line.get("x") or []) == len(line.get("y") or []):
            return line
    return None


def _lyric_records(document: dict, t02: dict | None) -> list[dict]:
    records = []
    groups: dict[str, list[dict]] = {}
    rms = _line(t02, "1 s RMS") if t02 else None
    lufs = _line(t02, "3 s short-term LUFS") if t02 else None
    for segment in document["segments"]:
        records.append(_line_record(document, segment))
        key = _normalize(segment["text"])
        if key:
            groups.setdefault(key, []).append(segment)
        if segment["usable"]:
            records.append(_density_record(document, segment))
            _append_mean(
                records,
                document,
                segment,
                rms,
                "ly:level:",
                "ev:t02:rms-1s",
                "dBFS",
                square=True,
            )
            _append_mean(
                records,
                document,
                segment,
                lufs,
                "ly:lufs:",
                "ev:t02:short-term-lufs",
                "LUFS",
                square=False,
            )
    for key, group in groups.items():
        if len(group) < 2:
            continue
        token = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
        records.append(
            _lyric_ref(
                document,
                f"ly:repeat:{token}",
                "textual",
                key,
                float(len(group)),
                None,
                "written-tokens-v1",
                [f"ly:{segment['id']}" for segment in group],
                "A normalized line that occurs more than once. Not a melody or hook.",
                None,
            )
        )
    return records


def _line_record(document: dict, segment: dict) -> dict:
    interval = [segment["start_s"], segment["end_s"]] if segment["usable"] else None
    verified = "true" if segment["artist_verified"] else "false"
    return _lyric_ref(
        document,
        f"ly:{segment['id']}",
        "textual",
        "lyric_line",
        segment["text"],
        None,
        "written-tokens-v1",
        [],
        (
            f"timing_origin={segment['timing_origin']}. artist_verified={verified}. "
            "Written text is not sung timing."
        ),
        interval,
    )


def _density_record(document: dict, segment: dict) -> dict:
    span = segment["end_s"] - segment["start_s"]
    return _lyric_ref(
        document,
        f"ly:density:{segment['id']}",
        "textual",
        "written_words_per_second",
        word_count(segment["text"]) / span,
        "words/s",
        "written-tokens-v1",
        [f"ly:{segment['id']}"],
        "Written tokens per second of the supplied interval. Not vocal delivery or breaths.",
        [segment["start_s"], segment["end_s"]],
    )


def _mean_square_db(levels: list[float]) -> float:
    """Invert T02's 10*log10(mean square), average power, and convert back."""
    power = sum(10 ** (level / 10.0) for level in levels) / len(levels)
    return 10.0 * math.log10(power)


def _append_mean(
    records: list[dict],
    document: dict,
    segment: dict,
    line: dict | None,
    prefix: str,
    source_id: str,
    unit: str,
    square: bool,
) -> None:
    if line is None:
        return
    samples = [
        value
        for time_s, value in zip(line["x"], line["y"], strict=True)
        if value is not None and segment["start_s"] <= float(time_s) < segment["end_s"]
    ]
    if not samples:
        return
    if square:
        value = _mean_square_db(samples)
        method = "t02-stored-mean-square-v1"
        caveat = _RMS_CAVEAT
    else:
        value = sum(samples) / len(samples)
        method = "t02-stored-sample-mean-v1"
        caveat = _LUFS_CAVEAT
    records.append(
        _lyric_ref(
            document,
            f"{prefix}{segment['id']}",
            "measured",
            source_id,
            value,
            unit,
            method,
            [f"ly:{segment['id']}", source_id],
            caveat,
            [segment["start_s"], segment["end_s"]],
        )
    )


def _lyric_ref(
    document: dict,
    evidence_id: str,
    evidence_class: str,
    name: str,
    value: float | str | None,
    unit: str | None,
    method: str,
    cites: list[str],
    caveat: str,
    interval: list[float] | None,
) -> dict:
    analysis = ANALYSIS_VERSION if evidence_class == "measured" else None
    return {
        "id": evidence_id,
        "evidence_class": evidence_class,
        "name": name,
        "interval_s": interval,
        "value": value,
        "unit": unit,
        "method": method,
        "analysis_version": analysis,
        "lyric_document_id": document["id"],
        "lyric_revision": document["revision"],
        "cites": cites,
        "caveat": caveat,
        "persisted": False,
    }
