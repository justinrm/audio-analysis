"""PNG drawings of stored chart documents. Headless; no display.

Renderer identity is separate from analysis version ``m1-v3``. ``png-r2`` draws
a stored bar series on its own panel when a line series is also present.
``png-r1`` files are left in place. T03 displays the stored positive-Hz samples
on a log frequency axis. The chart JSON, including ``y_scale`` and the ``dB``
unit, is not modified.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.ticker import FuncFormatter

RENDERER_VERSION = "png-r2"
GROUND = "#14171c"
PANEL = "#1b1f26"
INK = "#e8e6e1"
ENERGY = "#8eb4d4"
LUFS_COLOR = "#c5d4c0"
ESTIMATED = "#c5d0dc"
REVIEW = "#c4a36a"
AXIS = "#a8b0ba"
HEATMAP = LinearSegmentedColormap.from_list("pass3", ["#4c6680", "#8eb4d4", "#e6e0d4"])

_EVIDENCE = {
    "measured": "Measured",
    "estimated": "Estimated",
    "textual": "Textual",
    "interpretive": "Interpretive",
    "unknown": "Unknown",
    "not_applicable": "Not applicable",
}


def format_file_time(seconds: float) -> str:
    if math.isnan(seconds):
        return ""
    absolute = abs(float(seconds))
    if abs(absolute - round(absolute)) <= 0.049:
        whole = round(absolute)
        return f"{whole // 60}:{whole % 60:02d}"
    minutes = int(absolute // 60)
    remain = absolute - minutes * 60
    whole = int(remain)
    tenth = min(9, int((remain - whole) * 10))
    return f"{minutes}:{whole:02d}.{tenth}"


def format_frequency(hz: float) -> str:
    if math.isnan(hz):
        return ""
    absolute = abs(float(hz))
    sign = "-" if hz < 0 else ""
    if absolute >= 1000:
        khz = absolute / 1000
        text = str(int(khz)) if float(khz).is_integer() else f"{khz:.1f}".removesuffix(".0")
        return f"{sign}{text} kHz"
    return f"{sign}{round(absolute)} Hz"


def valid_png(path: Path) -> bool:
    if not path.is_file():
        return False
    data = path.read_bytes()
    return len(data) > 32 and data.startswith(b"\x89PNG\r\n\x1a\n") and b"IEND" in data[-32:]


def presentation_dir(analysis: Path) -> Path:
    return analysis / "presentation" / RENDERER_VERSION


def presentation_png(analysis: Path, kind: str) -> Path:
    return presentation_dir(analysis) / f"{kind}.png"


def read_manifest(analysis: Path) -> dict | None:
    path = presentation_dir(analysis) / "manifest.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def write_manifest(analysis: Path, kinds: list[str], algorithm_version: str) -> None:
    directory = presentation_dir(analysis)
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "renderer_version": RENDERER_VERSION,
        "algorithm_version": algorithm_version,
        "kinds": kinds,
    }
    temporary = directory / ".manifest.json.tmp"
    temporary.write_text(json.dumps(payload, indent=2) + "\n")
    os.replace(temporary, directory / "manifest.json")


def rendered_png(analysis: Path, kind: str, algorithm_version: str = "m1-v3") -> Path | None:
    manifest = read_manifest(analysis)
    if manifest is None:
        return None
    if manifest.get("renderer_version") != RENDERER_VERSION:
        return None
    if manifest.get("algorithm_version") != algorithm_version:
        return None
    if kind not in (manifest.get("kinds") or []):
        return None
    path = presentation_png(analysis, kind)
    if not valid_png(path):
        return None
    return path


def write_png(path: Path, document: dict) -> None:
    if document.get("status") != "ready":
        return
    figure = render_figure(document)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path)
    plt.close(figure)


def publish_png(path: Path, document: dict) -> None:
    """Write a validated PNG and replace the destination only after that succeeds."""
    if document.get("status") != "ready":
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.{os.getpid()}.tmp.png")
    try:
        write_png(temporary, document)
        if not valid_png(temporary):
            raise RuntimeError("PNG validation failed")
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def render_figure(document: dict):
    kind = document.get("chart_kind")
    series = document.get("series") or {}
    lines = series.get("lines") or []
    bars = series.get("bars") or []
    heat = series.get("heatmap") or {}
    if kind == "T04" and heat.get("z"):
        return _spectrogram(document, lines, heat)
    if kind == "T09" and heat.get("z"):
        return _matrix(document, heat)
    if kind == "T05":
        return _panels(
            document,
            [
                (_unit(lines, "ratio"), "Correlation", (-1.0, 1.0)),
                (_unit(lines, "dB"), "Side/mid (dB)", None),
            ],
        )
    if kind == "T02":
        return _panels(
            document,
            [
                (_unit(lines, "dBFS"), "dBFS", None),
                (_unit(lines, "LUFS"), "LUFS", None),
            ],
            bars,
        )
    if kind == "T11":
        return _panels(
            document,
            [
                (_unit(lines, "dBFS"), "dBFS", None),
                (_unit(lines, "LUFS"), "LUFS", None),
            ],
        )
    if _unit(lines, "amplitude") and _unit(lines, "dBFS"):
        return _panels(
            document,
            [
                (_unit(lines, "amplitude"), "Normalized amplitude", None),
                (_unit(lines, "dBFS"), "dBFS", None),
            ],
        )
    if kind == "T03":
        return _spectrum(document, lines, bars)
    if bars and lines and not heat.get("z"):
        return _panels(document, [(lines, _line_ylabel(document, lines), None)], bars)
    if bars and not lines and not heat.get("z"):
        return _bars(document, bars)
    return _lines(document, lines)


def _unit(lines: list, unit: str) -> list:
    return [line for line in lines if line.get("unit") == unit]


def _title(document: dict) -> str:
    word = _EVIDENCE.get(str(document.get("evidence_class")), "")
    title = str(document.get("title") or "")
    return f"{title} — {word}" if word else title


def _style_figure(figure) -> None:
    figure.patch.set_facecolor(GROUND)


def _style_axis(axis) -> None:
    axis.set_facecolor(PANEL)
    axis.tick_params(colors=INK, labelsize=8)
    for spine in axis.spines.values():
        spine.set_color("#3a4150")
    axis.xaxis.label.set_color(AXIS)
    axis.yaxis.label.set_color(AXIS)
    axis.title.set_color(INK)
    axis.grid(True, color="#2a3140", linewidth=0.4)


def _pairs(line: dict) -> tuple[list, list]:
    xs: list = []
    ys: list = []
    for x_value, y_value in zip(line["x"], line["y"], strict=True):
        if y_value is None:
            continue
        xs.append(x_value)
        ys.append(y_value)
    return xs, ys


def _paint(document: dict, line: dict, index: int) -> tuple[str, str]:
    unit = line.get("unit") or ""
    kind = document.get("chart_kind")
    if kind == "T11":
        palette = [INK, ENERGY, "#d7c4b0", "#a8b0ba"]
        return palette[index % len(palette)], "-"
    if unit == "LUFS":
        return LUFS_COLOR, "--"
    if unit == "ratio":
        return INK, "-"
    if kind == "T05" and unit == "dB":
        return ENERGY, "--"
    if unit == "amplitude":
        return INK, "-"
    if unit == "dBFS":
        return ENERGY, "-"
    if unit == "score" or document.get("evidence_class") == "estimated":
        return ESTIMATED, "--"
    palette = [INK, ENERGY, "#d7c4b0", "#a8b0ba"]
    return palette[index % len(palette)], "-" if index == 0 else "--"


def _plot_lines(axis, document: dict, lines: list) -> None:
    for index, line in enumerate(lines):
        xs, ys = _pairs(line)
        if not xs:
            continue
        color, style = _paint(document, line, index)
        axis.plot(xs, ys, color=color, linestyle=style, label=f"{line['name']} ({line.get('unit') or ''})")
    if lines:
        axis.legend(facecolor=PANEL, edgecolor="#3a4150", labelcolor=INK, fontsize=8)


def _mark_time(axis, document: dict) -> None:
    label = str((document.get("axis_definitions") or {}).get("x", ""))
    if not label.lower().startswith("time"):
        return
    markers = document.get("review_markers") or []
    for marker in markers:
        axis.axvline(marker["time_s"], color=REVIEW, linewidth=0.7, linestyle="--")


def _time_axis(axis, document: dict, which: str) -> None:
    name = str((document.get("axis_definitions") or {}).get(which, ""))
    if name.lower().startswith("time"):
        axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: format_file_time(value)))
        if which == "y":
            axis.yaxis.set_major_formatter(FuncFormatter(lambda value, _pos: format_file_time(value)))


def _line_ylabel(document: dict, lines: list) -> str:
    axis_def = document.get("axis_definitions") or {}
    ylabel = lines[0].get("unit") if lines else axis_def.get("y") or ""
    if ylabel == "score":
        return str(axis_def.get("y") or ylabel)
    return str(ylabel)


def _bar_ylabel(document: dict) -> str:
    kind = document.get("chart_kind")
    if kind == "T06":
        return "Autocorrelation"
    if kind == "T07":
        return "Share"
    return str((document.get("axis_definitions") or {}).get("y") or "")


def _panels(
    document: dict,
    groups: list[tuple[list, str, tuple[float, float] | None]],
    bars: list | None = None,
):
    present = [group for group in groups if group[0]]
    bar_items = list(bars or [])
    if not present:
        if bar_items:
            return _bars(document, bar_items)
        figure, axes = plt.subplots(figsize=(8.2, 3.6), dpi=100)
        _style_figure(figure)
        _style_axis(axes)
        axes.set_title(_title(document))
        return figure
    if not bar_items:
        figure, axes = plt.subplots(
            len(present),
            1,
            sharex=True,
            squeeze=False,
            figsize=(8.2, 2.5 * len(present)),
            dpi=100,
        )
        _style_figure(figure)
        for axis, (lines, ylabel, bounds) in zip(axes[:, 0], present, strict=True):
            _style_axis(axis)
            _plot_lines(axis, document, lines)
            _mark_time(axis, document)
            _time_axis(axis, document, "x")
            axis.set_ylabel(ylabel)
            if bounds is not None:
                axis.set_ylim(*bounds)
        axes[0, 0].set_title(_title(document))
        x_name = str((document.get("axis_definitions") or {}).get("x") or "")
        axes[-1, 0].set_xlabel(x_name)
        figure.tight_layout()
        return figure
    figure = plt.figure(figsize=(8.2, 2.5 * len(present) + 3.4), dpi=100)
    _style_figure(figure)
    grid = figure.add_gridspec(len(present) + 1, 1, height_ratios=[2.5] * len(present) + [3.4])
    share = None
    line_axes = []
    for index, (lines, ylabel, bounds) in enumerate(present):
        axis = figure.add_subplot(grid[index, 0], sharex=share)
        share = axis
        line_axes.append(axis)
        _style_axis(axis)
        _plot_lines(axis, document, lines)
        _mark_time(axis, document)
        _time_axis(axis, document, "x")
        axis.set_ylabel(ylabel)
        if bounds is not None:
            axis.set_ylim(*bounds)
    bar_axis = figure.add_subplot(grid[len(present), 0])
    _style_axis(bar_axis)
    _paint_bars(bar_axis, document, bar_items)
    line_axes[0].set_title(_title(document))
    x_name = str((document.get("axis_definitions") or {}).get("x") or "")
    line_axes[-1].set_xlabel(x_name)
    figure.tight_layout()
    return figure


def _paint_spectrum(axis, document: dict, lines: list) -> None:
    _style_axis(axis)
    _plot_lines(axis, document, lines)
    positive = [x for line in lines for x in line["x"] if x > 0]
    if positive:
        axis.set_xscale("log")
        axis.set_xlim(min(positive), max(positive))
    axis.xaxis.set_major_formatter(FuncFormatter(lambda value, _pos: format_frequency(value)))
    axis_def = document.get("axis_definitions") or {}
    axis.set_xlabel(axis_def.get("x") or "")
    axis.set_ylabel(lines[0].get("unit") if lines else "")
    axis.set_title(_title(document))


def _spectrum(document: dict, lines: list, bars: list | None = None):
    bar_items = list(bars or [])
    if not bar_items:
        figure, axis = plt.subplots(figsize=(8.2, 3.6), dpi=100)
        _style_figure(figure)
        _paint_spectrum(axis, document, lines)
        figure.tight_layout()
        return figure
    figure = plt.figure(figsize=(8.2, 7.0), dpi=100)
    _style_figure(figure)
    grid = figure.add_gridspec(2, 1, height_ratios=[3.6, 3.4])
    _paint_spectrum(figure.add_subplot(grid[0, 0]), document, lines)
    bar_axis = figure.add_subplot(grid[1, 0])
    _style_axis(bar_axis)
    _paint_bars(bar_axis, document, bar_items)
    figure.tight_layout()
    return figure


def _paint_bars(axis, document: dict, bars: list) -> None:
    color = ESTIMATED if document.get("evidence_class") == "estimated" else ENERGY
    axis.bar([item["label"] for item in bars], [item["value"] for item in bars], color=color)
    axis.tick_params(axis="x", labelrotation=45 if len(bars) > 6 else 0, labelsize=7)
    if document.get("chart_kind") == "T07":
        axis.set_ylim(0, 1)
    axis.set_ylabel(_bar_ylabel(document))


def _bars(document: dict, bars: list):
    figure, axis = plt.subplots(figsize=(8.2, 3.6), dpi=100)
    _style_figure(figure)
    _style_axis(axis)
    _paint_bars(axis, document, bars)
    axis.set_title(_title(document))
    if document.get("chart_kind") == "T10":
        figure.text(
            0.01,
            0.01,
            "Ending bars are window levels. Review checkpoints are separate.",
            color=AXIS,
            fontsize=8,
        )
        figure.tight_layout(rect=(0, 0.06, 1, 1))
    else:
        figure.tight_layout()
    return figure


def _lines(document: dict, lines: list):
    figure, axis = plt.subplots(figsize=(8.2, 3.6), dpi=100)
    _style_figure(figure)
    _style_axis(axis)
    _plot_lines(axis, document, lines)
    _mark_time(axis, document)
    _time_axis(axis, document, "x")
    axis_def = document.get("axis_definitions") or {}
    axis.set_xlabel(axis_def.get("x") or "")
    axis.set_ylabel(_line_ylabel(document, lines))
    axis.set_title(_title(document))
    figure.tight_layout()
    return figure


def _extent(xs: list, ys: list) -> list[float]:
    x0 = float(xs[0]) if xs else 0.0
    x1 = float(xs[-1]) if xs else 1.0
    y0 = float(ys[0]) if ys else 0.0
    y1 = float(ys[-1]) if ys else 1.0
    if x0 == x1:
        x1 = x0 + 1.0
    if y0 == y1:
        y1 = y0 + 1.0
    return [x0, x1, y0, y1]


def _frequency_ticks(hz: list) -> list[tuple[float, str]]:
    targets = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]
    positive = [float(value) for value in hz if value > 0]
    if not positive:
        return []
    maximum = max(positive)
    minimum = min(positive)
    chosen: dict[float, str] = {}
    for target in targets:
        if target > maximum * 1.05:
            continue
        best = min(positive, key=lambda value: abs(math.log(value) - math.log(target)))
        chosen[best] = format_frequency(best)
    span = maximum - minimum or 1.0
    kept: list[tuple[float, str]] = []
    for value, label in sorted(chosen.items()):
        if any(abs(value - previous) < span * 0.12 for previous, _label in kept):
            continue
        kept.append((value, label))
    return kept


def _spectrogram(document: dict, lines: list, heat: dict):
    count = 2 if lines else 1
    figure, axes = plt.subplots(count, 1, figsize=(8.2, 3.2 * count), dpi=100, squeeze=False)
    _style_figure(figure)
    heat_axis = axes[0, 0]
    _style_axis(heat_axis)
    image = heat_axis.imshow(
        heat["z"],
        origin="lower",
        aspect="auto",
        cmap=HEATMAP,
        extent=_extent(heat.get("x") or [], heat.get("y") or []),
    )
    colorbar = figure.colorbar(image, ax=heat_axis, fraction=0.046)
    colorbar.set_label("dB rel. median" if lines else "Stored value", color=INK)
    colorbar.ax.yaxis.set_tick_params(color=INK, labelcolor=INK)
    ticks = _frequency_ticks(heat.get("y") or [])
    if ticks:
        heat_axis.set_yticks([item[0] for item in ticks])
        heat_axis.set_yticklabels([item[1] for item in ticks])
    heat_axis.set_ylabel("Frequency (Hz)")
    _time_axis(heat_axis, document, "x")
    heat_axis.set_title(_title(document))
    if lines:
        band = axes[1, 0]
        _style_axis(band)
        _plot_lines(band, document, lines)
        _time_axis(band, document, "x")
        band.set_ylabel(lines[0].get("unit") or "dB rel. median")
        band.set_xlabel((document.get("axis_definitions") or {}).get("x") or "")
    else:
        heat_axis.set_xlabel((document.get("axis_definitions") or {}).get("x") or "")
    figure.tight_layout()
    return figure


def _matrix(document: dict, heat: dict):
    figure, axis = plt.subplots(figsize=(8.2, 4.2), dpi=100)
    _style_figure(figure)
    _style_axis(axis)
    image = axis.imshow(
        heat["z"],
        origin="lower",
        aspect="auto",
        cmap=HEATMAP,
        extent=_extent(heat.get("x") or [], heat.get("y") or []),
    )
    colorbar = figure.colorbar(image, ax=axis, fraction=0.046)
    colorbar.set_label("Cosine similarity", color=INK)
    colorbar.ax.yaxis.set_tick_params(color=INK, labelcolor=INK)
    _time_axis(axis, document, "x")
    _time_axis(axis, document, "y")
    axis_def = document.get("axis_definitions") or {}
    axis.set_xlabel(axis_def.get("x") or "")
    axis.set_ylabel(axis_def.get("y") or "")
    axis.set_title(_title(document))
    figure.tight_layout()
    return figure
