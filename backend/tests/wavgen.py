import struct
from pathlib import Path


def write_wav(path: Path, fmt: bytes, data: bytes) -> None:
    fmt_chunk = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    if len(fmt) % 2:
        fmt_chunk += b"\x00"
    data_chunk = b"data" + struct.pack("<I", len(data)) + bytes(data)
    body = b"WAVE" + fmt_chunk + data_chunk
    path.write_bytes(b"RIFF" + struct.pack("<I", len(body)) + body)


def pcm_wav(path: Path, samples: list[int], rate: int, channels: int, bits: int) -> None:
    width = bits // 8
    data = bytearray()
    for sample in samples:
        data += int(sample).to_bytes(width, "little", signed=True)
    block = channels * width
    fmt = struct.pack("<HHIIHH", 1, channels, rate, rate * block, block, bits)
    write_wav(path, fmt, data)


def float_wav(path: Path) -> None:
    data = struct.pack("<f", 0.25)
    fmt = struct.pack("<HHIIHH", 3, 1, 8000, 32000, 4, 32)
    write_wav(path, fmt, data)
