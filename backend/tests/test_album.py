import hashlib
import json
import math
import sqlite3
import zipfile
from pathlib import Path

import pytest
from app.album import compare, render_report
from app.config import Settings
from app.db import MIGRATIONS, _apply_versioned, connect
from app.main import create_app
from app.measure import ALGORITHM_VERSION, PARAMS_HASH
from app.png import ENERGY, _paint
from fastapi.testclient import TestClient

from tests.wavgen import pcm_wav

_SEQ = 0


def track(**overrides) -> dict:
    """Build stored chart documents. compare() does not read the flat keys."""
    global _SEQ
    _SEQ += 1
    flat = {
        "asset_id": f"asset-{_SEQ}",
        "original_name": f"tone-{_SEQ}.wav",
        "sha256": f"{_SEQ:064x}",
        "duration_s": 4.0,
        "sample_rate": 44100,
        "channels": 2,
        "analysis_status": "completed",
        "playback_status": "ready",
        "included": True,
        "omit_reason": None,
        "algorithm_version": "m1-v3",
        "params_hash": "hash-a",
        "lufs": -14.0,
        "lra": 5.0,
        "peak": -1.0,
        "rms": -18.0,
        "crest": 17.0,
        "true_peak": -0.8,
        "reconstructed": -0.5,
        "correlation": 0.9,
        "side_mid": -12.0,
        "fold": -0.4,
        "sub_corr": 0.7,
        "bands": [("20\u201360 Hz", 10.0), ("10000\u201322050 Hz", 5.0)],
        "rms_x": [0.0, 2.0],
        "rms_y": [-20.0, -10.0],
        "t05_status": None,
        "metrics_lufs": None,
        "metrics_peak": None,
        "metrics_rms": None,
        "t02_method": "ffmpeg-ebur128+frame-rms-v1",
        "t01_method": "frame-rms+master-minmax-envelope-v1",
    }
    flat.update(overrides)
    charts: dict = {}
    if flat["included"]:
        charts["T01"] = _chart(
            "T01",
            flat["t01_method"],
            [
                _summary("Sample peak", flat["peak"], "dBFS"),
                _summary("Sample peak time", 1.25, "s"),
                _summary("Whole-file RMS", flat["rms"], "dBFS"),
                _summary("Crest factor", flat["crest"], "dB"),
            ],
            lines=[_line("1 s RMS", flat["rms_x"], flat["rms_y"], "dBFS")],
        )
        charts["T02"] = _chart(
            "T02",
            flat["t02_method"],
            [
                _summary("Integrated loudness", flat["lufs"], "LUFS"),
                _summary("Loudness range", flat["lra"], "LU"),
                _summary("FFmpeg true peak", flat["true_peak"], "dBTP"),
            ],
            lines=[
                _line("1 s RMS", flat["rms_x"], flat["rms_y"], "dBFS"),
                _line("3 s short-term LUFS", flat["rms_x"], flat["rms_y"], "LUFS"),
            ],
            caveats=["Short-term LUFS needs a 3 s window. None were reported."]
            if flat["lra"] is None
            else [],
        )
        charts["T03"] = _chart(
            "T03",
            "welch-nperseg-8192-v1",
            [_summary("Below 20 Hz", 1.5, "%")],
            bars=[{"label": label, "value": value} for label, value in flat["bands"]],
        )
        charts["T05"] = _t05(flat)
        charts["T06"] = _chart(
            "T06",
            "onset-autocorr-v1",
            [],
            bars=[{"label": "120.0 BPM", "value": 0.42}],
            evidence="estimated",
        )
        charts["T10"] = _chart(
            "T10",
            "tail-silence-rail-4x-peak-v1",
            [
                _summary("4x reconstructed peak", flat["reconstructed"], "dBTP"),
                _summary("4x peak time", 3.5, "s"),
                _summary("Full-scale samples", 0, ""),
                _summary("Endpoint", "zero", ""),
                _summary("Sub-threshold intervals", 1, ""),
            ],
            bars=[{"label": "last 50 ms RMS", "value": -70.0}],
        )
        charts["T10"]["silence"] = [{"start_s": 0.0, "end_s": 0.05}]
        if flat["t05_status"] == "missing":
            charts.pop("T05")
    metrics_lufs = flat["lufs"] if flat["metrics_lufs"] is None else flat["metrics_lufs"]
    metrics_peak = flat["peak"] if flat["metrics_peak"] is None else flat["metrics_peak"]
    metrics_rms = flat["rms"] if flat["metrics_rms"] is None else flat["metrics_rms"]
    return {
        "asset_id": flat["asset_id"],
        "original_name": flat["original_name"],
        "sha256": flat["sha256"],
        "duration_s": flat["duration_s"],
        "sample_rate": flat["sample_rate"],
        "channels": flat["channels"],
        "analysis_status": flat["analysis_status"],
        "playback_status": flat["playback_status"],
        "included": flat["included"],
        "omit_reason": flat["omit_reason"],
        "algorithm_version": flat["algorithm_version"],
        "params_hash": flat["params_hash"],
        "metrics": {
            "algorithm_version": flat["algorithm_version"],
            "params_hash": flat["params_hash"],
            "sample_peak_dbfs": metrics_peak,
            "rms_dbfs": metrics_rms,
            "loudness": {"integrated_lufs": metrics_lufs},
        },
        "charts": charts,
    }


def _summary(label: str, value, unit: str) -> dict:
    if value is None:
        text = "undefined"
    elif isinstance(value, str):
        text = value
    elif isinstance(value, float) and not math.isfinite(value):
        text = "nan"
    elif unit:
        text = f"{value} {unit}"
    else:
        text = str(value)
    return {"label": label, "value": text}


def _line(name: str, xs: list, ys: list, unit: str) -> dict:
    return {"name": name, "unit": unit, "x": list(xs), "y": list(ys)}


def _chart(
    kind: str,
    method: str,
    summary: list,
    lines: list | None = None,
    bars: list | None = None,
    evidence: str = "measured",
    caveats: list | None = None,
) -> dict:
    return {
        "chart_kind": kind,
        "status": "ready",
        "evidence_class": evidence,
        "method_id": method,
        "summary": summary,
        "caveats": caveats or [],
        "series": {"lines": lines or [], "bars": bars or [], "heatmap": None},
    }


def _t05(flat: dict) -> dict:
    status = flat["t05_status"]
    if flat["channels"] == 1 or status == "not_applicable":
        return {
            "chart_kind": "T05",
            "status": "not_available",
            "evidence_class": "not_applicable",
            "method_id": "none",
            "summary": [_summary("Whole-file correlation", 0, "")],
            "caveats": ["Mono input has no stereo field. No right channel was invented."],
            "series": {"lines": [], "bars": [], "heatmap": None},
        }
    if status == "failed":
        return {
            "chart_kind": "T05",
            "status": "failed",
            "evidence_class": "unknown",
            "method_id": "none",
            "summary": [_summary("Whole-file correlation", flat["correlation"], "")],
            "caveats": ["RuntimeError: stereo failed"],
            "series": {"lines": [], "bars": [], "heatmap": None},
        }
    return _chart(
        "T05",
        "lr-correlation-1s-v1",
        [
            _summary("Whole-file correlation", flat["correlation"], ""),
            _summary("Side/mid", flat["side_mid"], "dB"),
            _summary("Mono fold-down change", flat["fold"], "dB"),
            _summary("Below 120 Hz correlation", flat["sub_corr"], ""),
        ],
    )


def _scalar(document: dict, name: str) -> dict:
    return next(item for item in document["scalars"] if item["name"] == name)


def _delta(pair: dict, name: str) -> dict:
    return next(item for item in pair["deltas"] if item["name"] == name)


def test_pair_keeps_units_apart():
    loud = compare(
        [track(lufs=-14.0, peak=-1.0, true_peak=-1.0, reconstructed=-0.6), track(lufs=-11.5, peak=-3.0, true_peak=-0.25, reconstructed=-0.1)],
        "seconds",
    )
    delta = {item["name"]: item["delta"] for item in loud["pairs"][0]["deltas"]}
    assert delta["integrated_loudness"] == -11.5 - -14.0
    assert _delta(loud["pairs"][0], "integrated_loudness")["unit"] == "LU"
    assert _scalar(loud["tracks"][0], "integrated_loudness")["unit"] == "LUFS"
    peak_delta = _delta(loud["pairs"][0], "sample_peak")
    assert peak_delta["delta"] == -3.0 - -1.0
    assert peak_delta["unit"] == "dB"
    assert _scalar(loud["tracks"][0], "sample_peak")["unit"] == "dBFS"
    assert _delta(loud["pairs"][0], "rms")["unit"] == "dB"
    assert _scalar(loud["tracks"][0], "rms")["unit"] == "dBFS"
    true_peak = _delta(loud["pairs"][0], "ffmpeg_true_peak")
    assert true_peak["delta"] == -0.25 - -1.0
    assert true_peak["unit"] == "dB"
    assert _scalar(loud["tracks"][0], "ffmpeg_true_peak")["unit"] == "dBTP"
    assert _scalar(loud["tracks"][0], "ffmpeg_true_peak")["value"] == -1.0
    reconstructed = _delta(loud["pairs"][0], "reconstructed_peak")
    assert reconstructed["delta"] == -0.1 - -0.6
    assert reconstructed["unit"] == "dB"
    assert _scalar(loud["tracks"][0], "reconstructed_peak")["unit"] == "dBTP"
    assert _scalar(loud["tracks"][0], "reconstructed_peak")["value"] == -0.6
    assert "dBFS" not in {
        item["unit"]
        for item in loud["pairs"][0]["deltas"]
        if item["name"] in {"integrated_loudness", "sample_peak", "rms"}
    }
    assert all(
        item["name"] != "ffmpeg_true_peak" or item["method_id"] == "ffmpeg-ebur128"
        for item in loud["tracks"][0]["scalars"]
    )
    names = [item["name"] for item in loud["pairs"][0]["deltas"]]
    assert "ffmpeg_true_peak" in names
    assert "reconstructed_peak" in names


def test_report_names_recordings_and_formats_the_difference():
    document = compare(
        [
            track(original_name="First.wav", lufs=-14.2, true_peak=-1.25, reconstructed=-0.8),
            track(original_name="Second.wav", lufs=-11.1, true_peak=-0.5, reconstructed=-0.2),
        ],
        "seconds",
    )
    report = render_report(
        document,
        [
            {
                "asset_id": document["tracks"][0]["asset_id"],
                "checkpoint_id": "sample_peak",
                "status": "intentional",
                "note": "ends hot",
                "fact": "Sample peak -1.00 dBFS at 1.250 s.",
            }
        ],
    )
    assert "2. Second.wav minus 1. First.wav" in report
    assert "3.1 LU" in report
    assert "3.0999999999999996" not in report
    assert "Sample peak: 0.00 dB" in report
    assert "Sample peak: -1.00 dBFS" in report
    assert "FFmpeg true peak: -1.25 dBTP" in report
    assert "FFmpeg true peak: 0.75 dB" in report
    assert "4× reconstructed peak: -0.80 dBTP" in report
    assert "4× reconstructed peak: 0.60 dB" in report
    assert "0.75 dBTP" not in report
    assert "0.60 dBTP" not in report
    assert "sample_peak" not in report
    assert "1. First.wav, Sample peak: Intentional." in report
    assert "Note: ends hot" in report
    assert "not a probability" in report
    assert "not a confirmed tempo" in report
    assert document["tracks"][0]["asset_id"] not in report


def test_three_included_tracks_make_three_pairs():
    result = compare([track(), track(), track()], "seconds")
    assert len(result["pairs"]) == 3
    assert len(result["spectral_distances"]) == 3


def test_mono_correlation_is_not_zero():
    mono = compare([track(channels=1), track(channels=2, correlation=0.2)], "seconds")
    stereo = _scalar(mono["tracks"][0], "correlation")
    assert stereo["evidence_class"] == "not_applicable"
    assert stereo["value"] is None
    assert all(item["value"] is None for item in mono["tracks"][0]["scalars"] if item["unit"] == "ratio")


def test_failed_stereo_is_not_mono_or_a_measurement():
    result = compare(
        [track(channels=2, t05_status="failed", correlation=0.0), track()],
        "seconds",
    )
    stereo = _scalar(result["tracks"][0], "correlation")
    assert stereo["evidence_class"] == "unknown"
    assert stereo["evidence_class"] != "not_applicable"
    assert stereo["value"] is None
    assert _delta(result["pairs"][0], "correlation")["delta"] is None


def test_missing_stereo_chart_is_not_a_measurement():
    result = compare([track(t05_status="missing"), track()], "seconds")
    stereo = _scalar(result["tracks"][0], "correlation")
    assert stereo["evidence_class"] == "unknown"
    assert stereo["value"] is None


def test_unanalyzed_neighbor_stays_listed():
    result = compare([track(included=False, omit_reason="analysis_incomplete"), track(), track()], "seconds")
    assert result["status"] == "ready"
    assert [item["included"] for item in result["tracks"]] == [False, True, True]
    assert len(result["pairs"]) == 1


def test_band_edges_block_distance():
    result = compare(
        [
            track(bands=[("20\u201360 Hz", 10), ("10000\u201322050 Hz", 5)]),
            track(bands=[("20\u201360 Hz", 12), ("10000\u201324000 Hz", 4)]),
        ],
        "seconds",
    )
    assert result["spectral_distances"][0]["reason"] == "band_edges_differ"
    assert result["spectral_distances"][0]["value"] is None


def test_band_distance_is_half_the_l1_share():
    result = compare(
        [
            track(bands=[("20\u201360 Hz", 10.0), ("10000\u201322050 Hz", 5.0)]),
            track(bands=[("20\u201360 Hz", 12.0), ("10000\u201322050 Hz", 1.0)]),
        ],
        "seconds",
    )
    distance = result["spectral_distances"][0]
    assert distance["status"] == "ready"
    assert distance["value"] == 3.0
    assert distance["unit"] == "percentage points"
    assert distance["method_id"] == "band-share-l1-v1"


def test_progress_does_not_resample():
    ready = compare(
        [
            track(rms_x=[0.0, 2.0], rms_y=[-20.0, -10.0], duration_s=4.0),
            track(rms_x=[0.0, 1.0], rms_y=[-12.0, -12.0], duration_s=2.0),
        ],
        "progress",
    )
    line = ready["panel"]["series"]["lines"][0]
    assert line["x"] == [0.0, 0.5]
    assert line["y"] == [-20.0, -10.0]
    assert len(line["x"]) == 2
    assert ready["panel"]["axis_definitions"]["x"] == "Progress (fraction of duration)"
    assert "bars" not in ready["panel"]["series"] or ready["panel"]["series"]["bars"] == []


def test_nonfinite_and_missing_are_not_zero():
    silent = compare(
        [
            track(lufs=float("nan"), peak=None, rms_y=[float("nan"), None], bands=[("20\u201360 Hz", float("nan"))]),
            track(),
        ],
        "seconds",
    )
    loudness = _scalar(silent["tracks"][0], "integrated_loudness")
    peak = _scalar(silent["tracks"][0], "sample_peak")
    assert loudness["value"] is None
    assert peak["value"] is None
    delta = _delta(silent["pairs"][0], "integrated_loudness")
    assert delta["delta"] is None
    assert delta["reason"] == "missing_value"
    line = silent["panel"]["series"]["lines"][0]
    assert line["y"][0] is None
    assert line["y"][1] is None
    assert len(line["y"]) == 2
    assert silent["spectral_distances"][0]["value"] is None
    blob = repr(silent)
    assert "nan" not in blob.lower()
    assert "inf" not in blob.lower()


def test_summary_disagreement_keeps_the_summary():
    result = compare(
        [track(lufs=-14.0, metrics_lufs=-14.2), track()],
        "seconds",
    )
    scalar = _scalar(result["tracks"][0], "integrated_loudness")
    assert scalar["value"] == -14.0
    assert scalar["metrics_value"] == -14.2
    assert "summary_metrics_disagree" in result["caveats"]


def test_one_recording_is_not_ready():
    result = compare([track()], "seconds")
    assert result["status"] == "not_available"
    assert result["not_available_reason"] == "need_two_recordings"
    assert result["panel"] is None
    assert result["pairs"] == []


def test_parameter_hash_mismatch_keeps_the_track():
    result = compare([track(params_hash="one"), track(params_hash="two")], "seconds")
    assert result["status"] == "ready"
    assert [item["included"] for item in result["tracks"]] == [True, True]
    assert "parameter hashes differ across included recordings" in result["caveats"]


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


def _stored_snapshot(data_root: Path, sha: str) -> tuple[bytes, str, dict[str, bytes]]:
    blob = (data_root / "blobs" / sha).read_bytes()
    analysis = data_root / "analysis" / sha / "m1-v3"
    files = {
        str(path.relative_to(analysis)): path.read_bytes()
        for path in sorted(analysis.rglob("*"))
        if path.is_file()
    }
    return blob, hashlib.sha256(blob).hexdigest(), files


def _assert_preserved(data_root: Path, sha: str, before: tuple[bytes, str, dict[str, bytes]]) -> None:
    blob, digest, files = _stored_snapshot(data_root, sha)
    assert blob == before[0]
    assert digest == before[1]
    assert files == before[2]


def _upload(client: TestClient, project_id: str, path: Path, filename: str) -> dict:
    with path.open("rb") as handle:
        response = client.post(
            f"/api/projects/{project_id}/assets",
            files={"file": (filename, handle, "audio/wav")},
        )
    assert response.status_code == 200, response.text
    return response.json()["asset"]


def _write_cache(data_root: Path, asset: dict, *, mono: bool = False, lufs: float = -14.0) -> None:
    dest = data_root / "analysis" / asset["sha256"] / "m1-v3"
    dest.mkdir(parents=True)
    peak = -1.0
    charts = {
        "T01": _chart(
            "T01",
            "frame-rms+master-minmax-envelope-v1",
            [
                _summary("Sample peak", peak, "dBFS"),
                _summary("Sample peak time", 0.1, "s"),
                _summary("Whole-file RMS", -18.0, "dBFS"),
                _summary("Crest factor", 17.0, "dB"),
            ],
            lines=[_line("1 s RMS", [0.0, 1.0], [-20.0, -16.0], "dBFS")],
        ),
        "T02": _chart(
            "T02",
            "ffmpeg-ebur128+frame-rms-v1",
            [
                _summary("Integrated loudness", lufs, "LUFS"),
                _summary("Loudness range", 4.0, "LU"),
                _summary("FFmpeg true peak", -0.6, "dBTP"),
            ],
            lines=[
                _line("1 s RMS", [0.0, 1.0], [-20.0, -16.0], "dBFS"),
                _line("3 s short-term LUFS", [0.0, 1.0], [-14.0, -13.0], "LUFS"),
            ],
        ),
        "T03": _chart(
            "T03",
            "welch-nperseg-8192-v1",
            [_summary("Below 20 Hz", 1.0, "%")],
            bars=[
                {"label": "20\u201360 Hz", "value": 10.0},
                {"label": "10000\u201322050 Hz", "value": 5.0},
            ],
        ),
        "T06": _chart(
            "T06",
            "onset-autocorr-v1",
            [],
            bars=[{"label": "120.0 BPM", "value": 0.4}],
            evidence="estimated",
        ),
        "T10": _chart(
            "T10",
            "tail-silence-rail-4x-peak-v1",
            [
                _summary("4x reconstructed peak", -0.4, "dBTP"),
                _summary("4x peak time", 0.2, "s"),
                _summary("Full-scale samples", 0, ""),
                _summary("Endpoint", "zero", ""),
                _summary("Sub-threshold intervals", 0, ""),
            ],
            bars=[{"label": "last 50 ms RMS", "value": -80.0}],
        ),
    }
    if mono:
        charts["T05"] = {
            "chart_kind": "T05",
            "status": "not_available",
            "evidence_class": "not_applicable",
            "method_id": "none",
            "summary": [],
            "caveats": ["Mono input has no stereo field. No right channel was invented."],
            "series": {"lines": [], "bars": [], "heatmap": None},
        }
    else:
        charts["T05"] = _chart(
            "T05",
            "lr-correlation-1s-v1",
            [
                _summary("Whole-file correlation", 0.8, ""),
                _summary("Side/mid", -12.0, "dB"),
                _summary("Mono fold-down change", -0.2, "dB"),
                _summary("Below 120 Hz correlation", 0.6, ""),
            ],
        )
    for kind, document in charts.items():
        (dest / f"{kind}.json").write_text(json.dumps(document), encoding="utf-8")
    metrics = {
        "algorithm_version": "m1-v3",
        "params_hash": "album-test-hash",
        "sample_peak_dbfs": peak,
        "rms_dbfs": -18.0,
        "loudness": {"integrated_lufs": lufs},
    }
    (dest / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")


def _complete(client: TestClient, asset_id: str) -> None:
    client.app.state.db.execute(
        "UPDATE assets SET analysis_status = 'completed' WHERE id = ?",
        (asset_id,),
    )
    client.app.state.db.commit()


def _wav(path: Path, channels: int, seed: int = 1) -> None:
    sample = 1000 + seed
    frame = [sample, -sample] if channels == 2 else [sample]
    pcm_wav(path, frame * 8, 8000, channels, 16)


def test_album_links_existing_asset_without_copying_bytes(client: TestClient, settings: Settings, tmp_path: Path):
    study = client.post("/api/projects", json={"name": "Study"}).json()
    album = client.post("/api/projects", json={"name": "Album", "mode": "album"}).json()
    wav = tmp_path / "tone.wav"
    _wav(wav, 2)
    uploaded = _upload(client, study["id"], wav, "tone.wav")
    blob = (settings.data_root / "blobs" / uploaded["sha256"]).read_bytes()
    linked = client.post(
        f"/api/projects/{album['id']}/members",
        json={"asset_id": uploaded["id"]},
    )
    assert linked.status_code == 200
    assert (settings.data_root / "blobs" / uploaded["sha256"]).read_bytes() == blob
    rejected = client.post(
        f"/api/projects/{album['id']}/assets",
        files={"file": ("tone.wav", wav.read_bytes(), "audio/wav")},
    )
    assert rejected.status_code == 400
    assert rejected.json()["error"] == "album_does_not_import"
    projects = client.get("/api/projects").json()
    assert any(item["id"] == study["id"] and item["mode"] == "study" for item in projects)
    assert client.get(f"/api/projects/{study['id']}/comparison").status_code == 404
    assert client.get(f"/api/projects/{study['id']}/comparison").json()["error"] == "not_album"
    assert client.get(f"/api/projects/{album['id']}/comparison?x=beats").status_code == 400
    duplicate = client.post(f"/api/projects/{album['id']}/members", json={"asset_id": uploaded["id"]})
    assert duplicate.status_code == 409
    removed = client.delete(f"/api/projects/{album['id']}/members/{uploaded['id']}")
    assert removed.status_code == 204
    assert (settings.data_root / "blobs" / uploaded["sha256"]).read_bytes() == blob
    assert client.get(f"/api/assets/{uploaded['id']}").status_code == 200


def test_review_starts_unchecked_and_does_not_change_the_number(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    measured = {"calls": 0}

    def boom(*_args, **_kwargs):
        measured["calls"] += 1
        raise AssertionError("album comparison measured a WAV")

    monkeypatch.setattr("app.measure.levels", boom)
    study = client.post("/api/projects", json={"name": "Study"}).json()
    album = client.post("/api/projects", json={"name": "Album", "mode": "album"}).json()
    ids = []
    snapshots = []
    for index, loudness in enumerate((-14.0, -11.0, -16.0)):
        path = tmp_path / f"tone-{index}.wav"
        _wav(path, 2, seed=index + 1)
        asset = _upload(client, study["id"], path, path.name)
        _write_cache(settings.data_root, asset, lufs=loudness)
        _complete(client, asset["id"])
        snapshots.append((asset["sha256"], _stored_snapshot(settings.data_root, asset["sha256"])))
        ids.append(asset["id"])
        linked = client.post(f"/api/projects/{album['id']}/members", json={"asset_id": asset["id"]})
        assert linked.status_code == 200
        _assert_preserved(settings.data_root, asset["sha256"], snapshots[-1][1])
    mono_path = tmp_path / "mono.wav"
    _wav(mono_path, 1, seed=20)
    mono = _upload(client, study["id"], mono_path, "mono.wav")
    _write_cache(settings.data_root, mono, mono=True, lufs=-13.0)
    _complete(client, mono["id"])
    mono_before = _stored_snapshot(settings.data_root, mono["sha256"])
    assert client.post(f"/api/projects/{album['id']}/members", json={"asset_id": mono["id"]}).status_code == 200
    bare_path = tmp_path / "bare.wav"
    _wav(bare_path, 2, seed=30)
    bare = _upload(client, study["id"], bare_path, "bare.wav")
    bare_blob = (settings.data_root / "blobs" / bare["sha256"]).read_bytes()
    assert client.post(f"/api/projects/{album['id']}/members", json={"asset_id": bare["id"]}).status_code == 200

    comparison = client.get(f"/api/projects/{album['id']}/comparison")
    assert comparison.status_code == 200, comparison.text
    body = comparison.json()
    assert measured["calls"] == 0
    assert body["status"] == "ready"
    included = [item for item in body["tracks"] if item["included"]]
    assert len(included) == 4
    assert len(body["pairs"]) == 6
    mono_track = next(item for item in body["tracks"] if item["asset_id"] == mono["id"])
    correlation = next(item for item in mono_track["scalars"] if item["name"] == "correlation")
    assert correlation["evidence_class"] == "not_applicable"
    assert correlation["value"] is None
    bare_track = next(item for item in body["tracks"] if item["asset_id"] == bare["id"])
    assert bare_track["included"] is False
    assert bare_track["omit_reason"] == "analysis_incomplete"

    order = client.put(
        f"/api/projects/{album['id']}/order",
        json={"asset_ids": list(reversed([*ids, mono["id"], bare["id"]]))},
    )
    assert order.status_code == 200, order.text
    detail = client.get(f"/api/projects/{album['id']}").json()
    assert [item["id"] for item in detail["assets"]] == list(reversed([*ids, mono["id"], bare["id"]]))
    for sha, before in snapshots:
        _assert_preserved(settings.data_root, sha, before)
    _assert_preserved(settings.data_root, mono["sha256"], mono_before)
    assert (settings.data_root / "blobs" / bare["sha256"]).read_bytes() == bare_blob

    reviews = client.get(f"/api/projects/{album['id']}/reviews")
    assert reviews.status_code == 200, reviews.text
    peak = next(item for item in reviews.json() if item["checkpoint_id"] == "sample_peak")
    assert peak["status"] == "unchecked"
    saved = client.put(
        f"/api/projects/{album['id']}/reviews",
        json={
            "asset_id": peak["asset_id"],
            "checkpoint_id": "sample_peak",
            "status": "intentional",
            "note": "ends hot on purpose",
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["status"] == "intentional"
    assert saved.json()["value"] == peak["value"]
    assert saved.json()["unit"] == peak["unit"]
    again = client.get(f"/api/projects/{album['id']}/reviews").json()
    stored = next(
        item
        for item in again
        if item["checkpoint_id"] == "sample_peak" and item["asset_id"] == peak["asset_id"]
    )
    assert stored["value"] == peak["value"]
    assert stored["status"] == "intentional"
    for sha, before in snapshots:
        _assert_preserved(settings.data_root, sha, before)
    assert client.app.state.db.execute("SELECT COUNT(*) FROM export_runs").fetchone()[0] == 0


def test_schema_v5_preserves_rows_and_foreign_keys(tmp_path: Path):
    database = tmp_path / "studio.sqlite3"
    conn = sqlite3.connect(database)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = OFF")
    for name in ("001_init.sql", "002_analysis.sql", "003_lyrics.sql", "004_exports.sql"):
        conn.executescript((MIGRATIONS / name).read_text())
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA user_version = 4")
    sha = "ab" * 32
    content = "cd" * 32
    now = "2026-01-01T00:00:00+00:00"
    conn.execute(
        "INSERT INTO projects (id, name, mode, created_at, updated_at) VALUES (?, ?, 'study', ?, ?)",
        ("p1", "Kept study", now, now),
    )
    conn.execute(
        """
        INSERT INTO assets (
          id, sha256, original_name, byte_length, duration_s, sample_rate, channels,
          subtype, analysis_status, playback_status, created_at
        ) VALUES (?, ?, 'kept.wav', 44, 1.0, 44100, 2, 'pcm_16', 'completed', 'ready', ?)
        """,
        ("a1", sha, now),
    )
    conn.execute(
        "INSERT INTO project_assets (project_id, asset_id, ordering) VALUES ('p1', 'a1', 0)"
    )
    conn.execute(
        "INSERT INTO lyric_files (sha256, byte_length, created_at) VALUES (?, 4, ?)",
        (content, now),
    )
    conn.execute(
        """
        INSERT INTO lyric_uploads (
          id, project_id, asset_id, file_sha256, source_kind, original_name, created_at
        ) VALUES ('up1', 'p1', 'a1', ?, 'txt', 'kept.txt', ?)
        """,
        (content, now),
    )
    conn.execute(
        """
        INSERT INTO lyric_documents (
          id, upload_id, project_id, asset_id, revision, is_current, created_at
        ) VALUES ('doc1', 'up1', 'p1', 'a1', 1, 1, ?)
        """,
        (now,),
    )
    conn.execute(
        """
        INSERT INTO lyric_segments (
          id, document_id, ordinal, text, start_s, end_s, timing_origin, artist_verified, note
        ) VALUES ('seg1', 'doc1', 0, 'kept line', NULL, NULL, 'unplaced', 0, '')
        """
    )
    conn.execute(
        """
        INSERT INTO annotations (
          id, project_id, asset_id, segment_id, start_s, end_s, text, created_at
        ) VALUES ('ann1', 'p1', 'a1', 'seg1', 0.0, 0.5, 'kept note', ?)
        """,
        (now,),
    )
    conn.execute(
        """
        INSERT INTO export_runs (
          id, project_id, asset_id, profile, lyrics_mode, lyric_revision,
          source_sha256, algorithm_version, params_hash, content_sha256, created_at
        ) VALUES (
          'export-1', 'p1', 'a1', 'technical', 'summarized', 1, ?, 'm1-v3', 'params', ?, ?
        )
        """,
        (sha, content, now),
    )
    conn.commit()
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()

    migrated = connect(database)
    try:
        assert migrated.execute("PRAGMA user_version").fetchone()[0] == 5
        assert migrated.execute("SELECT name FROM projects WHERE id = 'p1'").fetchone()[0] == "Kept study"
        assert migrated.execute("SELECT sha256 FROM assets WHERE id = 'a1'").fetchone()[0] == sha
        assert migrated.execute("SELECT ordering FROM project_assets WHERE asset_id = 'a1'").fetchone()[0] == 0
        assert migrated.execute("SELECT text FROM lyric_segments WHERE id = 'seg1'").fetchone()[0] == "kept line"
        assert migrated.execute("SELECT text FROM annotations WHERE id = 'ann1'").fetchone()[0] == "kept note"
        assert (
            migrated.execute("SELECT content_sha256 FROM export_runs WHERE id = 'export-1'").fetchone()[0]
            == content
        )
        assert migrated.execute("PRAGMA foreign_key_check").fetchall() == []
        migrated.execute(
            "INSERT INTO projects (id, name, mode, created_at, updated_at) VALUES (?, ?, 'album', ?, ?)",
            ("p2", "Album", now, now),
        )
        migrated.commit()
        assert migrated.execute("SELECT mode FROM projects WHERE id = 'p2'").fetchone()[0] == "album"
        assert migrated.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        migrated.close()


def _ready_pair(client: TestClient, settings: Settings, tmp_path: Path) -> tuple[str, str, str]:
    study = client.post("/api/projects", json={"name": "Study"}).json()
    album = client.post("/api/projects", json={"name": "Album", "mode": "album"}).json()
    sha = ""
    for index in (1, 2):
        path = tmp_path / f"export-{index}.wav"
        _wav(path, 2, seed=40 + index)
        asset = _upload(client, study["id"], path, path.name)
        _write_cache(settings.data_root, asset, lufs=-14.0 - index)
        _complete(client, asset["id"])
        sha = asset["sha256"]
        assert client.post(
            f"/api/projects/{album['id']}/members",
            json={"asset_id": asset["id"]},
        ).status_code == 200
    return study["id"], album["id"], sha


def test_album_zip_hashes_report_not_png_and_skips_wav(
    client: TestClient, settings: Settings, tmp_path: Path
):
    _study, album_id, sha = _ready_pair(client, settings, tmp_path)
    before = _stored_snapshot(settings.data_root, sha)
    first = client.post(f"/api/projects/{album_id}/album-export")
    assert first.status_code == 200, first.text
    first_body = first.json()
    published = settings.data_root / "exports" / f"{first_body['export_id']}.zip"
    published_bytes = published.read_bytes()
    second = client.post(f"/api/projects/{album_id}/album-export")
    assert second.status_code == 200, second.text
    second_body = second.json()
    assert first_body["content_sha256"] == second_body["content_sha256"]
    assert first_body["export_id"] != second_body["export_id"]
    assert published.read_bytes() == published_bytes
    with zipfile.ZipFile(published) as archive:
        names = archive.namelist()
        assert not any(name.endswith(".wav") or ".." in name.split("/") for name in names)
        assert set(names) == set(first_body["files"])
        assert "comparison.json" in names and "album-report.md" in names
        report = archive.read("album-report.md").decode()
        comparison = json.loads(archive.read("comparison.json"))
    assert "quality score" not in report.lower()
    assert "defective" not in report.lower()
    headings = [line[3:] for line in report.splitlines() if line.startswith("## ")]
    assert headings == [
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
    ]
    assert "The application did not listen" in report
    assert "Welch PSD" in report
    assert "minus" in report
    assert "export-1.wav" in report
    assert comparison["comparison_version"] == "album-qc-v1"
    assert "created_at" not in comparison
    _assert_preserved(settings.data_root, sha, before)
    assert client.app.state.db.execute("SELECT COUNT(*) FROM export_runs").fetchone()[0] == 0
    download = client.get(f"/api/projects/{album_id}/album-exports/{first_body['export_id']}")
    assert download.status_code == 200
    assert download.content == published_bytes


def test_png_failure_publishes_nothing(client: TestClient, settings: Settings, tmp_path: Path, monkeypatch):
    _study, album_id, sha = _ready_pair(client, settings, tmp_path)
    before = _stored_snapshot(settings.data_root, sha)

    def boom(_document):
        raise RuntimeError("png")

    monkeypatch.setattr("app.album.render_figure", boom)
    failed = client.post(f"/api/projects/{album_id}/album-export")
    assert failed.status_code >= 400
    assert list((settings.data_root / "exports").glob("*.zip")) == []
    assert client.app.state.db.execute("SELECT COUNT(*) FROM album_export_runs").fetchone()[0] == 0
    _assert_preserved(settings.data_root, sha, before)


def test_t02_dbfs_color_unchanged_and_t11_tracks_differ():
    assert _paint({"chart_kind": "T02"}, {"unit": "dBFS"}, 0)[0] == ENERGY
    first = _paint({"chart_kind": "T11"}, {"unit": "dBFS"}, 0)
    second = _paint({"chart_kind": "T11"}, {"unit": "dBFS"}, 1)
    assert first[0] != second[0]
    assert first[1] == "-"
    assert second[1] == "-"


def test_versioned_migration_rolls_back_the_schema_version(tmp_path: Path):
    database = tmp_path / "plain.sqlite3"
    conn = sqlite3.connect(database)
    conn.execute("PRAGMA user_version = 4")
    conn.execute("CREATE TABLE kept (id TEXT)")
    conn.execute("INSERT INTO kept (id) VALUES ('row')")
    conn.commit()
    with pytest.raises(sqlite3.OperationalError):
        _apply_versioned(conn, "CREATE TABLE added (id TEXT);\nSELECT missing_album_migration;\n", 5)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 4
    assert conn.execute("SELECT id FROM kept").fetchone()[0] == "row"
    assert conn.execute("SELECT name FROM sqlite_master WHERE name = 'added'").fetchone() is None
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    conn.close()


def test_failed_v5_migration_keeps_the_existing_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    database = tmp_path / "studio.sqlite3"
    conn = sqlite3.connect(database)
    conn.executescript((MIGRATIONS / "001_init.sql").read_text())
    conn.execute("PRAGMA user_version = 4")
    conn.execute(
        "INSERT INTO projects (id, name, mode, created_at, updated_at) VALUES ('p1', 'Kept study', 'study', 't', 't')"
    )
    conn.commit()
    conn.close()
    real_read = Path.read_text

    def fail_after_the_script(self: Path, *args: object, **kwargs: object) -> str:
        text = real_read(self, *args, **kwargs)
        if self.name == "005_album.sql":
            return text + "\nSELECT raise_album_migration;\n"
        return text

    monkeypatch.setattr(Path, "read_text", fail_after_the_script)
    with pytest.raises(sqlite3.OperationalError):
        connect(database)
    kept = sqlite3.connect(database)
    try:
        assert kept.execute("PRAGMA user_version").fetchone()[0] == 4
        assert kept.execute("SELECT name FROM projects WHERE id = 'p1'").fetchone()[0] == "Kept study"
        assert kept.execute("SELECT name FROM sqlite_master WHERE name = 'album_reviews'").fetchone() is None
        assert kept.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        kept.close()


def test_album_rejects_study_records_and_keeps_existing_ones(
    client: TestClient, settings: Settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    study = client.post("/api/projects", json={"name": "Study"}).json()
    album = client.post("/api/projects", json={"name": "Album", "mode": "album"}).json()
    wav = tmp_path / "tone.wav"
    _wav(wav, 2)
    uploaded = _upload(client, study["id"], wav, "tone.wav")
    other = tmp_path / "other.wav"
    _wav(other, 2, seed=2)
    second = _upload(client, study["id"], other, "other.wav")
    assert client.post(f"/api/projects/{album['id']}/members", json={"asset_id": uploaded["id"]}).status_code == 200
    assert client.post(f"/api/projects/{album['id']}/members", json={"asset_id": second["id"]}).status_code == 200

    lyric = client.post(
        f"/api/projects/{album['id']}/assets/{uploaded['id']}/lyrics",
        files={"file": ("line.txt", b"kept line\n", "text/plain")},
    )
    assert lyric.status_code == 400
    assert lyric.json()["error"] == "not_study"
    annotation = client.post(
        f"/api/projects/{album['id']}/assets/{uploaded['id']}/annotations",
        json={"start_s": 0, "end_s": 1, "text": "note"},
    )
    assert annotation.status_code == 400
    assert annotation.json()["error"] == "not_study"
    exported = client.post(
        f"/api/projects/{album['id']}/assets/{uploaded['id']}/exports",
        json={"profile": "technical", "lyrics": "summarized"},
    )
    assert exported.status_code == 400
    assert exported.json()["error"] == "not_study"
    study_lyric = client.post(
        f"/api/projects/{study['id']}/assets/{uploaded['id']}/lyrics",
        files={"file": ("line.txt", b"kept line\n", "text/plain")},
    )
    assert study_lyric.status_code == 201, study_lyric.text

    now = "2026-01-01T00:00:00+00:00"
    content = "ab" * 32
    db = client.app.state.db
    db.execute("INSERT INTO lyric_files (sha256, byte_length, created_at) VALUES (?, 4, ?)", (content, now))
    db.execute(
        """
        INSERT INTO lyric_uploads (
          id, project_id, asset_id, file_sha256, source_kind, original_name, created_at
        ) VALUES ('up-album', ?, ?, ?, 'txt', 'album.txt', ?)
        """,
        (album["id"], uploaded["id"], content, now),
    )
    db.execute(
        """
        INSERT INTO lyric_documents (
          id, upload_id, project_id, asset_id, revision, is_current, created_at
        ) VALUES ('doc-album', 'up-album', ?, ?, 1, 1, ?)
        """,
        (album["id"], uploaded["id"], now),
    )
    db.commit()
    blocked = client.delete(f"/api/projects/{album['id']}/members/{uploaded['id']}")
    assert blocked.status_code == 409
    assert blocked.json()["error"] == "member_has_records"
    assert "lyric document" in blocked.json()["message"]
    assert db.execute("SELECT id FROM lyric_documents WHERE id = 'doc-album'").fetchone()[0] == "doc-album"
    members = [item["id"] for item in client.get(f"/api/projects/{album['id']}").json()["assets"]]
    assert uploaded["id"] in members
    assert db.in_transaction is False

    original = db.execute

    def fail_resequence(sql, parameters=()):
        if isinstance(sql, str) and sql.lstrip().startswith("UPDATE project_assets SET ordering"):
            raise sqlite3.OperationalError("forced")
        return original(sql, parameters)

    monkeypatch.setattr(db, "execute", fail_resequence)
    failed = client.delete(f"/api/projects/{album['id']}/members/{second['id']}")
    assert failed.status_code == 500
    assert failed.json()["error"] == "member_not_removed"
    members = [item["id"] for item in client.get(f"/api/projects/{album['id']}").json()["assets"]]
    assert second["id"] in members
    assert db.in_transaction is False
    del settings


def test_batch_membership_keeps_order_and_does_not_duplicate_jobs(
    client: TestClient, settings: Settings, tmp_path: Path
):
    study = client.post("/api/projects", json={"name": "Study"}).json()
    album = client.post("/api/projects", json={"name": "Album", "mode": "album"}).json()
    anchor_path = tmp_path / "anchor.wav"
    _wav(anchor_path, 1, seed=1)
    anchor = _upload(client, study["id"], anchor_path, "anchor.wav")
    blobs = {
        anchor["sha256"]: (settings.data_root / "blobs" / anchor["sha256"]).read_bytes(),
    }
    linked = client.post(f"/api/projects/{album['id']}/members", json={"asset_id": anchor["id"]})
    assert linked.status_code == 200

    missing = client.post(f"/api/projects/{album['id']}/members", json={"asset_id": "missing"})
    assert missing.status_code == 404
    assert [item["id"] for item in client.get(f"/api/projects/{album['id']}").json()["assets"]] == [anchor["id"]]

    assets = []
    for index in range(15):
        path = tmp_path / f"track-{index:02d}.wav"
        _wav(path, 1, seed=index + 2)
        asset = _upload(client, study["id"], path, path.name)
        blobs[asset["sha256"]] = (settings.data_root / "blobs" / asset["sha256"]).read_bytes()
        assets.append(asset)
        added = client.post(f"/api/projects/{album['id']}/members", json={"asset_id": asset["id"]})
        assert added.status_code == 200
        assert added.json()["ordering"] == index + 1

    duplicate = client.post(f"/api/projects/{album['id']}/members", json={"asset_id": assets[0]["id"]})
    assert duplicate.status_code == 409
    ordered = [item["id"] for item in client.get(f"/api/projects/{album['id']}").json()["assets"]]
    assert ordered == [anchor["id"], *[asset["id"] for asset in assets]]

    fresh = assets[0]
    first = client.post(f"/api/assets/{fresh['id']}/analyze")
    assert first.status_code == 202
    assert first.json()["status"] == "queued"
    second = client.post(f"/api/assets/{fresh['id']}/analyze")
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["status"] == "queued"
    queued_jobs = client.app.state.db.execute(
        "SELECT COUNT(*) FROM jobs WHERE asset_id = ? AND status = 'queued'",
        (fresh["id"],),
    ).fetchone()[0]
    assert queued_jobs == 1

    running = assets[1]
    running_job = client.post(f"/api/assets/{running['id']}/analyze")
    assert running_job.status_code == 202
    client.app.state.db.execute(
        "UPDATE jobs SET status = 'running' WHERE id = ?",
        (running_job.json()["id"],),
    )
    client.app.state.db.execute(
        "UPDATE assets SET analysis_status = 'running' WHERE id = ?",
        (running["id"],),
    )
    client.app.state.db.commit()
    again = client.post(f"/api/assets/{running['id']}/analyze")
    assert again.json()["id"] == running_job.json()["id"]
    assert again.json()["status"] == "running"
    assert client.get(f"/api/assets/{running['id']}").json()["analysis_status"] == "running"
    assert (
        client.app.state.db.execute("SELECT COUNT(*) FROM jobs WHERE asset_id = ?", (running["id"],)).fetchone()[0]
        == 1
    )

    done = assets[2]
    metrics = settings.data_root / "analysis" / done["sha256"] / "m1-v3" / "metrics.json"
    metrics.parent.mkdir(parents=True)
    metrics.write_text('{"algorithm_version":"m1-v3"}\n', encoding="utf-8")
    before_metrics = metrics.read_bytes()
    client.app.state.db.execute(
        """
        INSERT INTO analysis_runs (
          id, asset_id, algorithm_version, params_hash, status, metrics_path, evidence_path
        ) VALUES (?, ?, ?, ?, 'completed', ?, ?)
        """,
        ("run-done", done["id"], ALGORITHM_VERSION, PARAMS_HASH, str(metrics), str(metrics)),
    )
    client.app.state.db.execute(
        "UPDATE assets SET analysis_status = 'completed' WHERE id = ?",
        (done["id"],),
    )
    client.app.state.db.commit()
    reused = client.post(f"/api/assets/{done['id']}/analyze")
    assert reused.status_code == 202
    assert reused.json()["status"] == "completed"
    assert metrics.read_bytes() == before_metrics
    assert list(metrics.parent.iterdir()) == [metrics]
    assert (
        client.app.state.db.execute(
            "SELECT COUNT(*) FROM jobs WHERE asset_id = ? AND status IN ('queued', 'running')",
            (done["id"],),
        ).fetchone()[0]
        == 0
    )

    failed = assets[3]
    client.app.state.db.execute(
        "UPDATE assets SET analysis_status = 'failed' WHERE id = ?",
        (failed["id"],),
    )
    client.app.state.db.commit()
    retried = client.post(f"/api/assets/{failed['id']}/analyze")
    assert retried.status_code == 202
    assert retried.json()["status"] == "queued"
    repeated = client.post(f"/api/assets/{failed['id']}/analyze")
    assert repeated.json()["id"] == retried.json()["id"]

    for sha, raw in blobs.items():
        assert (settings.data_root / "blobs" / sha).read_bytes() == raw
    assert not (settings.data_root / "exports").exists()
    opened = client.get(f"/api/projects/{album['id']}")
    assert opened.status_code == 200
    assert [item["id"] for item in opened.json()["assets"]] == ordered
