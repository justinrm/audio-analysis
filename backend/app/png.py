"""PNG drawings of stored chart documents. Headless; no display."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def write_png(path: Path, document: dict) -> None:
    if document.get("status") != "ready":
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
    series = document["series"]
    heatmap = series.get("heatmap")
    if heatmap and heatmap.get("z"):
        image = ax.imshow(
            heatmap["z"],
            origin="lower",
            aspect="auto",
            cmap="magma",
            extent=[
                heatmap["x"][0] if heatmap["x"] else 0,
                heatmap["x"][-1] if heatmap["x"] else 1,
                heatmap["y"][0] if heatmap["y"] else 0,
                heatmap["y"][-1] if heatmap["y"] else 1,
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
    ax.set_ylabel(axis.get("y") or "")
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
