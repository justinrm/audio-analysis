# Next session

## Start here

Read [PROJECT_STATUS.md](PROJECT_STATUS.md) for the accepted baseline and verification limits. Use the [documentation index](docs/README.md) for the approved requirements.

The latest accepted implementation slices are M3-A and M3-B, accepted November 7, 2026, on `milestone-3-deterministic-exports` from `d80fc44`. Milestone 3 overall remains open. Milestone 2, accepted with exceptions the same day, stays accepted at `ee72581` before this export work. M2-A, M2-B, and M2-C remain accepted. Studio Precision Pass 3, accepted the same day on `studio-precision-pass3` from parent `b35cdb1`, remains accepted. Pass 2 at `883275e` remains accepted. Commit `260cb677` is the Pass 3 readiness proposal. Commit `b35cdb1` is the documentation reconciliation. Neither of those two commits is the Pass 3 implementation acceptance.

The November 6 audit recorded GitHub `main` at `260cb677` and recorded the local Cursor branch, HEAD, upstream divergence, and worktree as unknown. That audit executed documentation checks only. [Verification history](PROJECT_STATUS.md#verification-history) separates prior recorded test runs from that audit's checks. See [Open items](PROJECT_STATUS.md#open-items) for the bundle, playback, assetless Analyzer, and contract issues that remain.

Historical pre-integration check: before the documentation patch was applied, local `main` was clean and synchronized with `origin/main` at `260cb677`. That observation does not rewrite the audit.

`b35cdb1` reconciled the documentation and was on local `main` and `origin/main` before this branch. That reconciliation does not by itself accept Pass 3.

## Accepted baseline

Milestone 2 is accepted with two deferred synchronization requirements.

1. Waveform zoom and chart zoom are not synchronized. Chart zoom stays local to the chart on screen. Future acceptance: one visible time window is shared by the waveform and the file-time charts, and either surface can move it, without changing stored samples.
2. A selected lyric region is navigable. The waveform highlight follows the playhead. L01 and L03 do not mark that region as the selected one. Future acceptance: the selected usable interval is identifiable on the waveform and on L01 and L03 together, including when other regions also contain the playhead.

M2-C covers L01–L05 in Lyrics & Inspiration: the unified music-and-lyrics timeline, written phrasing and density, energy and dynamic contrast, spectral and textual repetition, and evidence-cited musical DNA and transferable principles. The charts read stored `m1-v3` evidence and the current lyric document. Shared playback and the existing revision and provenance semantics stay in place. Source hashes, `m1-v3`, T01–T10, and `png-r1` are unchanged.

Accepted limitations: mixed evidence classes can display `Unknown` with an explanation. Short recordings may lack T08/T09. L02 may display full-precision stored words/s values. Native keyboard activation of the data-table controls was not manually reverified. Previously documented scientific, renderer, and accessibility gaps remain open.

M3-A and M3-B are accepted. M3-A exports a Technical ZIP from stored `m1-v3` evidence and valid `png-r1` artifacts, including a recording with no lyrics. M3-B adds `lyric-png-v1` L01–L05 figures, a deterministic Markdown brief, a Lyricist ZIP, and a Combined ZIP. Export does not decode the WAV, remeasure, or rewrite the technical cache. Accepted limitations: stored T03 power remains `dB`; `png-r1` still omits bar panels when a line series is present; a missing valid PNG stays `png_unavailable`; a crash after ZIP publication and before the SQLite insert can leave an unlisted `exports/{id}.zip`. Milestone 3 overall remains open.

Pass 3 covers coordinated ECharts and Matplotlib presentation, in-page chart data tables, and `png-r1` regeneration from stored chart JSON. `m1-v3` is unchanged.

Static renderer files live at `analysis/{sha256}/m1-v3/presentation/png-r1/`. Refresh existing chart JSON with `python -m app.refresh_png --data-root PATH` (`--dry-run`, `--sha256`, and repeatable `--kind` are optional). The app does not refresh PNGs on startup. Until that refresh, the image route returns `png_unavailable` and does not serve a legacy PNG. A current image response sends `X-Renderer-Version: png-r1` and `Cache-Control: no-cache`.

Accepted limitations: native keyboard activation of the data-table controls was not manually verified. G3, G4, and G6 remain open. Stored T03 power is still `dB`, not dB/Hz. Chart zoom is still independent of the waveform. PNG output still omits bar panels when a line series is present.

## Current handoff

Milestone 2 is accepted with the two exceptions above. M3-A and M3-B are accepted. Milestone 3 overall remains open. The [Milestone 3 export scope](docs/superpowers/plans/2026-11-07-milestone-3-exports.md) remains the package reference. A narrative client remains a separate later authorization. Do not start Milestone 4.

Reported implementation QA is in [PROJECT_STATUS.md](PROJECT_STATUS.md#verification-history). That session recorded 84 backend tests, 63 frontend tests, passing Ruff, TypeScript, and the production build, plus Technical, Lyricist, and Combined browser downloads. The closeout rerun is a separate row.

## Not authorized

The optional narrative provider, Album QC, T11, and unrelated technical debt are not authorized. Milestone 2 acceptance is not a license to start that work. M3-A and M3-B acceptance is not acceptance of Milestone 3 overall.

## Cursor handoff

1. Run `git status --short --branch`, `git rev-parse HEAD`, and `git log -5 --oneline --decorate` in the local checkout. Preserve unrelated work.
2. Stop. M3-A and M3-B are accepted and Milestone 3 overall remains open. Do not start Milestone 4 or a narrative client.
3. Keep the Milestone 2 acceptance, both exceptions, and the Pass 2 and Pass 3 records intact.

Protect `m1-v3`, T01–T10 stored data and methods, the original WAV bytes, waveform/transport continuity, lyric draft and revision semantics, evidence labels, and the independent use of each workspace.

## If the owner requests a baseline reproduction

Use the [local startup and check commands](README.md#install-and-run) and the test sections in [Project status](PROJECT_STATUS.md#verification-history). Record SHA, environment, command, result, warnings, and scenarios skipped. For a browser baseline, record playback across workspace and chart changes, one waveform instance, draft retention, hidden-workspace keyboard exclusion, notes, and widths 1440, 1280, 1000 and 390 pixels. Use synthetic or owner-approved local recordings. Inspect playback and annotations without modifying masters or the analysis cache. A passing check supplies evidence for review.
