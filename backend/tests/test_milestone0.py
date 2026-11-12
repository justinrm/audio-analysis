import asyncio
import hashlib
import sqlite3
import struct
from pathlib import Path

import pytest
from app.audio import bucket_count
from app.config import Settings
from app.main import AppError, create_app, spool_upload
from fastapi.testclient import TestClient

from tests.wavgen import float_wav, pcm_wav


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        data_root=tmp_path,
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


def _project(client: TestClient, name: str = "Study") -> str:
    response = client.post("/api/projects", json={"name": name})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "study"
    return body["id"]


def _upload(client: TestClient, project_id: str, path: Path, filename: str | None = None):
    upload_name = filename if filename is not None else path.name
    with path.open("rb") as handle:
        return client.post(
            f"/api/projects/{project_id}/assets",
            files={"file": (upload_name, handle, "audio/wav")},
        )


def _jobs(client: TestClient) -> int:
    return client.app.state.db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]


def test_health(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["database"] == "ok"
    assert body["analysis"] == "available"
    assert body["ffmpeg_version"] not in ("", "unavailable")


def test_foreign_keys_on(client: TestClient) -> None:
    connection = client.app.state.db
    assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 5
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(
            "INSERT INTO project_assets (project_id, asset_id, ordering) VALUES ('missing', 'missing', 0)"
        )


def test_pcm16_metadata_and_hash(client: TestClient, settings: Settings, tmp_path: Path) -> None:
    path = tmp_path / "stereo.wav"
    frames = 4410
    pcm_wav(path, [1000, -1000] * frames, 44100, 2, 16)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    project_id = _project(client)
    response = _upload(client, project_id, path)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["cache"] == "miss"
    asset = body["asset"]
    assert asset["subtype"] == "pcm_16"
    assert asset["sample_rate"] == 44100
    assert asset["channels"] == 2
    assert asset["duration_s"] == pytest.approx(0.1)
    assert asset["analysis_status"] == "not_run"
    assert asset["playback_status"] == "ready"
    assert asset["sha256"] == digest
    assert asset["byte_length"] == path.stat().st_size
    blob = settings.data_root / "blobs" / digest
    assert blob.read_bytes() == path.read_bytes()
    assert hashlib.sha256(blob.read_bytes()).hexdigest() == digest


def test_pcm24_derivative_preserves_master(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    path = tmp_path / "master24.wav"
    pcm_wav(path, [1000] * 4800, 48000, 1, 24)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    project_id = _project(client)
    response = _upload(client, project_id, path)
    assert response.status_code == 200, response.text
    asset = response.json()["asset"]
    assert response.json()["cache"] == "miss"
    assert asset["subtype"] == "pcm_24"
    assert asset["sample_rate"] == 48000
    assert asset["channels"] == 1
    assert asset["duration_s"] == pytest.approx(0.1)
    assert asset["playback_status"] == "ready"
    blob = settings.data_root / "blobs" / digest
    assert blob.read_bytes() == raw
    derivative = settings.data_root / "derivatives" / digest
    copies = list(derivative.glob("*.wav"))
    assert len(copies) == 1
    playback = copies[0].read_bytes()
    assert playback != raw
    assert hashlib.sha256(blob.read_bytes()).hexdigest() == digest
    with copies[0].open("rb") as handle:
        header = handle.read(44)
    bits = struct.unpack_from("<H", header, 34)[0]
    rate = struct.unpack_from("<I", header, 24)[0]
    channels = struct.unpack_from("<H", header, 22)[0]
    assert bits == 16
    assert rate == 48000
    assert channels == 1
    stream = client.get(f"/api/assets/{asset['id']}/stream")
    assert stream.status_code == 200
    assert stream.headers["content-type"].startswith("audio/wav")
    assert stream.content == playback
    assert stream.content != raw


def test_float_and_invalid_wav_rejected(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    project_id = _project(client)
    floated = tmp_path / "float.wav"
    float_wav(floated)
    response = _upload(client, project_id, floated)
    assert response.status_code == 400
    assert "float" in response.json()["message"].lower()

    integer32 = tmp_path / "int32.wav"
    pcm_wav(integer32, [1], 8000, 1, 32)
    response = _upload(client, project_id, integer32)
    assert response.status_code == 400
    assert "32-bit" in response.json()["message"]

    garbage = tmp_path / "nope.wav"
    garbage.write_bytes(b"this is not a wav")
    response = _upload(client, project_id, garbage)
    assert response.status_code == 400
    assert "not a wav" in response.json()["message"].lower()

    text = tmp_path / "notes.txt"
    text.write_bytes(b"RIFF")
    response = _upload(client, project_id, text, filename="notes.txt")
    assert response.status_code == 400
    assert response.json()["error"] == "not_wav"
    assert list((settings.data_root / "tmp").glob("*")) == []
    assert list((settings.data_root / "blobs").glob("*")) == []


def test_hostile_filename_is_not_a_path(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    path = tmp_path / "tone.wav"
    pcm_wav(path, [1, -1] * 100, 8000, 1, 16)
    project_id = _project(client)
    response = _upload(client, project_id, path, filename="../../etc/passwd.wav")
    assert response.status_code == 200, response.text
    assert response.json()["asset"]["original_name"] == "../../etc/passwd.wav"
    for found in settings.data_root.rglob("*"):
        assert found.name != "passwd.wav"
        assert "etc" not in found.parts
        assert ".." not in found.parts


def test_oversized_and_too_long_remove_temp(tmp_path: Path) -> None:
    short = tmp_path / "short.wav"
    pcm_wav(short, [0] * 800, 8000, 1, 16)
    tiny = Settings(
        data_root=tmp_path / "tiny",
        max_bytes=80,
        max_duration_s=900,
        cors_origin="http://127.0.0.1:5173",
    )
    app = create_app(tiny)
    with TestClient(app) as test_client:
        project_id = _project(test_client)
        response = _upload(test_client, project_id, short)
        assert response.status_code == 413
        assert "limit" in response.json()["message"].lower()
        assert list((tiny.data_root / "tmp").glob("*")) == []
        assert app.state.db.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 0
    app.state.db.close()

    brief = Settings(
        data_root=tmp_path / "brief",
        max_bytes=500 * 1024 * 1024,
        max_duration_s=0.05,
        cors_origin="http://127.0.0.1:5173",
    )
    longer = tmp_path / "longer.wav"
    pcm_wav(longer, [0] * 8000, 8000, 1, 16)
    app = create_app(brief)
    with TestClient(app) as test_client:
        project_id = _project(test_client)
        response = _upload(test_client, project_id, longer)
        assert response.status_code == 400
        assert "exceeds" in response.json()["message"].lower()
        assert list((brief.data_root / "tmp").glob("*")) == []
        assert app.state.db.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 0
    app.state.db.close()


def test_interrupted_upload_removes_temp(tmp_path: Path) -> None:
    dest = tmp_path / "tmp" / "upload.part"

    class Reader:
        def __init__(self) -> None:
            self.calls = 0

        async def read(self, _size: int) -> bytes:
            self.calls += 1
            if self.calls == 1:
                return b"RIFF" + b"\x00" * 64
            raise ConnectionResetError("client gone")

    with pytest.raises(AppError) as caught:
        asyncio.run(spool_upload(Reader(), dest, 1_000_000))
    assert caught.value.code == "upload_interrupted"
    assert not dest.exists()
    assert list((tmp_path / "tmp").glob("*")) == []


def test_duplicate_import_reuses_blob(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    path = tmp_path / "again.wav"
    pcm_wav(path, [4, -4] * 200, 16000, 1, 16)
    project_id = _project(client)
    first = _upload(client, project_id, path)
    second = _upload(client, project_id, path)
    assert first.json()["cache"] == "miss"
    assert second.json()["cache"] == "hit"
    assert first.json()["asset"]["id"] == second.json()["asset"]["id"]
    connection = client.app.state.db
    assert connection.execute("SELECT COUNT(*) FROM assets").fetchone()[0] == 1
    assert connection.execute("SELECT COUNT(*) FROM project_assets").fetchone()[0] == 1
    assert len(list((settings.data_root / "blobs").iterdir())) == 1
    detail = client.get(f"/api/projects/{project_id}")
    assert len(detail.json()["assets"]) == 1


def test_range_request(client: TestClient, tmp_path: Path) -> None:
    path = tmp_path / "range.wav"
    pcm_wav(path, [0] * 1600, 8000, 1, 16)
    project_id = _project(client)
    asset_id = _upload(client, project_id, path).json()["asset"]["id"]
    response = client.get(f"/api/assets/{asset_id}/stream", headers={"Range": "bytes=0-43"})
    assert response.status_code == 206
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.headers["content-range"].startswith("bytes 0-43/")
    assert len(response.content) == 44
    assert response.content[:4] == b"RIFF"


def test_analyze_enqueues_without_running(client: TestClient, tmp_path: Path) -> None:
    path = tmp_path / "idle.wav"
    pcm_wav(path, [0] * 800, 8000, 1, 16)
    project_id = _project(client)
    asset = _upload(client, project_id, path).json()["asset"]
    response = client.post(f"/api/assets/{asset['id']}/analyze")
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "queued"
    assert body["asset_id"] == asset["id"]
    assert _jobs(client) == 1
    again = client.get(f"/api/assets/{asset['id']}")
    assert again.json()["analysis_status"] == "queued"
    missing = client.get("/api/jobs/does-not-exist")
    assert missing.status_code == 404
    charts = client.get(f"/api/assets/{asset['id']}/charts")
    assert charts.status_code == 200
    assert {item["status"] for item in charts.json()["charts"]} == {"not_run"}


def test_peaks_preserve_min_max(client: TestClient, tmp_path: Path) -> None:
    path = tmp_path / "square.wav"
    positive = [16384] * 2000
    negative = [-8192] * 2000
    pcm_wav(path, positive + negative, 8000, 1, 16)
    project_id = _project(client)
    asset_id = _upload(client, project_id, path).json()["asset"]["id"]
    response = client.get(f"/api/assets/{asset_id}/peaks")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["method_id"] == "playback_minmax_envelope_v1"
    assert body["sample_rate"] == 8000
    assert body["channels"] == 1
    assert body["duration_s"] == pytest.approx(0.5)
    buckets = body["buckets"]
    assert len(buckets) == bucket_count(4000)
    assert all(
        isinstance(item["min"], float) and isinstance(item["max"], float) for item in buckets
    )
    assert all(item["min"] <= item["max"] for item in buckets)
    highs = [item for item in buckets if item["max"] > 0.4]
    lows = [item for item in buckets if item["min"] < -0.2]
    assert highs and lows
    assert all(
        item["min"] == pytest.approx(0.5) and item["max"] == pytest.approx(0.5) for item in highs
    )
    assert all(
        item["min"] == pytest.approx(-0.25) and item["max"] == pytest.approx(-0.25) for item in lows
    )


def test_derivative_failure_keeps_master(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch
) -> None:
    def boom(*_args, **_kwargs):
        raise RuntimeError("ffmpeg failed")

    monkeypatch.setattr("app.main.write_pcm16_derivative", boom)
    path = tmp_path / "fail24.wav"
    pcm_wav(path, [50] * 2400, 24000, 1, 24)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    project_id = _project(client)
    response = _upload(client, project_id, path)
    assert response.status_code == 200, response.text
    asset = response.json()["asset"]
    assert asset["playback_status"] == "unavailable"
    assert asset["analysis_status"] == "not_run"
    assert asset["subtype"] == "pcm_24"
    blob = settings.data_root / "blobs" / digest
    assert blob.read_bytes() == raw
    stream = client.get(f"/api/assets/{asset['id']}/stream")
    assert stream.status_code == 409
    assert stream.content != raw
    assert "not streamed" in stream.json()["message"].lower()
    peaks = client.get(f"/api/assets/{asset['id']}/peaks")
    assert peaks.status_code == 409
    assert _jobs(client) == 0
