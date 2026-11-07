"""Write one asset's chart, evidence, and metric files."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from app.charts import KINDS, build_all, not_run
from app.measure import ALGORITHM_VERSION, PARAMS_HASH, decode_wav
from app.png import RENDERER_VERSION, presentation_png, publish_png, write_manifest

DECODER_NOTE = (
    "Integer PCM is divided by its own full scale: 32768 for 16-bit and "
    "8388608 for 24-bit. This is not the legacy unconditional /2**31 scale."
)


def analysis_dir(data_root: Path, sha256: str, version: str = ALGORITHM_VERSION) -> Path:
    return data_root / "analysis" / sha256 / version


def dumps(payload: dict) -> str:
    return json.dumps(payload, indent=2, allow_nan=False)


def run_analysis(master: Path, dest: Path, asset_id: str, sha256: str) -> dict:
    audio = decode_wav(master)
    charts = build_all(audio, master)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    written: list[str] = []
    for kind, document in charts.items():
        (dest / f"{kind}.json").write_text(dumps(document))
        if document["status"] == "ready":
            try:
                publish_png(presentation_png(dest, kind), document)
                written.append(kind)
            except Exception as exc:  # noqa: BLE001 - a missing PNG must not drop the measurements
                document["caveats"].append(f"PNG was not written: {type(exc).__name__}")
                (dest / f"{kind}.json").write_text(dumps(document))
    write_manifest(dest, written, ALGORITHM_VERSION)
    metrics = _metrics(audio, charts, asset_id, sha256)
    evidence = _evidence(audio, charts, asset_id, metrics)
    (dest / "metrics.json").write_text(dumps(metrics))
    (dest / "evidence.json").write_text(dumps(evidence))
    return metrics


def _metrics(audio, charts: dict, asset_id: str, sha256: str) -> dict:
    duration = audio.samples.shape[0] / audio.sample_rate
    t02 = charts["T02"]
    loudness = {}
    for item in t02["summary"]:
        if item["label"] == "Integrated loudness":
            loudness["integrated_lufs"] = float(item["value"].split()[0])
        elif item["label"] == "Loudness range":
            loudness["lra_lu"] = float(item["value"].split()[0])
        elif item["label"] == "FFmpeg true peak":
            loudness["true_peak_dbtp"] = float(item["value"].split()[0])
    sample_peak = _labeled(charts["T01"], "Sample peak")
    rms = _labeled(charts["T01"], "Whole-file RMS")
    return {
        "asset_id": asset_id,
        "algorithm_version": ALGORITHM_VERSION,
        "params_hash": PARAMS_HASH,
        "decoder_note": DECODER_NOTE,
        "sha256": sha256,
        "duration_s": duration,
        "sample_rate": audio.sample_rate,
        "channels": int(audio.samples.shape[1]),
        "sample_peak_dbfs": sample_peak,
        "rms_dbfs": rms,
        "loudness": loudness,
        "charts": {kind: charts[kind]["status"] for kind in KINDS},
    }


def _labeled(document: dict, label: str) -> float | None:
    for item in document["summary"]:
        if item["label"] == label and item["value"] not in {"undefined", "none"}:
            return float(item["value"].split()[0])
    return None


def _evidence(audio, charts: dict, asset_id: str, metrics: dict) -> dict:
    duration = audio.samples.shape[0] / audio.sample_rate
    records = []

    def add(name: str, value, unit: str, kind: str, method: str, caveat: str, confidence: str):
        if value is None:
            return
        records.append(
            {
                "id": f"ev:{name}",
                "asset_id": asset_id,
                "kind": kind,
                "name": name,
                "interval_s": [0.0, duration],
                "value": value,
                "unit": unit,
                "method": method,
                "confidence": confidence,
                "caveat": caveat,
            }
        )

    add(
        "sample_peak_dbfs",
        metrics.get("sample_peak_dbfs"),
        "dBFS",
        "measured",
        "sample-peak:" + ALGORITHM_VERSION,
        "Sample peak is not reconstructed true peak.",
        "high",
    )
    add(
        "rms_dbfs",
        metrics.get("rms_dbfs"),
        "dBFS",
        "measured",
        "rms:" + ALGORITHM_VERSION,
        "RMS is not loudness.",
        "high",
    )
    loud = metrics.get("loudness") or {}
    add(
        "integrated_lufs",
        loud.get("integrated_lufs"),
        "LUFS",
        "measured",
        "ffmpeg-ebur128:" + ALGORITHM_VERSION,
        "EBU R128 integrated loudness.",
        "high",
    )
    add(
        "lra_lu",
        loud.get("lra_lu"),
        "LU",
        "measured",
        "ffmpeg-ebur128:" + ALGORITHM_VERSION,
        "Loudness range is not crest factor.",
        "high",
    )
    add(
        "true_peak_dbtp",
        loud.get("true_peak_dbtp"),
        "dBTP",
        "measured",
        "ffmpeg-ebur128:" + ALGORITHM_VERSION,
        "Does not by itself establish audible clipping.",
        "high",
    )
    t06 = charts["T06"]
    if t06["status"] == "ready" and t06["series"]["bars"]:
        add(
            "pulse_candidate_bpm",
            float(t06["series"]["bars"][0]["label"].split()[0]),
            "BPM",
            "estimated",
            "onset-autocorr:" + ALGORITHM_VERSION,
            "Not a beat grid. Half-time and double-time remain hypotheses.",
            "low",
        )
    return {"algorithm_version": ALGORITHM_VERSION, "asset_id": asset_id, "records": records}


def public_summary(document: dict, asset_id: str) -> dict:
    kind = document["chart_kind"]
    ready = document["status"] == "ready"
    return {
        "chart_kind": kind,
        "status": document["status"],
        "title": document["title"],
        "evidence_class": document["evidence_class"],
        "method_id": document["method_id"],
        "method_version": document["method_version"],
        "caveats": document["caveats"],
        "summary": document["summary"],
        "not_available_reason": document.get("not_available_reason"),
        "error": document.get("error"),
        "data_url": f"/api/assets/{asset_id}/charts/{kind}/data",
        "png_url": (
            f"/api/assets/{asset_id}/charts/{kind}/image?renderer={RENDERER_VERSION}" if ready else None
        ),
    }


def empty_registry(asset_id: str) -> list[dict]:
    return [public_summary(not_run(kind), asset_id) for kind in KINDS]
