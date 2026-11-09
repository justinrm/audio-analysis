# Milestone 4 Album QC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan as one assignment. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an Album QC workspace that orders existing recordings, compares stored `m1-v3` measurements, records human listening statuses, and exports one deterministic report.

**Architecture:** An album is a project with `mode = "album"`. Membership points at existing asset rows and does not copy WAV bytes. T11 is built on read from stored chart JSON, the same way L01–L05 are built on read. Listening statuses are the only new persisted album facts. The report reuses the current ZIP publication pattern. `m1-v3` is not rewritten.

**Tech Stack:** React 19, TypeScript, Vite, ECharts, Python 3.12, FastAPI, Pydantic, SQLite, Matplotlib, stdlib `zipfile`. No new dependency.

**Spec:** [MVP specification](../../01_TECHNICAL_MVP_SPEC.md) Screen E, §4A item 8, §7 comparison route, and Milestone 4; [chart requirements](../../04_TECHNICAL_CHART_REQUIREMENTS.md) T11; [decision register](../../OPEN_DECISIONS_AND_UNCERTAINTIES.md) G3 and G6. [PROJECT_STATUS.md](../../../PROJECT_STATUS.md) owns acceptance. This plan does not authorize implementation.

## Global Constraints

- `ALGORITHM_VERSION` stays `m1-v3`. T01–T10 methods and stored files stay unchanged.
- Comparison version is `album-qc-v1`. Report version is `album-report-v1`. Neither is an analysis version.
- Do not decode a WAV, call `measure.py`, or write `analysis/{sha256}/m1-v3/` from an album route.
- Do not copy, move, or rewrite `blobs/{sha256}`.
- A comparison is `ready` only when at least two tracks are included. Track count is not fixed at four or eight.
- LUFS, LU, dBFS, dB, dBTP, ratio, BPM, and percentage points stay separate. Never subtract across units or across the FFmpeg true peak and the 4× reconstructed peak.
- Do not resample, interpolate, z-score, or renormalize a series to build a common baseline.
- Do not overlay the stored Welch PSD. Its unit remains `dB` (G3), and frequency grids are not a shared axis.
- A checklist status is a human attribution. The server never writes `confirmed_issue` by itself.
- No quality score, mastering grade, or instruction to change a master.
- No narrative provider, NVIDIA NIM, cloud, account, or new audio library.
- Regenerate `frontend/src/api/types.ts` with `uv run python scripts/export_openapi_types.py`. Do not hand-edit it.
- Technical Analysis and Lyrics & Inspiration keep working for one recording, including a recording with no lyrics.

## Review Focus

These are the failures most likely to reach a person using the workspace. Each one has a test on the unit that owns it.

1. Loudness and level drawn or subtracted on one axis. A person expects LUFS and dBFS on separate scales, and expects no “difference” between them.
2. A mono recording shown as stereo correlation `0` or given an invented right channel. A person expects `not_applicable` and no T05 number.
3. One unanalyzed or short recording removing the others from the album. A person expects that recording listed with a reason, and the completed neighbors still compared.
4. Reorder, review, or export changing master bytes or `m1-v3`. A person expects the same blob and the same `metrics.json`.
5. A true-peak, silence, or level-spread fact arriving already marked as a confirmed issue. A person expects `unchecked` until they choose a status.

---

## 1. Current reusable components and verified gaps

Inspected at `6c4bb85`. Album QC is still the empty state in `frontend/src/App.tsx`.

| Need | Reuse | Gap |
| --- | --- | --- |
| One master per hash | `assets.sha256` is unique. Upload inserts `project_assets` and does not copy an existing blob. | No route adds an existing asset id to a second project. |
| Order | `project_assets.ordering`, read by `ORDER BY ordering, created_at`. | Nothing edits that order after insert. `projects.mode` allows only `study`. |
| Analysis availability | `assets.analysis_status` and `analysis/{sha256}/m1-v3/metrics.json`. | No album view reads them together. |
| Level, loudness, crest | T01 summary: Sample peak, Whole-file RMS, Crest factor. T02 summary: Integrated loudness, Loudness range, FFmpeg true peak. T02 lines: `1 s RMS` in dBFS, `3 s short-term LUFS` in LUFS. | No cross-track reader. |
| Spectrum | T03 bars are eight band percentages. The top band ends at that file’s Nyquist. The PSD line is `dB`, not dB/Hz. | No shared-grid overlay exists, and none should be invented. |
| Stereo | T05 summary correlation, side/mid dB, mono fold-down dB, sub-120 Hz correlation. Mono chart status is `not_available`. | No album row for that status. |
| Rhythm | T06 bars, evidence class `estimated`. | Must stay labeled provisional. |
| Endings | T10 summary, `silence` intervals `{start_s, end_s}`, rail count, endpoint, 4× reconstructed peak. | Distinct from the FFmpeg true peak. |
| Charts | ECharts `ChartView` splits T02 and L03 into dBFS and LUFS panels. Each line already carries its own `[x, y]` pairs. `seriesPaint` colors every dBFS line the same. | T11 must join that split and color tracks by series index. |
| PNG | `render_figure` splits T02 the same way. `_paint` also uses one dBFS color. G6 drops bar panels when a line series is present. | T11 is a line document only. Do not add bars to it. |
| Export | `exports.py` writes a temp ZIP, checks membership and content hash, replaces `exports/{id}.zip`, then inserts SQLite. Content hash covers chart JSON, metrics, evidence, and `brief.md`. It excludes the manifest, README, `created_at`, and PNG bytes. | `export_runs.profile` does not include an album, and `asset_id` is required. Leave that table alone. |
| Playback | `/api/assets/{id}/stream` and `/peaks`, one WaveSurfer in the analyzer. | Album audition uses those URLs for the selected asset. It does not add a second player per track. |
| Library | `POST /api/projects` with a name, always stored as `study`. | Album creation needs `mode`, and the library must ignore album rows. |

Rejected from the Album Observatory notes: a client-held album document, SVG charts, PCA, z-scores, motif or emotion charts, and a gapless album timeline. Those notes are research. They are not a schema to import.

## 2. Proposed T11 data and API contracts

`album-qc-v1` reads files. It does not measure.

```python
COMPARISON_VERSION = "album-qc-v1"
REPORT_VERSION = "album-report-v1"

def summary_number(document: dict, label: str) -> float | None:
    for item in document.get("summary") or []:
        if item.get("label") == label and item.get("value") not in {"undefined", "none"}:
            token = str(item["value"]).split()[0]
            try:
                return float(token)
            except ValueError:
                return None
    return None
```

`GET /api/projects/{id}/comparison?x=seconds|progress`

`x` defaults to `seconds`. Unknown values return 400 `invalid_x`. A study project returns 404 `not_album`.

Response `ComparisonDocument`:

| Field | Values |
| --- | --- |
| `comparison_version` | `album-qc-v1` |
| `project_id`, `name` | the album project |
| `status` | `ready` when at least two tracks are included; otherwise `not_available` |
| `not_available_reason` | `need_two_recordings` or null |
| `x_mode` | `seconds` or `progress` |
| `tracks` | album order, including omitted tracks |
| `pairs` | same-unit deltas for included tracks, combinations in order, not a fixed matrix |
| `spectral_distances` | one row per pair |
| `panel` | one `ChartDocument` with `chart_kind` `T11`, or null when not `ready` |
| `caveats` | the fixed sentences below |

Each track:

| Field | Rule |
| --- | --- |
| `ordering` | `0..n-1` |
| `asset_id`, `original_name`, `sha256` | the asset row |
| `duration_s`, `sample_rate`, `channels`, `analysis_status`, `playback_status` | the asset row |
| `algorithm_version`, `params_hash` | from `metrics.json`, else null |
| `included` | true only when `analysis_status` is `completed`, `metrics.json` says `algorithm_version` `m1-v3`, and T01, T02, and T03 JSON exist |
| `omit_reason` | `analysis_incomplete`, `unsupported_analysis_version`, or `chart_missing`; null when included |
| `scalars` | the table below; missing numbers are null, not zero |
| `bands` | T03 bar label and percentage; empty when T03 is absent |
| `pulse` | T06 bar label and autocorrelation, evidence class `estimated` |
| `endings` | endpoint text, tail RMS, silence intervals, rail count, reconstructed peak |

Scalars, in this order, taken from chart summaries:

| Name | Unit | Class | Source label | Method |
| --- | --- | --- | --- | --- |
| `integrated_loudness` | `LUFS` | `measured` | Integrated loudness | `ffmpeg-ebur128` |
| `loudness_range` | `LU` | `measured` | Loudness range | `ffmpeg-ebur128` |
| `sample_peak` | `dBFS` | `measured` | Sample peak | `sample-peak` |
| `rms` | `dBFS` | `measured` | Whole-file RMS | `rms` |
| `crest_factor` | `dB` | `measured` | Crest factor | `crest` |
| `ffmpeg_true_peak` | `dBTP` | `measured` | FFmpeg true peak | `ffmpeg-ebur128` |
| `reconstructed_peak` | `dBTP` | `measured` | 4x reconstructed peak | `4x-reconstructed-peak` |
| `correlation` | `ratio` | `measured` or `not_applicable` | Whole-file correlation | `lr-correlation-1s` |
| `side_mid` | `dB` | same | Side/mid | `lr-correlation-1s` |
| `mono_fold_down` | `dB` | same | Mono fold-down change | `lr-correlation-1s` |
| `sub_bass_correlation` | `ratio` | same | Below 120 Hz correlation | `lr-correlation-1s` |

When T05 status is not `ready`, the four stereo scalars are `not_applicable` and null. Do not read a number from a mono file.

If `metrics.json` `integrated_lufs`, `sample_peak_dbfs`, or `rms_dbfs` differs from the matching summary by more than `0.05`, keep the summary as the displayed value, copy the metrics value onto the scalar as `metrics_value`, and add the caveat `summary_metrics_disagree`. Do not pick one silently.

A pair exists only for two included tracks. `delta` is `right.value - left.value` when both values are non-null, the units match, and the method ids match. Otherwise `delta` is null and `reason` is `missing_value` or `method_mismatch`. There is no pair between `ffmpeg_true_peak` and `reconstructed_peak`.

The T11 panel copies stored T02 lines named `1 s RMS` and `3 s short-term LUFS`, in that order, for each included track in album order. The line name becomes `{ordering + 1}. {original_name} — {stored name}`. In `progress` mode, each x is `x / duration_s` and each y is copied, including nulls. No point is inserted. The panel’s evidence class is `measured`, `method_id` is `stored-m1-v3-series`, and `method_version` is `album-qc-v1`. Its x axis label is `Time (s)` or `Progress (fraction of duration)`. Its caveats are the fixed list. It has lines only, no bars and no heatmap, so the G6 mixed-panel omission cannot drop a T11 series.

Fixed caveats, always present on a ready document:

- `Album order is a listening sequence, not a statement that the recordings form a released album.`
- `Values keep the unit and method stored for that recording. They are not normalized onto a common baseline.`
- `Loudness range is not crest factor. RMS is not loudness. Sample peak dBFS, FFmpeg dBTP, and 4× reconstructed dBTP are different measurements.`
- `Band-share distance is not timbral, musical, or creative similarity. The Welch PSD line is not overlaid.`
- `Pulse candidates are provisional onset-autocorrelation estimates, not a beat grid.`
- `A listening checkpoint is not an audible defect.`
- `Progress mode changes only the x coordinate. It does not resample the series.`

Other routes, album mode only:

| Route | Behavior |
| --- | --- |
| `POST /api/projects` `{name, mode?}` | `mode` defaults to `study`. `album` is the other allowed value. |
| `GET /api/assets` | every asset row, no file bytes |
| `POST /api/projects/{id}/members` `{asset_id}` | link an existing asset. 404 `unknown_asset`. 409 `already_member`. 404 `not_album` for a study. |
| `DELETE /api/projects/{id}/members/{asset_id}` | remove the link and that asset’s review rows. Do not delete the asset or blob. |
| `PUT /api/projects/{id}/order` `{asset_ids}` | the list must be exactly the current members. Rewrite `ordering` as `0..n-1`. |
| `GET /api/projects/{id}/reviews` | stored rows plus derived unchecked rows for applicable checkpoints |
| `PUT /api/projects/{id}/reviews` `{asset_id, checkpoint_id, status, note}` | human status. `note` is at most 500 characters. |
| `POST /api/projects/{id}/album-export` | publish the ZIP |
| `GET /api/projects/{id}/album-exports/{export_id}` | download that ZIP |

`POST /api/projects/{id}/assets` on an album returns 400 `album_does_not_import`. Import stays in a study. The same hash can then be added by asset id, and the blob stays one file.

Study export routes are unchanged.

## 3. SQLite and storage

Migration `backend/migrations/005_album.sql`, applied from `db.py` when `user_version < 5`, with foreign keys off for the rebuild and on again after it. Follow `_migrate_v2`.

```sql
CREATE TABLE projects_v5 (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  mode TEXT NOT NULL CHECK (mode IN ('study', 'album')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

INSERT INTO projects_v5 (id, name, mode, created_at, updated_at)
SELECT id, name, mode, created_at, updated_at FROM projects;

DROP TABLE projects;
ALTER TABLE projects_v5 RENAME TO projects;

CREATE TABLE album_reviews (
  project_id TEXT NOT NULL REFERENCES projects(id),
  asset_id TEXT NOT NULL DEFAULT '',
  checkpoint_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (
    status IN ('unchecked', 'confirmed_issue', 'intentional', 'not_audible')
  ),
  note TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL,
  PRIMARY KEY (project_id, asset_id, checkpoint_id)
);

CREATE TABLE album_export_runs (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES projects(id),
  comparison_version TEXT NOT NULL,
  report_version TEXT NOT NULL,
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 64),
  created_at TEXT NOT NULL
);
```

`asset_id` `''` is the album-level `level_spread` row. Do not add a foreign key from that column to `assets`. The handler rejects an asset id that is not `''` and not a current member.

No new directory for comparison JSON. The ZIP lives at `exports/{id}.zip`, same as a recording export. A crash after the file replace and before the insert can leave an unlisted ZIP. Disclose that. Do not try to make the filesystem and SQLite one transaction.

`export_runs` is not altered.

## 4. Frontend workspace

`/album` lists album projects and creates one. `/album?project={id}` is the workspace. `App.tsx` gains that query on the existing album route. The rail sentence can say the studio also compares a set. The analyzer route stays one recording.

`library.tsx` requests projects and renders only `mode === "study"`. An album name does not open as a study.

`frontend/src/album.tsx`:

- Members in order, with display name, short hash, analysis status, `m1-v3` or the omit reason, duration, rate, and channels.
- Add control fed by `GET /api/assets`. Choosing one calls the member route. No file input on this page.
- Up and down controls call the order route with the full id list.
- A link to `/analyzer?asset={id}&project={albumId}` opens the existing analyzer. Lyric documents stay on the study project where they were saved. Album QC does not copy them.
- One transport for the selected member, using the existing stream and peaks helpers. Playback unavailable stays `unavailable`.
- Scalar tables grouped by unit. Pair rows show a delta only when the API sent one.
- Band table. Distance row shows the number or `band_edges_differ`. No PSD chart.
- Pulse table marked estimated and provisional.
- Ending facts and the checklist.
- Seconds / progress control refetches `?x=`. The T11 `ChartView` is rendered without `onSeek`. The caption says the overlay does not audition a recording.
- Checklist buttons seek: set the selected asset, then seek the stored time through the existing transport. Silence uses `start_s`. Peaks use the stored peak time from the scalar or ending fact.

`lineGroups` treats `T11` like `T02`: dBFS and LUFS are separate groups. `seriesPaint` and `png._paint`, before their unit colors, use the existing four-color palette by series index when `chart_kind` is `T11`, with a solid stroke. The legend is the line name. Colors repeat after four series; the name distinguishes them. T02 colors stay on the T02 branch.

Do not compute a y value in the browser.

## 5. Comparison calculations and scientific caveats

Band distance, only for an included pair:

```python
def band_distance(left: list[dict], right: list[dict]) -> dict:
    if [item["label"] for item in left] != [item["label"] for item in right]:
        return {"status": "not_available", "reason": "band_edges_differ", "value": None,
                "unit": "percentage points", "method_id": "band-share-l1-v1"}
    if not left:
        return {"status": "not_available", "reason": "no_bands", "value": None,
                "unit": "percentage points", "method_id": "band-share-l1-v1"}
    total = sum(abs(a["value"] - b["value"]) for a, b in zip(left, right, strict=True))
    return {"status": "ready", "reason": None, "value": total / 2.0,
            "unit": "percentage points", "evidence_class": "measured",
            "method_id": "band-share-l1-v1"}
```

`total / 2` is the share that would have to move for the two stored percentage lists to match. The percentages are not renormalized. Below-20 Hz stays a separate T03 summary if it is shown in the track table, and it is not part of this sum. Different Nyquist labels (`10000–22050 Hz` versus `10000–24000 Hz`) produce `band_edges_differ` and no number. The en dash in stored labels must be compared as stored.

Parameter-hash mismatch does not drop a track. The track header shows each hash, and the document adds `parameter hashes differ across included recordings`.

Different sample rates do not drop a track. Rate stays on the track. Series are not resampled onto either rate.

Short-file LRA and missing short-term LUFS stay null or absent, with the caveat already stored on T02 copied onto that track. Do not invent a 3 s window.

## 6. Listening-checkpoint persistence

Applicable checkpoints. The GET view synthesizes any missing row as `unchecked` with an empty note. PUT is the only writer.

| Id | Scope | Fact shown | Included when |
| --- | --- | --- | --- |
| `sample_peak` | track | sample peak and its time | track included |
| `ffmpeg_true_peak` | track | FFmpeg dBTP | value is non-null |
| `reconstructed_peak` | track | 4× dBTP and its time | value is non-null |
| `full_scale_rail` | track | full-scale sample count | track included |
| `endpoint` | track | zero or non-zero | track included |
| `tail_level` | track | last stored tail RMS | a tail exists |
| `subthreshold` | track | silence count and intervals, or “no sub-threshold interval stored” | track included |
| `mono_compatibility` | track | correlation, fold-down, sub-120 | T05 is `ready` |
| `level_spread` | album (`asset_id` `''`) | max integrated LUFS minus min, in LU | at least two included loudness values |

Status values: `unchecked`, `confirmed_issue`, `intentional`, `not_audible`. Labels in the page: Unchecked, Confirmed issue, Intentional, Not audible.

PUT returns 400 `checkpoint_not_applicable` when the id does not apply. 400 `invalid_status` otherwise. The measurement text in the response does not change when the status changes.

No cutoff turns a spread, a peak over 0 dBTP, or a silence interval into `confirmed_issue`. The page says a measurement anomaly is not proof of an audible defect.

## 7. Deterministic report and export

`POST` builds the comparison at `x=seconds`, reads the stored reviews, and writes:

```text
manifest.json
comparison.json
album-report.md
charts/T11_album_comparison.png
```

`comparison.json` is the document without `created_at`. `album-report.md` is `render_report(document, reviews)`. It has these headings and no others: Album, Order, Level, Spectrum, Stereo, Dynamics, Rhythm, Endings, Listening review, Methods, Limitations. Each heading interpolates fields from the document. It does not add adjectives about the music.

Methods names `album-qc-v1`, `album-report-v1`, `band-share-l1-v1`, and the per-scalar method ids. Limitations repeat the fixed caveats, state that the application did not listen, and state that PNG bytes are outside the content hash.

Content hash uses the same byte recipe as `exports._content_sha256`, over `comparison.json` and `album-report.md` only. The manifest carries `content_sha256`, `created_at`, `comparison_version`, `report_version`, project id, and `files`. PNG bytes and the manifest are outside the hash, matching the recording packages. Repeating an export from the same charts and reviews keeps `content_sha256`. The ZIP bytes can still differ because `created_at` changes.

Publication: write a temp ZIP, reject a member whose name contains `..` or ends in `.wav`, check the name set and the content hash, `os.replace` to `exports/{id}.zip`, then insert `album_export_runs`. If the PNG renderer fails, the export fails and no ZIP is published. T11 has no bar series, so this does not depend on the G6 omission.

The figure goes through `render_figure` after the T11 branch exists. Do not add a second plotting stack.

## 8. Implementation order

One assignment, four units. Do not start it until the owner authorizes this plan. Cursor Multitask stays off. The document shape, the migration, and the generated types are one path.

### Task 1: Comparison from stored charts

**Files:**
- Create: `backend/app/album.py`
- Test: `backend/tests/test_album.py`

**Interfaces:**
- Consumes: T01–T03, T05, T06, and T10 dicts plus a metrics dict, as stored on disk
- Produces: `compare(tracks: list[dict], x_mode: str) -> dict` with the `ComparisonDocument` fields

- [ ] **Step 1: Write the failing tests**

```python
def track(**overrides) -> dict:
    base = {
        "included": True,
        "channels": 2,
        "duration_s": 4.0,
        "lufs": -14.0,
        "peak": -1.0,
        "correlation": 0.9,
        "bands": [("20–60 Hz", 10.0), ("10000–22050 Hz", 5.0)],
        "rms_x": [0.0, 2.0],
        "rms_y": [-20.0, -10.0],
        "algorithm_version": "m1-v3",
    }
    base.update(overrides)
    return base


# Map each track() into stored T01, T02, T03, and T05 documents in the test.
# compare() reads those documents. It does not accept this flat helper.


def test_pair_keeps_units_apart():
    loud = compare([track(lufs=-14.0, peak=-1.0), track(lufs=-11.5, peak=-3.0)], "seconds")
    delta = {item["name"]: item["delta"] for item in loud["pairs"][0]["deltas"]}
    assert delta["integrated_loudness"] == -11.5 - -14.0
    assert "dBFS" not in {item["unit"] for item in loud["pairs"][0]["deltas"] if item["name"] == "integrated_loudness"}
    assert all(item["name"] != "ffmpeg_true_peak" or item["method_id"] == "ffmpeg-ebur128"
               for item in loud["tracks"][0]["scalars"])

def test_mono_correlation_is_not_zero():
    mono = compare([track(channels=1), track(channels=2, correlation=0.2)], "seconds")
    stereo = next(item for item in mono["tracks"][0]["scalars"] if item["name"] == "correlation")
    assert stereo["evidence_class"] == "not_applicable"
    assert stereo["value"] is None

def test_unanalyzed_neighbor_stays_listed():
    result = compare([track(included=False), track(), track()], "seconds")
    assert result["status"] == "ready"
    assert [item["included"] for item in result["tracks"]] == [False, True, True]
    assert len(result["pairs"]) == 1

def test_band_edges_block_distance():
    result = compare([
        track(bands=[("20–60 Hz", 10), ("10000–22050 Hz", 5)]),
        track(bands=[("20–60 Hz", 12), ("10000–24000 Hz", 4)]),
    ], "seconds")
    assert result["spectral_distances"][0]["reason"] == "band_edges_differ"
    assert result["spectral_distances"][0]["value"] is None

def test_progress_does_not_resample():
    ready = compare([
        track(rms_x=[0.0, 2.0], rms_y=[-20.0, -10.0], duration_s=4.0),
        track(rms_x=[0.0, 1.0], rms_y=[-12.0, -12.0], duration_s=2.0),
    ], "progress")
    line = ready["panel"]["series"]["lines"][0]
    assert line["x"] == [0.0, 0.5]
    assert line["y"] == [-20.0, -10.0]
    assert len(line["x"]) == 2
```

Build the fixtures as chart-document dicts. Do not call `measure`.

- [ ] **Step 2: Run** `uv run pytest tests/test_album.py -q` from `backend/`. Expected: fail because `compare` is missing.

- [ ] **Step 3: Implement** `compare`, `summary_number`, `band_distance`, and the T11 line copy in `album.py`. Three tracks must yield three pairs. Add a test with three included tracks and `assert len(result["pairs"]) == 3`.

- [ ] **Step 4: Run the same pytest.** Expected: pass.

### Task 2: Album project, membership, reviews

**Files:**
- Create: `backend/migrations/005_album.sql`
- Modify: `backend/app/db.py`
- Modify: `backend/app/main.py`
- Modify: `backend/app/album.py`
- Test: `backend/tests/test_album.py`

**Interfaces:**
- Consumes: `compare`
- Produces: the routes in section 2 except export. `Project.mode` is `study | album`. `ProjectCreate.mode` defaults to `study`.

- [ ] **Step 1: Write failing HTTP tests** using `create_app` and `pcm_wav`, as `test_milestone0.py` does.

```python
def test_album_links_existing_asset_without_copying_bytes(client, data_root):
    study = client.post("/api/projects", json={"name": "Study"}).json()
    album = client.post("/api/projects", json={"name": "Album", "mode": "album"}).json()
    uploaded = client.post(f"/api/projects/{study['id']}/assets", files={"file": wav}).json()
    blob = (data_root / "blobs" / uploaded["asset"]["sha256"]).read_bytes()
    linked = client.post(f"/api/projects/{album['id']}/members", json={"asset_id": uploaded["asset"]["id"]})
    assert linked.status_code == 200
    assert (data_root / "blobs" / uploaded["asset"]["sha256"]).read_bytes() == blob
    assert client.post(f"/api/projects/{album['id']}/assets", files={"file": wav}).status_code == 400

def test_review_starts_unchecked_and_does_not_change_the_number(client):
    # two included tracks with fixture chart JSON written under analysis/{sha}/m1-v3/
    reviews = client.get(f"/api/projects/{album_id}/reviews").json()
    peak = next(item for item in reviews if item["checkpoint_id"] == "sample_peak")
    assert peak["status"] == "unchecked"
    saved = client.put(f"/api/projects/{album_id}/reviews", json={
        "asset_id": peak["asset_id"], "checkpoint_id": "sample_peak",
        "status": "intentional", "note": "ends hot on purpose",
    }).json()
    assert saved["status"] == "intentional"
    assert saved["value"] == peak["value"]
    assert saved["unit"] == peak["unit"]
```

Also assert: a third track makes three pair rows; reorder does not change blob or `metrics.json` bytes; a mono member has no correlation value; `GET /api/projects` still returns an existing study.

- [ ] **Step 2: Run the new tests.** Expected: fail on missing routes.

- [ ] **Step 3: Add the migration and routes.** Monkeypatch `app.measure.levels` to raise in the comparison test and assert it is not called.

- [ ] **Step 4: Run** `uv run pytest tests/test_album.py tests/test_milestone0.py tests/test_exports.py -q`. Expected: pass.

### Task 3: T11 figure and album ZIP

**Files:**
- Modify: `backend/app/png.py`
- Modify: `backend/app/album.py` with `render_report` and `publish_album_export`
- Test: `backend/tests/test_album.py`
- Test: `backend/tests/test_png_presentation.py` only if an existing T02 color assertion needs a sibling

**Interfaces:**
- Consumes: `compare` and the review rows
- Produces: `render_report(document: dict, reviews: list[dict]) -> str` and `publish_album_export(...) -> dict`

- [ ] **Step 1: Write failing tests**

```python
def test_album_zip_hashes_report_not_png_and_skips_wav(client, data_root):
    first = client.post(f"/api/projects/{album_id}/album-export").json()
    second = client.post(f"/api/projects/{album_id}/album-export").json()
    assert first["content_sha256"] == second["content_sha256"]
    assert first["export_id"] != second["export_id"]
    with zipfile.ZipFile(data_root / "exports" / f"{first['export_id']}.zip") as archive:
        names = archive.namelist()
        assert not any(name.endswith(".wav") for name in names)
        assert "comparison.json" in names and "album-report.md" in names
        report = archive.read("album-report.md").decode()
    assert "quality score" not in report.lower()
    assert "defective" not in report.lower()
    before = (data_root / "analysis" / sha / "m1-v3" / "metrics.json").read_bytes()
    assert before == (data_root / "analysis" / sha / "m1-v3" / "metrics.json").read_bytes()

def test_t02_dbfs_color_unchanged_and_t11_tracks_differ():
    assert _paint({"chart_kind": "T02"}, {"unit": "dBFS"}, 0)[0] == ENERGY
    first = _paint({"chart_kind": "T11"}, {"unit": "dBFS"}, 0)[0]
    second = _paint({"chart_kind": "T11"}, {"unit": "dBFS"}, 1)[0]
    assert first != second
```

- [ ] **Step 2: Run those tests.** Expected: fail.

- [ ] **Step 3: Add the T11 branches in `render_figure` and `_paint`.** T02’s branch stays `kind == "T02"`. Publish with the temp-file, validate, replace, insert sequence.

- [ ] **Step 4: Run** `uv run pytest tests/test_album.py tests/test_png_presentation.py tests/test_exports.py -q`. Expected: pass.

### Task 4: Workspace and generated types

**Files:**
- Modify: `frontend/src/App.tsx`, `frontend/src/library.tsx`, `frontend/src/chart.tsx`, `frontend/src/chart-format.ts`, `frontend/src/api/client.ts`
- Create: `frontend/src/album.tsx`, `frontend/src/album.test.tsx`
- Generated: `frontend/src/api/types.ts` via the script
- Test: `frontend/src/chart.test.tsx`, `frontend/src/library.test.tsx`

**Interfaces:**
- Consumes: the routes and `ChartDocument` panel
- Produces: the workspace in section 4

- [ ] **Step 1: Regenerate types, then write a failing Vitest** that renders two album tracks, shows LUFS and dBFS under separate headings, shows mono stereo as not applicable, and shows a checkpoint as Unchecked. A second test renders a T11 document and expects two y axes. A library test with one album and one study shows only the study.

- [ ] **Step 2: Run** `pnpm test -- src/album.test.tsx src/library.test.tsx src/chart.test.tsx` from `frontend/`. Expected: fail.

- [ ] **Step 3: Implement the page and the T11 group in `lineGroups`.** `seriesPaint` returns the palette by index for `T11` before the dBFS color. Add the chart-format assertion that a T02 dBFS series stays `SERIES_ENERGY`.

- [ ] **Step 4: Run the same Vitest, then** `pnpm typecheck`. Expected: pass.

- [ ] **Step 5: Run** `scripts/verify.sh` once from the repository root.

Do not commit from this plan unless the owner asks. Do not mark Milestone 4 accepted.

## 9. Backend and frontend regression tests

Beyond the new tests:

- `tests/test_milestone0.py` still creates a study and uploads a WAV.
- `tests/test_exports.py` still publishes technical, lyricist, and combined ZIPs. `export_runs` gains no album row.
- `tests/test_milestone1.py` still sees `ALGORITHM_VERSION == "m1-v3"`.
- A lyric save still does not change `metrics.json`.
- Frontend export, lyric, and chart tests stay green. T02’s dBFS and LUFS split stays in place.
- `pnpm typecheck` fails if a new union member is unhandled. Album route handling needs a `never` check in the route switch.

## 10. Browser QA and real-album acceptance

Automated fixtures are synthetic WAVs from `backend/tests/wavgen.py` plus hand-written chart JSON. They do not need the owner’s masters.

After `scripts/verify.sh`, exercise a disposable data root:

1. Import two stereo tones and one mono tone into a study. Analyze the two stereo tones. Leave the mono tone unanalyzed, then write no cache for it.
2. Create an album. Add all three by the asset list. Confirm one blob directory entry per hash.
3. Reorder. Reload. The order sticks. Open one row in the analyzer and return. The album order is unchanged.
4. Confirm the unanalyzed row has a reason and the two analyzed rows still show LUFS, dBFS, and dBTP in separate columns.
5. Set one peak checkpoint to Intentional. Reload. The number is unchanged.
6. Switch progress mode. The y values in the data table match seconds mode.
7. Download the album ZIP. Its names match the manifest. It contains no WAV. A second download from the same state keeps `content_sha256`.
8. At 1440 px and 390 px, the page stacks and `scrollWidth` equals `clientWidth`.

Real-album acceptance is a later owner decision. The completed eight-song album and the legacy four-song audit may be used only as private local files, and only without modifying masters, hashes, or `m1-v3`. They are not fixtures to commit, and they are not permission to reopen a creative choice. Acceptance of Milestone 4 needs the owner to listen and set checklist statuses. A passing synthetic suite does not accept the milestone.

## 11. Owner decisions

Implementation waits on one decision: the owner authorizes this plan as the Milestone 4 assignment.

No second product decision is open inside that assignment.

- Welch PSD overlay is out. G3 leaves the stored unit as `dB`, and unequal frequency grids would require invented samples. Band-share distance is the spectrum comparison. Putting the PSD on a common grid would be a new measurement and a new version, which this plan does not include.
- Album projects do not import files. Studies do. That keeps one blob per hash.
- The overlay chart does not seek. Checkpoint controls seek the selected recording. One playhead cannot sit on two masters.
- Private album listening is the acceptance gate after the software works. It is not a reason to delay the synthetic tests.

Cursor Multitask stays off for the implementation session. One agent should take the four units in order. Splitting the frontend from the API races the generated types and the comparison document.

The next assignment, after authorization, is: implement this file from Task 1 through Task 4, run `scripts/verify.sh` and the disposable browser pass, and stop before claiming Milestone 4 acceptance.
