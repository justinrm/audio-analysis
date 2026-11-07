"""L01–L05 charts from stored technical JSON and the current lyric document.

This module reads chart files. It does not decode audio or recompute measurements.
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path

from app.lyrics import word_count

ANALYSIS_VERSION = "m1-v3"
LEVEL_CONTRAST_DB = 1.0
LYRIC_KINDS = ("L01", "L02", "L03", "L04", "L05")
_STORED_KINDS = ("T02", "T08", "T09")

_TITLES = {
    "L01": "Unified music-and-lyrics timeline",
    "L02": "Phrasing and written density",
    "L03": "Energy and dynamic contrast",
    "L04": "Repetition map",
    "L05": "Musical DNA and transferable principles",
}
_WORD_CAVEAT = "Word counts are written tokens, not vocal delivery or breaths."
_TIMED_CAVEAT = (
    "Interval values are means of stored full-mix samples. "
    "They are not singing intensity, vocal energy, or emotion."
)
_CHANGE_CAVEAT = "Not a verified verse, chorus, or section boundary."
_T08_MISSING = "Provisional change markers are unavailable."
_WINDOW_SENTENCE = "These are analysis windows, not verses, choruses, or emotional sections."
_MELODY_CAVEAT = "A bright cell is not a matching melody or hook."
_T02_MISSING = "Stored T02 energy is not m1-v3."
_NO_SAMPLE = "No stored 1 s RMS sample falls inside this written interval."
_FIXED_REFUSALS = (
    (
        "tempo",
        "No transferable tempo principle. An onset candidate is not a beat grid, meter, or groove.",
    ),
    ("melody", "No melody or hook principle. Spectral similarity is not melodic identity."),
    ("section", "No section principle. A spectral change point is not a verified verse or chorus."),
    (
        "vocal",
        "No vocal-performance principle. This milestone does not estimate singing, alignment, or delivery.",
    ),
    ("emotion", "No emotion principle. Full-mix level is not mood."),
    (
        "instrumentation",
        "No instrumentation principle. Spectral shape is not an instrument identity.",
    ),
)
_REPEAT_REFUSAL = "No written-repetition principle. No normalized line occurs more than once."
_LEVEL_TEMPLATES = {
    "absent": "No level-contrast principle. Stored T02 energy is unavailable.",
    "few": (
        "No level-contrast principle. "
        "Fewer than two written intervals contain a stored 1 s RMS sample."
    ),
    "overlap": (
        "No level-contrast principle. "
        "The written intervals overlap, so their stored levels are not compared."
    ),
}


def chart_class(classes: list[str]) -> tuple[str, str | None]:
    present = sorted({item for item in classes if item})
    if len(present) == 1:
        return present[0], None
    if not present:
        return "unknown", None
    return "unknown", "This chart combines " + ", ".join(present) + "."


def load_stored_charts(data_root: Path, sha256: str) -> dict[str, dict | None]:
    root = data_root / "analysis" / sha256 / ANALYSIS_VERSION
    found: dict[str, dict | None] = {}
    for kind in _STORED_KINDS:
        path = root / f"{kind}.json"
        found[kind] = json.loads(path.read_text()) if path.is_file() else None
    return found


def build_lyric_chart(
    kind: str,
    bundle: dict,
    charts: dict[str, dict | None],
    document: dict | None = None,
) -> dict:
    if kind not in _TITLES:
        raise ValueError(kind)
    builders = {"L01": _l01, "L02": _l02, "L03": _l03, "L04": _l04, "L05": _l05}
    return builders[kind](bundle, charts, document)


def summary_for(document: dict, project_id: str, asset_id: str) -> dict:
    kind = document["chart_kind"]
    return {
        "chart_kind": kind,
        "status": document["status"],
        "title": document["title"],
        "evidence_class": document["evidence_class"],
        "method_id": document["method_id"],
        "method_version": document["method_version"],
        "caveats": document["caveats"],
        "summary": document["summary"],
        "not_available_reason": document.get("not_available_reason"),
        "error": document.get("error"),
        "data_url": f"/api/projects/{project_id}/assets/{asset_id}/lyric-charts/{kind}/data",
        "png_url": None,
    }


def _ready(chart: dict | None) -> dict | None:
    if not chart:
        return None
    if chart.get("status") != "ready" or chart.get("method_version") != ANALYSIS_VERSION:
        return None
    return chart


def _line(document: dict | None, name: str) -> dict | None:
    if document is None:
        return None
    for line in (document.get("series") or {}).get("lines") or []:
        if line.get("name") == name and len(line.get("x") or []) == len(line.get("y") or []):
            return line
    return None


def _copy_line(line: dict, evidence_class: str, evidence_id: str) -> dict:
    return {
        "name": line["name"],
        "unit": line["unit"],
        "x": list(line["x"]),
        "y": list(line["y"]),
        "evidence_class": evidence_class,
        "evidence_id": evidence_id,
    }


def _t02_reason(chart: dict | None) -> str:
    if chart and chart.get("method_version") == ANALYSIS_VERSION:
        return chart.get("not_available_reason") or chart.get("error") or _T02_MISSING
    return _T02_MISSING


def _identity(bundle: dict, document: dict | None) -> tuple[str | None, int | None]:
    if document is not None:
        return document.get("id"), document.get("revision")
    return bundle.get("lyric_document_id"), bundle.get("lyric_revision")


def _blank(kind: str, bundle: dict, document: dict | None, analysis: str | None) -> dict:
    lyric_id, revision = _identity(bundle, document)
    return {
        "chart_kind": kind,
        "status": "ready",
        "title": _TITLES[kind],
        "evidence_class": "unknown",
        "method_id": "lyrics-v1",
        "method_version": "lyrics-v1",
        "analysis_version": analysis,
        "lyric_document_id": lyric_id,
        "lyric_revision": revision,
        "caveats": [],
        "summary": [],
        "series": {"lines": [], "bars": [], "heatmap": None},
        "axis_definitions": {"x": "", "y": "", "y_scale": "linear"},
        "review_markers": [],
        "regions": [],
        "rows": [],
        "insufficient": [],
        "not_available_reason": None,
        "error": None,
    }


def _unavailable(kind: str, bundle: dict, document: dict | None, reason: str) -> dict:
    document_out = _blank(kind, bundle, document, None)
    document_out["status"] = "not_available"
    document_out["not_available_reason"] = reason
    return document_out


def _finish(document: dict, classes: list[str]) -> dict:
    evidence, caveat = chart_class(classes)
    document["evidence_class"] = evidence
    if caveat:
        document["caveats"].append(caveat)
    return document


def _usable(document: dict | None) -> list[dict]:
    if not document:
        return []
    return [segment for segment in document.get("segments") or [] if segment.get("usable")]


def _regions(document: dict | None) -> list[dict]:
    regions = []
    for segment in _usable(document):
        regions.append(
            {
                "evidence_id": f"ly:{segment['id']}",
                "segment_id": segment["id"],
                "label": _region_label(segment),
                "start_s": segment["start_s"],
                "end_s": segment["end_s"],
                "evidence_class": "textual",
            }
        )
    return regions


def _region_label(segment: dict) -> str:
    text = " ".join(str(segment.get("text") or "").split())
    if not text:
        return f"Line {int(segment.get('ordinal', 0)) + 1}"
    if len(text) > 80:
        return text[:79] + "…"
    return text


def _timing_counts(document: dict) -> list[dict]:
    validation = document.get("validation") or []

    def count(code: str) -> str:
        return str(sum(1 for item in validation if item.get("code") == code))

    untimed = sum(
        1
        for segment in document.get("segments") or []
        if segment.get("start_s") is None or segment.get("end_s") is None
    )
    return [
        {"label": "Untimed lines", "value": str(untimed)},
        {"label": "Reversed cues", "value": count("reversed_time")},
        {"label": "Malformed cues", "value": count("malformed_time")},
        {"label": "Out-of-range cues", "value": count("out_of_range")},
    ]


def _records(bundle: dict) -> dict[str, dict]:
    return {item["id"]: item for item in bundle.get("records") or [] if item.get("id")}


def _l01(bundle: dict, charts: dict[str, dict | None], document: dict | None) -> dict:
    stored = _ready(charts.get("T02"))
    rms = _line(stored, "1 s RMS")
    if rms is None:
        return _unavailable("L01", bundle, document, _t02_reason(charts.get("T02")))
    chart = _blank("L01", bundle, document, ANALYSIS_VERSION)
    chart["series"]["lines"] = [_copy_line(rms, "measured", "ev:t02:rms-1s")]
    chart["axis_definitions"] = {"x": "Time (s)", "y": rms.get("unit") or "dBFS", "y_scale": "linear"}
    t08 = _ready(charts.get("T08"))
    markers = _change_markers(t08)
    if markers:
        chart["review_markers"] = markers
    elif t08 is None:
        chart["caveats"].append(_T08_MISSING)
    else:
        stored = [item for item in t08.get("caveats") or [] if item]
        chart["caveats"].extend(stored or [_T08_MISSING])
    chart["regions"] = _regions(document)
    if document is not None:
        chart["summary"].extend(_timing_counts(document))
    if not chart["regions"]:
        chart["summary"].append({"label": "Lyric timing", "value": "unavailable"})
    classes = ["measured"]
    if chart["regions"]:
        classes.append("textual")
    return _finish(chart, classes)


def _change_markers(t08: dict | None) -> list[dict]:
    if t08 is None:
        return []
    markers = []
    for marker in t08.get("review_markers") or []:
        kind = marker.get("kind")
        label = marker.get("label")
        if kind != "provisional_change" and label not in ("provisional_change", "provisional change"):
            continue
        markers.append(
            {
                "time_s": marker["time_s"],
                "label": label or "provisional change",
                "kind": kind or "provisional_change",
                "value": marker.get("value"),
                "caveat": _CHANGE_CAVEAT,
            }
        )
    return markers


def _l02(bundle: dict, charts: dict[str, dict | None], document: dict | None) -> dict:
    del charts
    if document is None:
        return _unavailable("L02", bundle, None, "No lyric document is attached.")
    chart = _blank("L02", bundle, document, None)
    chart["axis_definitions"] = {"x": "Line", "y": "Written words", "y_scale": "linear"}
    chart["caveats"] = [_WORD_CAVEAT]
    segments = document.get("segments") or []
    origins = {"subtitle_supplied": 0, "manual_edit": 0, "manual_verified": 0, "unplaced": 0}
    bars = []
    xs: list[float] = []
    ys: list[float | None] = []
    for segment in segments:
        origin = segment.get("timing_origin") or "unplaced"
        origins[origin] = origins.get(origin, 0) + 1
        bars.append(
            {
                "label": str(int(segment.get("ordinal", 0)) + 1),
                "value": float(word_count(segment.get("text") or "")),
                "evidence_class": "textual",
                "evidence_id": f"ly:{segment['id']}",
            }
        )
        xs.append(float(int(segment.get("ordinal", 0)) + 1))
        if segment.get("usable"):
            span = float(segment["end_s"]) - float(segment["start_s"])
            ys.append(word_count(segment.get("text") or "") / span)
        else:
            ys.append(None)
    chart["series"]["bars"] = bars
    if segments:
        chart["series"]["lines"] = [
            {
                "name": "Written words per second",
                "unit": "words/s",
                "x": xs,
                "y": ys,
                "evidence_class": "textual",
                "evidence_id": "ly:density",
            }
        ]
    chart["summary"] = [
        {"label": "Supplied timing", "value": str(origins["subtitle_supplied"])},
        {"label": "Manually edited", "value": str(origins["manual_edit"])},
        {"label": "Manually verified", "value": str(origins["manual_verified"])},
        {"label": "Unavailable timing", "value": str(origins["unplaced"])},
    ]
    return _finish(chart, ["textual"])


def _l03(bundle: dict, charts: dict[str, dict | None], document: dict | None) -> dict:
    stored = _ready(charts.get("T02"))
    rms = _line(stored, "1 s RMS")
    lufs = _line(stored, "3 s short-term LUFS")
    if stored is None or (rms is None and lufs is None):
        return _unavailable("L03", bundle, document, _t02_reason(charts.get("T02")))
    chart = _blank("L03", bundle, document, ANALYSIS_VERSION)
    lines = []
    if rms is not None:
        lines.append(_copy_line(rms, "measured", "ev:t02:rms-1s"))
    if lufs is not None:
        lines.append(_copy_line(lufs, "measured", "ev:t02:short-term-lufs"))
    chart["series"]["lines"] = lines
    chart["axis_definitions"] = {"x": "Time (s)", "y": "dBFS or LUFS", "y_scale": "linear"}
    regions = _regions(document)
    classes = ["measured"]
    if not regions:
        chart["series"]["bars"] = [
            {
                "label": bar["label"],
                "value": float(bar["value"]),
                "evidence_class": "measured",
                "evidence_id": "ev:t02:windows",
            }
            for bar in (stored.get("series") or {}).get("bars") or []
            if bar.get("label") is not None and bar.get("value") is not None
        ]
        chart["summary"].append(
            {
                "label": "Lyric timing",
                "value": "unavailable. Showing stored full-mix energy only.",
            }
        )
        chart["caveats"].extend(list(stored.get("caveats") or []))
        if not any("analysis windows, not verses" in caveat for caveat in chart["caveats"]):
            chart["caveats"].append(_WINDOW_SENTENCE)
        if chart["series"]["bars"]:
            classes.extend(["measured"] * len(chart["series"]["bars"]))
    else:
        chart["regions"] = regions
        chart["caveats"].append(_TIMED_CAVEAT)
        classes.append("textual")
        _timed_summary(chart, bundle, document)
    return _finish(chart, classes)


def _timed_summary(chart: dict, bundle: dict, document: dict | None) -> None:
    found = _records(bundle)
    ordered = sorted(_usable(document), key=lambda item: (item["start_s"], item["end_s"], item["id"]))
    for segment in ordered:
        level = found.get(f"ly:level:{segment['id']}")
        lufs = found.get(f"ly:lufs:{segment['id']}")
        span = f"{segment['start_s']:.3f}\u2013{segment['end_s']:.3f} s"
        if level is None or level.get("value") is None:
            chart["summary"].append({"label": span, "value": _NO_SAMPLE})
        else:
            chart["summary"].append(
                {
                    "label": f"Stored 1 s RMS mean {span}",
                    "value": f"{float(level['value']):.2f} dBFS",
                }
            )
        if lufs is not None and lufs.get("value") is not None:
            chart["summary"].append(
                {
                    "label": f"Stored short-term LUFS mean {span}",
                    "value": f"{float(lufs['value']):.2f} LUFS",
                }
            )
    for left, right in itertools.pairwise(ordered):
        if _segment_overlap(left, right):
            continue
        left_level = found.get(f"ly:level:{left['id']}")
        right_level = found.get(f"ly:level:{right['id']}")
        if (
            left_level is None
            or right_level is None
            or left_level.get("value") is None
            or right_level.get("value") is None
        ):
            continue
        delta = float(right_level["value"]) - float(left_level["value"])
        chart["summary"].append(
            {"label": "Contrast", "value": f"Stored 1 s RMS means differ by {delta:.2f} dB."}
        )


def _segment_overlap(left: dict, right: dict) -> bool:
    return left["start_s"] < right["end_s"] and right["start_s"] < left["end_s"]


def _l04(bundle: dict, charts: dict[str, dict | None], document: dict | None) -> dict:
    t09 = _ready(charts.get("T09"))
    if t09 is None and document is None:
        return _unavailable(
            "L04",
            bundle,
            None,
            "The recurrence chart is unavailable and no lyric document is attached.",
        )
    chart = _blank("L04", bundle, document, ANALYSIS_VERSION if t09 is not None else None)
    classes: list[str] = []
    if t09 is None:
        chart["caveats"].append("The recurrence chart is unavailable.")
    else:
        heat = (t09.get("series") or {}).get("heatmap")
        if heat:
            chart["series"]["heatmap"] = {
                "x": list(heat.get("x") or []),
                "y": list(heat.get("y") or []),
                "z": [list(row) for row in heat.get("z") or []],
            }
        axis = t09.get("axis_definitions") or {}
        chart["axis_definitions"] = {
            "x": axis.get("x") or "Time (s)",
            "y": axis.get("y") or "Time (s)",
            "y_scale": axis.get("y_scale") or "linear",
        }
        chart["caveats"].extend(list(t09.get("caveats") or []))
        if not any("not a matching melody" in caveat for caveat in chart["caveats"]):
            chart["caveats"].append(_MELODY_CAVEAT)
        classes.append("estimated")
    repeats = [
        item
        for item in bundle.get("records") or []
        if str(item.get("id", "")).startswith("ly:repeat:")
    ]
    if document is None:
        chart["summary"].append(
            {"label": "Lyric document", "value": "No lyric document. Text repetition is unavailable."}
        )
    else:
        for item in repeats:
            chart["rows"].append(_finding_row(item))
            classes.append("textual")
    return _finish(chart, classes)


def _l05(bundle: dict, charts: dict[str, dict | None], document: dict | None) -> dict:
    del charts
    ready = bundle.get("analysis_version") == ANALYSIS_VERSION or bool(bundle.get("lyric_document_id"))
    chart = _blank(
        "L05",
        bundle,
        document,
        ANALYSIS_VERSION if bundle.get("analysis_version") == ANALYSIS_VERSION else None,
    )
    records = [item for item in bundle.get("records") or [] if item.get("id")]
    finding_ids: set[str] = set()
    if ready:
        for item in records:
            if _is_finding(item):
                chart["rows"].append(_finding_row(item))
                finding_ids.add(item["id"])
        principles = _principles(records, finding_ids)
        chart["rows"].extend(principles)
    else:
        chart["status"] = "not_available"
        chart["not_available_reason"] = "No technical evidence and no lyric document."
        principles = []
    chart["insufficient"] = _insufficient(records, principles)
    return _finish(chart, [row["evidence_class"] for row in chart["rows"]])


def _is_finding(item: dict) -> bool:
    evidence_id = item["id"]
    if item.get("persisted"):
        return True
    if evidence_id in ("ev:t02:rms-1s", "ev:t02:short-term-lufs"):
        return True
    return evidence_id.startswith("ly:") and not evidence_id.startswith("ly:principle:")


def _finding_row(item: dict) -> dict:
    value = item.get("value")
    if isinstance(value, float):
        shown = format(value, ".6g")
    elif value is None:
        shown = ""
    else:
        shown = str(value)
    return {
        "evidence_id": item["id"],
        "evidence_class": item.get("evidence_class") or "unknown",
        "kind": "finding",
        "name": item.get("name") or item["id"],
        "value": shown,
        "unit": item.get("unit"),
        "cites": list(item.get("cites") or []),
        "caveat": item.get("caveat") or "",
    }


def _principles(records: list[dict], finding_ids: set[str]) -> list[dict]:
    rows = []
    for item in records:
        if not str(item.get("id", "")).startswith("ly:repeat:"):
            continue
        token = item["id"].split(":", 2)[2]
        count = item.get("value")
        number = int(count) if isinstance(count, (int, float)) and float(count).is_integer() else count
        row = {
            "evidence_id": f"ly:principle:written-repetition:{token}",
            "evidence_class": "interpretive",
            "kind": "principle",
            "name": "written_repetition",
            "value": (
                f"A written line occurs {number} times. "
                "Transferable mechanism: a later lyric can bring a phrase back. "
                "Do not copy this recording's words. The repeat is not a melody or hook."
            ),
            "unit": None,
            "cites": [item["id"]],
            "caveat": "Conditional on written repetition in this document. Not a melody or hook.",
        }
        if _cites_resolve(row, finding_ids):
            rows.append(row)
    contrast = _level_principle(records)
    if contrast is not None and _cites_resolve(contrast, finding_ids):
        rows.append(contrast)
    return rows


def _cites_resolve(row: dict, finding_ids: set[str]) -> bool:
    return all(cite in finding_ids for cite in row["cites"])


def _level_pairs(records: list[dict]) -> list[tuple[dict, dict, float]]:
    levels = [
        item
        for item in records
        if str(item.get("id", "")).startswith("ly:level:") and item.get("interval_s") and item.get("value") is not None
    ]
    levels.sort(key=lambda item: (item["interval_s"][0], item["interval_s"][1], item["id"]))
    pairs = []
    for left, right in itertools.pairwise(levels):
        left_span = left["interval_s"]
        right_span = right["interval_s"]
        if left_span[0] < right_span[1] and right_span[0] < left_span[1]:
            continue
        pairs.append((left, right, float(right["value"]) - float(left["value"])))
    return pairs


def _level_principle(records: list[dict]) -> dict | None:
    if not any(item.get("id") == "ev:t02:rms-1s" for item in records):
        return None
    levels = [item for item in records if str(item.get("id", "")).startswith("ly:level:")]
    if len(levels) < 2:
        return None
    pairs = _level_pairs(records)
    if not pairs:
        return None
    left, right, delta = max(pairs, key=lambda item: (abs(item[2]), -item[0]["interval_s"][0], item[0]["id"]))
    if abs(delta) < LEVEL_CONTRAST_DB:
        return None
    a0, a1 = left["interval_s"]
    b0, b1 = right["interval_s"]
    return {
        "evidence_id": "ly:principle:level-contrast",
        "evidence_class": "interpretive",
        "kind": "principle",
        "name": "level_contrast",
        "value": (
            f"The written intervals {a0:.3f}\u2013{a1:.3f} s and {b0:.3f}\u2013{b1:.3f} s "
            f"differ by {delta:.2f} dB in the mean of stored 1 s RMS values. "
            "Transferable mechanism: a later lyric can change where the full mix already changes level. "
            "This is not singing intensity, vocal performance, or emotion."
        ),
        "unit": "dB",
        "cites": [left["id"], right["id"]],
        "caveat": "lyrics-v1 reports this only at or above 1.00 dB of stored full-mix RMS means.",
    }


def _level_reason(records: list[dict]) -> str:
    if not any(item.get("id") == "ev:t02:rms-1s" for item in records):
        return _LEVEL_TEMPLATES["absent"]
    levels = [
        item
        for item in records
        if str(item.get("id", "")).startswith("ly:level:") and item.get("value") is not None
    ]
    if len(levels) < 2:
        return _LEVEL_TEMPLATES["few"]
    pairs = _level_pairs(records)
    if not pairs:
        return _LEVEL_TEMPLATES["overlap"]
    delta = max(abs(item[2]) for item in pairs)
    return (
        "No level-contrast principle. "
        f"The largest stored 1 s RMS mean difference is {delta:.2f} dB, "
        "under the 1.00 dB lyrics-v1 gate."
    )


def _insufficient(records: list[dict], principles: list[dict]) -> list[dict]:
    names = {row["name"] for row in principles}
    rows = []
    if "written_repetition" not in names:
        repeats = [item for item in records if str(item.get("id", "")).startswith("ly:repeat:")]
        reason = _REPEAT_REFUSAL
        if repeats:
            reason = (
                "No written-repetition principle. "
                "The cited repetition record is not a finding in this chart."
            )
        rows.append({"code": "written_repetition", "reason": reason, "cites": []})
    if "level_contrast" not in names:
        rows.append({"code": "level_contrast", "reason": _level_reason(records), "cites": []})
    present = {item.get("id") for item in records}
    cites = {
        "tempo": ["ev:pulse_candidate_bpm"] if "ev:pulse_candidate_bpm" in present else [],
        "melody": ["ev:t09:similarity"] if "ev:t09:similarity" in present else [],
        "section": ["ev:t08:provisional-change"] if "ev:t08:provisional-change" in present else [],
        "vocal": [],
        "emotion": [],
        "instrumentation": [],
    }
    for code, reason in _FIXED_REFUSALS:
        rows.append({"code": code, "reason": reason, "cites": cites[code]})
    return rows
