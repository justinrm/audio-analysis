import hashlib
import json
import math
from pathlib import Path

import pytest
from app.charts import build_t05
from app.config import Settings
from app.main import create_app
from app.measure import (
    ChartUnavailable,
    correlation,
    decode_wav,
    levels,
    oversampled_peak,
    parse_ebur128,
    welch_bands,
)
from fastapi.testclient import TestClient

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


SUMMARY = """
[Parsed_ebur128_0] Summary:

  Integrated loudness:
    I:         -15.5 LUFS
    Threshold: -25.5 LUFS

  Loudness range:
    LRA:        20.0 LU
    Threshold: -35.5 LUFS
    LRA low:   -35.5 LUFS
    LRA high:  -15.5 LUFS

  True peak:
    Peak:      -12.0 dBFS
"""

METADATA = """
frame:0    pts:0       pts_time:0
lavfi.r128.S=-120.691
frame:30    pts:24000    pts_time:3
lavfi.r128.S=-15.540
"""


def _tone(
    path: Path,
    seconds: float,
    freq: float,
    amp: float,
    channels: int,
    bits: int,
    invert: bool = False,
) -> None:
    rate = 8000
    count = int(rate * seconds)
    full = 32767 if bits == 16 else 8388607
    samples: list[int] = []
    for index in range(count):
        value = int(amp * full * math.sin(2 * math.pi * freq * index / rate))
        if channels == 1:
            samples.append(value)
        elif invert:
            samples.extend((value, -value))
        else:
            samples.extend((value, value))
    pcm_wav(path, samples, rate, channels, bits)


def test_parse_ebur128_summary() -> None:
    parsed = parse_ebur128(SUMMARY, METADATA)
    assert parsed["integrated_lufs"] == pytest.approx(-15.5)
    assert parsed["lra_lu"] == pytest.approx(20.0)
    assert parsed["true_peak_dbtp"] == pytest.approx(-12.0)
    assert parsed["short_term"] == [{"time_s": 3.0, "lufs": -15.540}]


def test_sixteen_and_twenty_four_bit_share_a_scale(tmp_path: Path) -> None:
    sixteen = tmp_path / "a16.wav"
    twenty = tmp_path / "a24.wav"
    pcm_wav(sixteen, [16384] * 800, 8000, 1, 16)
    pcm_wav(twenty, [4_194_304] * 800, 8000, 1, 24)
    left = decode_wav(sixteen)
    right = decode_wav(twenty)
    assert left.samples[0, 0] == pytest.approx(0.5)
    assert right.samples[0, 0] == pytest.approx(0.5)
    assert left.samples[0, 0] == pytest.approx(16384 / 32768)
    assert (
        abs(20 * math.log10(abs(left.samples[0, 0])) - 20 * math.log10(abs(right.samples[0, 0])))
        < 0.05
    )


def test_sixteen_bit_full_scale_is_not_the_old_int32_scale(tmp_path: Path) -> None:
    path = tmp_path / "full.wav"
    pcm_wav(path, [32767], 8000, 1, 16)
    audio = decode_wav(path)
    assert audio.samples[0, 0] > 0.9
    assert audio.rail_count == 1


def test_stereo_correlation_and_mono(tmp_path: Path) -> None:
    same = tmp_path / "same.wav"
    flipped = tmp_path / "flip.wav"
    mono = tmp_path / "mono.wav"
    _tone(same, 1.0, 440, 0.5, 2, 16)
    _tone(flipped, 1.0, 440, 0.5, 2, 16, invert=True)
    _tone(mono, 1.0, 440, 0.5, 1, 16)
    same_audio = decode_wav(same)
    flipped_audio = decode_wav(flipped)
    assert correlation(same_audio.samples[:, 0], same_audio.samples[:, 1]) == pytest.approx(
        1, abs=1e-6
    )
    assert correlation(flipped_audio.samples[:, 0], flipped_audio.samples[:, 1]) == pytest.approx(
        -1, abs=1e-6
    )
    with pytest.raises(ChartUnavailable, match="Mono"):
        build_t05(decode_wav(mono), {})


def test_sine_energy_stays_in_band_and_under_nyquist(tmp_path: Path) -> None:
    path = tmp_path / "sine.wav"
    _tone(path, 1.0, 440, 0.5, 1, 16)
    audio = decode_wav(path)
    bands = welch_bands(audio)
    assert float(bands["freqs"].max()) <= 4000
    winner = max(bands["bands"], key=lambda item: item["percent"])
    assert winner["lo_hz"] == 250
    assert winner["percent"] > 50
    total = bands["below_20_hz_percent"] + sum(item["percent"] for item in bands["bands"])
    assert total == pytest.approx(100, abs=0.2)


def test_silence_stays_finite(tmp_path: Path) -> None:
    path = tmp_path / "quiet.wav"
    pcm_wav(path, [0] * 8000, 8000, 1, 16)
    audio = decode_wav(path)
    measured = levels(audio)
    encoded = json.dumps(measured["rms_dbfs"], allow_nan=False)
    assert math.isfinite(measured["rms_dbfs"])
    assert "NaN" not in encoded
    assert correlation(audio.samples[:, 0], audio.samples[:, 0]) is None


def test_oversampled_peak_can_exceed_the_sample_peak(tmp_path: Path) -> None:
    path = tmp_path / "inter.wav"
    samples = [30000 if index % 2 == 0 else -30000 for index in range(4000)]
    pcm_wav(path, samples, 8000, 1, 16)
    audio = decode_wav(path)
    sample_peak = float(abs(audio.samples).max())
    peak = oversampled_peak(audio)
    assert peak["linear"] > sample_peak
    assert math.isfinite(peak["dbtp"])


def test_worker_completes_charts_and_keeps_the_master(
    client: TestClient, tmp_path: Path, settings
) -> None:
    path = tmp_path / "study.wav"
    _tone(path, 5.0, 440, 0.4, 2, 16)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    project_id = _project(client)
    asset_id = _upload(client, project_id, path).json()["asset"]["id"]
    queued = client.post(f"/api/assets/{asset_id}/analyze")
    assert queued.status_code == 202
    assert queued.json()["status"] == "queued"
    assert client.app.state.worker.run_available() == 1
    done = client.get(f"/api/jobs/{queued.json()['id']}")
    assert done.json()["status"] == "completed", done.json()
    blob = settings.data_root / "blobs" / digest
    assert blob.read_bytes() == raw
    charts = client.get(f"/api/assets/{asset_id}/charts").json()["charts"]
    by_kind = {item["chart_kind"]: item for item in charts}
    assert by_kind["T02"]["status"] == "ready"
    assert by_kind["T05"]["status"] == "ready"
    assert by_kind["T08"]["status"] == "not_available"
    assert "LUFS" in by_kind["T02"]["summary"][0]["value"]
    data = client.get(f"/api/assets/{asset_id}/charts/T02/data")
    assert data.status_code == 200
    assert data.json()["series"]["lines"]
    image = client.get(f"/api/assets/{asset_id}/charts/T02/image")
    assert image.status_code == 200
    assert image.content.startswith(b"\x89PNG")
    evidence = client.get(f"/api/assets/{asset_id}/evidence")
    assert evidence.status_code == 200
    names = {item["name"] for item in evidence.json()["records"]}
    assert "integrated_lufs" in names
    assert "true_peak_dbtp" in names
    metrics_path = settings.data_root / "analysis" / digest / "m1-v1" / "metrics.json"
    before = metrics_path.read_bytes()
    cached = client.post(f"/api/assets/{asset_id}/analyze")
    assert cached.status_code == 202
    assert cached.json()["status"] == "completed"
    assert metrics_path.read_bytes() == before
    runs = client.app.state.db.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0]
    assert runs == 1
    encoded = metrics_path.read_text()
    assert "NaN" not in encoded and "Infinity" not in encoded


def test_a_failed_chart_does_not_hide_the_others(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    def boom(*_args, **_kwargs):
        raise RuntimeError("welch broke")

    monkeypatch.setattr("app.charts.build_t03", boom)
    path = tmp_path / "partial.wav"
    _tone(path, 5.0, 440, 0.4, 1, 16)
    project_id = _project(client)
    asset_id = _upload(client, project_id, path).json()["asset"]["id"]
    job = client.post(f"/api/assets/{asset_id}/analyze").json()
    assert client.app.state.worker.run_available() == 1
    assert client.get(f"/api/jobs/{job['id']}").json()["status"] == "completed"
    charts = {
        item["chart_kind"]: item
        for item in client.get(f"/api/assets/{asset_id}/charts").json()["charts"]
    }
    assert charts["T02"]["status"] == "ready"
    assert charts["T03"]["status"] == "failed"
    assert "welch broke" in charts["T03"]["error"]
    assert charts["T05"]["status"] == "not_available"


def test_interrupted_job_can_be_retried(client: TestClient, tmp_path: Path) -> None:
    path = tmp_path / "retry.wav"
    _tone(path, 1.0, 440, 0.2, 1, 16)
    project_id = _project(client)
    asset_id = _upload(client, project_id, path).json()["asset"]["id"]
    job_id = client.post(f"/api/assets/{asset_id}/analyze").json()["id"]
    client.app.state.db.execute("UPDATE jobs SET status = 'running' WHERE id = ?", (job_id,))
    client.app.state.db.execute(
        "UPDATE assets SET analysis_status = 'running' WHERE id = ?", (asset_id,)
    )
    client.app.state.db.commit()
    assert client.app.state.worker.recover_interrupted() == 1
    failed = client.get(f"/api/jobs/{job_id}").json()
    assert failed["status"] == "failed"
    assert failed["error"] == "interrupted"
    retried = client.post(f"/api/assets/{asset_id}/analyze")
    assert retried.status_code == 202
    assert retried.json()["status"] == "queued"
    assert retried.json()["id"] != job_id


def test_legacy_metrics_remain_a_comparison_target() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "references"
        / "legacy-audit"
        / "analysis"
        / "metrics.json"
    )
    tracks = json.loads(path.read_text())
    assert tracks[0]["loudness"]["integrated_lufs"]
    assert "sample_peak_dbfs" in tracks[0]
    assert "rms_dbfs" in tracks[0]
