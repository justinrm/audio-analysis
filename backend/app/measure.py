"""Pure measurements for one WAV. Constants are versioned as m1-v2.

Legacy audit math is the source of the window sizes. Decoding scales each
integer PCM width by its own full scale. The old unconditional /2**31 scale
is not used.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy import ndimage, signal

ALGORITHM_VERSION = "m1-v2"
PARAMS = {
    "welch_nperseg": 8192,
    "envelope_s": 0.1,
    "envelope_buckets": 4000,
    "overview_buckets": 250,
    "region_count": 4,
    "rms_s": 1.0,
    "downsample": 4,
    "rhythm_nperseg": 1024,
    "tonal_nperseg": 8192,
    "structure_bin_s": 2.0,
    "silence_dbfs": -60.0,
    "db_floor": 1e-16,
}
PARAMS_HASH = hashlib.sha256(
    json.dumps(PARAMS, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()
FLOOR = PARAMS["db_floor"]
NOTE_NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])
BANDS = (
    (20.0, 60.0),
    (60.0, 120.0),
    (120.0, 250.0),
    (250.0, 500.0),
    (500.0, 2000.0),
    (2000.0, 5000.0),
    (5000.0, 10000.0),
    (10000.0, None),
)


class ChartUnavailable(Exception):
    """The chart cannot be computed for this file. Other charts may still succeed."""


@dataclass(frozen=True)
class Decoded:
    samples: np.ndarray
    sample_rate: int
    rail_count: int
    rail_times_s: list[float]


def power_db(value: float) -> float:
    return float(10.0 * math.log10(max(float(value), FLOOR)))


def amp_db(value: float) -> float:
    return float(20.0 * math.log10(max(float(value), FLOOR)))


def finite(value: float) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("measurement was not finite")
    return number


def correlation(left: np.ndarray, right: np.ndarray) -> float | None:
    if left.size < 2 or right.size < 2:
        return None
    if float(np.std(left)) < 1e-8 or float(np.std(right)) < 1e-8:
        return None
    value = float(np.corrcoef(left, right)[0, 1])
    if not math.isfinite(value):
        return None
    return value


def _unpack(raw: bytes, width: int) -> tuple[np.ndarray, int]:
    if width == 2:
        integers = np.frombuffer(raw, dtype="<i2").astype(np.int32)
        return integers.astype(np.float64) / 32768.0, 32768
    if width == 3:
        packed = np.frombuffer(raw, dtype=np.uint8)
        if packed.size % 3 != 0:
            raise ValueError("24-bit PCM is truncated")
        integers = (
            packed[0::3].astype(np.int32)
            | (packed[1::3].astype(np.int32) << 8)
            | (packed[2::3].astype(np.int32) << 16)
        )
        integers = np.where(integers >= 0x800000, integers - 0x1000000, integers)
        return integers.astype(np.float64) / 8388608.0, 8388608
    raise ValueError(f"{width * 8}-bit PCM is not an analysis width")


def decode_wav(path: Path) -> Decoded:
    import wave

    with wave.open(str(path), "rb") as handle:
        channels = handle.getnchannels()
        rate = handle.getframerate()
        width = handle.getsampwidth()
        frames = handle.getnframes()
        raw = handle.readframes(frames)
    if channels < 1 or rate < 1 or frames < 1:
        raise ChartUnavailable("WAV has no samples to measure.")
    samples, full_scale = _unpack(raw, width)
    if samples.size != frames * channels:
        raise ValueError("decoded sample count does not match the WAV header")
    samples = samples.reshape(frames, channels)
    limit = (full_scale - 1) / full_scale
    mask = (samples <= -1.0) | (samples >= limit - 1e-12)
    positions = np.argwhere(mask)
    times = [float(int(row[0]) / rate) for row in positions[:30]]
    return Decoded(samples, rate, int(positions.shape[0]), times)


def _peak_location(samples: np.ndarray, rate: int) -> tuple[float, float, int]:
    flat = np.abs(samples)
    index = int(np.argmax(flat))
    frame, channel = np.unravel_index(index, samples.shape)
    return finite(flat[frame, channel]), float(frame) / rate, int(channel) + 1


def frame_power_db(samples: np.ndarray, rate: int, frame_s: float) -> tuple[np.ndarray, np.ndarray]:
    frame = max(1, round(rate * frame_s))
    count = samples.shape[0] // frame
    if count < 1:
        return np.array([]), np.array([])
    cut = samples[: count * frame]
    power = np.mean(cut.reshape(count, frame, samples.shape[1]) ** 2, axis=(1, 2))
    times = (np.arange(count) + 0.5) * frame / rate
    return times, 10.0 * np.log10(np.maximum(power, FLOOR))


def levels(audio: Decoded) -> dict:
    samples = audio.samples
    peak, peak_time, channel = _peak_location(samples, audio.sample_rate)
    power = float(np.mean(samples**2))
    rms_t, rms_db = frame_power_db(samples, audio.sample_rate, PARAMS["rms_s"])
    env_t, env_db = frame_power_db(samples, audio.sample_rate, PARAMS["envelope_s"])
    return {
        "rms_dbfs": power_db(power),
        "sample_peak_dbfs": amp_db(peak),
        "sample_peak_time_s": peak_time,
        "sample_peak_channel": channel,
        "crest_db": finite(amp_db(peak) - power_db(power)),
        "rms_1s_t": rms_t,
        "rms_1s_db": rms_db,
        "rms_100ms_t": env_t,
        "rms_100ms_db": env_db,
        "envelope": minmax_envelope(samples, audio.sample_rate, PARAMS["envelope_buckets"]),
        "overview": minmax_envelope(samples, audio.sample_rate, PARAMS["overview_buckets"]),
    }


def minmax_envelope(samples: np.ndarray, rate: int, limit: int) -> dict:
    """Min/max of the master inside equal sample buckets. Not a sample trace."""
    count = max(1, min(int(limit), samples.shape[0]))
    edges = np.linspace(0, samples.shape[0], count + 1, dtype=int)
    channel_min = samples.min(axis=1)
    channel_max = samples.max(axis=1)
    lows: list[float] = []
    highs: list[float] = []
    times: list[float] = []
    for start, stop in itertools.pairwise(edges):
        if stop <= start:
            continue
        lows.append(finite(float(channel_min[start:stop].min())))
        highs.append(finite(float(channel_max[start:stop].max())))
        times.append(finite(((start + stop) / 2) / rate))
    return {
        "t": times,
        "min": lows,
        "max": highs,
        "buckets": len(times),
        "bucket_s": finite(samples.shape[0] / rate / max(len(times), 1)),
    }


def region_deltas(times, values, duration: float, parts: int) -> list[dict]:
    """Mean level in equal-duration windows, minus the mean of the same series."""
    axis = np.asarray(times, dtype=float)
    series = np.asarray(values, dtype=float)
    usable = np.isfinite(series)
    if parts < 1 or duration <= 0 or not np.any(usable):
        return []
    baseline = float(np.mean(series[usable]))
    rows = []
    for index in range(parts):
        start = duration * index / parts
        end = duration * (index + 1) / parts
        inside = usable & (axis >= start) & (axis < end if index + 1 < parts else axis <= end)
        if not np.any(inside):
            continue
        level = float(np.mean(series[inside]))
        rows.append(
            {
                "start_s": finite(start),
                "end_s": finite(end),
                "level": finite(level),
                "delta": finite(level - baseline),
            }
        )
    return rows


def _nperseg(length: int, requested: int) -> int:
    if length < 256:
        raise ChartUnavailable(
            f"Need at least 256 samples for this spectrum. This file has {length}."
        )
    return int(min(requested, length))


def welch_bands(audio: Decoded) -> dict:
    samples = audio.samples
    rate = audio.sample_rate
    nperseg = _nperseg(samples.shape[0], PARAMS["welch_nperseg"])
    noverlap = nperseg // 2
    freqs, power = signal.welch(
        samples if samples.shape[1] > 1 else samples[:, 0],
        fs=rate,
        nperseg=nperseg,
        noverlap=noverlap,
        axis=0,
    )
    if power.ndim == 2:
        power = power.mean(axis=1)
    power = np.maximum(power, 0.0)
    total = float(power.sum())
    if total <= 0:
        raise ChartUnavailable("The spectrum has no energy.")
    nyquist = rate / 2
    if float(freqs.max()) > nyquist + 1e-6:
        raise ValueError("Welch returned a bin above Nyquist")
    bands = []
    for lo, hi in BANDS:
        upper = nyquist if hi is None else min(hi, nyquist)
        if lo >= upper:
            bands.append({"lo_hz": lo, "hi_hz": upper, "percent": 0.0})
            continue
        selected = power[(freqs >= lo) & (freqs < upper)]
        bands.append(
            {
                "lo_hz": lo,
                "hi_hz": upper,
                "percent": finite(float(selected.sum()) / total * 100.0),
            }
        )
    below = float(power[freqs < 20].sum()) / total * 100.0
    centroid = float((freqs * power).sum() / total)
    return {
        "freqs": freqs,
        "power": power,
        "bands": bands,
        "below_20_hz_percent": finite(below),
        "centroid_hz": finite(centroid),
        "nperseg": nperseg,
        "nyquist_hz": nyquist,
    }


def spectrogram(audio: Decoded) -> dict:
    mix = audio.samples.mean(axis=1)
    nperseg = _nperseg(mix.size, 2048)
    freqs, times, values = signal.spectrogram(
        mix,
        fs=audio.sample_rate,
        nperseg=nperseg,
        noverlap=nperseg // 2,
        mode="magnitude",
    )
    power = np.maximum(values, FLOOR)
    db = 10.0 * np.log10(power)
    db = db - np.median(db)
    coarse = []
    for name, lo, hi in (
        ("bass", 20.0, 250.0),
        ("body", 250.0, 2000.0),
        ("presence", 2000.0, 5000.0),
        ("air", 5000.0, audio.sample_rate / 2),
    ):
        if lo >= hi:
            continue
        selected = db[(freqs >= lo) & (freqs < hi)]
        if selected.size == 0:
            continue
        coarse.append({"name": name, "db": selected.mean(axis=0)})
    return {
        "freqs": _decimate_1d(freqs, 96),
        "times": _decimate_1d(times, 180),
        "db": _decimate_2d(db, 96, 180),
        "coarse_t": _decimate_1d(times, 180),
        "coarse": [{"name": item["name"], "db": _decimate_1d(item["db"], 180)} for item in coarse],
        "nperseg": nperseg,
    }


def stereo(audio: Decoded) -> dict:
    if audio.samples.shape[1] != 2:
        raise ChartUnavailable("Mono input has no stereo field. No right channel was invented.")
    left = audio.samples[:, 0]
    right = audio.samples[:, 1]
    mid = (left + right) / 2
    side = (left - right) / 2
    energy = float(np.mean(audio.samples**2))
    mid_power = float(np.mean(mid**2))
    side_power = float(np.mean(side**2))
    rate = audio.sample_rate
    frame = rate
    count = audio.samples.shape[0] // frame
    times: list[float] = []
    corr: list[float | None] = []
    side_mid: list[float | None] = []
    if count >= 1:
        for index in range(count):
            block = audio.samples[index * frame : (index + 1) * frame]
            times.append(index + 0.5)
            corr.append(correlation(block[:, 0], block[:, 1]))
            block_mid = (block[:, 0] + block[:, 1]) / 2
            block_side = (block[:, 0] - block[:, 1]) / 2
            side_mid.append(_ratio_db(np.mean(block_side**2), np.mean(block_mid**2)))
    sub = _sub_bass(audio)
    return {
        "correlation": correlation(left, right),
        "side_mid_db": _ratio_db(side_power, mid_power),
        "side_energy_percent": finite(side_power / max(energy, FLOOR) * 100.0),
        "mono_energy_change_db": power_db(mid_power) - power_db(energy)
        if energy > FLOOR
        else power_db(0),
        "times": times,
        "correlation_1s": corr,
        "side_mid_1s": side_mid,
        "sub_bass": sub,
    }


def _ratio_db(numerator: float, denominator: float) -> float | None:
    if denominator <= FLOOR:
        return None
    return power_db(float(numerator) / float(denominator))


def _sub_bass(audio: Decoded) -> dict | None:
    if audio.sample_rate <= 240:
        return None
    sos = signal.butter(6, 120, fs=audio.sample_rate, output="sos")
    low = signal.sosfilt(sos, audio.samples, axis=0)
    return {
        "correlation": correlation(low[:, 0], low[:, 1]),
        "side_mid_db": _ratio_db(
            float(np.mean(((low[:, 0] - low[:, 1]) / 2) ** 2)),
            float(np.mean(((low[:, 0] + low[:, 1]) / 2) ** 2)),
        ),
    }


def oversampled_peak(audio: Decoded, factor: int = 4) -> dict:
    samples = audio.samples
    rate = audio.sample_rate
    step = max(rate * 5, 1)
    best = 0.0
    best_time = 0.0
    best_channel = 1
    for start in range(0, samples.shape[0], step):
        end = min(start + step, samples.shape[0])
        left = max(0, start - 128)
        right = min(samples.shape[0], end + 128)
        up = signal.resample_poly(samples[left:right], factor, 1, axis=0, window=("kaiser", 8.6))
        up = up[(start - left) * factor : (end - left) * factor]
        if up.size == 0:
            continue
        magnitude = np.abs(up)
        index = int(np.argmax(magnitude))
        frame, channel = np.unravel_index(index, magnitude.shape)
        peak = float(magnitude[frame, channel])
        if peak > best:
            best = peak
            best_time = start / rate + frame / (rate * factor)
            best_channel = int(channel) + 1
    return {
        "dbtp": amp_db(best),
        "time_s": finite(best_time),
        "channel": best_channel,
        "linear": finite(best),
    }


def parse_ebur128(stderr: str, metadata: str) -> dict:
    if "Summary:" not in stderr:
        raise ValueError("FFmpeg ebur128 summary is missing")
    summary = stderr.split("Summary:", 1)[1]

    def read(pattern: str) -> float | None:
        match = re.search(pattern, summary)
        if match is None:
            return None
        return float(match.group(1))

    integrated = read(r"I:\s*([-\d.]+) LUFS")
    if integrated is None or not math.isfinite(integrated):
        raise ValueError("FFmpeg did not report integrated LUFS")
    lra = read(r"LRA:\s*([-\d.]+) LU")
    true_peak = read(r"True peak:\s*Peak:\s*([-\d.]+)")
    frames = []
    row: dict | None = None
    for line in metadata.splitlines():
        if line.startswith("frame:"):
            if row:
                frames.append(row)
            match = re.search(r"pts_time:(\S+)", line)
            row = {"time": float(match.group(1))} if match else None
        elif "=" in line and row is not None:
            key, raw = line.split("=", 1)
            row[key.replace("lavfi.r128.", "")] = float(raw)
    if row:
        frames.append(row)
    short = [
        {"time_s": item["time"], "lufs": item["S"]}
        for item in frames
        if "S" in item and item["time"] >= 3 and item["S"] > -70
    ]
    return {
        "integrated_lufs": finite(integrated),
        "lra_lu": None if lra is None or not math.isfinite(lra) else finite(lra),
        "true_peak_dbtp": None
        if true_peak is None or not math.isfinite(true_peak)
        else finite(true_peak),
        "short_term": short,
    }


def measure_loudness(path: Path, timeout_s: float) -> dict:
    with tempfile.TemporaryDirectory() as directory:
        meta = Path(directory) / "ebur128.txt"
        proc = subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-nostats",
                "-i",
                str(path),
                "-af",
                f"ebur128=metadata=1:peak=true,ametadata=print:file={meta}",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        metadata = meta.read_text() if meta.is_file() else ""
    if proc.returncode != 0:
        tail = proc.stderr[-400:].strip()
        raise RuntimeError(tail or "FFmpeg ebur128 failed")
    return parse_ebur128(proc.stderr, metadata)


def _downsample(audio: Decoded) -> tuple[np.ndarray, float]:
    mix = audio.samples.mean(axis=1)
    factor = PARAMS["downsample"]
    if mix.size < factor * 256:
        raise ChartUnavailable("File is too short to downsample for this estimate.")
    reduced = signal.resample_poly(mix, 1, factor)
    return reduced, audio.sample_rate / factor


def rhythm(audio: Decoded) -> dict:
    reduced, rate = _downsample(audio)
    nperseg = _nperseg(reduced.size, PARAMS["rhythm_nperseg"])
    noverlap = max(0, nperseg - max(1, nperseg // 8))
    freqs, times, spectrum = signal.stft(
        reduced,
        fs=rate,
        nperseg=nperseg,
        noverlap=noverlap,
        boundary=None,
        padded=False,
    )
    if times.size < 8:
        raise ChartUnavailable("Not enough frames for a pulse estimate.")
    magnitude = np.abs(spectrum)
    flux = np.maximum(np.diff(np.log1p(100 * magnitude), axis=1), 0)
    band = (freqs >= 40) & (freqs < min(5500, rate / 2))
    if not np.any(band):
        band = np.ones(freqs.shape, dtype=bool)
    onset = np.mean(flux[band], axis=0)
    window = min(101, onset.size if onset.size % 2 else max(1, onset.size - 1))
    if window >= 3:
        onset = np.maximum(onset - ndimage.median_filter(onset, size=window), 0)
    onset_t = times[1:]
    dt = float(onset_t[1] - onset_t[0]) if onset_t.size > 1 else 0.0
    candidates, hypotheses = _pulse_candidates(onset, dt) if dt > 0 else ([], [])
    return {
        "candidates": candidates,
        "hypotheses": hypotheses,
        "onset_t": onset_t,
        "onset": onset,
        "sample_rate": rate,
    }


def _pulse_candidates(onset: np.ndarray, dt: float) -> tuple[list[dict], list[dict]]:
    centered = onset - float(onset.mean())
    if float(np.max(np.abs(centered))) < 1e-8:
        return [], []
    acf = signal.correlate(centered, centered, mode="full", method="fft")[len(centered) - 1 :]
    acf = acf / np.maximum(np.arange(len(centered), 0, -1), 1)
    acf = acf / max(float(acf[0]), 1e-12)
    lo = max(1, int(60 / 200 / dt))
    hi = min(len(acf) - 1, int(60 / 45 / dt))
    if hi <= lo:
        return [], []
    peaks, _ = signal.find_peaks(acf[lo:hi], distance=3)
    peaks = peaks + lo
    peaks = sorted(peaks, key=lambda index: float(acf[index]), reverse=True)[:6]
    candidates = [
        {"bpm": finite(60 / (index * dt)), "acf": finite(float(acf[index]))} for index in peaks
    ]
    if not peaks:
        return [], []
    hypotheses = []
    primary = peaks[0]
    for relation, factor in (("half-time", 2.0), ("double-time", 0.5)):
        target = primary * factor
        if target < 1 or target >= len(acf):
            continue
        nearest = min(peaks, key=lambda index: abs(index - target))
        if nearest == primary or abs(nearest - target) > max(2.0, 0.15 * target):
            continue
        hypotheses.append(
            {
                "relation": relation,
                "bpm": finite(60 / (nearest * dt)),
                "acf": finite(float(acf[nearest])),
                "provenance": "autocorrelation-peak",
            }
        )
    return candidates, hypotheses


def tonality(audio: Decoded) -> dict:
    reduced, rate = _downsample(audio)
    nperseg = PARAMS["tonal_nperseg"]
    if reduced.size < nperseg:
        raise ChartUnavailable(
            f"Pitch-class estimate wants {nperseg} downsampled samples. "
            f"This file has {reduced.size}."
        )
    freqs, _times, spectrum = signal.stft(
        reduced,
        fs=rate,
        nperseg=nperseg,
        noverlap=nperseg - 1200,
        boundary=None,
        padded=False,
    )
    magnitude = np.abs(spectrum).astype(np.float64)
    if magnitude.shape[1] < 1:
        raise ChartUnavailable("Pitch-class estimate produced no frames.")
    harmonic = magnitude
    chosen = (freqs >= 65) & (freqs <= min(2000, rate / 2))
    if not np.any(chosen):
        raise ChartUnavailable("Sample rate leaves no 65–2000 Hz band for pitch class.")
    weights = np.sqrt(np.maximum(harmonic[chosen], 0))
    midi = 69 + 12 * np.log2(np.maximum(freqs[chosen], 1e-6) / 440)
    classes = np.rint(midi).astype(int) % 12
    chroma = np.zeros(12, dtype=np.float64)
    for pitch in range(12):
        chroma[pitch] = float(weights[classes == pitch].sum())
    total = float(chroma.sum())
    if total <= FLOOR:
        raise ChartUnavailable("No harmonic energy for a pitch-class estimate.")
    chroma /= total
    ranked = []
    for mode, profile in (("major", MAJOR), ("minor", MINOR)):
        for shift in range(12):
            score = correlation(chroma, np.roll(profile, shift))
            if score is None:
                continue
            ranked.append({"key": f"{NOTE_NAMES[shift]} {mode}", "r": score})
    ranked.sort(key=lambda item: item["r"], reverse=True)
    return {
        "pitch_class": [finite(value) for value in chroma],
        "names": NOTE_NAMES,
        "candidates": ranked[:6],
        "sample_rate": rate,
    }


def structure(audio: Decoded) -> dict:
    duration = audio.samples.shape[0] / audio.sample_rate
    if audio.sample_rate / 2 <= 40:
        raise ChartUnavailable("Sample rate is too low for the structure bands.")
    centers = np.arange(1.0, duration - 1.0, PARAMS["structure_bin_s"])
    if centers.size < 4:
        raise ChartUnavailable(
            "Structure estimates need at least four 2-second bins. This file is shorter."
        )
    mix = audio.samples.mean(axis=1)
    nperseg = _nperseg(mix.size, 2048)
    freqs, times, spectrum = signal.stft(
        mix,
        fs=audio.sample_rate,
        nperseg=nperseg,
        noverlap=nperseg // 2,
        boundary=None,
        padded=False,
    )
    power = np.maximum(np.abs(spectrum) ** 2, FLOOR)
    edges = np.geomspace(40, min(5500, audio.sample_rate / 2), 33)
    bands = []
    for lo, hi in itertools.pairwise(edges):
        selected = power[(freqs >= lo) & (freqs < hi)]
        bands.append(selected.mean(axis=0) if selected.size else np.full(times.shape, FLOOR))
    stacked = np.stack(bands)
    logs = []
    for center in centers:
        window = (times >= center - 1) & (times < center + 1)
        column = (
            stacked[:, window].mean(axis=1) if np.any(window) else np.full(stacked.shape[0], FLOOR)
        )
        logs.append(np.log10(np.maximum(column, FLOOR)))
    logs = np.array(logs)
    shape = logs - logs.mean(axis=1, keepdims=True)
    norm = shape / np.maximum(np.std(shape, axis=0, keepdims=True), 0.15)
    novelty = np.zeros(centers.shape[0])
    for index in range(3, centers.size - 3):
        later = norm[index : index + 3].mean(axis=0)
        earlier = norm[index - 3 : index].mean(axis=0)
        novelty[index] = float(np.linalg.norm(later - earlier) / math.sqrt(norm.shape[1]))
    transitions = []
    if centers.size >= 7:
        peaks, _ = signal.find_peaks(novelty, distance=2, prominence=0.05)
        order = sorted(peaks, key=lambda index: novelty[index], reverse=True)[:8]
        transitions = [finite(float(centers[index])) for index in sorted(order)]
    similarity = _cosine_rows(shape)
    return {
        "times": [finite(float(value)) for value in centers],
        "novelty": [finite(float(value)) for value in novelty],
        "transitions_s": transitions,
        "similarity": _decimate_matrix([finite(float(value)) for value in centers], similarity, 48),
    }


def _cosine_rows(features: np.ndarray) -> np.ndarray:
    centered = features - features.mean(axis=0)
    norms = np.linalg.norm(centered, axis=1, keepdims=True)
    scaled = centered / np.maximum(norms, 1e-12)
    matrix = scaled @ scaled.T
    return np.nan_to_num(matrix, nan=0.0, posinf=0.0, neginf=0.0)


def ending(audio: Decoded, peak: dict) -> dict:
    samples = audio.samples
    rate = audio.sample_rate
    duration = samples.shape[0] / rate

    def tail(ms: int) -> dict:
        count = max(1, int(rate * ms / 1000))
        piece = samples[-count:]
        local, _, _ = _peak_location(piece, rate)
        return {
            "last_ms": ms,
            "rms_dbfs": power_db(float(np.mean(piece**2))),
            "peak_dbfs": amp_db(local),
        }

    silence = _silence_intervals(audio)
    endpoint = [finite(float(value)) for value in samples[-1]]
    spans = [1000, 500, 100, 50]
    return {
        "duration_s": duration,
        "tails": [tail(ms) for ms in spans if ms / 1000 <= duration + 1e-9],
        "endpoint": endpoint,
        "endpoint_nonzero": any(abs(value) > 1e-6 for value in endpoint),
        "silence": silence,
        "rail_count": audio.rail_count,
        "rail_times_s": audio.rail_times_s,
        "oversampled_peak_dbtp": peak["dbtp"],
        "oversampled_peak_time_s": peak["time_s"],
        "oversampled_peak_channel": peak["channel"],
    }


def _silence_intervals(audio: Decoded) -> list[dict]:
    times, values = frame_power_db(audio.samples, audio.sample_rate, 0.05)
    if times.size == 0:
        return []
    quiet = values < PARAMS["silence_dbfs"]
    intervals = []
    start = None
    for index, flag in enumerate(quiet):
        if flag and start is None:
            start = index
        if not flag and start is not None:
            intervals.append(_interval(times, start, index))
            start = None
    if start is not None:
        intervals.append(_interval(times, start, len(times)))
    return intervals[:50]


def _interval(times: np.ndarray, start: int, end: int) -> dict:
    hop = float(times[1] - times[0]) if times.size > 1 else 0.05
    return {
        "start_s": finite(float(times[start]) - hop / 2),
        "end_s": finite(float(times[end - 1]) + hop / 2),
    }


def _decimate_1d(values: np.ndarray, limit: int) -> np.ndarray:
    if values.size <= limit:
        return values
    edges = np.linspace(0, values.size, limit + 1).astype(int)
    reduced = []
    for start, stop in itertools.pairwise(edges):
        if stop <= start:
            continue
        reduced.append(float(np.mean(values[start:stop])))
    return np.array(reduced)


def _decimate_2d(values: np.ndarray, rows: int, cols: int) -> np.ndarray:
    freq = _block_mean(values, rows, axis=0)
    return _block_mean(freq, cols, axis=1)


def _block_mean(values: np.ndarray, limit: int, axis: int) -> np.ndarray:
    count = values.shape[axis]
    if count <= limit:
        return values
    edges = np.linspace(0, count, limit + 1).astype(int)
    parts = []
    for start, stop in itertools.pairwise(edges):
        if stop <= start:
            continue
        sl = [slice(None), slice(None)]
        sl[axis] = slice(start, stop)
        parts.append(values[tuple(sl)].mean(axis=axis))
    return np.stack(parts, axis=axis)


def _decimate_matrix(times: list[float], matrix: np.ndarray, limit: int) -> dict:
    reduced = _decimate_2d(matrix, limit, limit)
    axis = _decimate_1d(np.array(times), reduced.shape[0])
    return {
        "x": [finite(float(value)) for value in axis],
        "y": [finite(float(value)) for value in axis],
        "z": [[finite(float(value)) for value in row] for row in reduced],
    }
