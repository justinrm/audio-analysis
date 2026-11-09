"""Lyric figure drawings of existing L01–L05 documents.

Renderer identity is separate from analysis version ``m1-v3`` and from ``png-r1``.
This module does not draw T01–T10 and does not read audio.
``lyric-png-v1`` remains the renderer of already published ZIP snapshots.
"""

from __future__ import annotations

import itertools
import os
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter, MaxNLocator

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

LYRIC_RENDERER_VERSION = "lyric-png-v2"
L05_FINDING_CAP = 8
L05_PRINCIPLE_CAP = 6
L04_ROW_CAP = 8
_CLASS_ORDER = {
    "measured": 0,
    "estimated": 1,
    "textual": 2,
    "interpretive": 3,
    "unknown": 4,
    "not_applicable": 5,
}


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
        return _timeline(document)
    if kind == "L02":
        return _density(document)
    if kind == "L03":
        return _energy(document)
    if kind == "L04":
        return _repetition(document)
    if kind == "L05":
        return _principles(document)
    return _caption(document)


def l05_figure_text(document: dict) -> str:
    return _l05_body(document)


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


def _timeline(document: dict):
    regions = _usable_regions(document)
    figure = plt.figure(figsize=(10, 6.4 if regions else 5.8), dpi=120, layout="constrained")
    _style_figure(figure)
    if regions:
        grid = figure.add_gridspec(2, 1, height_ratios=[5, 1.1], hspace=0.16)
        axis = figure.add_subplot(grid[0])
        lane = figure.add_subplot(grid[1], sharex=axis)
    else:
        axis = figure.add_subplot(111)
        lane = None
    _style_axis(axis)
    _lines(axis, document, "Full-mix")
    _markers(axis, document)
    _legend(axis)
    axis.set_ylabel(document.get("axis_definitions", {}).get("y") or "dBFS")
    note = (
        "The curve is stored full-mix level. Lyric timing is not measured from the audio. "
        "Provisional lines are spectral-change candidates, not verified song sections."
    )
    if lane is None:
        axis.set_xlabel(document.get("axis_definitions", {}).get("x") or "Time (s)")
    else:
        axis.tick_params(labelbottom=False)
        _interval_lane(lane, regions)
    _time_formatter(axis)
    _note(figure, document, note)
    _reserve_title(figure)
    return figure


def _density(document: dict):
    figure, axis = plt.subplots(figsize=(10, 5.8), dpi=120)
    _style_figure(figure)
    _style_axis(axis)
    bars = (document.get("series") or {}).get("bars") or []
    positions = [_bar_position(bar, index) for index, bar in enumerate(bars)]
    values = [float(bar.get("value") or 0) for bar in bars]
    if positions:
        axis.bar(positions, values, width=0.72, color=ENERGY, label="Written word count")
        ticks = _sparse_positions(len(positions))
        axis.set_xticks([positions[index] for index in ticks])
        axis.set_xticklabels([_bar_tick(bars[index], positions[index]) for index in ticks])
        axis.set_xlim(min(positions) - 0.6, max(positions) + 0.6)
    axis.set_ylabel("Written words")
    axis.set_xlabel("Line number")
    line = _named((document.get("series") or {}).get("lines") or [], "Written words per second")
    if line is not None:
        twin = axis.twinx()
        _style_axis(twin)
        xs, ys = _present(line)
        twin.plot(xs, ys, color=REVIEW, marker="o", linewidth=1.2, label="Timed written-word rate")
        twin.set_ylabel("Written words/s")
        _legend(axis, twin)
    else:
        _legend(axis)
    _note(
        figure,
        document,
        "Bars are written word counts. The line is the timed written-word rate where timing is usable. "
        "Written density does not measure vocal delivery or breaths.",
    )
    figure.tight_layout(rect=(0, 0, 1, 0.86))
    return figure


def _energy(document: dict):
    lines = (document.get("series") or {}).get("lines") or []
    groups = _level_groups(lines)
    regions = _usable_regions(document)
    bars = (document.get("series") or {}).get("bars") or []
    plan = _energy_plan(groups, regions, bars)
    figure = plt.figure(figsize=(10, 2.6 * len(plan) + 1.1), dpi=120, layout="constrained")
    _style_figure(figure)
    ratios = [1.15 if group["key"] == "lane" else 3.1 for group in plan]
    grid = figure.add_gridspec(len(plan), 1, height_ratios=ratios, hspace=0.28)
    time_indexes = [index for index, group in enumerate(plan) if group["key"] != "bars"]
    last_time = time_indexes[-1] if time_indexes else None
    share = None
    for index, group in enumerate(plan):
        axis = figure.add_subplot(grid[index], sharex=None if group["key"] == "bars" else share)
        if share is None and group["key"] != "bars":
            share = axis
        _style_axis(axis)
        if group["key"] == "lane":
            _interval_lane(axis, regions)
            continue
        if group["key"] == "bars":
            axis.bar(
                [str(bar.get("label")) for bar in bars],
                [float(bar.get("value") or 0) for bar in bars],
                color=LUFS_COLOR,
                label="Stored full-mix window",
            )
            axis.set_ylabel("Stored full-mix window")
            _legend(axis)
            continue
        color = LUFS_COLOR if group["key"] == "LUFS" else ENERGY
        for line in group["lines"]:
            xs, ys = _present(line)
            if not xs:
                continue
            axis.plot(xs, ys, color=color, linewidth=1.4, label=str(line.get("name") or group["key"]))
        axis.set_ylabel(group["ylabel"])
        _legend(axis)
        _time_formatter(axis)
        if index != last_time or regions:
            axis.tick_params(labelbottom=False)
        if index == last_time and not regions:
            axis.set_xlabel(document.get("axis_definitions", {}).get("x") or "Time (s)")
    _note(
        figure,
        document,
        "dBFS and LUFS stay on separate axes. Both are stored full-mix measurements, not vocal intensity.",
    )
    _reserve_title(figure)
    return figure


def _repetition(document: dict):
    figure, axes = plt.subplots(2, 1, figsize=(10, 7.6), dpi=120, height_ratios=[3.2, 1.6])
    _style_figure(figure)
    heat_axis, text_axis = axes
    _style_axis(heat_axis)
    heat = (document.get("series") or {}).get("heatmap") or {}
    grid = np.asarray(heat.get("z") or [], dtype=float)
    mapped = _draw_similarity(heat_axis, figure, grid, list(heat.get("x") or []), list(heat.get("y") or []))
    if not mapped:
        heat_axis.set_axis_off()
        heat_axis.text(
            0.5,
            0.5,
            "Spectral similarity is unavailable."
            if grid.size == 0
            else "Stored time coordinates do not match this matrix, so it is not drawn on a bin-index axis.",
            ha="center",
            va="center",
            color=INK,
            wrap=True,
        )
    text_axis.set_axis_off()
    text_axis.text(
        0.01,
        0.98,
        _repetition_copy(document),
        va="top",
        ha="left",
        color=INK,
        fontsize=9,
    )
    _note(
        figure,
        document,
        "Spectral similarity is not textual repetition, a melody, or a hook.",
    )
    figure.tight_layout(rect=(0, 0, 1, 0.90))
    return figure


def _principles(document: dict):
    figure = plt.figure(figsize=(10, 12.5), dpi=120)
    _style_figure(figure)
    body = l05_figure_text(document)
    figure.text(0.05, 0.97, body, va="top", ha="left", color=INK, fontsize=9)
    return figure


def _energy_plan(groups: list[dict], regions: list[dict], bars: list[dict]) -> list[dict]:
    plan = list(groups)
    if regions:
        plan.append({"key": "lane"})
    if bars:
        plan.append({"key": "bars"})
    if not plan:
        plan.append({"key": "other", "lines": [], "ylabel": "Stored value"})
    return plan


def _level_groups(lines: list[dict]) -> list[dict]:
    buckets: dict[str, list[dict]] = {"dBFS": [], "LUFS": [], "other": []}
    for line in lines:
        unit = str(line.get("unit") or "")
        name = str(line.get("name") or "")
        if unit == "LUFS" or "LUFS" in name:
            buckets["LUFS"].append(line)
        elif unit == "dBFS" or "RMS" in name:
            buckets["dBFS"].append(line)
        else:
            buckets["other"].append(line)
    labels = {
        "dBFS": "Full-mix RMS (dBFS)",
        "LUFS": "Short-term loudness (LUFS)",
        "other": "Stored full-mix value",
    }
    return [
        {"key": key, "lines": rows, "ylabel": labels[key]}
        for key, rows in buckets.items()
        if rows
    ]


def _draw_similarity(axis, figure, grid: np.ndarray, xs: list, ys: list) -> bool:
    if grid.ndim != 2 or grid.size == 0:
        return False
    rows, cols = grid.shape
    if len(xs) != cols or len(ys) != rows or not _increasing(xs) or not _increasing(ys):
        return False
    x_edges = _bin_edges([float(value) for value in xs])
    y_edges = _bin_edges([float(value) for value in ys])
    image = axis.pcolormesh(
        x_edges,
        y_edges,
        grid,
        cmap=HEATMAP,
        shading="flat",
    )
    colorbar = figure.colorbar(image, ax=axis, fraction=0.046)
    colorbar.set_label("Cosine similarity", color=INK)
    colorbar.ax.yaxis.set_tick_params(color=INK, labelcolor=INK)
    axis.set_title("Spectral similarity. Not textual repetition.", color=INK, fontsize=11)
    axis.set_xlim(x_edges[0], x_edges[-1])
    axis.set_ylim(y_edges[0], y_edges[-1])
    axis.set_xlabel("Time")
    axis.set_ylabel("Time")
    _time_formatter(axis, "x")
    _time_formatter(axis, "y")
    axis.xaxis.set_major_locator(MaxNLocator(nbins=6))
    axis.yaxis.set_major_locator(MaxNLocator(nbins=6))
    return True


def _bin_edges(centers: list[float]) -> list[float]:
    if len(centers) == 1:
        # ponytail: one center has no neighbor; ±1 s matches the 2 s structure bin.
        return [centers[0] - 1.0, centers[0] + 1.0]
    edges = [centers[0] - (centers[1] - centers[0]) / 2]
    for left, right in itertools.pairwise(centers):
        edges.append((left + right) / 2)
    edges.append(centers[-1] + (centers[-1] - centers[-2]) / 2)
    return edges


def _increasing(values: list) -> bool:
    numbers = [float(value) for value in values]
    return all(numbers[index] < numbers[index + 1] for index in range(len(numbers) - 1))


def _interval_lane(axis, regions: list[dict]) -> None:
    _style_axis(axis)
    axis.grid(False)
    starts = [float(region["start_s"]) for region in regions]
    widths = [float(region["end_s"]) - float(region["start_s"]) for region in regions]
    axis.barh([0.5] * len(widths), widths, left=starts, height=0.55, color=REVIEW, alpha=0.55, linewidth=0)
    axis.set_ylim(0, 1)
    axis.set_yticks([])
    axis.set_ylabel("Lyric intervals")
    axis.set_xlabel("Time")
    _time_formatter(axis)


def _usable_regions(document: dict) -> list[dict]:
    regions = []
    for region in document.get("regions") or []:
        start = region.get("start_s")
        end = region.get("end_s")
        if start is None or end is None:
            continue
        if not (float(end) > float(start)):
            continue
        regions.append(region)
    return regions


def _lines(axis, document: dict, prefix: str) -> None:
    for line in (document.get("series") or {}).get("lines") or []:
        xs, ys = _present(line)
        if not xs:
            continue
        axis.plot(xs, ys, label=f"{prefix}: {line.get('name')}", linewidth=1.4)


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
    wrapped = textwrap.fill(note, width=92)
    figure.suptitle(f"{_heading(document)}\n{wrapped}", color=INK, fontsize=11)


def _reserve_title(figure) -> None:
    engine = figure.get_layout_engine()
    if engine is not None:
        engine.set(rect=(0, 0, 1, 0.88))


def _bar_position(bar: dict, index: int) -> float:
    try:
        return float(bar.get("label"))
    except (TypeError, ValueError):
        return float(index + 1)


def _bar_tick(bar: dict, position: float) -> str:
    label = bar.get("label")
    if label is not None and str(label).strip():
        return str(label)
    if float(position).is_integer():
        return str(int(position))
    return str(position)


def _sparse_positions(count: int, budget: int = 8) -> list[int]:
    if count <= 0:
        return []
    if count <= budget:
        return list(range(count))
    last = count - 1
    indexes = {0, last}
    for step in range(1, budget - 1):
        indexes.add(round(last * step / (budget - 1)))
    return sorted(indexes)


def _clock(seconds: float) -> str:
    sign = "-" if seconds < 0 else ""
    total = abs(float(seconds))
    minutes, secs = divmod(round(total), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{sign}{hours}:{minutes:02d}:{secs:02d}"
    return f"{sign}{minutes}:{secs:02d}"


def _time_formatter(axis, which: str = "x") -> None:
    formatter = FuncFormatter(lambda value, _position: _clock(value))
    target = axis.xaxis if which == "x" else axis.yaxis
    target.set_major_formatter(formatter)


def _repetition_copy(document: dict) -> str:
    rows = list(document.get("rows") or [])
    shown = rows[:L04_ROW_CAP]
    lines = [
        "Textual repetition uses written lines. It is not the spectral-similarity matrix.",
        (
            f"Showing {len(shown)} of {len(rows)} written-repetition rows, "
            "the first rows in stored order. Complete rows are in L04.json."
        ),
    ]
    if not rows:
        lines.append("Textual repetition is unavailable.")
    for row in shown:
        lines.append(f"{row.get('name')}: {row.get('value')}  {row.get('evidence_id')}")
    return "\n".join(lines)


def _l05_body(document: dict) -> str:
    findings = [row for row in document.get("rows") or [] if row.get("kind") == "finding"]
    principles = [row for row in document.get("rows") or [] if row.get("kind") == "principle"]
    summary = [row for row in findings if not _line_evidence(str(row.get("evidence_id") or ""))]
    lines_only = [row for row in findings if _line_evidence(str(row.get("evidence_id") or ""))]
    ordered = sorted(summary, key=_finding_rank)
    shown = ordered[:L05_FINDING_CAP]
    principle_rows = sorted(principles, key=lambda row: str(row.get("evidence_id") or ""))
    shown_principles = principle_rows[:L05_PRINCIPLE_CAP]
    blocks = [
        _heading(document),
        "",
        (
            f"Showing {len(shown)} of {len(findings)} findings. "
            "Rule: summary records other than individual lyric lines, "
            f"at most {L05_FINDING_CAP}, ordered by evidence class then evidence id. "
            f"{len(lines_only)} lyric-line records stay in lyricist/charts/L05.json and are not printed here."
        ),
        "",
        "Findings",
    ]
    if shown:
        blocks.extend(_plain_row(row) for row in shown)
    else:
        blocks.append("No summary finding is stored on this chart.")
    blocks.extend(["", "Transferable principles"])
    blocks.append(
        f"Showing {len(shown_principles)} of {len(principle_rows)} principles, "
        f"the first {L05_PRINCIPLE_CAP} in evidence-id order. "
        "These rows are interpretive. Complete principles are in L05.json."
    )
    if shown_principles:
        blocks.extend(_plain_row(row) for row in shown_principles)
    else:
        blocks.append("None met the lyrics-v1 gate.")
    blocks.extend(["", "What this chart cannot determine"])
    insufficient = document.get("insufficient") or []
    if insufficient:
        for item in insufficient:
            cites = ", ".join(item.get("cites") or [])
            suffix = f" Citations: {cites}." if cites else ""
            blocks.append(f"{item.get('code')}: {item.get('reason')}{suffix}")
    else:
        blocks.append("No insufficient-evidence rows were stored.")
    blocks.extend(["", "References"])
    references = [str(row.get("evidence_id")) for row in [*shown, *shown_principles] if row.get("evidence_id")]
    blocks.append(", ".join(references) if references else "None on this figure.")
    blocks.append("Evidence classes name how a value was obtained. They are not listening impressions.")
    wrapped: list[str] = []
    for line in blocks:
        wrapped.extend(textwrap.wrap(line, width=92) or [""])
    return "\n".join(wrapped)


def _line_evidence(evidence_id: str) -> bool:
    if not evidence_id.startswith("ly:"):
        return False
    return not evidence_id.startswith(("ly:density", "ly:level:", "ly:lufs:", "ly:repeat:", "ly:principle:"))


def _finding_rank(row: dict) -> tuple[int, str]:
    klass = str(row.get("evidence_class") or "unknown")
    return (_CLASS_ORDER.get(klass, 9), str(row.get("evidence_id") or ""))


def _plain_row(row: dict) -> str:
    value = str(row.get("value") or "").strip()
    unit = str(row.get("unit") or "").strip()
    if value and unit and unit not in value:
        shown = f"{value} {unit}"
    else:
        shown = value or "stored"
    cites = ", ".join(row.get("cites") or [])
    cite = f" Cites {cites}." if cites else ""
    caveat = str(row.get("caveat") or "").strip()
    caveat_bit = f" {caveat}" if caveat else ""
    name = row.get("name") or "Finding"
    klass = row.get("evidence_class") or "unknown"
    return f"{name}: {shown}. Evidence class {klass}.{cite}{caveat_bit}"
