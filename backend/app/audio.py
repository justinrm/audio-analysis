from __future__ import annotations

import math
import os
import struct
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path

CONVERSION_VERSION = "pcm_s16le-triangular-v1"
PEAK_METHOD = "playback_minmax_envelope_v1"
_PCM_GUID = bytes.fromhex("0100000000001000800000aa00389b71")
_FLOAT_GUID = bytes.fromhex("0300000000001000800000aa00389b71")


class WavRejected(ValueError):
    pass


@dataclass(frozen=True)
class WavInfo:
    subtype: str
    sample_rate: int
    channels: int
    duration_s: float
    data_bytes: int


def probe_wav(path: Path) -> WavInfo:
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        file_size = handle.tell()
        handle.seek(0)
        header = handle.read(12)
        if len(header) < 12 or header[0:4] != b"RIFF" or header[8:12] != b"WAVE":
            raise WavRejected("Not a WAV file.")
        fmt: bytes | None = None
        data_bytes: int | None = None
        data_pos: int | None = None
        while True:
            chunk_header = handle.read(8)
            if not chunk_header:
                break
            if len(chunk_header) < 8:
                raise WavRejected("Truncated WAV chunk header.")
            chunk_id, size = struct.unpack("<4sI", chunk_header)
            start = handle.tell()
            if start + size > file_size:
                raise WavRejected("WAV data is truncated.")
            if chunk_id == b"fmt ":
                fmt = handle.read(size)
            elif chunk_id == b"data" and data_bytes is None:
                data_bytes = size
                data_pos = start
                handle.seek(size, os.SEEK_CUR)
            else:
                handle.seek(size, os.SEEK_CUR)
            if size % 2 == 1:
                handle.seek(1, os.SEEK_CUR)
        if fmt is None:
            raise WavRejected("WAV file is missing a format chunk.")
        if data_bytes is None or data_pos is None:
            raise WavRejected("WAV file is missing audio data.")
        if data_pos + data_bytes > file_size:
            raise WavRejected("WAV data is truncated.")
        if len(fmt) < 16:
            raise WavRejected("WAV format chunk is too short.")
        audio_format, channels, rate, _byte_rate, block_align, bits = struct.unpack(
            "<HHIIHH", fmt[:16]
        )
        if channels < 1 or rate < 1 or block_align < 1:
            raise WavRejected("WAV file has an invalid channel count or sample rate.")
        subtype, bits = _classify(audio_format, bits, fmt)
        if block_align != channels * (bits // 8):
            raise WavRejected(
                f"WAV block alignment {block_align} does not match {bits}-bit PCM "
                f"with {channels} channel(s)."
            )
        if data_bytes % block_align != 0:
            raise WavRejected("WAV data chunk is not a whole number of frames.")
        frames = data_bytes // block_align
        if frames < 1:
            raise WavRejected("WAV file has no audio frames.")
        return WavInfo(subtype, rate, channels, frames / rate, data_bytes)


def _classify(audio_format: int, bits: int, fmt: bytes) -> tuple[str, int]:
    guid = fmt[24:40] if len(fmt) >= 40 else b""
    if audio_format == 3 or guid == _FLOAT_GUID:
        raise WavRejected("32-bit float WAV is not accepted. Export 16-bit or 24-bit integer PCM.")
    if audio_format == 0xFFFE:
        if guid != _PCM_GUID:
            raise WavRejected("Unsupported WAV subtype. Export 16-bit or 24-bit integer PCM.")
        if len(fmt) < 40:
            raise WavRejected("Invalid extensible WAV format chunk.")
        valid_bits = struct.unpack_from("<H", fmt, 18)[0]
        if bits not in (16, 24) or valid_bits not in (16, 24):
            raise WavRejected(
                f"{bits}-bit WAV (valid bits {valid_bits}) is not accepted. "
                "Export 16-bit or 24-bit integer PCM."
            )
        bits = valid_bits
    elif audio_format != 1:
        raise WavRejected(
            f"WAV format code {audio_format} is not accepted. Export 16-bit or 24-bit integer PCM."
        )
    if bits == 16:
        return "pcm_16", 16
    if bits == 24:
        return "pcm_24", 24
    raise WavRejected(f"{bits}-bit PCM is not accepted. Export 16-bit or 24-bit integer PCM.")


def blob_path(data_root: Path, sha256: str) -> Path:
    if len(sha256) != 64 or any(c not in "0123456789abcdef" for c in sha256):
        raise ValueError("asset hash is not a sha256 hex digest")
    return data_root / "blobs" / sha256


def derivative_path(data_root: Path, sha256: str) -> Path:
    return data_root / "derivatives" / sha256 / f"{CONVERSION_VERSION}.wav"


def peaks_path(data_root: Path, sha256: str, kind: str) -> Path:
    return data_root / "peaks" / sha256 / f"{kind}-{PEAK_METHOD}.json"


def write_pcm16_derivative(source: Path, dest: Path, info: WavInfo) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_suffix(".partial.wav")
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:a:0",
        "-vn",
        "-af",
        f"aresample=osr={info.sample_rate}:osf=s16:dither_method=triangular",
        "-c:a",
        "pcm_s16le",
        str(partial),
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        partial.unlink(missing_ok=True)
        raise RuntimeError("ffmpeg could not write a playback derivative") from exc
    if proc.returncode != 0:
        partial.unlink(missing_ok=True)
        detail = (proc.stderr or "").strip() or "ffmpeg failed"
        raise RuntimeError(detail)
    try:
        out = probe_wav(partial)
    except WavRejected as exc:
        partial.unlink(missing_ok=True)
        raise RuntimeError("ffmpeg did not write a PCM WAV") from exc
    same_shape = (
        out.subtype == "pcm_16"
        and out.sample_rate == info.sample_rate
        and out.channels == info.channels
        and abs(out.duration_s - info.duration_s) <= (1 / info.sample_rate)
    )
    if not same_shape:
        partial.unlink(missing_ok=True)
        raise RuntimeError("Playback derivative does not preserve rate, channels, or duration.")
    os.replace(partial, dest)


def playback_file(data_root: Path, sha256: str, subtype: str, playback_status: str) -> Path | None:
    if playback_status != "ready":
        return None
    path = (
        blob_path(data_root, sha256) if subtype == "pcm_16" else derivative_path(data_root, sha256)
    )
    if path.is_file():
        return path
    return None


def bucket_count(nframes: int) -> int:
    return max(1, min(1000, nframes))


def compute_peaks(path: Path) -> dict:
    """Min/max envelope from a chunked read of a 16-bit playback WAV."""
    with wave.open(str(path), "rb") as handle:
        if handle.getsampwidth() != 2:
            raise WavRejected("Peaks are computed from the 16-bit playback file only.")
        channels = handle.getnchannels()
        rate = handle.getframerate()
        nframes = handle.getnframes()
        if channels < 1 or rate < 1 or nframes < 1:
            raise WavRejected("Playback file has no audio frames.")
        count = bucket_count(nframes)
        mins = [math.inf] * count
        maxs = [-math.inf] * count
        frame_index = 0
        while frame_index < nframes:
            raw = handle.readframes(8192)
            if not raw:
                break
            frame_bytes = 2 * channels
            got = len(raw) // frame_bytes
            for index in range(got):
                bucket = min(count - 1, (frame_index + index) * count // nframes)
                base = index * frame_bytes
                for channel in range(channels):
                    offset = base + channel * 2
                    sample = int.from_bytes(raw[offset : offset + 2], "little", signed=True)
                    value = sample / 32768.0
                    mins[bucket] = min(mins[bucket], value)
                    maxs[bucket] = max(maxs[bucket], value)
            frame_index += got
        buckets = []
        for low, high in zip(mins, maxs, strict=True):
            if not math.isfinite(low) or not math.isfinite(high):
                raise WavRejected("Peak envelope contained a non-finite sample.")
            buckets.append({"min": low, "max": high})
        return {
            "duration_s": nframes / rate,
            "sample_rate": rate,
            "channels": channels,
            "method_id": PEAK_METHOD,
            "buckets": buckets,
        }


def ffmpeg_version() -> str:
    try:
        proc = subprocess.run(
            ["ffmpeg", "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unavailable"
    parts = proc.stdout.splitlines()[0].split() if proc.stdout else []
    if len(parts) >= 3 and parts[0] == "ffmpeg" and parts[1] == "version":
        return parts[2]
    return "unavailable"
