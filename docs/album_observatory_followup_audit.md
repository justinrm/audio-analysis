# Album Observatory follow-up audit

Snapshot of the working tree at `4d1e71b`, including the then-uncommitted lyrics workspace, SQLite statement lock, and `.gitignore` rule. It is not an acceptance decision. Sentences below about what was uncommitted describe that snapshot.

Verification and preparation only. No application code was changed. The T02 stored-sample experiment is specified below and was not implemented.

Browser and assistive-technology checks were not run. Conclusions about hover tooltips, playback lag, and screen-reader behavior are from source inspection unless a test is named.

## 1. Executive recommendation

Keep the accepted stack and the split between Technical Analysis and Lyrics & Inspiration. Do not import Album Observatory code, data, or its free-text confidence vocabulary.

The earlier review’s main frontend claim still holds, with a tighter reading of the chart code: the analyzer publishes a playback time and draws it as a mark line, and it does not show the nearest stored T02 point. A T02-only readout of stored chart-document points would add information the evidence panel does not show. It is feasible without a new dependency, a new measurement, or a change to `m1-v3`. It is not redundant with the current evidence panel. Whether the default ECharts item tooltip already shows a raw point on hover was not checked in a browser; that tooltip is not configured, and it is not a keyboard readout.

Do not build the readout until you approve the experiment in section 8.

`references/album-observatory/` is private research, untracked, and absent from history. This working tree now ignores that directory. The ignore is not committed. `HEAD` still has no rule for it.

## 2. Verified repository state

`HEAD` is `4d1e71b` on `main`. `git remote -v` lists `origin` as `https://github.com/justinrm/audio-analysis.git`. Local `main` is ahead of `origin/main` by `a387bb2` and `4d1e71b`. Nothing was fetched, pushed, or committed in this session.

The committed rule in `.cursor/rules/project.mdc` names the architecture: React 19, TypeScript, Vite, WaveSurfer, ECharts, Python 3.12, FastAPI, FFmpeg, NumPy, SciPy, SQLite, and local files. `frontend/package.json` pins `echarts` 6.1.0 and `wavesurfer.js` 8.0.2. `backend/app/measure.py` sets `ALGORITHM_VERSION = "m1-v3"`.

Checks run against the working tree, which includes uncommitted M2-B and the SQLite statement lock:

| Check | Result |
|---|---|
| `backend/`: `uv run ruff check .` | Passed |
| `backend/`: `uv run pytest -q` | 58 passed, 4.39s. One Starlette warning: `httpx` with `starlette.testclient` is deprecated. |
| `frontend/`: `pnpm typecheck` | Passed |
| `frontend/`: `pnpm test` | 4 files, 31 tests passed |
| `frontend/`: `pnpm build` | Passed. The JS chunk is about 1.45 MB. Vite warned that it is over 500 kB. |

No browser session was opened.

### Capability classification

| Capability | Class | Evidence |
|---|---|---|
| WAV ingest, SHA-256, byte-identical master, 16-bit playback from the blob, 24-bit triangular-dither derivative, derivative failure keeps the master | Implemented and verified by pytest. Not re-checked in a browser. | `backend/tests/test_milestone0.py`: `test_pcm16_metadata_and_hash`, `test_pcm24_derivative_preserves_master`, `test_derivative_failure_keeps_master`, `test_range_request`, `test_hostile_filename_is_not_a_path`, `test_duplicate_import_reuses_blob` |
| Analyze returns 202 and does not measure in the request; worker writes charts; one chart failure leaves the others | Implemented and verified by pytest | `backend/tests/test_milestone0.py` `test_analyze_enqueues_without_running`; `backend/tests/test_milestone1.py` `test_worker_completes_charts_and_keeps_the_master`, `test_a_failed_chart_does_not_hide_the_others`, `test_interrupted_job_can_be_retried` |
| WaveSurfer transport, seek, waveform from `playback_minmax_envelope_v1`, shared playhead on file-time charts | Implemented. Vitest covers the playhead handoff with a mocked WaveSurfer. Real audio, drag-seek, and zoom were not browser-checked. | `frontend/src/analyzer.tsx` `Transport`; `frontend/src/playback.test.tsx`; `frontend/src/chart.test.tsx` “moves a playhead on file-time axes without rebuilding the chart” |
| T01–T10 chart documents and PNG files | Implemented and verified by pytest for the measurement and document contracts those tests name. Interactive rendering is Vitest against a mocked ECharts, plus source inspection. | `backend/app/charts.py` `KINDS`; `backend/tests/test_milestone1.py`; `frontend/src/chart.tsx`; `frontend/src/catalog.ts` |
| `m1-v3` cache | Implemented and verified | `ALGORITHM_VERSION` in `backend/app/measure.py`; `test_corrected_measurements_are_not_served_as_m1_v2`; cache path `analysis/{sha256}/m1-v3/` via `backend/app/pipeline.py` `analysis_dir` |
| Evidence class separate from status | Implemented. Chart UI prints both. Canonical `EvidenceRef` is a backend response the technical panel does not fetch. | `frontend/src/analyzer.tsx` evidence aside; `frontend/src/catalog.test.tsx`; `backend/app/main.py` `ChartDocument` and `project_evidence` |
| M2-A lyric storage, timing origin, validation, annotations, canonical evidence, analysis cache left unchanged | Implemented at `4d1e71b` and covered by `backend/tests/test_lyrics.py`. The concurrent-read test is an uncommitted addition and passed with the rest. | `backend/app/lyrics.py`, `backend/migrations/003_lyrics.sql`, routes in `backend/app/main.py` |
| M2-B lyric workspace: edit TXT/Markdown/SRT, regions, verification, notes, shared transport | Implemented in the working tree. Vitest passed. Not browser-checked. Not accepted. | Untracked `frontend/src/lyrics.tsx`, `frontend/src/lyrics.test.tsx`; modifications in `frontend/src/analyzer.tsx`, `frontend/src/api/client.ts` |
| SQLite statement lock for overlapping lyric reads | Implemented in the working tree and covered by `test_concurrent_lyric_gets_return_the_same_document`. Not a milestone. | `backend/app/db.py` |
| M2-C / L01–L05 | Specified, not implemented | `docs/superpowers/plans/2026-10-13-milestone-2.md`. No `lyric_charts.py` or `lyric-charts.tsx`. Lyric aside says inspiration charts are not in this slice (`frontend/src/lyrics.tsx`). |
| Technical, Lyricist, and Combined ZIP export; narrative client | Specified, not implemented. Per-chart PNG exists. | `test_narrative_and_export_routes_are_absent` expects 404. `GET /api/assets/{id}/charts/{kind}/image` in `backend/app/main.py`. |
| Album QC / T11 | Specified. The route is an empty state. | `frontend/src/App.tsx` album page. `docs/04_TECHNICAL_CHART_REQUIREMENTS.md` T11. |

`Audio_Reference_Studio_Project_Context.md` is not in the tree. `graphify-out/` is not in the tree.

## 3. Milestone reconciliation

There is no decision-log file. Acceptance text lives in `.cursor/rules/project.mdc` and in older handoffs that disagree with it.

| Record | What it says | How to treat it |
|---|---|---|
| `docs/03_CURSOR_AGENT_FIRST_SESSION.md` | Historical Milestone 0 session. Stop at Milestone 0 acceptance. | Historical. It does not record that acceptance. |
| `NEXT_SESSION.md` | Milestone 1 remediation at `m1-v2` is waiting for the owner. Do not start Milestone 2. Chart zoom was not clicked in the browser. | Outdated. `HEAD` is `m1-v3` and already contains M2-A. |
| `docs/README.md` | Next decision is to approve the plan. | Outdated relative to the commits after it. |
| Committed `.cursor/rules/project.mdc` at `4d1e71b`, blame author Justin Merwin | Milestone 0 is `e4f1223`. Milestone 1 is accepted at `a387bb2` (`m1-v3`, T01–T10). M2-A lyric evidence is authorized. Do not start M2-B, M2-C, ZIP export, album comparison, or a narrative client unless asked. | Strongest committed status record. It calls Milestone 1 accepted. It calls M2-A authorized, not accepted. |
| Uncommitted edit to that same rule | M2-A is accepted at `4d1e71b`. M2-B is in the working tree and is not accepted. | Working-tree claim. This audit does not treat it as a new owner decision. |
| Commit messages | Implementation descriptions. Several are co-authored by Cursor. They do not say “owner accepted.” | Implementation records, not a separate approval. |

Implemented versus accepted:

- Milestone 0 code is on `e4f1223` and still covered by `test_milestone0.py`. A standalone owner-approval note was not found. The later committed rule treats that commit as Milestone 0 and treats Milestone 1 as accepted.
- Milestone 1 is implemented at `a387bb2` and recorded as accepted in the committed rule. This session did not repeat a listening or browser acceptance.
- M2-A is implemented and committed at `4d1e71b`. The committed rule authorizes it. An acceptance sentence exists only in the uncommitted rule edit.
- M2-B is uncommitted source plus Vitest. It is not accepted. The committed rule says not to start it unless asked. It is already in the tree; this session left it in place.
- M2-C, ZIP export, narrative, and Album QC/T11 are not started, matching the committed rule.

## 4. Private-data Git safety

The previous review’s path mismatch is real.

| Path | State |
|---|---|
| `references/album-observatory/` | Present. Untracked. Not in any commit (`git log --all` for that path is empty). Not staged. |
| `research/references/album-observatory/` | Absent. |

At the start of this session the uncommitted `.gitignore` ignored the absent path. `HEAD` ignored neither path. `git check-ignore` did not match the real directory, and `git status` listed it as untracked. `references/legacy-audit/` stays tracked; the new rule does not match it.

Corrective action, uncommitted: `.gitignore` now contains `references/album-observatory/`.

After that edit:

- `git check-ignore -v references/album-observatory` matches `.gitignore:49`.
- `git status --ignored --short` shows `!! references/album-observatory/`.
- `git ls-files` for that path is empty.

No history rewrite, no deletion, no commit, and no push. Private file contents were not opened and are not quoted.

Remaining risk: the ignore exists only in this working tree. A checkout of `HEAD`, or a commit that adds files without this `.gitignore` hunk, can still pick up the directory. `git add -f` would also override the ignore. Commit the ignore rule before any broad `git add` if you want the protection on `HEAD`.

## 5. Assessment of the earlier recommendations

The review at `docs/album_observatory_reference_review.md` was re-read against current source. Its private analytical files were not reopened.

| Earlier claim | Finding |
|---|---|
| Nearest stored sample is missing | Supported. `ChartView` seeks from a click’s converted x value and draws the playhead at playback time. It does not look up `series.lines[].y`. |
| ECharts tooltip already names the stored point | Not established. `optionFor` in `frontend/src/chart.tsx` sets no chart tooltip. The playhead series sets `tooltip: { show: false }`. ECharts 6’s default in `frontend/node_modules/echarts/lib/component/tooltip/TooltipModel.js` is `show: true`, `trigger: 'item'`, `triggerOn: 'mousemove\|click\|mousewheel'`. Item content comes from the series data index (`seriesFormatTooltip.js`), which for these lines is the stored `[x, y]` pair. There is no formatter for unit, window, evidence class, or caveat. `showSymbol: false` makes it uncertain whether a hover target appears. That needs a browser check. |
| Playback time is shared | Supported. `Transport` listens to WaveSurfer `timeupdate` and calls `onTime`. `Analyzer` stores that number as `playhead` and passes it to `TechnicalBoard`, `ChartView`, and `LyricsWorkspace`. Chart clicks and review-marker buttons call `onSeek`, which calls `wave.setTime`. The Seek range does the same. |
| Sample values come from chart documents | Supported for rendering. Line data is `line.x.map((x, i) => [x, line.y[i]])`. The browser does not compute loudness. The technical panel does not call `GET /api/assets/{id}/evidence` or the project canonical-evidence route. |
| Timestamps, windows, and resolution | T02’s 1 s RMS times are frame centers from `_frame_power`: `(index + 0.5) * frame / rate`, with `frame = round(rate * 1.0)` and a dropped trailing partial frame (`backend/app/measure.py`). The 3 s series stores FFmpeg `pts_time` for frames with `time >= 3` and `S > -70` (`parse_ebur128`). Quieter short-term frames are omitted, not stored as null. `build_t02` leaves `hop_s` null. The series name is the only window label on the document. `hop_s`, `sample_rate`, `time_start_s`, and `time_end_s` are written on some chart files and are not fields of the generated `ChartDocument` type. T02 is not a decimated view of a denser T02 series. The 100 ms RMS series is on T01. |
| Evidence inspector already shows the same information | The technical aside shows `evidence_class`, `method_id`, `method_version`, summary strings, and caveats. It does not show a playhead sample, a sample timestamp, an evidence id, or an interval. The lyric aside shows timing origin and notes on the cue, and its Evidence block is the word “textual” plus a sentence that timing is not measured from the audio. |
| Keyboard access to chart measurements | Partial. The Seek range, review-marker buttons, lyric jump buttons, and lyric forms are native controls. The chart node is `role="img"` with `aria-label` set to the chart title and has no key handler. |
| Accessible data table | Specified in `docs/04_TECHNICAL_CHART_REQUIREMENTS.md` (“chart alternative data table”, “keyboard seek controls”). No table is rendered. Chart JSON and per-chart PNG are the data and image outputs. |
| Waveform zoom synchronized with ECharts data zoom | Not implemented. WaveSurfer is created without a zoom setting. ECharts `dataZoom` links file-time axes inside one chart. T01 additionally swaps overview and detail envelope series when the zoomed span is under 99.5%. That zoom does not move the waveform or the lyric list. |
| Chart interaction causes extra renders or playback lag | Not browser-measured. Source: the ECharts instance is created in an effect that depends on `chart`, and playhead updates call `setOption` only for the mark-line series. Vitest asserts the chart is not re-initialized when `playhead` changes. `setPlayhead` still re-renders `TechnicalBoard` and, once the lyric panel has been opened, `LyricsWorkspace` on each `timeupdate`. |
| M2-A/M2-B already cover the lyric workspace, and L01–L05 are not started | M2-A is committed. M2-B is uncommitted and unaccepted. L01–L05 are not started. The review’s “accepted product” paragraph overstates M2-B. |
| Keep Technical Analysis and Lyrics & Inspiration co-equal | The working tree still has both tabs. Album QC remains an empty state. |

## 6. Adopt / experiment / defer / reject

| Item | Decision | Why |
|---|---|---|
| Ignore `references/album-observatory/` | Adopted in the working tree | The real directory was committable. Commit the rule before a broad add. |
| T02 stored-sample inspector | Experiment, after approval | Adds the stored point, its unit, and the sample-time versus playback-time distinction. Limited to T02. |
| One evidence receipt that still shows class, timing origin, and listening status as separate fields | Defer | The fields already exist on `EvidenceRef`, `ReviewMarker`, and lyric segments. The technical panel does not load them. A receipt is presentation work beyond the T02 experiment. |
| Shared time-window controller | Defer | Seek and playhead are already shared. Zoom is not. L01 is the point where a shared window has a chart region to attach to. |
| Keyboard path to the T02 sample | Include in the T02 experiment | Text in the evidence column, driven by the existing Seek control. No second slider. |
| Full alternative data table for every chart | Defer | Required by the chart contract, larger than this experiment, and not a reason to block the T02 readout. |
| Milestone 4 comparison rules as a written constraint | Defer | Valid later. Writing them is not this session, and building T11 is not authorized. |
| Album Observatory runtime, `album.json`, or SVG charts | Reject | Different renderer and a client-held album document. |
| Free-text confidence as a stored field, or one collapsed score | Reject | `evidence_class`, chart `status`, `timing_origin`, and listening checkpoints stay separate. |
| Emotional, motif, or similarity views in the analyzer | Reject | Out of the current milestones and outside the evidence rules. |
| Changing DSP, `m1-v3`, or the chart cache to feed the inspector | Reject | The inspector must read the loaded T02 document only. |

## 7. Three frontend opportunities

### A. Playhead-linked sample inspector

Worth a T02 experiment. The evidence panel answers “how was this chart made?” The missing answer is “which stored point is nearest the playhead?”

T02 is a poor place to show one number. A ready document can contain:

- `1 s RMS` in dBFS, one sample per non-overlapping 1 s frame, timestamp at the frame center, last partial frame omitted.
- `3 s short-term LUFS`, irregular `pts_time` values, frames at or below −70 LUFS omitted.
- Category bars of relative RMS-power versus the file, labeled as time ranges. Those bars are not playhead samples. The playhead is not drawn on that category axis.

A 1 s RMS point and a 3 s LUFS point at different stored times are both valid. The inspector should list each line series. It should not blend them, and it should not read T01’s 100 ms RMS or `metrics.json`.

The default item tooltip, if it appears on hover, can show a raw data pair for one hovered series. It does not show evidence class, the other series, playback time as a separate figure, or a keyboard-reachable value. The readout would not be a second copy of the evidence panel.

### B. Consolidated evidence receipt

The current technical panel already shows class, method, version, summary, and caveats for the selected chart. It does not show evidence id, a numeric interval, timing origin, review/listening status, or artist notes. Those live on other objects:

- `EvidenceRef` and `CanonicalEvidence` from `GET /api/projects/{project_id}/assets/{asset_id}/evidence`.
- `ReviewMarker` on the chart document, already rendered as seek buttons with an optional caveat.
- Lyric `timing_origin`, `artist_verified`, segment note, and annotation rows in the lyric workspace.

A receipt can place those fields in one column. It must not average them into a score, and it must not add a schema. The lyric Evidence block is still only “textual”. That gap is real and larger than T02. It should wait until the T02 experiment is accepted or rejected, so the technical column is not redesigned twice.

### C. Coordinated time navigation

Already shared: playback time, chart click seek on a file-time axis, review-marker seek, the Seek range, lyric-region edits, and lyric jump buttons. `activeSegmentId` follows the playhead.

Not shared: ECharts `dataZoom`, WaveSurfer visible range, and lyric-list scroll. The waveform has no zoom control. A shared window controller would be new behavior. It is not justified while L01 regions do not exist. Leave it unspecified beyond this gap.

## 8. T02 experiment proposal

Question: does naming the nearest stored T02 point, separately from playback time, make the loudness chart easier to check, without looking like a new measurement?

Recommendation: yes, run it after approval. It is not already implemented. Stop if a browser pass shows that the only new text repeats an existing caveat and the stored value is already obvious from the tooltip and the summary.

### Files

| File | Change |
|---|---|
| `frontend/src/stored-sample.ts` | New pure lookup. No ECharts and no DSP. |
| `frontend/src/stored-sample.test.ts` | Vitest for selection only. |
| `frontend/src/analyzer.tsx` | Render the readout in the technical evidence aside when the selected chart is ready T02. |
| `frontend/src/chart.tsx` | No change. The playhead mark line stays at playback time. |

`ChartView` already receives `playhead` and the `ChartDocument`. Keeping the lookup out of `setOption` is what protects the chart from extra renders.

### Contract to reuse

Use the loaded `ChartDocument` only: `series.lines[]` (`name`, `unit`, `x`, `y`), `evidence_class`, `method_id`, `method_version`, `status`. Types are the generated ones in `frontend/src/api/types.ts`.

Do not read `hop_s`. T02 leaves it null, and the generated type does not declare it. Do not add an OpenAPI field in this experiment. The measurement window shown to the user is the series name (`1 s RMS` or `3 s short-term LUFS`). The document does not store a per-point window start and end. Do not derive a window by subtracting neighboring timestamps: for short-term LUFS that spacing is the FFmpeg frame hop, while the series name says the window is 3 s. For 1 s RMS the spacing matches the frame length, and the stored time is the center, not the window edge.

Ignore `series.bars`. They stay in the existing summary.

Do not call `/metrics`, `/evidence`, or the T01 document.

### Selection

For one line series and a finite playback time:

1. If `x` is empty, or `x.length !== y.length`, that series is unavailable.
2. Consider only indexes whose `x` value is finite.
3. Choose the minimum `abs(x - playbackTime)`. Tie: keep the earlier index. This matches `nearestIndex` in `frontend/src/chart.tsx`, which updates the best index only when the distance is strictly smaller.
4. The displayed value is `y` at that index. Never a weighted mix of two points.
5. If that `y` is `null`, `NaN`, or non-finite, show the stored time and an empty value. Do not walk to a neighboring finite `y`.
6. If playback time is below the first finite `x` or above the last, still show that endpoint and say the playback time is outside the stored samples.
7. Repeat independently for every line series. A missing short-term series stays absent. Do not invent a LUFS value.
8. If playback time is `null`, show that playback time is not available yet. Do not pretend the first sample is current.
9. If no series yields a finite stored time, show an empty state: no stored T02 sample.

Omitted short-term frames (`S <= -70`) are gaps in `x`. The nearest stored point may be far from the playhead. Showing both times is the honest behavior. Filling the gap is not.

### Accessibility

Put the readout in the evidence aside as text: series name, value, unit, stored sample time, playback time, evidence class, method id, method version, and one fixed sentence that this is a stored chart point. Caveats stay the paragraphs the aside already prints.

The existing Seek range is the keyboard control. Do not add a second range. Do not set `aria-live` on the readout. `timeupdate` fires for the whole time the transport is playing, and a live region would talk continuously. A screen-reader user can read the text when they move to the aside. The chart canvas stays `role="img"` and is not the place the value lives.

A full data table is out of this experiment.

### Render and performance

Compute the lookup during render of `TechnicalBoard` from `playhead` and `document`. That component already re-renders when `playhead` changes. Do not call `echarts.setOption` from the lookup. Do not put the result in `ChartView` state. The existing playhead test must still see a single `echarts.init` when the playhead moves.

T02 line lengths are on the order of the duration in seconds, plus short-term frames. A linear scan per `timeupdate` is enough. No index cache.

### Tests

`frontend/src/stored-sample.test.ts`:

- Times `0.5, 2.5, 10` at playback `2.0` return `2.5` and that point’s `y`, not `1.5` or an interpolated y.
- Equal distance between index 0 and index 1 keeps index 0.
- Playback before the first time and after the last returns the endpoint and an outside flag.
- Nearest `y` of `null` stays empty and does not use the next finite y.
- Non-finite `y` stays empty.
- Unequal `x` and `y` lengths are unavailable.
- Two series with different times each return their own nearest point.
- Empty lines return the empty state.

One render test in the existing analyzer/catalog style: a T02 document shows both series names, the stored time, the playback time, and `measured`, and does not show a midpoint value. The chart playhead test stays as it is.

Backend pytest does not need a new case. The experiment does not change HTTP, DSP, or cache bytes.

### Browser checks after implementation

These are acceptance checks for the implementation session, not results from this one.

- On a ready T02, pause, move Seek, and confirm each displayed number equals a point in the chart JSON.
- Confirm a time between two RMS samples shows the nearer sample’s time, and the playback clock shows the other time.
- Confirm a file with no short-term series does not show a LUFS row.
- Play for several seconds: audio continues, and the chart canvas is not recreated.
- Tab to Seek and change it from the keyboard. The aside text updates.
- Switch to T01. The T02 readout is gone. Seek, chart click, and the lyric tab still work.

### Stop and rollback

Stop if the readout requires a new dependency, an OpenAPI change, a read of `metrics.json`, interpolation, or a `setOption` on every `timeupdate` beyond the current mark line. Stop if the browser pass shows the readout only repeats the summary and the caveats.

Rollback is deleting `frontend/src/stored-sample.ts`, its test, and the aside block in `frontend/src/analyzer.tsx`. `m1-v3` files stay untouched.

### Acceptance criteria

1. The displayed value is exactly one stored T02 `y`, copied from the loaded document.
2. No interpolation and no DSP.
3. Stored sample time and playback time are both labeled.
4. Series name, unit, chart `evidence_class`, `method_id`, and `method_version` are shown. The series name is the window label. A numeric window interval is not invented.
5. No finite stored time, a null or non-finite `y`, or a missing series produces an empty value for that series.
6. Playback, seek, chart click, and chart zoom code paths are unchanged.
7. Keyboard users can move Seek and read the aside. The value is not only inside the canvas.
8. Playhead updates do not re-initialize ECharts.
9. `m1-v3` documents and cache keys are unchanged.
10. No new frontend dependency.

## 9. Unresolved questions

- No browser or assistive-technology pass. Default item-tooltip visibility with `showSymbol: false` is unverified.
- No separate owner-approval document for Milestone 0, Milestone 1, or M2-A. The committed rule is the only acceptance sentence, and it accepts Milestone 1 while only authorizing M2-A.
- Whether FastAPI’s `ChartDocument` response (`extra: allow`) still emits `hop_s` on the wire was not probed. The experiment does not need that field.
- FFmpeg `pts_time` is stored as the short-term x value. The chart file does not say whether that instant is the start, center, or end of the 3 s window.
- Playback smoothness under `timeupdate` was not measured.
- `origin` is configured and `main` is two commits ahead. This session did not check whether the remote received them. The committed project rule still says the repository has no git remote.
- The working tree contains M2-B and the SQLite lock. This audit did not review that diff for defects. Tests above include it.

## 10. Decisions requiring owner approval

1. Commit the `.gitignore` rule for `references/album-observatory/` before any add that could include that directory. This session did not commit it.
2. Approve or reject the T02 experiment in section 8. Implementation waits on that approval.
3. Say whether M2-A at `4d1e71b` is accepted. The committed rule only authorizes it. The uncommitted rule claims acceptance.
4. Say what to do with the uncommitted M2-B workspace. It is not accepted. This session did not revert it and did not continue it.
5. Leave M2-C, ZIP export, narrative, and Album QC/T11 unstarted.
