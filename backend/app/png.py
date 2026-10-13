"""PNG drawings of stored chart documents. Headless; no display."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def write_png(path: Path, document: dict) -> None:
    if document.get("status") != "ready":
        return
    series = document["series"]
    lines = series.get("lines") or []
    amplitude = [line for line in lines if line.get("unit") == "amplitude"]
    levels = [line for line in lines if line.get("unit") == "dBFS"]
    heatmap = series.get("heatmap")
    if amplitude and levels and not (heatmap and heatmap.get("z")):
        _write_level_panels(path, document, amplitude, levels)
        return
    fig, ax = plt.subplots(figsize=(8.2, 3.6), dpi=100)
    fig.patch.set_facecolor("#161b22")
    ax.set_facecolor("#12171d")
    ax.tick_params(colors="#e6e0d4")
    for spine in ax.spines.values():
        spine.set_color("#3a4451")
    ax.yaxis.label.set_color("#e6e0d4")
    ax.xaxis.label.set_color("#e6e0d4")
    ax.title.set_color("#e6e0d4")
    if heatmap and heatmap.get("z"):
        image = ax.imshow(
            heatmap["z"],
            origin="lower",
            aspect="auto",
            cmap="magma",
            extent=[
                heatmap["x"][0] if heatmap["x"] else 0,
                heatmap["x"][-1] if heatmap["x"] else 1,
                *_heat_ylim(document, heatmap),
            ],
        )
        fig.colorbar(image, ax=ax, fraction=0.046)
    for line in series.get("lines") or []:
        pairs = [(x, y) for x, y in zip(line["x"], line["y"], strict=True) if y is not None]
        if pairs:
            ax.plot([item[0] for item in pairs], [item[1] for item in pairs], label=line["name"])
    bars = series.get("bars") or []
    if bars and not series.get("lines") and not (heatmap and heatmap.get("z")):
        ax.bar([item["label"] for item in bars], [item["value"] for item in bars], color="#b08d57")
        ax.tick_params(axis="x", labelrotation=45, labelsize=7)
    axis = document.get("axis_definitions") or {}
    ax.set_xlabel(axis.get("x") or "")
    ax.set_ylabel(_line_ylabel(lines, axis.get("y") or ""))
    if axis.get("y_scale") == "log" and not (heatmap and heatmap.get("z")):
        positive = [x for line in series.get("lines") or [] for x in line["x"] if x > 0]
        if positive:
            ax.set_xscale("log")
    ax.set_title(document["title"])
    if str((document.get("axis_definitions") or {}).get("x", "")).lower().startswith("time"):
        for marker in document.get("review_markers") or []:
            ax.axvline(marker["time_s"], color="#b08d57", linewidth=0.6)
    if series.get("lines"):
        ax.legend(facecolor="#1d242d", edgecolor="#3a4451", labelcolor="#e6e0d4", fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def _heat_ylim(document: dict, heatmap: dict) -> tuple[float, float]:
    ranges = document.get("frequency_ranges") or []
    if ranges:
        return float(ranges[0]["lo_hz"]), float(ranges[-1]["hi_hz"])
    return (
        float(heatmap["y"][0]) if heatmap.get("y") else 0.0,
        float(heatmap["y"][-1]) if heatmap.get("y") else 1.0,
    )


def _line_ylabel(lines: list, label: str) -> str:
    if lines and str(label).startswith("Relative RMS-power"):
        units = list(dict.fromkeys(line.get("unit") or "" for line in lines if line.get("unit")))
        return " / ".join(units)
    return label


def _write_level_panels(path: Path, document: dict, amplitude: list, levels: list) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(8.2, 5.4), dpi=100, sharex=True)
    fig.patch.set_facecolor("#161b22")
    _plot_named(axes[0], amplitude)
    _plot_named(axes[1], levels)
    for ax in axes:
        ax.set_facecolor("#12171d")
        ax.tick_params(colors="#e6e0d4")
        for spine in ax.spines.values():
            spine.set_color("#3a4451")
        ax.yaxis.label.set_color("#e6e0d4")
        ax.xaxis.label.set_color("#e6e0d4")
        ax.title.set_color("#e6e0d4")
        for marker in document.get("review_markers") or []:
            ax.axvline(marker["time_s"], color="#b08d57", linewidth=0.6)
        ax.legend(facecolor="#1d242d", edgecolor="#3a4451", labelcolor="#e6e0d4", fontsize=8)
    axes[0].set_ylabel("Normalized amplitude")
    axes[1].set_ylabel("dBFS")
    axes[0].set_title(document["title"])
    axes[1].set_xlabel((document.get("axis_definitions") or {}).get("x") or "")
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)


def _plot_named(ax, lines: list) -> None:
    for line in lines:
        pairs = [(x, y) for x, y in zip(line["x"], line["y"], strict=True) if y is not None]
        if pairs:
            ax.plot([item[0] for item in pairs], [item[1] for item in pairs], label=line["name"])
