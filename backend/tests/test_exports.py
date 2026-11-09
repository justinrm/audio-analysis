import hashlib
import io
import json
import math
import re
import socket
import zipfile
from pathlib import Path

import pytest
from app.config import Settings
from app.main import create_app
from app.measure import decode_wav
from fastapi.testclient import TestClient

from tests.test_milestone0 import _project, _upload
from tests.wavgen import pcm_wav

LINE = "UNIQUE_LYRIC_LINE_ZEBRA"
SRT = (
    "1\n00:00:00,000 --> 00:00:01,000\n"
    f"{LINE}\n\n"
    "2\n00:00:01,200 --> 00:00:02,000\n"
    f"{LINE}\n\n"
    "3\n00:00:02,500 --> 00:00:02,000\n"
    "Backwards\n"
)


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


def _tone(path: Path, seconds: float, channels: int) -> None:
    rate = 8000
    count = int(rate * seconds)
    samples: list[int] = []
    for index in range(count):
        value = int(0.4 * 32767 * math.sin(2 * math.pi * 440 * index / rate))
        if channels == 1:
            samples.append(value)
        else:
            samples.extend((value, -value))
    pcm_wav(path, samples, rate, channels, 16)


def _study(client: TestClient, tmp_path: Path, channels: int = 1) -> tuple[str, str, str]:
    path = tmp_path / "tone.wav"
    _tone(path, 3.0, channels)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    project_id = _project(client, "Study")
    uploaded = _upload(client, project_id, path)
    assert uploaded.status_code == 200, uploaded.text
    return project_id, uploaded.json()["asset"]["id"], digest


def _analyze(client: TestClient, asset_id: str) -> None:
    queued = client.post(f"/api/assets/{asset_id}/analyze")
    assert queued.status_code == 202, queued.text
    assert client.app.state.worker.run_available() == 1
    done = client.get(f"/api/jobs/{queued.json()['id']}")
    assert done.json()["status"] == "completed", done.json()


def _files(root: Path) -> dict[str, bytes]:
    return {str(path.relative_to(root)): path.read_bytes() for path in root.rglob("*") if path.is_file()}


def _export(client: TestClient, project_id: str, asset_id: str, profile: str, lyrics: str = "summarized"):
    created = client.post(
        f"/api/projects/{project_id}/assets/{asset_id}/exports",
        json={"profile": profile, "lyrics": lyrics},
    )
    assert created.status_code == 200, created.text
    body = created.json()
    downloaded = client.get(
        f"/api/projects/{project_id}/assets/{asset_id}/exports/{body['export_id']}"
    )
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.headers["content-type"].startswith("application/zip")
    package = zipfile.ZipFile(io.BytesIO(downloaded.content))
    return body, package


def _png_size(data: bytes) -> tuple[int, int]:
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    assert data[12:16] == b"IHDR"
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


def test_export_sources_do_not_import_measure_or_http() -> None:
    root = Path(__file__).resolve().parents[1] / "app"
    for name in ("exports.py", "lyric_png.py"):
        source = (root / name).read_text()
        assert "app.measure" not in source
        assert "decode_wav" not in source
        assert "httpx" not in source
        assert "requests" not in source
        assert "urllib" not in source


def test_not_run_technical_zip_states_the_gap(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, asset_id, digest = _study(client, tmp_path)
    blob = settings.data_root / "blobs" / digest
    before = blob.read_bytes()

    def boom(*_args, **_kwargs):
        raise AssertionError("export decoded audio")

    monkeypatch.setattr("app.measure.decode_wav", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    body, package = _export(client, project_id, asset_id, "technical")
    names = package.namelist()
    assert not any(name.startswith("lyricist/") or name.endswith(".wav") for name in names)
    chart = json.loads(package.read("technical/charts/T01.json"))
    assert chart["status"] == "not_run"
    assert "technical/charts/T01.png" not in names
    assert "T01" in body["png_unavailable"]
    assert body["narrative"] == "none"
    assert body["source_sha256"] == digest
    assert body["lyric_document_id"] is None
    assert blob.read_bytes() == before
    decode_wav(blob)


def test_analyzed_technical_zip_copies_evidence_without_touching_the_cache(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    project_id, asset_id, digest = _study(client, tmp_path, channels=2)
    _analyze(client, asset_id)
    analysis = settings.data_root / "analysis" / digest / "m1-v3"
    blob = settings.data_root / "blobs" / digest
    before_analysis = _files(analysis)
    before_blob = blob.read_bytes()
    body, package = _export(client, project_id, asset_id, "technical")
    again, _second = _export(client, project_id, asset_id, "technical")
    assert body["content_sha256"] == again["content_sha256"]
    assert body["export_id"] != again["export_id"]
    assert body["algorithm_version"] == "m1-v3"
    assert body["params_hash"]
    assert body["renderer_version"] == "png-r1"
    assert body["lyric_renderer_version"] is None
    names = package.namelist()
    assert "technical/metrics.json" in names
    assert "technical/evidence.json" in names
    assert package.read("technical/metrics.json") == before_analysis["metrics.json"]
    assert package.read("technical/charts/T02.json") == before_analysis["T02.json"]
    assert package.read("technical/charts/T03.json") == before_analysis["T03.json"]
    assert b"dB/Hz" not in package.read("technical/charts/T03.json")
    readme = package.read("technical/README.md").decode()
    assert "dB/Hz" in readme
    assert "png-r1" in readme
    assert "technical/charts/T02.png" in names
    assert _png_size(package.read("technical/charts/T02.png"))[0] >= 200
    assert _files(analysis) == before_analysis
    assert blob.read_bytes() == before_blob
    stored = (settings.data_root / "exports" / f"{body['export_id']}.zip").is_file()
    assert stored


def test_missing_and_legacy_pngs_are_not_served(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    project_id, asset_id, digest = _study(client, tmp_path, channels=2)
    _analyze(client, asset_id)
    analysis = settings.data_root / "analysis" / digest / "m1-v3"
    presentation = analysis / "presentation"
    legacy = presentation / "old"
    legacy.mkdir(parents=True)
    (legacy / "T01.png").write_bytes(b"\x89PNG\r\n\x1a\n" + b"legacy")
    for path in presentation.rglob("*"):
        if path.is_file() and path.parent != legacy:
            path.unlink()
    for path in sorted(presentation.rglob("*"), reverse=True):
        if path.is_dir() and path != legacy and not any(path.iterdir()):
            path.rmdir()
    body, package = _export(client, project_id, asset_id, "technical")
    assert "T01" in body["png_unavailable"]
    assert not any(name.endswith(".png") for name in package.namelist())
    assert json.loads(package.read("technical/charts/T01.json"))["chart_kind"] == "T01"
    assert not (presentation / "png-r1").exists()


def test_mono_t05_stays_unavailable(client: TestClient, tmp_path: Path) -> None:
    project_id, asset_id, _digest = _study(client, tmp_path, channels=1)
    _analyze(client, asset_id)
    _body, package = _export(client, project_id, asset_id, "technical")
    chart = json.loads(package.read("technical/charts/T05.json"))
    assert chart["status"] == "not_available"
    assert chart["evidence_class"] == "not_applicable"
    assert "technical/charts/T05.png" not in package.namelist()


def test_lyric_packages_require_a_document(client: TestClient, tmp_path: Path) -> None:
    project_id, asset_id, _digest = _study(client, tmp_path)
    for profile in ("lyricist", "combined"):
        denied = client.post(
            f"/api/projects/{project_id}/assets/{asset_id}/exports",
            json={"profile": profile},
        )
        assert denied.status_code == 409, denied.text
        assert denied.json()["error"] == "no_lyrics"
    technical = client.post(
        f"/api/projects/{project_id}/assets/{asset_id}/exports",
        json={"profile": "technical"},
    )
    assert technical.status_code == 200, technical.text
    assert technical.json()["lyrics_mode"] == "summarized"


def test_lyric_modes_revision_and_combined_package(
    client: TestClient, settings: Settings, tmp_path: Path
) -> None:
    project_id, asset_id, digest = _study(client, tmp_path, channels=2)
    _analyze(client, asset_id)
    analysis = settings.data_root / "analysis" / digest / "m1-v3"
    before = _files(analysis)
    uploaded = client.post(
        f"/api/projects/{project_id}/assets/{asset_id}/lyrics",
        files={"file": ("cues.srt", SRT.encode(), "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document = uploaded.json()
    segment_id = document["segments"][0]["id"]
    summarized, summary_zip = _export(client, project_id, asset_id, "lyricist", "summarized")
    included, included_zip = _export(client, project_id, asset_id, "lyricist", "included")
    omitted, omitted_zip = _export(client, project_id, asset_id, "lyricist", "omitted")
    for body in (summarized, included, omitted):
        assert body["lyric_revision"] == 1
        assert body["lyric_document_id"] == document["id"]
        assert body["lyric_source_sha256"] == hashlib.sha256(SRT.encode()).hexdigest()
        assert body["lyric_renderer_version"] == "lyric-png-v2"
        assert body["brief_template_version"] == "lyric-brief-v2"
    assert summarized["content_sha256"] != included["content_sha256"]
    summary_text = b"".join(summary_zip.read(name) for name in summary_zip.namelist())
    omitted_text = b"".join(omitted_zip.read(name) for name in omitted_zip.namelist())
    assert LINE.encode() not in summary_text
    assert LINE.encode() not in omitted_text
    assert b"Backwards" not in summary_text
    included_text = b"".join(
        included_zip.read(name) for name in included_zip.namelist() if name.endswith((".json", ".md"))
    )
    assert LINE.encode() in included_text
    regions = json.loads(summary_zip.read("lyricist/charts/L01.json"))["regions"]
    assert regions
    assert all(region["start_s"] < region["end_s"] for region in regions)
    assert all(LINE not in region["label"] for region in regions)
    again, _again_zip = _export(client, project_id, asset_id, "lyricist", "summarized")
    assert again["content_sha256"] == summarized["content_sha256"]
    published = settings.data_root / "exports" / f"{summarized['export_id']}.zip"
    published_bytes = published.read_bytes()
    brief = summary_zip.read("lyricist/brief.md").decode()
    assert "## Reference identity and provenance" in brief
    assert "## What the available evidence establishes" in brief
    assert "## What this package cannot determine" in brief
    assert "lyric-brief-v2" in brief
    assert "lyric-png-v2" in brief
    evidence = json.loads(summary_zip.read("lyricist/evidence.json"))
    known = {item["id"] for item in evidence["records"]}
    cites = set(re.findall(r"`((?:ev|ly):[^`]+)`", brief))
    assert cites
    assert cites <= known
    assert "singing" in brief.lower() or "vocal" in brief.lower()
    for kind in ("L01", "L02", "L03", "L04", "L05"):
        width, height = _png_size(summary_zip.read(f"lyricist/charts/{kind}.png"))
        assert width >= 200 and height >= 200
    combined, combined_zip = _export(client, project_id, asset_id, "combined", "summarized")
    combined_names = combined_zip.namelist()
    assert sum(name.endswith("metrics.json") for name in combined_names) == 1
    assert sum(name.endswith("evidence.json") for name in combined_names) == 1
    assert "metrics.json" in combined_names
    assert "technical/charts/T01.json" in combined_names
    assert "lyricist/brief.md" in combined_names
    assert combined["lyric_revision"] == 1
    edited = client.put(
        f"/api/projects/{project_id}/assets/{asset_id}/lyric-segments/{segment_id}",
        json={"expected_revision": 1, "text": "A different written line"},
    )
    assert edited.status_code == 200, edited.text
    assert edited.json()["revision"] == 2
    saved = client.get(f"/api/projects/{project_id}/assets/{asset_id}/exports/{summarized['export_id']}")
    saved_zip = zipfile.ZipFile(io.BytesIO(saved.content))
    saved_manifest = json.loads(saved_zip.read("lyricist/manifest.json"))
    assert saved_manifest["lyric_revision"] == 1
    assert LINE.encode() not in saved.content
    assert _files(analysis) == before
    later, _later_zip = _export(client, project_id, asset_id, "lyricist", "summarized")
    assert later["lyric_revision"] == 2
    assert later["content_sha256"] != summarized["content_sha256"]
    assert published.read_bytes() == published_bytes


def test_failed_export_publishes_nothing(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, asset_id, _digest = _study(client, tmp_path)

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr("app.exports.os.replace", boom)
    failed = client.post(
        f"/api/projects/{project_id}/assets/{asset_id}/exports",
        json={"profile": "technical"},
    )
    assert failed.status_code == 500, failed.text
    assert failed.json()["error"] == "export_failed"
    exports = settings.data_root / "exports"
    published = list(exports.glob("*.zip")) if exports.exists() else []
    assert published == []
    assert list(exports.glob(".*")) == [] if exports.exists() else True
    count = client.app.state.db.execute("SELECT COUNT(*) FROM export_runs").fetchone()[0]
    assert count == 0


def test_insert_failure_removes_the_published_zip(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_id, asset_id, _digest = _study(client, tmp_path)

    def boom(*_args, **_kwargs):
        raise RuntimeError("row failed")

    monkeypatch.setattr("app.exports._insert_run", boom)
    failed = client.post(
        f"/api/projects/{project_id}/assets/{asset_id}/exports",
        json={"profile": "technical"},
    )
    assert failed.status_code == 500, failed.text
    exports = settings.data_root / "exports"
    assert list(exports.glob("*.zip")) == []
    count = client.app.state.db.execute("SELECT COUNT(*) FROM export_runs").fetchone()[0]
    assert count == 0


def test_export_identity_is_membership_scoped(client: TestClient, tmp_path: Path) -> None:
    project_id, asset_id, _digest = _study(client, tmp_path)
    body, _package = _export(client, project_id, asset_id, "technical")
    other = _project(client, "Other")
    missing = client.get(f"/api/projects/{project_id}/assets/{asset_id}/exports/not-an-id")
    assert missing.status_code == 404
    absent = client.get(
        f"/api/projects/{project_id}/assets/{asset_id}/exports/00000000-0000-4000-8000-000000000000"
    )
    assert absent.status_code == 404
    crossed = client.get(f"/api/projects/{other}/assets/{asset_id}/exports/{body['export_id']}")
    assert crossed.status_code == 404
    outsider = client.post(
        f"/api/projects/{other}/assets/{asset_id}/exports",
        json={"profile": "technical"},
    )
    assert outsider.status_code == 404
