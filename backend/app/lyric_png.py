"""Lyric-png-v1 drawings of existing L01–L05 documents.

This module does not draw T01–T10 and does not read audio.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from app.png import (
    AXIS,
    ENERGY,
    HEATMAP,
    INK,
    LUFS_COLOR,
    REVIEW,
    _style_axis,
    _style_figure,
    valid_png,
)

LYRIC_RENDERER_VERSION = "lyric-png-v1"


def write_lyric_png(path: Path, document: dict) -> None:
    figure = render_lyric_figure(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.tmp.png")
    try:
        figure.savefig(temporary, facecolor=figure.get_facecolor())
        if not valid_png(temporary):
            raise RuntimeError("lyric PNG validation failed")
        os.replace(temporary, path)
    finally:
        plt.close(figure)
        if temporary.exists():
            temporary.unlink()


def render_lyric_figure(document: dict):
    if document.get("status") != "ready":
        return _caption(document)
    kind = document.get("chart_kind")
    if kind == "L01":
        return _timeline(document, "Full-mix level and lyric intervals are separate.")
    if kind == "L02":
        return _density(document)
    if kind == "L03":
        return _energy(document)
    if kind == "L04":
        return _repetition(document)
    if kind == "L05":
        return _principles(document)
    return _caption(document)


def _caption(document: dict):
    figure = plt.figure(figsize=(10, 5.8), dpi=120)
    _style_figure(figure)
    reason = document.get("not_available_reason") or document.get("error") or "No chart data."
    figure.text(0.5, 0.62, _heading(document), ha="center", va="center", color=INK, fontsize=14)
    figure.text(
        0.5,
        0.48,
        f"Status: {document.get('status')}",
        ha="center",
        va="center",
        color=AXIS,
        fontsize=11,
    )
    figure.text(0.08, 0.28, str(reason), ha="left", va="center", color=INK, fontsize=10, wrap=True)
    figure.text(
        0.5,
        0.1,
        "No series was invented for this figure.",
        ha="center",
        color=AXIS,
        fontsize=9,
    )
    return figure


def _timeline(document: dict, note: str):
    figure, axis = plt.subplots(figsize=(10, 5.8), dpi=120)
    _style_figure(figure)
    _style_axis(axis)
    _lines(axis, document)
    _regions(axis, document)
    _markers(axis, document)
    _legend(axis)
    axis.set_xlabel(document.get("axis_definitions", {}).get("x") or "Time (s)")
    axis.set_ylabel("Full-mix level")
    _note(figure, document, note)
    figure.tight_layout()
    return figure


def _density(document: dict):
    figure, axis = plt.subplots(figsize=(10, 5.8), dpi=120)
    _style_figure(figure)
    _style_axis(axis)
    bars = (document.get("series") or {}).get("bars") or []
    labels = [str(bar.get("label")) for bar in bars]
    values = [float(bar.get("value") or 0) for bar in bars]
    axis.bar(labels, values, color=ENERGY, label="Written word count")
    axis.set_ylabel("Written words")
    axis.set_xlabel("Line")
    line = _named((document.get("series") or {}).get("lines") or [], "Written words per second")
    if line is not None:
        twin = axis.twinx()
        _style_axis(twin)
        xs, ys = _present(line)
        twin.plot(xs, ys, color=REVIEW, marker="o", label="Timed written-word rate")
        twin.set_ylabel("Written words/s")
        _legend(axis, twin)
    else:
        _legend(axis)
    _note(
        figure,
        document,
        "Written word counts are not singing. The rate uses the written interval only.",
    )
    figure.tight_layout()
    return figure


def _energy(document: dict):
    bars = (document.get("series") or {}).get("bars") or []
    figure, axes = plt.subplots(2 if bars else 1, 1, figsize=(10, 7.2 if bars else 5.8), dpi=120)
    _style_figure(figure)
    axis = axes[0] if bars else axes
    _style_axis(axis)
    _lines(axis, document)
    regions = document.get("regions") or []
    if regions:
        _regions(axis, document)
        note = "Lines are full-mix measurements. Spans are lyric intervals, not vocal intensity."
    else:
        note = "No lyric intervals. Showing stored full-mix energy only."
    _legend(axis)
    axis.set_xlabel(document.get("axis_definitions", {}).get("x") or "Time (s)")
    axis.set_ylabel("Full-mix level")
    if bars:
        bars_axis = axes[1]
        _style_axis(bars_axis)
        bars_axis.bar(
            [str(bar.get("label")) for bar in bars],
            [float(bar.get("value") or 0) for bar in bars],
            color=LUFS_COLOR,
            label="Stored full-mix window",
        )
        bars_axis.set_ylabel("Full-mix window value")
        _legend(bars_axis)
    _note(figure, document, note)
    figure.tight_layout()
    return figure


def _repetition(document: dict):
    figure, axes = plt.subplots(2, 1, figsize=(10, 7.2), dpi=120)
    _style_figure(figure)
    heat_axis, text_axis = axes
    _style_axis(heat_axis)
    heat = (document.get("series") or {}).get("heatmap") or {}
    grid = np.asarray(heat.get("z") or [], dtype=float)
    if grid.ndim == 2 and grid.size:
        heat_axis.imshow(grid, origin="lower", aspect="auto", cmap=HEATMAP, interpolation="nearest")
        heat_axis.set_title("Spectral similarity. Not textual repetition.", color=INK, fontsize=11)
    else:
        heat_axis.set_axis_off()
        heat_axis.text(0.5, 0.5, "Spectral similarity is unavailable.", ha="center", color=INK)
    text_axis.set_axis_off()
    rows = document.get("rows") or []
    if rows:
        body = ["Textual repetition (written lines, not spectral similarity):"]
        for row in rows[:12]:
            body.append(f"{row.get('name')}: {row.get('value')}  {row.get('evidence_id')}")
    else:
        body = ["Textual repetition is unavailable."]
    text_axis.text(0.01, 0.95, "\n".join(body), va="top", color=INK, fontsize=9, family="monospace")
    _note(figure, document, "A bright spectral cell is not a repeated lyric line.")
    figure.tight_layout()
    return figure


def _principles(document: dict):
    figure = plt.figure(figsize=(10, 11), dpi=120)
    _style_figure(figure)
    blocks = [_heading(document), ""]
    findings = [row for row in document.get("rows") or [] if row.get("kind") == "finding"]
    principles = [row for row in document.get("rows") or [] if row.get("kind") == "principle"]
    blocks.append("Findings")
    blocks.extend(_row_lines(findings) or ["None stored in this chart."])
    blocks.append("")
    blocks.append("Transferable principles")
    blocks.extend(_row_lines(principles) or ["None met the lyrics-v1 gate."])
    blocks.append("")
    blocks.append("Insufficient evidence")
    insufficient = document.get("insufficient") or []
    if insufficient:
        for item in insufficient:
            cites = ", ".join(item.get("cites") or [])
            suffix = f" ({cites})" if cites else ""
            blocks.append(f"{item.get('code')}: {item.get('reason')}{suffix}")
    else:
        blocks.append("None.")
    wrapped = []
    for line in blocks:
        wrapped.extend(textwrap.wrap(line, width=96) or [""])
    figure.text(
        0.04,
        0.96,
        "\n".join(wrapped[:56]),
        va="top",
        ha="left",
        color=INK,
        fontsize=8,
        family="monospace",
    )
    return figure


def _lines(axis, document: dict) -> None:
    for line in (document.get("series") or {}).get("lines") or []:
        xs, ys = _present(line)
        if not xs:
            continue
        axis.plot(xs, ys, label=f"Full mix: {line.get('name')}", linewidth=1.4)


def _legend(*axes) -> None:
    handles = []
    labels = []
    for axis in axes:
        found, names = axis.get_legend_handles_labels()
        handles.extend(found)
        labels.extend(names)
    if labels:
        axes[0].legend(
            handles,
            labels,
            facecolor="#1b1f26",
            edgecolor="#3a4150",
            labelcolor=INK,
            fontsize=8,
        )


def _regions(axis, document: dict) -> None:
    labeled = False
    for region in document.get("regions") or []:
        start = region.get("start_s")
        end = region.get("end_s")
        if start is None or end is None:
            continue
        axis.axvspan(
            float(start),
            float(end),
            color=REVIEW,
            alpha=0.25,
            label="Lyric interval" if not labeled else None,
        )
        labeled = True


def _markers(axis, document: dict) -> None:
    labeled = False
    for marker in document.get("review_markers") or []:
        if marker.get("time_s") is None:
            continue
        axis.axvline(
            float(marker["time_s"]),
            color=AXIS,
            linewidth=0.8,
            label="Provisional change" if not labeled else None,
        )
        labeled = True


def _present(line: dict) -> tuple[list[float], list[float]]:
    xs: list[float] = []
    ys: list[float] = []
    for x_value, y_value in zip(line.get("x") or [], line.get("y") or [], strict=False):
        if y_value is None:
            continue
        xs.append(float(x_value))
        ys.append(float(y_value))
    return xs, ys


def _named(lines: list[dict], name: str) -> dict | None:
    for line in lines:
        if line.get("name") == name:
            return line
    return None


def _heading(document: dict) -> str:
    return f"{document.get('chart_kind')} {document.get('title') or ''}".strip()


def _note(figure, document: dict, note: str) -> None:
    figure.suptitle(f"{_heading(document)}\n{note}", color=INK, fontsize=11)


def _row_lines(rows: list[dict]) -> list[str]:
    written = []
    for row in rows[:16]:
        cites = ", ".join(row.get("cites") or [])
        cite = f" cites {cites}" if cites else ""
        value = row.get("value") or ""
        written.append(f"{row.get('evidence_id')}: {row.get('name')} {value}{cite}".strip())
    return written
