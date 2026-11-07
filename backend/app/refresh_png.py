"""Regenerate static chart PNGs from stored chart JSON.

Does not decode audio, rerun ``m1-v3``, or rewrite metrics. A dry run creates
no files. Start it explicitly:

    uv run python -m app.refresh_png --data-root PATH [--dry-run] [--sha256 HEX] [--kind T03]
"""

from __future__ import annotations

import argparse
import fcntl
import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from app.charts import KINDS
from app.measure import ALGORITHM_VERSION
from app.png import (
    RENDERER_VERSION,
    presentation_dir,
    presentation_png,
    publish_png,
    read_manifest,
    valid_png,
    write_manifest,
)


@dataclass(frozen=True)
class RefreshItem:
    sha256: str
    kind: str
    action: str
    detail: str = ""


def refresh_tree(
    data_root: Path,
    *,
    dry_run: bool = False,
    sha256: str | None = None,
    kinds: set[str] | None = None,
) -> list[RefreshItem]:
    root = data_root / "analysis"
    if not root.is_dir():
        return []
    items: list[RefreshItem] = []
    for sha_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        if sha256 and sha_dir.name != sha256:
            continue
        analysis = sha_dir / ALGORITHM_VERSION
        if not analysis.is_dir():
            continue
        items.extend(_refresh_one(sha_dir.name, analysis, dry_run=dry_run, kinds=kinds))
    return items


def _refresh_one(
    sha256: str,
    analysis: Path,
    *,
    dry_run: bool,
    kinds: set[str] | None,
) -> list[RefreshItem]:
    planned = _labeled(_plan(sha256, analysis, kinds), dry_run=dry_run)
    if dry_run or not any(item.action == "regenerate" for item in planned):
        return planned
    with _lock(presentation_dir(analysis)):
        planned = _plan(sha256, analysis, kinds)
        written: list[str] = []
        finished: list[RefreshItem] = []
        for item in planned:
            if item.action != "regenerate":
                finished.append(item)
                continue
            path = analysis / f"{item.kind}.json"
            before = path.read_bytes()
            document = json.loads(before)
            try:
                publish_png(presentation_png(analysis, item.kind), document)
            except Exception as exc:  # noqa: BLE001 - report and keep the previous image
                finished.append(RefreshItem(sha256, item.kind, "failed", type(exc).__name__))
                continue
            if path.read_bytes() != before:
                finished.append(RefreshItem(sha256, item.kind, "failed", "chart json changed"))
                continue
            written.append(item.kind)
            finished.append(RefreshItem(sha256, item.kind, "regenerated"))
        listed = [kind for kind in KINDS if _keep(kind, written, analysis)]
        write_manifest(analysis, listed, ALGORITHM_VERSION)
        return finished


def _labeled(items: list[RefreshItem], *, dry_run: bool) -> list[RefreshItem]:
    if not dry_run:
        return items
    return [
        RefreshItem(item.sha256, item.kind, "dry-run" if item.action == "regenerate" else item.action, item.detail)
        for item in items
    ]


def _keep(kind: str, written: list[str], analysis: Path) -> bool:
    if not valid_png(presentation_png(analysis, kind)):
        return False
    if kind in written:
        return True
    manifest = read_manifest(analysis)
    if manifest is None:
        return False
    return (
        manifest.get("renderer_version") == RENDERER_VERSION
        and manifest.get("algorithm_version") == ALGORITHM_VERSION
        and kind in (manifest.get("kinds") or [])
    )


def _plan(sha256: str, analysis: Path, kinds: set[str] | None) -> list[RefreshItem]:
    manifest = read_manifest(analysis)
    current = (
        manifest is not None
        and manifest.get("renderer_version") == "png-r1"
        and manifest.get("algorithm_version") == ALGORITHM_VERSION
    )
    items: list[RefreshItem] = []
    for kind in KINDS:
        if kinds and kind not in kinds:
            continue
        path = analysis / f"{kind}.json"
        if not path.is_file():
            items.append(RefreshItem(sha256, kind, "skipped", "missing json"))
            continue
        try:
            document = json.loads(path.read_text())
        except json.JSONDecodeError:
            items.append(RefreshItem(sha256, kind, "failed", "invalid json"))
            continue
        if not isinstance(document, dict) or document.get("status") != "ready":
            items.append(RefreshItem(sha256, kind, "skipped", "not ready"))
            continue
        png = presentation_png(analysis, kind)
        if current and manifest is not None and kind in manifest.get("kinds", []) and valid_png(png):
            items.append(RefreshItem(sha256, kind, "skipped", "current"))
            continue
        items.append(RefreshItem(sha256, kind, "regenerate"))
    return items


@contextmanager
def _lock(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    handle = (directory / ".refresh.lock").open("a+")
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Regenerate chart PNGs from stored chart JSON.")
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--sha256")
    parser.add_argument("--kind", action="append", dest="kinds")
    args = parser.parse_args(argv)
    selected = set(args.kinds) if args.kinds else None
    items = refresh_tree(args.data_root, dry_run=args.dry_run, sha256=args.sha256, kinds=selected)
    failed = 0
    for item in items:
        detail = f" {item.detail}" if item.detail else ""
        action = "dry-run" if args.dry_run and item.action == "regenerate" else item.action
        print(f"{action} {item.sha256} {item.kind}{detail}")
        if item.action == "failed":
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
