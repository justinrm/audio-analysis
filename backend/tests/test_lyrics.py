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
        assert upgraded.execute("PRAGMA user_version").fetchone()[0] == 3
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
