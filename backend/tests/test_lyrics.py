import asyncio
import hashlib
import json
import math
import sqlite3
from pathlib import Path

import anyio
import pytest
from app.config import Settings
from app.db import MIGRATIONS, _migrate_v2, connect
from app.lyric_charts import build_lyric_chart
from app.lyrics import word_count
from app.main import create_app
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from tests.test_milestone0 import _project, _upload
from tests.wavgen import pcm_wav


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_root=tmp_path / "data",
        max_bytes=500 * 1024 * 1024,
        max_duration_s=900,
        cors_origin="http://127.0.0.1:5173",
    )


@pytest.fixture
def client(settings: Settings):
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client
    app.state.db.close()


def _wav(path: Path) -> None:
    pcm_wav(path, [1000] * 16000, 8000, 1, 16)


def _study(client: TestClient, tmp_path: Path, name: str = "Study") -> tuple[str, str]:
    path = tmp_path / f"{name}.wav"
    _wav(path)
    project_id = _project(client, name)
    uploaded = _upload(client, project_id, path)
    assert uploaded.status_code == 200, uploaded.text
    return project_id, uploaded.json()["asset"]["id"]


def _post(client: TestClient, project_id: str, asset_id: str, name: str, content: bytes):
    return client.post(
        f"/api/projects/{project_id}/assets/{asset_id}/lyrics",
        files={"file": (name, content, "text/plain")},
    )


def _plant(settings: Settings, sha: str) -> tuple[Path, Path, Path]:
    dest = settings.data_root / "analysis" / sha / "m1-v3"
    dest.mkdir(parents=True)
    metrics = dest / "metrics.json"
    evidence = dest / "evidence.json"
    t02 = dest / "T02.json"
    metrics.write_text('{"algorithm_version":"m1-v3"}\n')
    evidence.write_text(
        json.dumps(
            {
                "algorithm_version": "m1-v3",
                "asset_id": "asset",
                "records": [
                    {
                        "id": "ev:rms_dbfs",
                        "kind": "measured",
                        "name": "rms_dbfs",
                        "interval_s": [0.0, 2.0],
                        "value": -20.0,
                        "unit": "dBFS",
                        "method": "rms:m1-v3",
                        "caveat": "RMS is not loudness.",
                    }
                ],
            }
        )
    )
    t02.write_text(
        json.dumps(
            {
                "status": "ready",
                "method_version": "m1-v3",
                "method_id": "ffmpeg-ebur128+frame-rms-v1",
                "series": {
                    "lines": [
                        {"name": "1 s RMS", "unit": "dBFS", "x": [0.5], "y": [-12.0]},
                    ]
                },
            }
        )
    )
    return metrics, evidence, t02


def test_word_count_keeps_markdown_marks() -> None:
    assert word_count("## Keep *this*") == 2


def test_empty_srt_and_txt(client: TestClient, tmp_path: Path) -> None:
    project_id, asset_id = _study(client, tmp_path)
    empty_srt = _post(client, project_id, asset_id, "empty.srt", b"")
    assert empty_srt.status_code == 201, empty_srt.text
    body = empty_srt.json()
    assert body["segments"] == []
    assert body["validation"] == [
        {"segment_id": None, "code": "unparsed", "detail": "no SRT cues"}
    ]
    empty_txt = _post(client, project_id, asset_id, "empty.txt", b"")
    assert empty_txt.status_code == 201, empty_txt.text
    assert empty_txt.json()["segments"] == []
    assert empty_txt.json()["validation"] == []
    assert empty_txt.json()["revision"] == 1


def test_lines_are_unplaced_and_markdown_text_is_kept(
    client: TestClient, tmp_path: Path
) -> None:
    project_id, asset_id = _study(client, tmp_path)
    uploaded = _post(client, project_id, asset_id, "song.md", b"## Keep *this*\n\nNext\n")
    assert uploaded.status_code == 201, uploaded.text
    segments = uploaded.json()["segments"]
    assert [item["text"] for item in segments] == ["## Keep *this*", "Next"]
    assert [item["timing_origin"] for item in segments] == ["unplaced", "unplaced"]
    assert all(item["start_s"] is None and item["end_s"] is None for item in segments)
    assert all(item["usable"] is False and item["artist_verified"] is False for item in segments)


def test_srt_keeps_reversed_malformed_overlap_and_range(
    client: TestClient, tmp_path: Path
) -> None:
    project_id, asset_id = _study(client, tmp_path)
    content = (
        "1\n"
        "00:00:02,000 --> 00:00:01,000\n"
        "Backwards\n\n"
        "2\n"
        "not a time\n"
        "Kept\n\n"
        "3\n"
        "00:00:00,000 --> 00:00:01,500\n"
        "One\n\n"
        "4\n"
        "00:00:01,000 --> 00:00:02,000\n"
        "Two\n\n"
        "5\n"
        "00:00:00,000 --> 00:00:03,000\n"
        "Late\n"
    )
    uploaded = _post(client, project_id, asset_id, "cues.srt", content.encode())
    assert uploaded.status_code == 201, uploaded.text
    body = uploaded.json()
    by_text = {item["text"]: item for item in body["segments"]}
    backwards = by_text["Backwards"]
    assert backwards["start_s"] == 2
    assert backwards["end_s"] == 1
    assert backwards["timing_origin"] == "subtitle_supplied"
    assert backwards["usable"] is False
    assert backwards["artist_verified"] is False
    malformed = by_text["not a time\nKept"]
    assert malformed["start_s"] is None and malformed["end_s"] is None
    assert malformed["timing_origin"] == "unplaced"
    late = by_text["Late"]
    assert late["usable"] is False
    assert late["start_s"] == 0 and late["end_s"] == 3
    codes = {(row["segment_id"], row["code"]) for row in body["validation"]}
    assert (backwards["id"], "reversed_time") in codes
    assert (malformed["id"], "malformed_time") in codes
    assert (late["id"], "out_of_range") in codes
    one = by_text["One"]
    two = by_text["Two"]
    assert one["usable"] is True and two["usable"] is True
    overlap = [row for row in body["validation"] if row["code"] == "overlap"]
    assert {row["segment_id"] for row in overlap} == {one["id"], two["id"]}
    assert any(row["detail"] == f"{one['id']} overlaps {two['id']}" for row in overlap)
    assert any(row["detail"] == f"{two['id']} overlaps {one['id']}" for row in overlap)


def test_source_bytes_survive_a_text_edit(client: TestClient, tmp_path: Path) -> None:
    project_id, asset_id = _study(client, tmp_path)
    raw = b"1\n00:00:00,000 --> 00:00:01,000\nHello\n"
    uploaded = _post(client, project_id, asset_id, "hello.srt", raw)
    segment_id = uploaded.json()["segments"][0]["id"]
    edited = client.put(
        f"/api/projects/{project_id}/assets/{asset_id}/lyric-segments/{segment_id}",
        json={"expected_revision": 1, "text": "Changed"},
    )
    assert edited.status_code == 200, edited.text
    source = client.get(f"/api/projects/{project_id}/assets/{asset_id}/lyrics/source")
    assert source.status_code == 200
    assert source.content == raw


def test_text_edit_of_reversed_cue_keeps_supplied_times(
    client: TestClient, tmp_path: Path
) -> None:
    project_id, asset_id = _study(client, tmp_path)
    raw = b"1\n00:00:02,000 --> 00:00:01,000\nBackwards\n"
    uploaded = _post(client, project_id, asset_id, "back.srt", raw)
    segment = uploaded.json()["segments"][0]
    edited = client.put(
        f"/api/projects/{project_id}/assets/{asset_id}/lyric-segments/{segment['id']}",
        json={"expected_revision": 1, "text": "Still backwards"},
    )
    assert edited.status_code == 200, edited.text
    current = edited.json()["segments"][0]
    assert current["text"] == "Still backwards"
    assert current["start_s"] == 2 and current["end_s"] == 1
    assert current["timing_origin"] == "subtitle_supplied"
    assert current["artist_verified"] is False


def test_time_edit_verify_and_note(client: TestClient, tmp_path: Path) -> None:
    project_id, asset_id = _study(client, tmp_path)
    uploaded = _post(client, project_id, asset_id, "line.txt", b"Hello\n")
    segment_id = uploaded.json()["segments"][0]["id"]
    base = f"/api/projects/{project_id}/assets/{asset_id}/lyric-segments/{segment_id}"
    rejected = client.post(base + "/verify", json={"expected_revision": 1, "verified": True})
    assert rejected.status_code == 422
    assert rejected.json()["error"] == "interval_not_usable"
    assert client.get(f"/api/projects/{project_id}/assets/{asset_id}/lyrics").json()["segments"][0][
        "timing_origin"
    ] == "unplaced"
    moved = client.put(
        base,
        json={"expected_revision": 1, "start_s": 0.2, "end_s": 0.8},
    )
    assert moved.status_code == 200, moved.text
    body = moved.json()
    assert body["revision"] == 2
    current = body["segments"][0]
    assert current["id"] == segment_id
    assert current["timing_origin"] == "manual_edit"
    assert current["artist_verified"] is False
    noted = client.put(base, json={"expected_revision": 2, "note": "listen here"})
    assert noted.status_code == 200, noted.text
    assert noted.json()["revision"] == 3
    assert noted.json()["segments"][0]["timing_origin"] == "manual_edit"
    assert noted.json()["segments"][0]["note"] == "listen here"
    verified = client.post(base + "/verify", json={"expected_revision": 3, "verified": True})
    assert verified.status_code == 200, verified.text
    assert verified.json()["segments"][0]["timing_origin"] == "manual_verified"
    assert verified.json()["segments"][0]["artist_verified"] is True
    cleared = client.post(
        base + "/verify",
        json={"expected_revision": verified.json()["revision"], "verified": False},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["segments"][0]["timing_origin"] == "manual_edit"
    assert cleared.json()["segments"][0]["artist_verified"] is False
    rows = client.app.state.db.execute(
        "SELECT COUNT(*) FROM lyric_segment_revisions WHERE segment_id = ?",
        (segment_id,),
    ).fetchone()[0]
    assert rows >= 2


def test_stale_revision_does_not_overwrite(client: TestClient, tmp_path: Path) -> None:
    project_id, asset_id = _study(client, tmp_path)
    uploaded = _post(client, project_id, asset_id, "line.txt", b"Hello\n")
    segment_id = uploaded.json()["segments"][0]["id"]
    url = f"/api/projects/{project_id}/assets/{asset_id}/lyric-segments/{segment_id}"
    first = client.put(url, json={"expected_revision": 1, "text": "Newer"})
    assert first.status_code == 200, first.text
    stale = client.put(url, json={"expected_revision": 1, "text": "Older"})
    assert stale.status_code == 409
    assert stale.json()["error"] == "stale_revision"
    assert stale.json()["current_revision"] == 2
    current = client.get(f"/api/projects/{project_id}/assets/{asset_id}/lyrics").json()
    assert current["segments"][0]["text"] == "Newer"


def test_project_isolation(client: TestClient, tmp_path: Path) -> None:
    path = tmp_path / "shared.wav"
    _wav(path)
    project_a = _project(client, "A")
    project_b = _project(client, "B")
    asset_id = _upload(client, project_a, path).json()["asset"]["id"]
    assert _upload(client, project_b, path).json()["asset"]["id"] == asset_id
    uploaded = _post(client, project_a, asset_id, "a.txt", b"Only A\n")
    segment_id = uploaded.json()["segments"][0]["id"]
    missing = client.get(f"/api/projects/{project_b}/assets/{asset_id}/lyrics")
    assert missing.status_code == 404
    assert missing.json()["error"] == "no_lyrics"
    foreign = client.put(
        f"/api/projects/{project_b}/assets/{asset_id}/lyric-segments/{segment_id}",
        json={"expected_revision": 1, "text": "Nope"},
    )
    assert foreign.status_code == 404
    assert foreign.json()["error"] == "not_current"
    assert client.get(f"/api/projects/{project_a}/assets/{asset_id}/lyrics").json()["segments"][0][
        "text"
    ] == "Only A"


def test_shared_lyric_file_is_removed_with_the_last_upload(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    path = tmp_path / "shared.wav"
    _wav(path)
    project_a = _project(client, "A")
    project_b = _project(client, "B")
    asset_id = _upload(client, project_a, path).json()["asset"]["id"]
    _upload(client, project_b, path)
    raw = b"Same line\n"
    digest = hashlib.sha256(raw).hexdigest()
    assert _post(client, project_a, asset_id, "a.txt", raw).status_code == 201
    assert _post(client, project_b, asset_id, "b.txt", raw).status_code == 201
    stored = settings.data_root / "lyrics" / digest
    assert stored.read_bytes() == raw
    blob = settings.data_root / "blobs" / _upload(client, project_a, path).json()["asset"]["sha256"]
    assert client.delete(f"/api/projects/{project_a}/assets/{asset_id}/lyrics").status_code == 204
    assert stored.is_file()
    assert client.delete(f"/api/projects/{project_b}/assets/{asset_id}/lyrics").status_code == 204
    assert not stored.exists()
    assert blob.is_file()


def test_lyric_edits_do_not_change_analysis_files(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    project_id, asset_id = _study(client, tmp_path)
    asset = client.get(f"/api/projects/{project_id}").json()["assets"][0]
    metrics, evidence, t02 = _plant(settings, asset["sha256"])
    before = (metrics.read_bytes(), evidence.read_bytes(), t02.read_bytes())
    jobs = client.app.state.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    uploaded = _post(
        client,
        project_id,
        asset_id,
        "timed.srt",
        b"1\n00:00:00,000 --> 00:00:01,000\nHello\n",
    )
    segment_id = uploaded.json()["segments"][0]["id"]
    url = f"/api/projects/{project_id}/assets/{asset_id}/lyric-segments/{segment_id}"
    assert client.put(url, json={"expected_revision": 1, "start_s": 0.1, "end_s": 0.4}).status_code == 200
    assert client.post(url + "/verify", json={"expected_revision": 2, "verified": True}).status_code == 200
    assert (metrics.read_bytes(), evidence.read_bytes(), t02.read_bytes()) == before
    assert client.app.state.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == jobs
    assert client.get(f"/api/projects/{project_id}").json()["assets"][0]["sha256"] == asset["sha256"]
    assert client.get(f"/api/projects/{project_id}").json()["assets"][0]["analysis_status"] == "not_run"


def test_level_uses_stored_t02_sample(client: TestClient, settings: Settings, tmp_path: Path) -> None:
    project_id, asset_id = _study(client, tmp_path)
    asset = client.get(f"/api/projects/{project_id}").json()["assets"][0]
    _metrics, evidence, t02 = _plant(settings, asset["sha256"])
    before = evidence.read_bytes(), t02.read_bytes()
    uploaded = _post(
        client,
        project_id,
        asset_id,
        "timed.srt",
        b"1\n00:00:00,000 --> 00:00:01,000\nHello\n",
    )
    segment_id = uploaded.json()["segments"][0]["id"]
    bundle = client.get(f"/api/projects/{project_id}/assets/{asset_id}/evidence")
    assert bundle.status_code == 200, bundle.text
    records = {item["id"]: item for item in bundle.json()["records"]}
    assert records["ev:rms_dbfs"]["persisted"] is True
    assert records["ev:rms_dbfs"]["evidence_class"] == "measured"
    level = records[f"ly:level:{segment_id}"]
    assert level["value"] == -12.0
    assert level["evidence_class"] == "measured"
    assert level["persisted"] is False
    assert level["cites"] == [f"ly:{segment_id}", "ev:t02:rms-1s"]
    assert level["method"] == "t02-stored-mean-square-v1"
    assert (evidence.read_bytes(), t02.read_bytes()) == before
    raw = client.get(f"/api/assets/{asset_id}/evidence")
    assert raw.status_code == 200
    assert raw.json()["records"][0]["kind"] == "measured"


def test_annotation_is_a_note(client: TestClient, tmp_path: Path) -> None:
    project_id, asset_id = _study(client, tmp_path)
    created = client.post(
        f"/api/projects/{project_id}/assets/{asset_id}/annotations",
        json={"start_s": 0.1, "end_s": 0.4, "text": "check the tail"},
    )
    assert created.status_code == 201, created.text
    assert "review_status" not in created.json()
    removed = client.delete(
        f"/api/projects/{project_id}/assets/{asset_id}/annotations/{created.json()['id']}"
    )
    assert removed.status_code == 204
    assert client.get(f"/api/projects/{project_id}/assets/{asset_id}/annotations").json() == []


def test_level_uses_mean_square_of_loud_and_silent_frames(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    project_id, asset_id = _study(client, tmp_path)
    asset = client.get(f"/api/projects/{project_id}").json()["assets"][0]
    dest = settings.data_root / "analysis" / asset["sha256"] / "m1-v3"
    dest.mkdir(parents=True)
    (dest / "T02.json").write_text(
        json.dumps(
            {
                "status": "ready",
                "method_version": "m1-v3",
                "method_id": "ffmpeg-ebur128+frame-rms-v1",
                "series": {
                    "lines": [
                        {
                            "name": "1 s RMS",
                            "unit": "dBFS",
                            "x": [0.5, 1.5],
                            "y": [0.0, -60.0],
                        }
                    ]
                },
            }
        )
    )
    uploaded = _post(
        client,
        project_id,
        asset_id,
        "span.srt",
        b"1\n00:00:00,000 --> 00:00:02,000\nBoth\n",
    )
    segment_id = uploaded.json()["segments"][0]["id"]
    bundle = client.get(f"/api/projects/{project_id}/assets/{asset_id}/evidence")
    level = {item["id"]: item for item in bundle.json()["records"]}[f"ly:level:{segment_id}"]
    power = (1.0 + 10 ** (-60 / 10)) / 2
    assert level["value"] == pytest.approx(10 * math.log10(power))
    assert level["method"] == "t02-stored-mean-square-v1"
    assert "10*log10" in level["caveat"]
    assert "not vocal energy" in level["caveat"].lower()


def test_existing_m1_database_gains_lyric_tables(tmp_path: Path) -> None:
    database = tmp_path / "studio.sqlite3"
    conn = sqlite3.connect(database)
    conn.executescript((MIGRATIONS / "001_init.sql").read_text())
    conn.execute("PRAGMA user_version = 1")
    conn.commit()
    _migrate_v2(conn)
    conn.execute(
        """
        INSERT INTO projects (id, name, mode, created_at, updated_at)
        VALUES ('project', 'Study', 'study', 't', 't')
        """
    )
    conn.execute(
        """
        INSERT INTO assets (
          id, sha256, original_name, byte_length, duration_s, sample_rate, channels,
          subtype, analysis_status, playback_status, created_at
        ) VALUES (
          'asset', ?, 'master.wav', 8, 1.0, 8000, 1, 'pcm_16', 'completed', 'ready', 't'
        )
        """,
        ("ab" * 32,),
    )
    conn.execute(
        """
        INSERT INTO project_assets (project_id, asset_id, ordering)
        VALUES ('project', 'asset', 0)
        """
    )
    conn.execute(
        """
        INSERT INTO analysis_runs (
          id, asset_id, algorithm_version, params_hash, status, metrics_path, evidence_path
        ) VALUES ('run', 'asset', 'm1-v3', 'params', 'completed', 'metrics.json', 'evidence.json')
        """
    )
    conn.commit()
    conn.close()
    upgraded = connect(database)
    try:
        assert upgraded.execute("PRAGMA user_version").fetchone()[0] == 4
        assert upgraded.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'export_runs'"
        ).fetchone()
        assert upgraded.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        asset = upgraded.execute(
            "SELECT sha256, analysis_status FROM assets WHERE id = 'asset'"
        ).fetchone()
        assert asset["sha256"] == "ab" * 32
        assert asset["analysis_status"] == "completed"
        run = upgraded.execute(
            "SELECT algorithm_version, status FROM analysis_runs WHERE id = 'run'"
        ).fetchone()
        assert run["algorithm_version"] == "m1-v3"
        assert run["status"] == "completed"
        assert upgraded.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'lyric_documents'"
        ).fetchone()
    finally:
        upgraded.close()


def test_narrative_and_export_routes_are_absent(client: TestClient, tmp_path: Path) -> None:
    project_id, _asset_id = _study(client, tmp_path)
    assert client.post(f"/api/projects/{project_id}/narratives").status_code == 404
    assert client.post(f"/api/projects/{project_id}/exports").status_code == 404


def test_concurrent_lyric_gets_return_the_same_document(settings: Settings, tmp_path: Path) -> None:
    app = create_app(settings)
    path = tmp_path / "tone.wav"
    _wav(path)

    async def burst() -> list[tuple[int, str | None]]:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            project = (await http.post("/api/projects", json={"name": "Study"})).json()
            uploaded = await http.post(
                f"/api/projects/{project['id']}/assets",
                files={"file": ("tone.wav", path.read_bytes(), "audio/wav")},
            )
            assert uploaded.status_code == 200, uploaded.text
            asset_id = uploaded.json()["asset"]["id"]
            lyric = await http.post(
                f"/api/projects/{project['id']}/assets/{asset_id}/lyrics",
                files={"file": ("lines.txt", b"first line\n", "text/plain")},
            )
            assert lyric.status_code == 201, lyric.text
            url = f"/api/projects/{project['id']}/assets/{asset_id}/lyrics"

            async def once() -> tuple[int, str | None]:
                response = await http.get(url)
                body = response.json()
                return response.status_code, body.get("id")

            return list(await asyncio.gather(*[once() for _ in range(32)]))

    try:
        results = anyio.run(burst)
    finally:
        app.state.db.close()
    assert {status for status, _document_id in results} == {200}
    assert len({document_id for _status, document_id in results}) == 1


_WORD_CAVEAT = "Word counts are written tokens, not vocal delivery or breaths."
_TIMED_CAVEAT = (
    "Interval values are means of stored full-mix samples. "
    "They are not singing intensity, vocal energy, or emotion."
)
_LEVEL_VALUE = (
    "The written intervals 0.000\u20131.000 s and 1.000\u20132.000 s differ by -10.00 dB "
    "in the mean of stored 1 s RMS values. "
    "Transferable mechanism: a later lyric can change where the full mix already changes level. "
    "This is not singing intensity, vocal performance, or emotion."
)
_REPEAT_VALUE = (
    "A written line occurs 2 times. "
    "Transferable mechanism: a later lyric can bring a phrase back. "
    "Do not copy this recording's words. The repeat is not a melody or hook."
)


def _segment(
    segment_id: str,
    text: str,
    start: float | None,
    end: float | None,
    *,
    usable_interval: bool,
    origin: str = "subtitle_supplied",
    ordinal: int = 0,
) -> dict:
    return {
        "id": segment_id,
        "ordinal": ordinal,
        "text": text,
        "start_s": start,
        "end_s": end,
        "timing_origin": origin,
        "usable": usable_interval,
    }


def _bundle(records: list[dict], *, version: str | None, document: dict | None) -> dict:
    return {
        "analysis_version": version,
        "lyric_document_id": None if document is None else document["id"],
        "lyric_revision": None if document is None else document["revision"],
        "records": records,
    }


def _document(segments: list[dict], validation: list[dict] | None = None) -> dict:
    return {"id": "doc", "revision": 3, "segments": segments, "validation": validation or []}


def _t02_pair() -> dict:
    return {
        "status": "ready",
        "method_version": "m1-v3",
        "method_id": "ffmpeg-ebur128+frame-rms-v1",
        "caveats": [
            "These are analysis windows, not verses, choruses, or emotional sections.",
        ],
        "series": {
            "lines": [
                {"name": "1 s RMS", "unit": "dBFS", "x": [0.5, 1.5], "y": [-12.0, -18.0]},
                {"name": "3 s short-term LUFS", "unit": "LUFS", "x": [0.5, 1.5], "y": [-14.0, -16.0]},
            ],
            "bars": [{"label": "0.0–1.0 s", "value": 1.25}],
        },
    }


def _view(evidence_id: str, evidence_class: str = "measured") -> dict:
    return {
        "id": evidence_id,
        "evidence_class": evidence_class,
        "name": evidence_id,
        "value": None,
        "unit": None,
        "cites": [],
        "caveat": "Stored chart series. Not recomputed.",
        "persisted": False,
    }


def _level(segment_id: str, value: float, start: float, end: float) -> dict:
    return {
        "id": f"ly:level:{segment_id}",
        "evidence_class": "measured",
        "name": "ev:t02:rms-1s",
        "value": value,
        "unit": "dBFS",
        "interval_s": [start, end],
        "cites": [f"ly:{segment_id}", "ev:t02:rms-1s"],
        "caveat": "stored mean",
        "persisted": False,
    }


def test_lyric_chart_module_does_not_measure() -> None:
    source = Path(build_lyric_chart.__code__.co_filename).read_text()
    assert "app.measure" not in source
    assert "app.charts" not in source
    assert "decode_wav" not in source


def test_l03_reuses_stored_series_and_bundle_means() -> None:
    first = _segment("a", "One", 0.0, 1.0, usable_interval=True, ordinal=0)
    second = _segment("b", "Two", 1.0, 2.0, usable_interval=True, ordinal=1)
    document = _document([first, second])
    records = [
        _view("ev:t02:rms-1s"),
        _view("ev:t02:short-term-lufs"),
        _level("a", -3.5, 0.0, 1.0),
        _level("b", -4.5, 1.0, 2.0),
    ]
    chart = build_lyric_chart(
        "L03",
        _bundle(records, version="m1-v3", document=document),
        {"T02": _t02_pair()},
        document,
    )
    copied = chart["series"]["lines"][0]
    assert copied["x"] == [0.5, 1.5]
    assert copied["y"] == [-12.0, -18.0]
    assert copied["evidence_id"] == "ev:t02:rms-1s"
    assert chart["series"]["lines"][1]["unit"] == "LUFS"
    assert chart["series"]["bars"] == []
    assert [(item["start_s"], item["end_s"]) for item in chart["regions"]] == [(0.0, 1.0), (1.0, 2.0)]
    summary = " ".join(item["value"] for item in chart["summary"])
    assert "-3.50 dBFS" in summary
    assert "-4.50 dBFS" in summary
    assert "Stored 1 s RMS means differ by -1.00 dB." in summary
    assert _TIMED_CAVEAT in chart["caveats"]
    assert chart["evidence_class"] == "unknown"
    assert chart["analysis_version"] == "m1-v3"


def test_l03_without_lyrics_keeps_stored_windows() -> None:
    chart = build_lyric_chart(
        "L03",
        _bundle([], version="m1-v3", document=None),
        {"T02": _t02_pair()},
        None,
    )
    assert chart["status"] == "ready"
    assert chart["evidence_class"] == "measured"
    assert chart["regions"] == []
    assert chart["series"]["bars"][0]["label"] == "0.0–1.0 s"
    assert any(
        item["label"] == "Lyric timing" and item["value"].startswith("unavailable")
        for item in chart["summary"]
    )
    assert any("analysis windows, not verses" in caveat for caveat in chart["caveats"])


def test_reversed_cues_are_not_lyric_regions() -> None:
    segment = _segment("a", "Backwards", 2.0, 1.0, usable_interval=False)
    document = _document([segment], [{"code": "reversed_time", "segment_id": "a", "detail": "2 > 1"}])
    charts = {"T02": _t02_pair()}
    bundle = _bundle([], version="m1-v3", document=document)
    for kind in ("L01", "L03"):
        chart = build_lyric_chart(kind, bundle, charts, document)
        assert chart["regions"] == []
        assert chart["status"] == "ready"
    counts = {
        item["label"]: item["value"]
        for item in build_lyric_chart("L01", bundle, charts, document)["summary"]
    }
    assert counts["Reversed cues"] == "1"
    assert counts["Lyric timing"] == "unavailable"
    empty_t08 = {
        "status": "ready",
        "method_version": "m1-v3",
        "review_markers": [],
        "caveats": ["No change point passed the prominence gate."],
    }
    quiet = build_lyric_chart("L01", bundle, {"T02": _t02_pair(), "T08": empty_t08}, document)
    assert quiet["review_markers"] == []
    assert "No change point passed the prominence gate." in quiet["caveats"]
    assert "Provisional change markers are unavailable." not in quiet["caveats"]


def test_l02_keeps_written_counts_without_a_time_axis() -> None:
    document = _document(
        [
            _segment("a", "Hello there", None, None, usable_interval=False, origin="unplaced"),
            _segment("b", "## Keep *this*", 0.0, 1.0, usable_interval=True, ordinal=1),
        ]
    )
    chart = build_lyric_chart("L02", _bundle([], version=None, document=document), {}, document)
    assert chart["status"] == "ready"
    assert chart["axis_definitions"]["x"] == "Line"
    assert chart["analysis_version"] is None
    assert chart["caveats"] == [_WORD_CAVEAT]
    assert [bar["value"] for bar in chart["series"]["bars"]] == [2.0, 2.0]
    assert chart["series"]["lines"][0]["y"] == [None, 2.0]
    assert chart["series"]["lines"][0]["unit"] == "words/s"
    labels = {item["label"]: item["value"] for item in chart["summary"]}
    assert labels["Unavailable timing"] == "1"
    assert labels["Supplied timing"] == "1"
    assert "vocal" not in chart["caveats"][0].lower() or "not vocal" in chart["caveats"][0].lower()


def test_l04_text_repeats_do_not_need_the_heatmap() -> None:
    document = _document(
        [
            _segment("a", "Again", None, None, usable_interval=False, origin="unplaced"),
            _segment("b", "Again", None, None, usable_interval=False, origin="unplaced", ordinal=1),
        ]
    )
    repeat = {
        "id": "ly:repeat:abc123",
        "evidence_class": "textual",
        "name": "again",
        "value": 2,
        "unit": None,
        "cites": ["ly:a", "ly:b"],
        "caveat": "Not a melody or hook.",
        "persisted": False,
    }
    bundle = _bundle([repeat], version=None, document=document)
    missing = build_lyric_chart("L04", bundle, {}, document)
    assert missing["status"] == "ready"
    assert missing["series"]["heatmap"] is None
    assert missing["rows"][0]["evidence_class"] == "textual"
    assert missing["rows"][0]["kind"] == "finding"
    assert "The recurrence chart is unavailable." in missing["caveats"]
    heat = {
        "status": "ready",
        "method_version": "m1-v3",
        "caveats": ["A bright cell is not a matching melody or hook."],
        "axis_definitions": {"x": "Time (s)", "y": "Time (s)", "y_scale": "linear"},
        "series": {"heatmap": {"x": [0.0, 2.0], "y": [0.0, 2.0], "z": [[1.0, 0.2], [0.2, 1.0]]}},
    }
    audio_only = build_lyric_chart("L04", _bundle([], version="m1-v3", document=None), {"T09": heat}, None)
    assert audio_only["series"]["heatmap"]["z"] == [[1.0, 0.2], [0.2, 1.0]]
    assert audio_only["rows"] == []
    assert any("Text repetition is unavailable." in item["value"] for item in audio_only["summary"])
    neither = build_lyric_chart("L04", _bundle([], version=None, document=None), {}, None)
    assert neither["status"] == "not_available"


def test_l05_principles_cite_findings_and_refuse_the_rest() -> None:
    document = _document(
        [
            _segment("a", "Bring it back", 0.0, 1.0, usable_interval=True),
            _segment("b", "Bring it back", 1.0, 2.0, usable_interval=True, ordinal=1),
        ]
    )
    records = [
        {
            "id": "ev:pulse_candidate_bpm",
            "evidence_class": "estimated",
            "name": "pulse",
            "value": 120.0,
            "unit": "BPM",
            "cites": [],
            "caveat": "candidate",
            "persisted": True,
        },
        _view("ev:t02:rms-1s"),
        _view("ev:t02:short-term-lufs"),
        _view("ev:t08:provisional-change", "estimated"),
        _view("ev:t09:similarity", "estimated"),
        {
            "id": "ly:a",
            "evidence_class": "textual",
            "name": "lyric_line",
            "value": "Bring it back",
            "unit": None,
            "cites": [],
            "caveat": "written",
            "persisted": False,
        },
        {
            "id": "ly:repeat:feed",
            "evidence_class": "textual",
            "name": "bring it back",
            "value": 2,
            "unit": None,
            "cites": ["ly:a", "ly:b"],
            "caveat": "Not a melody or hook.",
            "persisted": False,
        },
        _level("a", -10.0, 0.0, 1.0),
        _level("b", -20.0, 1.0, 2.0),
    ]
    chart = build_lyric_chart(
        "L05",
        _bundle(records, version="m1-v3", document=document),
        {},
        document,
    )
    findings = {row["evidence_id"] for row in chart["rows"] if row["kind"] == "finding"}
    principles = [row for row in chart["rows"] if row["kind"] == "principle"]
    assert "ev:pulse_candidate_bpm" in findings
    assert "ev:t08:provisional-change" not in findings
    assert "ev:t09:similarity" not in findings
    assert {row["evidence_id"] for row in principles} >= {
        "ly:principle:written-repetition:feed",
        "ly:principle:level-contrast",
    }
    for row in principles:
        assert set(row["cites"]) <= findings
    values = {row["evidence_id"]: row["value"] for row in principles}
    assert values["ly:principle:written-repetition:feed"] == _REPEAT_VALUE
    assert values["ly:principle:level-contrast"] == _LEVEL_VALUE
    refused = {item["code"]: item for item in chart["insufficient"]}
    for code in ("tempo", "melody", "section", "vocal", "emotion", "instrumentation"):
        assert code in refused
        assert code not in {row["name"] for row in principles}
    assert refused["tempo"]["cites"] == ["ev:pulse_candidate_bpm"]
    assert refused["melody"]["cites"] == ["ev:t09:similarity"]
    assert refused["section"]["cites"] == ["ev:t08:provisional-change"]
    assert refused["vocal"]["cites"] == []
    assert "written_repetition" not in refused
    assert "level_contrast" not in refused


def test_l05_refuses_small_overlap_and_missing_evidence() -> None:
    small = [
        _view("ev:t02:rms-1s"),
        _level("a", -10.0, 0.0, 1.0),
        _level("b", -10.4, 1.0, 2.0),
    ]
    chart = build_lyric_chart("L05", _bundle(small, version="m1-v3", document=None), {}, None)
    refused = {item["code"]: item["reason"] for item in chart["insufficient"]}
    assert "0.40 dB" in refused["level_contrast"]
    assert "1.00 dB" in refused["level_contrast"]
    assert all(row["name"] != "level_contrast" for row in chart["rows"])
    overlap = [
        _view("ev:t02:rms-1s"),
        _level("a", -10.0, 0.0, 2.0),
        _level("b", -20.0, 1.0, 3.0),
    ]
    overlapped = build_lyric_chart("L05", _bundle(overlap, version="m1-v3", document=None), {}, None)
    reason = next(item["reason"] for item in overlapped["insufficient"] if item["code"] == "level_contrast")
    assert "overlap" in reason
    pulse = build_lyric_chart(
        "L05",
        _bundle(
            [
                {
                    "id": "ev:pulse_candidate_bpm",
                    "evidence_class": "estimated",
                    "name": "pulse",
                    "value": 90,
                    "unit": "BPM",
                    "cites": [],
                    "caveat": "candidate",
                    "persisted": True,
                }
            ],
            version="m1-v3",
            document=None,
        ),
        {},
        None,
    )
    assert pulse["rows"][0]["evidence_class"] == "estimated"
    assert pulse["rows"][0]["kind"] == "finding"
    assert all(row["kind"] != "principle" or row["name"] != "tempo" for row in pulse["rows"])
    empty = build_lyric_chart("L05", _bundle([], version=None, document=None), {}, None)
    assert empty["status"] == "not_available"
    assert empty["not_available_reason"] == "No technical evidence and no lyric document."


def _chart_url(project_id: str, asset_id: str, kind: str) -> str:
    return f"/api/projects/{project_id}/assets/{asset_id}/lyric-charts/{kind}/data"


def _write_chart(settings: Settings, sha: str, name: str, payload: dict) -> Path:
    dest = settings.data_root / "analysis" / sha / "m1-v3"
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / name
    path.write_text(json.dumps(payload))
    return path


def test_lyric_chart_routes_reuse_storage_without_a_job(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    project_id, asset_id = _study(client, tmp_path)
    asset = client.get(f"/api/projects/{project_id}").json()["assets"][0]
    sha = asset["sha256"]
    metrics, evidence, t02 = _plant(settings, sha)
    before = {
        "metrics": metrics.read_bytes(),
        "evidence": evidence.read_bytes(),
        "t02": t02.read_bytes(),
    }
    t08 = _write_chart(
        settings,
        sha,
        "T08.json",
        {
            "status": "ready",
            "method_version": "m1-v3",
            "review_markers": [
                {
                    "time_s": 1.0,
                    "kind": "provisional_change",
                    "label": "provisional change",
                    "value": "peak",
                    "caveat": "stored",
                }
            ],
        },
    )
    t09 = _write_chart(
        settings,
        sha,
        "T09.json",
        {
            "status": "ready",
            "method_version": "m1-v3",
            "caveats": ["A bright cell is not a matching melody or hook."],
            "axis_definitions": {"x": "Time (s)", "y": "Time (s)", "y_scale": "linear"},
            "series": {"heatmap": {"x": [0.0], "y": [0.0], "z": [[1.0]]}},
        },
    )
    before["t08"] = t08.read_bytes()
    before["t09"] = t09.read_bytes()
    jobs = client.app.state.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    listed = client.get(f"/api/projects/{project_id}/assets/{asset_id}/lyric-charts")
    assert listed.status_code == 200, listed.text
    assert [item["chart_kind"] for item in listed.json()["charts"]] == ["L01", "L02", "L03", "L04", "L05"]
    assert all(item["png_url"] is None for item in listed.json()["charts"])
    uploaded = _post(
        client,
        project_id,
        asset_id,
        "pair.srt",
        b"1\n00:00:00,000 --> 00:00:01,000\nBring it back\n\n"
        b"2\n00:00:01,000 --> 00:00:02,000\nBring it back\n",
    )
    assert uploaded.status_code == 201, uploaded.text
    l01 = client.get(_chart_url(project_id, asset_id, "L01")).json()
    assert l01["series"]["lines"][0]["y"] == [-12.0]
    assert l01["review_markers"][0]["caveat"] == "Not a verified verse, chorus, or section boundary."
    assert l01["regions"]
    l05 = client.get(_chart_url(project_id, asset_id, "L05")).json()
    findings = {row["evidence_id"] for row in l05["rows"] if row["kind"] == "finding"}
    for row in l05["rows"]:
        if row["kind"] == "principle":
            assert set(row["cites"]) <= findings
    assert any(item["code"] == "vocal" for item in l05["insufficient"])
    assert client.get(_chart_url(project_id, asset_id, "L99")).status_code == 404
    assert client.app.state.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == jobs
    assert metrics.read_bytes() == before["metrics"]
    assert evidence.read_bytes() == before["evidence"]
    assert t02.read_bytes() == before["t02"]
    assert t08.read_bytes() == before["t08"]
    assert t09.read_bytes() == before["t09"]
    other = _project(client, "Other")
    hidden = client.get(f"/api/projects/{other}/assets/{asset_id}/lyric-charts")
    assert hidden.status_code == 404
    assert hidden.json()["error"] == "not_in_project"
    missing = client.get(f"/api/projects/missing-project/assets/{asset_id}/lyric-charts")
    assert missing.status_code == 404
    assert missing.json()["error"] == "not_found"


def test_half_open_bounds_revision_and_txt_charts(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    project_id, asset_id = _study(client, tmp_path)
    sha = client.get(f"/api/projects/{project_id}").json()["assets"][0]["sha256"]
    _metrics, evidence, t02 = _plant(settings, sha)
    t02.write_text(
        json.dumps(
            {
                "status": "ready",
                "method_version": "m1-v3",
                "method_id": "ffmpeg-ebur128+frame-rms-v1",
                "caveats": ["These are analysis windows, not verses, choruses, or emotional sections."],
                "series": {
                    "lines": [
                        {"name": "1 s RMS", "unit": "dBFS", "x": [1.0], "y": [-3.0]},
                        {"name": "3 s short-term LUFS", "unit": "LUFS", "x": [1.0], "y": [-8.0]},
                    ],
                    "bars": [{"label": "0.0–1.0 s", "value": 4.0}],
                },
            }
        )
    )
    stored = t02.read_bytes(), evidence.read_bytes()
    jobs = client.app.state.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    bare = client.get(_chart_url(project_id, asset_id, "L03")).json()
    assert bare["regions"] == []
    assert bare["series"]["bars"][0]["label"] == "0.0–1.0 s"
    assert bare["evidence_class"] == "measured"
    uploaded = _post(
        client,
        project_id,
        asset_id,
        "bounds.srt",
        b"1\n00:00:00,000 --> 00:00:01,000\nEarly\n\n"
        b"2\n00:00:01,000 --> 00:00:02,000\nLater\n",
    )
    body = uploaded.json()
    early, later = body["segments"]
    timed = client.get(_chart_url(project_id, asset_id, "L03")).json()
    assert timed["series"]["lines"][0]["x"] == [1.0]
    assert timed["series"]["lines"][0]["y"] == [-3.0]
    assert timed["series"]["lines"][1]["unit"] == "LUFS"
    assert timed["series"]["bars"] == []
    summary = {item["label"]: item["value"] for item in timed["summary"]}
    assert any(value == "No stored 1 s RMS sample falls inside this written interval." for value in summary.values())
    assert any(value == "-3.00 dBFS" for value in summary.values())
    assert any(value == "-8.00 LUFS" for value in summary.values())
    assert "dBFS" not in next(value for value in summary.values() if value.endswith("LUFS"))
    edited = client.put(
        f"/api/projects/{project_id}/assets/{asset_id}/lyric-segments/{later['id']}",
        json={"expected_revision": body["revision"], "start_s": 1.25, "end_s": 1.75},
    )
    assert edited.status_code == 200, edited.text
    revised = client.get(_chart_url(project_id, asset_id, "L03")).json()
    assert revised["lyric_revision"] == edited.json()["revision"]
    moved = next(item for item in revised["regions"] if item["segment_id"] == later["id"])
    assert moved["start_s"] == 1.25
    assert moved["end_s"] == 1.75
    assert early["id"] not in {item["segment_id"] for item in revised["regions"] if item["start_s"] == 1.25}
    text = _post(client, project_id, asset_id, "plain.txt", b"Hello there\n")
    assert text.status_code == 201, text.text
    l02 = client.get(_chart_url(project_id, asset_id, "L02")).json()
    assert l02["axis_definitions"]["x"] == "Line"
    assert l02["series"]["bars"][0]["value"] == 2
    assert l02["series"]["lines"][0]["y"] == [None]
    assert l02["caveats"] == [_WORD_CAVEAT]
    assert l02["lyric_revision"] == text.json()["revision"]
    l01 = client.get(_chart_url(project_id, asset_id, "L01")).json()
    assert l01["regions"] == []
    reversed_doc = _post(
        client,
        project_id,
        asset_id,
        "bad.srt",
        b"1\n00:00:02,000 --> 00:00:01,000\nNope\n",
    )
    assert reversed_doc.status_code == 201, reversed_doc.text
    assert client.get(_chart_url(project_id, asset_id, "L01")).json()["regions"] == []
    assert client.get(_chart_url(project_id, asset_id, "L03")).json()["regions"] == []
    shared = tmp_path / "shared.wav"
    _wav(shared)
    project_b = _project(client, "B")
    same = _upload(client, project_b, shared).json()["asset"]["id"]
    assert same == asset_id
    foreign = client.get(_chart_url(project_b, asset_id, "L02")).json()
    assert foreign["lyric_document_id"] is None
    assert foreign["status"] == "not_available"
    assert "Nope" not in json.dumps(foreign)
    assert (t02.read_bytes(), evidence.read_bytes()) == stored
    assert client.app.state.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == jobs
