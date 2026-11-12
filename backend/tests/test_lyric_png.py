"""Presentation checks for lyric-png-v2 and the lyric-brief-v2 template.

These tests render stored chart documents. They do not decode a WAV.
"""

from __future__ import annotations

import re

import matplotlib.pyplot as plt
import numpy as np
import pytest
from app.exports import BRIEF_TEMPLATE_VERSION, _brief
from app.lyric_png import LYRIC_RENDERER_VERSION, l05_figure_text, render_lyric_figure
from app.measure import ALGORITHM_VERSION
from app.png import RENDERER_VERSION

LINE = "UNIQUE_LYRIC_LINE_ZEBRA"


def _ready(kind: str, **overrides: object) -> dict:
    document = {
        "chart_kind": kind,
        "status": "ready",
        "title": kind,
        "evidence_class": "measured",
        "series": {"lines": [], "bars": [], "heatmap": None},
        "axis_definitions": {"x": "Time (s)", "y": "dBFS", "y_scale": "linear"},
        "regions": [],
        "review_markers": [],
        "rows": [],
        "insufficient": [],
        "caveats": [],
        "summary": [],
    }
    document.update(overrides)
    return document


def _close(figure) -> None:
    plt.close(figure)


def test_renderer_versions_stay_separate() -> None:
    assert LYRIC_RENDERER_VERSION == "lyric-png-v2"
    assert BRIEF_TEMPLATE_VERSION == "lyric-brief-v2"
    assert RENDERER_VERSION == "png-r2"
    assert ALGORITHM_VERSION == "m1-v3"


def test_l04_axis_uses_recording_time_not_bin_indexes() -> None:
    centers = [float(value) for value in np.linspace(1.0, 179.0, 46)]
    grid = [[0.25 for _ in centers] for _ in centers]
    figure = render_lyric_figure(
        _ready(
            "L04",
            series={"lines": [], "bars": [], "heatmap": {"x": centers, "y": centers, "z": grid}},
        )
    )
    figure.canvas.draw()
    left, right = figure.axes[0].get_xlim()
    labels = " ".join(tick.get_text() for tick in figure.axes[0].get_xticklabels())
    _close(figure)
    assert left < 5
    assert right > 160
    assert ":" in labels
    assert right != pytest.approx(45, abs=2)


def test_l04_nonuniform_centers_keep_their_gaps() -> None:
    centers = [0.0, 1.0, 10.0, 30.0]
    grid = [[0.1 for _ in centers] for _ in centers]
    figure = render_lyric_figure(
        _ready(
            "L04",
            series={"lines": [], "bars": [], "heatmap": {"x": centers, "y": list(centers), "z": grid}},
        )
    )
    left, right = figure.axes[0].get_xlim()
    _close(figure)
    assert left == pytest.approx(-0.5)
    assert right == pytest.approx(40.0)


def test_l04_refuses_a_bin_index_axis_when_coordinates_do_not_match() -> None:
    figure = render_lyric_figure(
        _ready(
            "L04",
            series={"lines": [], "bars": [], "heatmap": {"x": [0.0, 1.0], "y": [0.0, 1.0], "z": [[0.0]]}},
        )
    )
    text = " ".join(axis.texts[0].get_text() for axis in figure.axes if axis.texts)
    _close(figure)
    assert "do not match" in text


def test_l03_keeps_dbfs_and_lufs_on_separate_axes() -> None:
    rms = [-12.5, None, -11.25]
    lufs = [-14.0, -13.5]
    figure = render_lyric_figure(
        _ready(
            "L03",
            regions=[{"start_s": 1.5, "end_s": 4.25, "label": LINE}],
            series={
                "lines": [
                    {"name": "1 s RMS", "unit": "dBFS", "x": [0.0, 1.0, 2.0], "y": rms},
                    {"name": "3 s short-term LUFS", "unit": "LUFS", "x": [0.5, 2.5], "y": lufs},
                ],
                "bars": [],
                "heatmap": None,
            },
        )
    )
    labels = [axis.get_ylabel() for axis in figure.axes]
    paired = []
    for axis in figure.axes:
        names = [line.get_label() for line in axis.get_lines()]
        paired.append(names)
        values = [list(line.get_ydata()) for line in axis.get_lines()]
        if any("RMS" in name for name in names):
            assert values == [[-12.5, -11.25]]
        if any("LUFS" in name for name in names):
            assert values == [lufs]
    lane = next(axis for axis in figure.axes if axis.get_ylabel() == "Lyric intervals")
    span = lane.patches[0]
    _close(figure)
    assert "Full-mix RMS (dBFS)" in labels
    assert "Short-term loudness (LUFS)" in labels
    assert all(not ("RMS" in "".join(names) and "LUFS" in "".join(names)) for names in paired)
    assert span.get_x() == pytest.approx(1.5)
    assert span.get_width() == pytest.approx(2.75)
    assert LINE not in " ".join(labels)


def test_l02_uses_sparse_line_numbers_and_keeps_word_counts() -> None:
    counts = [4 if index % 2 == 0 else 1 for index in range(70)]
    figure = render_lyric_figure(
        _ready(
            "L02",
            series={
                "bars": [{"label": str(index + 1), "value": value} for index, value in enumerate(counts)],
                "lines": [
                    {
                        "name": "Written words per second",
                        "unit": "words/s",
                        "x": [float(index + 1) for index in range(70)],
                        "y": [value / 2 if index % 5 else None for index, value in enumerate(counts)],
                    }
                ],
                "heatmap": None,
            },
        )
    )
    axis = figure.axes[0]
    tick_text = [tick.get_text() for tick in axis.get_xticklabels() if tick.get_text()]
    heights = [patch.get_height() for patch in axis.patches]
    note = figure.get_suptitle() or ""
    _close(figure)
    assert len(tick_text) <= 8
    assert tick_text[0] == "1"
    assert tick_text[-1] == "70"
    assert heights == counts
    assert "vocal delivery" in note


def test_l01_intervals_stay_on_their_lane() -> None:
    figure = render_lyric_figure(
        _ready(
            "L01",
            series={
                "lines": [{"name": "1 s RMS", "unit": "dBFS", "x": [0.0, 10.0], "y": [-20.0, -12.0]}],
                "bars": [],
                "heatmap": None,
            },
            regions=[
                {"start_s": 2.0, "end_s": 3.5},
                {"start_s": 8.0, "end_s": 1.0},
                {"start_s": None, "end_s": 4.0},
            ],
            review_markers=[{"time_s": 6.0, "label": "provisional change"}],
        )
    )
    curve = figure.axes[0]
    lane = figure.axes[1]
    legend = [text.get_text() for text in curve.get_legend().get_texts()]
    _close(figure)
    assert lane.get_ylabel() == "Lyric intervals"
    assert len(lane.patches) == 1
    assert lane.patches[0].get_x() == pytest.approx(2.0)
    assert lane.patches[0].get_width() == pytest.approx(1.5)
    assert list(curve.get_lines()[0].get_ydata()) == [-20.0, -12.0]
    assert "Provisional change" in legend
    assert len(curve.patches) == 0


def test_l05_states_the_selection_and_does_not_invent_or_print_lines() -> None:
    rows = [
        {
            "kind": "finding",
            "evidence_id": f"ly:seg-{index}",
            "evidence_class": "textual",
            "name": "lyric_line",
            "value": f"{LINE} {index}",
            "cites": [],
        }
        for index in range(70)
    ]
    rows.append(
        {
            "kind": "finding",
            "evidence_id": "ev:t02:rms-1s",
            "evidence_class": "measured",
            "name": "1 s RMS",
            "value": "stored series",
            "cites": [],
        }
    )
    rows.append(
        {
            "kind": "principle",
            "evidence_id": "ly:principle:level-contrast",
            "evidence_class": "interpretive",
            "name": "level_contrast",
            "value": "The stored full-mix means differ by 1.20 dB.",
            "cites": ["ev:t02:rms-1s"],
            "caveat": "Not singing intensity.",
        }
    )
    document = _ready(
        "L05",
        rows=rows,
        insufficient=[{"code": "melody", "reason": "Spectral similarity is not melodic identity.", "cites": []}],
    )
    text = l05_figure_text(document)
    figure = render_lyric_figure(document)
    drawn = figure.texts[0].get_text()
    _close(figure)
    assert "Showing 1 of 71 findings" in text
    assert "70 lyric-line records" in text
    assert "L05.json" in text
    assert LINE not in text
    assert "guitar" not in text.lower()
    assert "sad" not in text.lower()
    assert text in drawn


def test_summarized_brief_selects_evidence_and_hides_lyric_text() -> None:
    contrasts = [
        {"label": "Contrast", "value": f"Stored 1 s RMS means differ by {index}.00 dB."}
        for index in range(40)
    ]
    charts = [
        {
            "chart_kind": "L02",
            "status": "ready",
            "summary": [{"label": "Supplied timing", "value": "70"}],
            "caveats": ["Word counts are written tokens, not vocal delivery or breaths."],
            "rows": [],
        },
        {
            "chart_kind": "L03",
            "status": "ready",
            "summary": [
                *contrasts,
                {"label": "Stored 1 s RMS mean 0.000–1.000 s", "value": "-12.00 dBFS"},
            ],
            "caveats": ["Interval values are means of stored full-mix samples."],
            "rows": [],
        },
        {
            "chart_kind": "L04",
            "status": "ready",
            "summary": [],
            "caveats": [],
            "rows": [
                {
                    "kind": "finding",
                    "evidence_id": "ly:repeat:abc",
                    "evidence_class": "textual",
                    "name": LINE,
                    "value": "2",
                    "cites": ["ly:line-1"],
                }
            ],
        },
        {
            "chart_kind": "L05",
            "status": "ready",
            "summary": [],
            "caveats": [],
            "rows": [
                {
                    "kind": "principle",
                    "evidence_id": "ly:principle:written-repetition:abc",
                    "evidence_class": "interpretive",
                    "name": "written_repetition",
                    "value": "A written line occurs 2 times.",
                    "cites": ["ly:repeat:abc"],
                }
            ],
            "insufficient": [
                {"code": "vocal", "reason": "No vocal-performance principle.", "cites": []}
            ],
        },
    ]
    evidence = {
        "records": [
            {
                "id": "ev:t02:rms-1s",
                "evidence_class": "measured",
                "name": "1 s RMS",
                "value": None,
                "unit": "dBFS",
            },
            {
                "id": "ly:line-1",
                "evidence_class": "textual",
                "name": "lyric_line",
                "value": LINE,
            },
            {
                "id": "ly:repeat:abc",
                "evidence_class": "textual",
                "name": LINE,
                "value": 2,
            },
        ]
    }
    document = {"id": "doc", "revision": 3, "source_sha256": "abc"}
    summarized = _brief("source-sha", None, document, "summarized", charts, evidence)
    omitted = _brief("source-sha", None, document, "omitted", charts, evidence)
    included = _brief("source-sha", None, document, "included", charts, evidence)
    known = {item["id"] for item in evidence["records"]}
    cites = set(re.findall(r"`((?:ev|ly):[^`]+)`", summarized))
    assert cites
    assert cites <= known
    assert LINE not in summarized
    assert LINE not in omitted
    assert LINE in included
    assert "Showing 3 of 40" in summarized
    assert summarized.count("differ by") == 3
    assert "0.000–1.000" not in summarized
    assert "lyric-brief-v2" in summarized
    assert "What this package cannot determine" in summarized
    assert "No vocal-performance principle." in summarized
    assert summarized == _brief("source-sha", None, document, "summarized", charts, evidence)


def test_brief_without_analysis_still_states_the_limits() -> None:
    text = _brief(
        "source-sha",
        None,
        {"id": "doc", "revision": 1, "source_sha256": "abc"},
        "summarized",
        [],
        {"records": []},
    )
    assert "No stored technical or summary evidence" in text
    assert "Singing performance" in text
    assert "Verified song sections" in text
    assert LINE not in text
