"""Chart documents for T01–T10. Each builder fails alone."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from app.measure import (
    ALGORITHM_VERSION,
    ChartUnavailable,
    Decoded,
    ending,
    levels,
    measure_loudness,
    oversampled_peak,
    region_deltas,
    rhythm,
    spectrogram,
    stereo,
    structure,
    tonality,
    welch_bands,
)

TITLES = {
    "T01": "Waveform and peak envelope",
    "T02": "Loudness and dynamics",
    "T03": "Long-term spectral balance",
    "T04": "Spectrogram",
    "T05": "Stereo and mono compatibility",
    "T06": "Rhythm and pulse evidence",
    "T07": "Pitch-class and tonal estimates",
    "T08": "Structure novelty",
    "T09": "Recurrence and self-similarity",
    "T10": "Ending, gap, and anomaly review",
}
KINDS = tuple(TITLES)


def _base(kind: str, status: str, evidence: str, method: str, caveats: list[str]) -> dict:
    return {
        "chart_kind": kind,
        "status": status,
        "title": TITLES[kind],
        "evidence_class": evidence,
        "method_id": method,
        "method_version": ALGORITHM_VERSION,
        "time_start_s": None,
        "time_end_s": None,
        "sample_rate": None,
        "hop_s": None,
        "axis_definitions": {"x": "", "y": "", "y_scale": "linear"},
        "series": {"lines": [], "bars": [], "heatmap": None},
        "review_markers": [],
        "summary": [],
        "caveats": caveats,
        "not_available_reason": None,
        "error": None,
    }


def not_run(kind: str) -> dict:
    document = _base(kind, "not_run", "unknown", "none", [])
    document["not_available_reason"] = "Analysis has not been run."
    return document


def _unavailable(kind: str, reason: str, evidence: str = "unknown") -> dict:
    document = _base(kind, "not_available", evidence, "none", [reason])
    document["not_available_reason"] = reason
    return document


def _failed(kind: str, exc: Exception) -> dict:
    message = f"{type(exc).__name__}: {exc}"[:300]
    document = _base(kind, "failed", "unknown", "none", [message])
    document["error"] = message
    return document


def _marker(time_s: float, kind: str, label: str, value: str, caveat: str) -> dict:
    return {
        "time_s": float(time_s),
        "kind": kind,
        "label": label,
        "value": value,
        "caveat": caveat,
    }


def _summary(label: str, value: str) -> dict:
    return {"label": label, "value": value}


def _line(name: str, times, values, unit: str) -> dict:
    ys = []
    xs = []
    for time, value in zip(times, values, strict=True):
        xs.append(float(time))
        ys.append(None if value is None else float(value))
    return {"name": name, "unit": unit, "x": xs, "y": ys}


def build_all(audio: Decoded, master: Path) -> dict[str, dict]:
    shared: dict = {}
    for name, fn in (
        ("levels", lambda: levels(audio)),
        ("peak", lambda: oversampled_peak(audio)),
        (
            "loudness",
            lambda: measure_loudness(
                master, timeout_s=max(60.0, audio.samples.shape[0] / audio.sample_rate * 4)
            ),
        ),
    ):
        try:
            shared[name] = fn()
        except Exception as exc:  # noqa: BLE001 - a shared measurement must not abort every chart
            shared[name] = exc
    documents = {}
    for kind in KINDS:
        builder = globals()[f"build_{kind.lower()}"]
        try:
            documents[kind] = builder(audio, shared)
        except ChartUnavailable as exc:
            evidence = "not_applicable" if kind == "T05" else "unknown"
            documents[kind] = _unavailable(kind, str(exc), evidence)
        except Exception as exc:  # noqa: BLE001 - one chart must not abort the others
            documents[kind] = _failed(kind, exc)
    return documents


def _require(shared: dict, name: str):
    value = shared[name]
    if isinstance(value, Exception):
        raise value
    return value


def build_t01(audio: Decoded, shared: dict) -> dict:
    data = _require(shared, "levels")
    envelope = data["envelope"]
    overview = data["overview"]
    document = _base(
        "T01",
        "ready",
        "measured",
        "frame-rms+master-minmax-envelope-v1",
        [
            "Envelope traces are min and max of the master inside equal buckets.",
            (
                f"The detail envelope uses {envelope['buckets']} buckets "
                f"({envelope['bucket_s'] * 1000:.1f} ms). "
                f"The overview uses {overview['buckets']} wider buckets "
                f"({overview['bucket_s'] * 1000:.1f} ms). Zoom uses the detail buckets."
            ),
            "A bucket max is not the exact sample. The sample-peak marker is the exact sample.",
            "100 ms and 1 s RMS are frame powers, not the waveform.",
            "The transport preview is a separate playback envelope, not this chart.",
        ],
    )
    document["sample_rate"] = audio.sample_rate
    document["hop_s"] = envelope["bucket_s"]
    document["axis_definitions"] = {"x": "Time (s)", "y": "Amplitude or dBFS", "y_scale": "linear"}
    document["series"]["lines"].extend(
        [
            _line("Envelope max", envelope["t"], envelope["max"], "amplitude"),
            _line("Envelope min", envelope["t"], envelope["min"], "amplitude"),
            _line("Overview envelope max", overview["t"], overview["max"], "amplitude"),
            _line("Overview envelope min", overview["t"], overview["min"], "amplitude"),
        ]
    )
    if len(data["rms_100ms_t"]):
        document["series"]["lines"].append(
            _line("100 ms RMS", data["rms_100ms_t"], data["rms_100ms_db"], "dBFS")
        )
    if len(data["rms_1s_t"]):
        document["series"]["lines"].append(
            _line("1 s RMS", data["rms_1s_t"], data["rms_1s_db"], "dBFS")
        )
    document["summary"] = [
        _summary("Sample peak", f"{data['sample_peak_dbfs']:.2f} dBFS"),
        _summary("Sample peak time", f"{data['sample_peak_time_s']:.3f} s"),
        _summary("Whole-file RMS", f"{data['rms_dbfs']:.2f} dBFS"),
        _summary("Crest factor", f"{data['crest_db']:.2f} dB"),
        _summary("Detail buckets", str(envelope["buckets"])),
        _summary("Overview buckets", str(overview["buckets"])),
    ]
    document["review_markers"] = [
        _marker(
            data["sample_peak_time_s"],
            "sample_peak",
            f"sample peak channel {data['sample_peak_channel']}",
            f"{data['sample_peak_dbfs']:.2f} dBFS",
            "Exact sample on the master. Not a reconstructed true peak and not an audible defect.",
        )
    ]
    document["time_start_s"] = 0.0
    document["time_end_s"] = audio.samples.shape[0] / audio.sample_rate
    return document


def build_t02(audio: Decoded, shared: dict) -> dict:
    loud = _require(shared, "loudness")
    level = _require(shared, "levels")
    document = _base(
        "T02",
        "ready",
        "measured",
        "ffmpeg-ebur128+frame-rms-v1",
        [
            "Integrated LUFS, LRA, and true peak come from FFmpeg EBU R128.",
            "1 s RMS is a separate custom power measurement. LRA is not crest factor.",
            "Reconstructed true peak is a listening checkpoint. It does not establish audible clipping.",
        ],
    )
    document["axis_definitions"] = {"x": "Time (s)", "y": "dBFS or LUFS", "y_scale": "linear"}
    if len(level["rms_1s_t"]):
        document["series"]["lines"].append(
            _line("1 s RMS", level["rms_1s_t"], level["rms_1s_db"], "dBFS")
        )
    if loud["short_term"]:
        document["series"]["lines"].append(
            _line(
                "3 s short-term LUFS",
                [item["time_s"] for item in loud["short_term"]],
                [item["lufs"] for item in loud["short_term"]],
                "LUFS",
            )
        )
    else:
        document["caveats"].append("Short-term LUFS needs a 3 s window. None were reported.")
    duration = audio.samples.shape[0] / audio.sample_rate
    if duration < 10 and loud["lra_lu"] is not None:
        document["caveats"].append(
            "LRA on a file shorter than 10 s is the FFmpeg figure, not a stable program range."
        )
    summary = [
        _summary("Integrated loudness", f"{loud['integrated_lufs']:.1f} LUFS"),
        _summary("Sample peak", f"{level['sample_peak_dbfs']:.2f} dBFS"),
    ]
    if loud["lra_lu"] is not None:
        summary.append(_summary("Loudness range", f"{loud['lra_lu']:.1f} LU"))
    if loud["true_peak_dbtp"] is not None:
        summary.append(_summary("FFmpeg true peak", f"{loud['true_peak_dbtp']:.1f} dBTP"))
    document["summary"] = summary
    regions = _regions(level, duration)
    if regions:
        document["series"]["bars"] = [
            {
                "label": f"{item['start_s']:.1f}–{item['end_s']:.1f} s",
                "value": item["delta"],
            }
            for item in regions
        ]
        document["summary"].extend(
            _summary(
                f"Window {item['start_s']:.1f}–{item['end_s']:.1f} s",
                f"{item['delta']:+.2f} dB vs file mean",
            )
            for item in regions
        )
        document["caveats"].append(
            "Windows are equal slices of the file. The bar is mean 1 s RMS, or 100 ms RMS "
            "when the file has fewer than two 1 s frames, minus the mean of that same series. "
            "These are analysis windows, not verses, choruses, or emotional sections."
        )
    else:
        document["caveats"].append("Not enough RMS frames for a region comparison.")
    document["time_end_s"] = duration
    return document


def _regions(level: dict, duration: float) -> list[dict]:
    parts = 4 if duration >= 4 else 2 if duration >= 1 else 0
    if parts == 0:
        return []
    times = level["rms_1s_t"]
    values = level["rms_1s_db"]
    if len(times) < 2:
        times = level["rms_100ms_t"]
        values = level["rms_100ms_db"]
    if len(times) < 2:
        return []
    return region_deltas(times, values, duration, parts)


def build_t03(audio: Decoded, shared: dict) -> dict:
    del shared
    data = welch_bands(audio)
    document = _base(
        "T03",
        "ready",
        "measured",
        f"welch-nperseg-{data['nperseg']}-v1",
        [
            "Band percentages are shares of Welch power, including energy below 20 Hz in the remainder.",
            "Spectrum shape is not brightness, vocal level, or instrument identity.",
        ],
    )
    if data["nperseg"] != 8192:
        document["caveats"].append(
            f"Welch used {data['nperseg']} samples because the file is shorter than 8192."
        )
    document["axis_definitions"] = {
        "x": "Frequency (Hz)",
        "y": "Power share (%)",
        "y_scale": "linear",
    }
    document["series"]["bars"] = [
        {
            "label": f"{int(item['lo_hz'])}–{int(item['hi_hz'])} Hz",
            "value": item["percent"],
        }
        for item in data["bands"]
    ]
    # Downsample the PSD for the log-frequency line. Skip 0 Hz.
    freqs = data["freqs"]
    power = data["power"]
    mask = freqs > 0
    step = max(1, int(mask.sum()) // 400)
    document["series"]["lines"].append(
        _line(
            "Welch PSD",
            freqs[mask][::step],
            10 * np.log10(np.maximum(power[mask][::step], 1e-16)),
            "dB",
        )
    )
    document["summary"] = [
        _summary("Power-weighted centroid", f"{data['centroid_hz']:.0f} Hz"),
        _summary("Below 20 Hz", f"{data['below_20_hz_percent']:.1f} %"),
        _summary("Nyquist", f"{data['nyquist_hz']:.0f} Hz"),
    ]
    document["summary"].extend(
        _summary(bar["label"], f"{bar['value']:.1f} %") for bar in document["series"]["bars"]
    )
    return document


def build_t04(audio: Decoded, shared: dict) -> dict:
    del shared
    data = spectrogram(audio)
    document = _base(
        "T04",
        "ready",
        "measured",
        f"stft-magnitude-nperseg-{data['nperseg']}-v1",
        [
            "Color is magnitude in dB relative to the track median, then averaged into display bins.",
            "The frequency axis is linearly spaced FFT bins, averaged into at most 96 rows. It is not a log-frequency scale.",
            "Band traces are bass 20–250 Hz, body 250–2000 Hz, presence 2000–5000 Hz, and air 5000 Hz to Nyquist. They are not vocal or instrument tracks.",
            "Averaging neighboring bins can lower a narrow peak. It does not move energy above Nyquist.",
        ],
    )
    document["axis_definitions"] = {"x": "Time (s)", "y": "Frequency (Hz)", "y_scale": "linear"}
    document["hop_s"] = data["nperseg"] / audio.sample_rate / 2
    document["series"]["heatmap"] = {
        "x": [float(value) for value in data["times"]],
        "y": [float(value) for value in data["freqs"]],
        "z": [[float(value) for value in row] for row in data["db"]],
    }
    document["summary"] = [
        _summary("Frequency scale", "linear FFT bins"),
        _summary("Nyquist", f"{audio.sample_rate / 2:.0f} Hz"),
        _summary("Display rows", str(len(data["freqs"]))),
    ]
    for item in data["coarse"]:
        document["series"]["lines"].append(
            _line(item["name"], data["coarse_t"], item["db"], "dB rel. median")
        )
    document["summary"].extend(_summary(item["name"], "time trace") for item in data["coarse"])
    document["time_end_s"] = audio.samples.shape[0] / audio.sample_rate
    return document


def build_t05(audio: Decoded, shared: dict) -> dict:
    del shared
    data = stereo(audio)
    document = _base(
        "T05",
        "ready",
        "measured",
        "lr-correlation-1s-v1",
        [
            "Low correlation is not proof of a phase failure.",
            "Undefined correlation means that window had no level variation.",
            "Sub-120 Hz figures are a linear-phase-free Butterworth split, not a mastering verdict.",
        ],
    )
    document["axis_definitions"] = {"x": "Time (s)", "y": "Correlation or dB", "y_scale": "linear"}
    document["hop_s"] = 1.0
    if data["times"]:
        document["series"]["lines"].append(
            _line("1 s correlation", data["times"], data["correlation_1s"], "ratio")
        )
        document["series"]["lines"].append(
            _line("1 s side/mid", data["times"], data["side_mid_1s"], "dB")
        )
    summary = []
    if data["correlation"] is None:
        summary.append(_summary("Whole-file correlation", "undefined"))
    else:
        summary.append(_summary("Whole-file correlation", f"{data['correlation']:.3f}"))
    if data["side_mid_db"] is None:
        summary.append(_summary("Side/mid", "undefined (mid at the silence floor)"))
    else:
        summary.append(_summary("Side/mid", f"{data['side_mid_db']:.1f} dB"))
    summary.append(_summary("Side energy", f"{data['side_energy_percent']:.1f} %"))
    summary.append(_summary("Mono fold-down change", f"{data['mono_energy_change_db']:.1f} dB"))
    sub = data["sub_bass"]
    if sub is None:
        document["caveats"].append("Sample rate is too low for a 120 Hz split.")
    elif sub["correlation"] is None:
        summary.append(_summary("Below 120 Hz correlation", "undefined"))
    else:
        summary.append(_summary("Below 120 Hz correlation", f"{sub['correlation']:.3f}"))
    document["summary"] = summary
    return document


def build_t06(audio: Decoded, shared: dict) -> dict:
    del shared
    data = rhythm(audio)
    document = _base(
        "T06",
        "ready",
        "estimated",
        "onset-autocorr-v1",
        [
            "Candidates are onset-autocorrelation peaks between 45 and 200 BPM.",
            "Half-time and double-time readings are hypotheses, not a second measurement and not a beat grid.",
            "This does not establish meter, syncopation, or groove.",
        ],
    )
    document["axis_definitions"] = {"x": "Time (s)", "y": "Onset strength", "y_scale": "linear"}
    document["sample_rate"] = int(data["sample_rate"])
    step = max(1, len(data["onset_t"]) // 800)
    document["series"]["lines"].append(
        _line("Onset strength", data["onset_t"][::step], data["onset"][::step], "score")
    )
    document["series"]["bars"] = [
        {"label": f"{item['bpm']:.1f} BPM", "value": item["acf"]} for item in data["candidates"]
    ]
    for item in data["hypotheses"]:
        document["series"]["bars"].append(
            {"label": f"{item['relation']} {item['bpm']:.1f} BPM", "value": item["acf"]}
        )
    if data["candidates"]:
        top = data["candidates"][0]["bpm"]
        document["caveats"].append(
            f"The strongest autocorrelation peak is {top:.1f} BPM. "
            "It is a pulse estimate, not a verified tempo, meter, beat grid, or groove."
        )
        if data["hypotheses"]:
            document["caveats"].append(
                "Half-time and double-time bars are other autocorrelation peaks near twice or "
                "half that period. They are not made by multiplying the displayed tempo."
            )
        else:
            document["caveats"].append(
                "No autocorrelation peak was found near half or double the strongest period."
            )
        document["summary"] = [
            _summary(item["label"], f"autocorrelation {item['value']:.3f}")
            for item in document["series"]["bars"]
        ]
    else:
        document["caveats"].append("No pulse candidate rose above a steady or silent onset curve.")
        document["summary"] = [_summary("Pulse candidates", "none")]
    return document


def build_t07(audio: Decoded, shared: dict) -> dict:
    del shared
    data = tonality(audio)
    document = _base(
        "T07",
        "ready",
        "estimated",
        "stft-pitch-class-krumhansl-v1",
        [
            "Pitch class is a partial-sensitive spectral estimate.",
            "Key names are correlations with a fixed profile. They are not a verified key or chord progression.",
        ],
    )
    document["axis_definitions"] = {"x": "Pitch class", "y": "Share", "y_scale": "linear"}
    document["series"]["bars"] = [
        {"label": name, "value": value}
        for name, value in zip(data["names"], data["pitch_class"], strict=True)
    ]
    document["summary"] = [
        _summary(item["key"], f"profile r {item['r']:.3f}") for item in data["candidates"]
    ]
    if not data["candidates"]:
        document["summary"] = [_summary("Key candidates", "undefined")]
    return document


def build_t08(audio: Decoded, shared: dict) -> dict:
    del shared
    data = structure(audio)
    document = _base(
        "T08",
        "ready",
        "estimated",
        "spectral-shape-novelty-2s-v1",
        [
            "Peaks are changes in spectral shape. They are not verified verses, choruses, or section counts.",
        ],
    )
    document["axis_definitions"] = {"x": "Time (s)", "y": "Novelty", "y_scale": "linear"}
    document["hop_s"] = 2.0
    document["series"]["lines"].append(_line("Novelty", data["times"], data["novelty"], "score"))
    document["review_markers"] = [
        _marker(
            time,
            "provisional_change",
            "provisional change",
            "spectral-shape novelty peak",
            "Not a verified verse, chorus, or section boundary.",
        )
        for time in data["transitions_s"]
    ]
    document["summary"] = [
        _summary("Provisional changes", str(len(data["transitions_s"]))),
    ]
    if not data["transitions_s"]:
        document["caveats"].append("No change point passed the prominence gate.")
    return document


def build_t09(audio: Decoded, shared: dict) -> dict:
    del shared
    data = structure(audio)
    document = _base(
        "T09",
        "ready",
        "estimated",
        "spectral-shape-cosine-v1",
        [
            "The heatmap is cosine similarity of spectral shape inside this recording.",
            "A bright cell is not a matching melody or hook.",
        ],
    )
    document["axis_definitions"] = {"x": "Time (s)", "y": "Time (s)", "y_scale": "linear"}
    document["series"]["heatmap"] = data["similarity"]
    document["summary"] = [
        _summary("Bins", str(len(data["times"]))),
        _summary("Bin spacing", "2 s"),
    ]
    return document


def build_t10(audio: Decoded, shared: dict) -> dict:
    peak = _require(shared, "peak")
    data = ending(audio, peak)
    document = _base(
        "T10",
        "ready",
        "measured",
        "tail-silence-rail-4x-peak-v1",
        [
            "Flags are listening checkpoints. They are not established clicks, dropouts, or audible clipping.",
            "Silence is a 50 ms frame below -60 dBFS, using a -160 dB floor for digital zero.",
        ],
    )
    document["axis_definitions"] = {"x": "Last milliseconds", "y": "dBFS", "y_scale": "linear"}
    document["series"]["bars"] = [
        {"label": f"last {item['last_ms']} ms RMS", "value": item["rms_dbfs"]}
        for item in data["tails"]
    ]
    document["review_markers"] = [
        _marker(
            data["oversampled_peak_time_s"],
            "reconstructed_peak",
            f"4x reconstructed peak channel {data['oversampled_peak_channel']}",
            f"{data['oversampled_peak_dbtp']:.2f} dBTP",
            "Listening checkpoint. Not an established click, dropout, or audible clip.",
        )
    ]
    document["review_markers"].extend(
        _marker(
            time,
            "full_scale_sample",
            "full-scale sample",
            "0 dBFS sample",
            "A sample reached the integer rail. That is not by itself an audible defect.",
        )
        for time in data["rail_times_s"][:10]
    )
    document["summary"] = [
        _summary("4x reconstructed peak", f"{data['oversampled_peak_dbtp']:.2f} dBTP"),
        _summary("4x peak time", f"{data['oversampled_peak_time_s']:.3f} s"),
        _summary("Full-scale samples", str(data["rail_count"])),
        _summary(
            "Endpoint",
            "non-zero" if data["endpoint_nonzero"] else "zero",
        ),
        _summary("Sub-threshold intervals", str(len(data["silence"]))),
    ]
    document["series"]["heatmap"] = None
    document["silence"] = data["silence"]
    return document
