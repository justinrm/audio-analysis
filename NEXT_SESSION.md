# Next session

## Start here

Read [PROJECT_STATUS.md](PROJECT_STATUS.md) for the accepted baseline and verification limits. Use the [documentation index](docs/README.md) for the approved requirements.

Milestone 4 Album QC is **accepted** as of November 11, 2026. The accepted implementation is published on `milestone-4-album-qc`, parent `858c062`, in [pull request #1](https://github.com/justinrm/audio-analysis/pull/1). That pull request is open against `main` and is not merged. `main` is still `858c062` and has not integrated Milestone 4. This handoff does not authorize another milestone, a merge, or further implementation.

Accepted Album QC functionality is Library multi-file WAV import into a study; ordered album membership; the Add recordings dialog; analysis orchestration through the existing analyze endpoint, one recording at a time, reusing a completed `m1-v3` run and leaving a queued or running job in place; comparison of stored evidence as `album-qc-v1`; human listening reviews; the T11 level overlay from stored level series; and the deterministic `album-report-v1` ZIP. Absolute sample peak and RMS stay dBFS. Differences of those levels are dB. Integrated loudness stays LUFS. Its differences are LU. Absolute FFmpeg true peak and 4× reconstructed peak stay dBTP. A difference of one true-peak measurement is dB. The numeric difference is unchanged. Album QC does not remeasure.

G9, the chart §2 Welch PSD overlay, stays deferred. A pair-differences layout refinement and a T11 visualization refinement are post-acceptance improvement candidates. They are not accepted deliverables and are not authorized. The visualization candidate is not G9.

Milestone 3 is **Accepted with Exception** as of November 8, 2026. The optional evidence-grounded AI narrative integration is deferred, not implemented and not removed. NVIDIA NIM remains unauthorized. The [Album QC plan](docs/superpowers/plans/2026-11-08-milestone-4-album-qc.md) is the accepted Milestone 4 scope. It is not a license for the deferred overlay or the two candidates.

The latest accepted presentation pass before Album QC is the Lyrics & Inspiration Workspace & Reference Package Quality Pass, accepted November 8, 2026, on `lyrics-reference-quality-pass`. New lyric figures use `lyric-png-v2` and new briefs use `lyric-brief-v2`. Published `lyric-png-v1` ZIPs stay immutable. The Analyzer Readability & Compact Recording Deck Pass, accepted November 8, 2026, on `analyzer-chart-readability` from `1e7fd9d`, remains accepted. It covers chart-container sizing, readable T01–T10 panels, the T04 axis-label correction, evidence beneath the charts, and a collapsible recording deck with one persistent WaveSurfer instance. It does not change `m1-v3`, stored units, original WAV bytes, or exports. M3-A and M3-B, accepted November 7, 2026, on `milestone-3-deterministic-exports` from `d80fc44`, remain the accepted export slices and are included in the Milestone 3 acceptance. Milestone 2, accepted with exceptions the same day, stays accepted at `ee72581` before the export work. M2-A, M2-B, and M2-C remain accepted. Studio Precision Pass 3, accepted the same day on `studio-precision-pass3` from parent `b35cdb1`, remains accepted. Pass 2 at `883275e` remains accepted. Commit `260cb677` is the Pass 3 readiness proposal. Commit `b35cdb1` is the documentation reconciliation. Neither of those two commits is the Pass 3 implementation acceptance.

The November 6 audit recorded GitHub `main` at `260cb677` and recorded the local Cursor branch, HEAD, upstream divergence, and worktree as unknown. That audit executed documentation checks only. [Verification history](PROJECT_STATUS.md#verification-history) separates prior recorded test runs from that audit's checks. See [Open items](PROJECT_STATUS.md#open-items) for the bundle, playback, assetless Analyzer, and contract issues that remain.

Historical pre-integration check: before the documentation patch was applied, local `main` was clean and synchronized with `origin/main` at `260cb677`. That observation does not rewrite the audit.

`b35cdb1` reconciled the documentation and was on local `main` and `origin/main` before this branch. That reconciliation does not by itself accept Pass 3.

## Accepted baseline

Milestone 4 is accepted with the limitations in the acceptance paragraph. The acceptance closeout did not rerun the suite. Before local commit `bb517b5`, `scripts/verify.sh` passed: Ruff, 118 pytest tests, TypeScript, 105 Vitest tests in 12 files, and the production build, with the existing Starlette `httpx` warning, the existing `png.py` legend warning three times, and the existing chunk-size warning (`dist/assets/index-DmM3nZkm.js`, 1,521.62 kB, gzip 492.31 kB). That git-closeout run did not open a browser session. The November 11 true-peak difference-unit row remains the record of that unit decision and reported the same suite counts. Earlier disposable browser QA used synthetic recordings. Private album masters were not used in those checks. Native keyboard activation of the data-table controls was not manually verified. Some batch checks did not leave the worker running, so queued jobs were not observed through to completion in the browser. Migration rollback was covered by pytest, not by a live database failure.

Milestone 2 is accepted with two deferred synchronization requirements.

1. Waveform zoom and chart zoom are not synchronized. Chart zoom stays local to the chart on screen. Future acceptance: one visible time window is shared by the waveform and the file-time charts, and either surface can move it, without changing stored samples.
2. A selected lyric region is navigable. The waveform highlight follows the playhead. L01 and L03 do not mark that region as the selected one. Future acceptance: the selected usable interval is identifiable on the waveform and on L01 and L03 together, including when other regions also contain the playhead.

M2-C covers L01–L05 in Lyrics & Inspiration: the unified music-and-lyrics timeline, written phrasing and density, energy and dynamic contrast, spectral and textual repetition, and evidence-cited musical DNA and transferable principles. The charts read stored `m1-v3` evidence and the current lyric document. Shared playback and the existing revision and provenance semantics stay in place. Source hashes, `m1-v3`, T01–T10, and `png-r1` are unchanged.

Accepted limitations: mixed evidence classes can display `Unknown` with an explanation. Short recordings may lack T08/T09. L02 may display full-precision stored words/s values. Native keyboard activation of the data-table controls was not manually reverified. Previously documented scientific, renderer, and accessibility gaps remain open.

M3-A and M3-B are accepted and sit inside the Milestone 3 acceptance. M3-A exports a Technical ZIP from stored `m1-v3` evidence and valid `png-r1` artifacts, including a recording with no lyrics. M3-B adds the lyric figures, a deterministic Markdown brief, a Lyricist ZIP, and a Combined ZIP. New lyric figures are `lyric-png-v2` and new briefs are `lyric-brief-v2`. Accepted `lyric-png-v1` snapshots stay immutable. Export does not decode the WAV, remeasure, or rewrite the technical cache. Accepted limitations: stored T03 power remains `dB`; `png-r1` still omits bar panels when a line series is present; a missing valid PNG stays `png_unavailable`; a crash after ZIP publication and before the SQLite insert can leave an unlisted `exports/{id}.zip`; a package content hash does not guarantee pixel-identical PNGs. The optional narrative integration remains a deferred requirement.

The Lyrics & Inspiration quality pass keeps Explore as the default, explicit Edit, searchable cue navigation, one waveform label for the selected or playing cue, the L01 interval lane, split L02 panels, and the clarified combined-evidence sentence. Canonical evidence classes are unchanged. Preserved limitations: L01's stored low-level ending can extend the scale toward −150 dBFS; lyric names stay in the cue list; short viewports may scroll; native keyboard focus was not comprehensively verified; the package content hash does not guarantee pixel-identical PNGs.

The Analyzer Readability & Compact Recording Deck Pass keeps playback, seek, volume, lyric-draft continuity, and the export controls. Deck modes share one WaveSurfer instance. Technical evidence is disclosed beneath the charts. L01 and L03 interactive readability was part of the accepted browser QA. Preserved limitations: Milestone 2's deferred shared-zoom and selected-region synchronization; G3; G6; existing short-viewport scrolling and responsive tradeoffs; and existing unverified data-table keyboard behavior.

Pass 3 covers coordinated ECharts and Matplotlib presentation, in-page chart data tables, and `png-r1` regeneration from stored chart JSON. `m1-v3` is unchanged.

Static renderer files live at `analysis/{sha256}/m1-v3/presentation/png-r1/`. Refresh existing chart JSON with `python -m app.refresh_png --data-root PATH` (`--dry-run`, `--sha256`, and repeatable `--kind` are optional). The app does not refresh PNGs on startup. Until that refresh, the image route returns `png_unavailable` and does not serve a legacy PNG. A current image response sends `X-Renderer-Version: png-r1` and `Cache-Control: no-cache`.

Accepted limitations: native keyboard activation of the data-table controls was not manually verified. G3 and G6 remain open. The Pass 3 in-page data table and heatmap scale are accepted. G4 stays open because chart zoom is still independent of the waveform. Stored T03 power is still `dB`, not dB/Hz. PNG output still omits bar panels when a line series is present.

## Current handoff

Milestone 4 is accepted and published on `milestone-4-album-qc` in [pull request #1](https://github.com/justinrm/audio-analysis/pull/1). The pull request is open against `main` and is not merged. `main` has not integrated Milestone 4. No further implementation is authorized. Do not start another milestone from this handoff. Do not merge unless the owner asks.

`m1-v3`, `png-r1`, stored measurements, WAV bytes, lyric provenance, and already published ZIP bytes stay unchanged. New lyric exports declare `lyric-png-v2` and `lyric-brief-v2`. The album report is `album-report-v1` and the comparison is `album-qc-v1`.

The owner-reported `No Sir Mastered.wav` validation remains Milestone 3 acceptance evidence. This handoff does not claim that any model listened to that recording. A text-and-image reading of the package is not musical-performance verification.

The [Milestone 3 export scope](docs/superpowers/plans/2026-11-07-milestone-3-exports.md) remains the package reference for M3-A and M3-B. The [Album QC plan](docs/superpowers/plans/2026-11-08-milestone-4-album-qc.md) is the accepted Milestone 4 scope. Reported QA, distinct from this closeout, is in [PROJECT_STATUS.md](PROJECT_STATUS.md#verification-history). This closeout did not rerun those checks.

## Not authorized

Another milestone is not authorized. Merging pull request #1 is not authorized. The repository has no configured CI pipeline. GitHub has not reported a passing automated suite for that pull request. A skipped Sourcery review is not a failed application test. The deferred narrative provider, NVIDIA NIM, contextual phrase-and-contrast summaries, structured artist-supplied listening observations, and optional AI narrative interpretation are not authorized. The chart §2 T11 Welch PSD overlay is deferred as G9 and is not a license to invent spectrum samples. The pair-differences layout refinement and the T11 visualization refinement are not authorized. The narrative requirement is deferred, not deleted. The three exploratory items are not accepted requirements. Milestone 2's exceptions are not a license to change stored measurements.

## Cursor handoff

1. Run `git status --short --branch`, `git rev-parse HEAD`, and `git log -5 --oneline --decorate` in the local checkout. Preserve unrelated work.
2. Treat Milestone 4 as accepted and published in pull request #1. Do not merge it from this handoff. Do not implement narrative AI, G9, the pair-differences layout refinement, the T11 visualization refinement, or another milestone unless the owner asks. Absolute true-peak levels stay dBTP. Differences of one true-peak measurement are dB.
3. Do not merge into `main`, enable auto-merge, or add CI. The latest recorded local suite is the November 11 git closeout: Ruff, 118 pytest tests, TypeScript, 105 Vitest tests, and the production build, with the existing warnings. This publication-status session did not rerun that suite.
4. Keep the Milestone 2 acceptance, both exceptions, the Pass 2 and Pass 3 records, the M3 narrative exception, G3, G6, G9, and the original WAV bytes intact.

Protect `m1-v3`, T01–T10 stored data and methods, the original WAV bytes, waveform/transport continuity, lyric draft and revision semantics, evidence labels, and the independent use of Technical Analysis and Lyrics & Inspiration. Album QC compares stored evidence. It does not replace those workspaces or remeasure the masters.

## If the owner requests a baseline reproduction

Use the [local startup and check commands](README.md#install-and-run) and the test sections in [Project status](PROJECT_STATUS.md#verification-history). Record SHA, environment, command, result, warnings, and scenarios skipped. For a browser baseline, record playback across workspace and chart changes, one waveform instance, draft retention, hidden-workspace keyboard exclusion, notes, and widths 1440, 1280, 1000 and 390 pixels. Use synthetic or owner-approved local recordings. Inspect playback and annotations without modifying masters or the analysis cache. A passing check supplies evidence for review.
