from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _load_env_file() -> None:
    """Fill unset variables from a local .env. Does not override the environment."""
    roots = [Path.cwd(), Path(__file__).resolve().parents[2]]
    seen: set[Path] = set()
    for root in roots:
        path = root / ".env"
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        for line in path.read_text().splitlines():
            text = line.strip()
            if not text or text.startswith("#") or "=" not in text:
                continue
            key, value = text.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))


@dataclass(frozen=True)
class Settings:
    data_root: Path
    max_bytes: int
    max_duration_s: float
    cors_origin: str

    @property
    def database_path(self) -> Path:
        return self.data_root / "studio.sqlite3"


def load_settings() -> Settings:
    _load_env_file()
    default_root = Path.home() / "Library" / "Application Support" / "AudioReferenceStudio"
    raw_root = os.environ.get("ARS_DATA_ROOT", "").strip()
    data_root = Path(raw_root).expanduser() if raw_root else default_root
    return Settings(
        data_root=data_root,
        max_bytes=int(os.environ.get("ARS_MAX_BYTES", str(500 * 1024 * 1024))),
        max_duration_s=float(os.environ.get("ARS_MAX_DURATION_S", "900")),
        cors_origin=os.environ.get("ARS_CORS_ORIGIN", "http://127.0.0.1:5173").strip(),
    )
