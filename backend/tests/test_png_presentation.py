"""Presentation PNGs and renderer refresh. These tests do not measure audio."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from app.measure import ALGORITHM_VERSION
from app.png import (
    RENDERER_VERSION,
    format_file_time,
    format_frequency,
    presentation_png,
    publish_png,
    render_figure,
    rendered_png,
    valid_png,
    write_manifest,
)
from app.refresh_png import main, refresh_tree
from matplotlib import pyplot as plt

from tests.wavgen import pcm_wav


def _document(kind: str, **series: object) -> dict:
    base = {
        "lines": [],
        "bars": [],
        "heatmap": None,
    }
    base.update(series)
    return {
        "chart_kind": kind,
        "status": "ready",
        "title": kind,
        "evidence_class": "measured" if kind not in {"T06", "T07", "T08", "T09"} else "estimated",
        "method_id": "fixture",
        "method_version": ALGORITHM_VERSION,
        "series": base,
        "axis_definitions": {"x": "Time (s)", "y": "dBFS", "y_scale": "linear"},
        "review_markers": [],
    }


def _close(figure) -> None:
    plt.close(figure)


def test_display_units() -> None:
    assert format_file_time(90) == "1:30"
    assert format_file_time(1.25) == "0:01.2"
    assert format_frequency(100) == "100 Hz"
    assert format_frequency(4000) == "4 kHz"


def test_coordinated_axes_do_not_change_the_document() -> None:
    loudness = _document(
        "T02",
        lines=[
            {"name": "1 s RMS", "unit": "dBFS", "x": [1, 2], "y": [-20, -10]},
            {"name": "3 s short-term LUFS", "unit": "LUFS", "x": [1, 2], "y": [-16, -9]},
        ],
        bars=[{"label": "0.0–1.0 s", "value": 0.4}],
    )
    loudness["axis_definitions"]["y"] = "Relative RMS-power level (dB)"
    spectrum = _document(
        "T03",
        lines=[{"name": "Welch PSD", "unit": "dB", "x": [20, 1000, 8000], "y": [-80, -40, -20]}],
        bars=[{"label": "20–500 Hz", "value": 12.5}],
    )
    spectrum["axis_definitions"] = {"x": "Frequency (Hz)", "y": "Power share (%)", "y_scale": "linear"}
    stereo = _document(
        "T05",
        lines=[
            {"name": "1 s correlation", "unit": "ratio", "x": [0, 1], "y": [0.2, 0.9]},
            {"name": "1 s side/mid", "unit": "dB", "x": [0, 1], "y": [-30, -4]},
        ],
    )
    share = _document("T07", bars=[{"label": "C", "value": 0.08}, {"label": "D", "value": 0.1}])
    share["axis_definitions"] = {"x": "Pitch class", "y": "Share", "y_scale": "linear"}
    pulse = _document(
        "T06",
        lines=[{"name": "Onset strength", "unit": "score", "x": [0, 1], "y": [0.2, 0.4]}],
        bars=[{"label": "122.3 BPM (double-time)", "value": 0.8}],
    )
    heat = _document(
        "T04",
        lines=[{"name": "bass", "unit": "dB rel. median", "x": [0, 2], "y": [-3, -1]}],
        heatmap={"x": [0, 2], "y": [100, 1000], "z": [[1, 2], [3, 4]]},
    )
    heat["axis_definitions"] = {"x": "Time (s)", "y": "Frequency (Hz)", "y_scale": "linear"}
    before = json.dumps([loudness, spectrum, stereo, share, pulse, heat])

    loudness_figure = render_figure(loudness)
    assert [axis.get_ylabel() for axis in loudness_figure.axes] == ["dBFS", "LUFS"]
    assert list(loudness_figure.axes[1].lines[0].get_ydata()) == [-16, -9]
    assert loudness_figure.axes[0].containers == []
    _close(loudness_figure)

    spectrum_figure = render_figure(spectrum)
    assert spectrum_figure.axes[0].get_xscale() == "log"
    assert spectrum_figure.axes[0].get_ylabel() == "dB"
    assert list(spectrum_figure.axes[0].lines[0].get_xdata()) == [20, 1000, 8000]
    assert spectrum_figure.axes[0].containers == []
    _close(spectrum_figure)

    stereo_figure = render_figure(stereo)
    assert stereo_figure.axes[0].get_ylim() == (-1, 1)
    assert list(stereo_figure.axes[1].lines[0].get_ydata()) == [-30, -4]
    _close(stereo_figure)

    share_figure = render_figure(share)
    assert share_figure.axes[0].get_ylim() == (0, 1)
    _close(share_figure)

    pulse_figure = render_figure(pulse)
    assert all(len(axis.containers) == 0 for axis in pulse_figure.axes)
    _close(pulse_figure)

    heat_figure = render_figure(heat)
    labels = [axis.get_ylabel() for axis in heat_figure.axes]
    assert "Frequency (Hz)" in labels
    assert "dB rel. median" in labels
    _close(heat_figure)

    assert json.dumps([loudness, spectrum, stereo, share, pulse, heat]) == before
    assert spectrum["axis_definitions"]["y_scale"] == "linear"
    assert spectrum["series"]["lines"][0]["unit"] == "dB"


def test_publish_replaces_only_a_valid_png(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "T10.png"
    document = _document("T10", bars=[{"label": "last 50 ms RMS", "value": -40}])
    publish_png(path, document)
    original = path.read_bytes()
    assert valid_png(path)
    assert list(tmp_path.glob(".*.tmp.png")) == []

    def reject(target: Path, _document: dict) -> None:
        target.write_bytes(b"not a png")

    monkeypatch.setattr("app.png.write_png", reject)
    with pytest.raises(RuntimeError):
        publish_png(path, document)
    assert path.read_bytes() == original
    assert list(tmp_path.glob(".*.tmp.png")) == []


def _ready_tree(root: Path, sha: str, documents: dict[str, dict]) -> Path:
    analysis = root / "analysis" / sha / ALGORITHM_VERSION
    analysis.mkdir(parents=True)
    for kind, document in documents.items():
        (analysis / f"{kind}.json").write_text(json.dumps(document))
    (analysis / "metrics.json").write_text('{"algorithm_version":"m1-v3","marker":1}\n')
    blob = root / "blobs" / sha
    blob.parent.mkdir()
    blob.write_bytes(b"original-master")
    return analysis


def test_refresh_is_versioned_and_does_not_touch_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sha = "a" * 64
    document = _document("T10", bars=[{"label": "last 50 ms RMS", "value": -12}])
    analysis = _ready_tree(tmp_path, sha, {"T10": document})
    legacy = analysis / "T10.png"
    legacy.write_bytes(b"\x89PNG\r\n\x1a\nlegacy")
    json_before = (analysis / "T10.json").read_bytes()
    metrics_before = (analysis / "metrics.json").read_bytes()
    blob_before = (tmp_path / "blobs" / sha).read_bytes()

    def exploded(*_args, **_kwargs):
        raise AssertionError("audio was decoded")

    monkeypatch.setattr("app.measure.decode_wav", exploded)

    dry = refresh_tree(tmp_path, dry_run=True, sha256=sha, kinds={"T10"})
    assert [(item.kind, item.action) for item in dry] == [("T10", "dry-run")]
    assert not (analysis / "presentation").exists()
    assert (analysis / "T10.json").read_bytes() == json_before

    first = refresh_tree(tmp_path, sha256=sha, kinds={"T10"})
    assert [(item.kind, item.action) for item in first] == [("T10", "regenerated")]
    current = presentation_png(analysis, "T10")
    assert valid_png(current)
    assert rendered_png(analysis, "T10") == current
    assert legacy.read_bytes().startswith(b"\x89PNG")
    assert (analysis / "T10.json").read_bytes() == json_before
    assert (analysis / "metrics.json").read_bytes() == metrics_before
    assert hashlib.sha256((tmp_path / "blobs" / sha).read_bytes()).hexdigest() == hashlib.sha256(blob_before).hexdigest()
    stamped = current.stat().st_mtime_ns

    second = refresh_tree(tmp_path, sha256=sha, kinds={"T10"})
    assert [(item.kind, item.action, item.detail) for item in second] == [("T10", "skipped", "current")]
    assert current.stat().st_mtime_ns == stamped

    previous = current.read_bytes()
    write_manifest(
        analysis,
        ["T10"],
        ALGORITHM_VERSION,
    )
    manifest_path = analysis / "presentation" / RENDERER_VERSION / "manifest.json"
    payload = json.loads(manifest_path.read_text())
    payload["renderer_version"] = "png-r0"
    manifest_path.write_text(json.dumps(payload))

    def fail(target: Path, _document: dict) -> None:
        target.write_bytes(b"partial")
        raise RuntimeError("interrupted")

    monkeypatch.setattr("app.png.write_png", fail)
    failed = refresh_tree(tmp_path, sha256=sha, kinds={"T10"})
    assert failed[0].action == "failed"
    assert current.read_bytes() == previous
    assert (analysis / "T10.json").read_bytes() == json_before
    assert rendered_png(analysis, "T10") is None


def test_refresh_reports_invalid_json_and_cli_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sha = "b" * 64
    analysis = _ready_tree(tmp_path, sha, {})
    (analysis / "T03.json").write_text("{")
    items = refresh_tree(tmp_path, sha256=sha, kinds={"T03"})
    assert items[0].action == "failed"
    assert items[0].detail == "invalid json"
    assert not presentation_png(analysis, "T03").exists()
    code = main(["--data-root", str(tmp_path), "--dry-run", "--sha256", sha, "--kind", "T03"])
    assert code == 1
    assert "failed" in capsys.readouterr().out


def test_image_route_serves_only_the_current_renderer(tmp_path: Path) -> None:
    from app.config import Settings
    from app.main import create_app
    from fastapi.testclient import TestClient

    settings = Settings(
        data_root=tmp_path,
        max_bytes=500 * 1024 * 1024,
        max_duration_s=900,
        cors_origin="http://127.0.0.1:5173",
    )
    source = tmp_path / "tone.wav"
    pcm_wav(source, [1000, -1000] * 200, 8000, 1, 16)
    app = create_app(settings)
    with TestClient(app) as client:
        project = client.post("/api/projects", json={"name": "Study"})
        with source.open("rb") as handle:
            uploaded = client.post(
                f"/api/projects/{project.json()['id']}/assets",
                files={"file": ("tone.wav", handle, "audio/wav")},
            )
        assert uploaded.status_code == 200, uploaded.text
        asset = uploaded.json()["asset"]
        analysis = tmp_path / "analysis" / asset["sha256"] / ALGORITHM_VERSION
        analysis.mkdir(parents=True)
        document = _document("T10", bars=[{"label": "last 50 ms RMS", "value": -3}])
        (analysis / "T10.json").write_text(json.dumps(document))
        (analysis / "T02.json").write_text(json.dumps(_document("T02")))
        legacy = analysis / "T02.png"
        legacy.write_bytes(b"\x89PNG\r\n\x1a\nlegacy-bytes")
        assert refresh_tree(tmp_path, sha256=asset["sha256"], kinds={"T10"})[0].action == "regenerated"
        image = client.get(f"/api/assets/{asset['id']}/charts/T10/image")
        assert image.status_code == 200
        assert image.content.startswith(b"\x89PNG")
        assert image.headers["x-renderer-version"] == RENDERER_VERSION
        assert image.headers["cache-control"] == "no-cache"
        stale = client.get(f"/api/assets/{asset['id']}/charts/T02/image")
        assert stale.status_code == 404
        assert legacy.is_file()
    app.state.db.close()
