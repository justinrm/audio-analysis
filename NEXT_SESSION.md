# Next session

## Start here

Read [PROJECT_STATUS.md](PROJECT_STATUS.md) for the accepted baseline and verification limits. Use the [documentation index](docs/README.md) for the approved requirements.

The latest accepted implementation checkpoint is Milestone 2-C, accepted November 7, 2026, on `milestone-2c-lyricist-visualizations` from parent `c239341`. Studio Precision Pass 3, accepted the same day on `studio-precision-pass3` from parent `b35cdb1`, remains accepted. Pass 2 at `883275e` remains accepted. Commit `260cb677` is the Pass 3 readiness proposal. Commit `b35cdb1` is the documentation reconciliation. Neither of those two commits is the Pass 3 implementation acceptance. Milestone 2 overall is not accepted.

The November 6 audit recorded GitHub `main` at `260cb677` and recorded the local Cursor branch, HEAD, upstream divergence, and worktree as unknown. That audit executed documentation checks only. [Verification history](PROJECT_STATUS.md#verification-history) separates prior recorded test runs from that audit's checks. See [Open items](PROJECT_STATUS.md#open-items) for the bundle, playback, assetless Analyzer, and contract issues that remain.

Historical pre-integration check: before the documentation patch was applied, local `main` was clean and synchronized with `origin/main` at `260cb677`. That observation does not rewrite the audit.

`b35cdb1` reconciled the documentation and was on local `main` and `origin/main` before this branch. That reconciliation does not by itself accept Pass 3.

## Accepted baseline

M2-C covers L01–L05 in Lyrics & Inspiration: the unified music-and-lyrics timeline, written phrasing and density, energy and dynamic contrast, spectral and textual repetition, and evidence-cited musical DNA and transferable principles. The charts read stored `m1-v3` evidence and the current lyric document. Shared playback and the existing revision and provenance semantics stay in place. Source hashes, `m1-v3`, T01–T10, and `png-r1` are unchanged.

Accepted limitations: mixed evidence classes can display `Unknown` with an explanation. Short recordings may lack T08/T09. L02 may display full-precision stored words/s values. Native keyboard activation of the data-table controls was not manually reverified. Lyricist PNG packages and deterministic exports belong to Milestone 3. Previously documented scientific, renderer, and accessibility gaps remain open.

Pass 3 covers coordinated ECharts and Matplotlib presentation, in-page chart data tables, and `png-r1` regeneration from stored chart JSON. `m1-v3` is unchanged.

Static renderer files live at `analysis/{sha256}/m1-v3/presentation/png-r1/`. Refresh existing chart JSON with `python -m app.refresh_png --data-root PATH` (`--dry-run`, `--sha256`, and repeatable `--kind` are optional). The app does not refresh PNGs on startup. Until that refresh, the image route returns `png_unavailable` and does not serve a legacy PNG. A current image response sends `X-Renderer-Version: png-r1` and `Cache-Control: no-cache`.

Accepted limitations: native keyboard activation of the data-table controls was not manually verified. G3, G4, and G6 remain open. Stored T03 power is still `dB`, not dB/Hz. Chart zoom is still independent of the waveform. PNG output still omits bar panels when a line series is present.

## Current handoff

M2-C is the latest accepted implementation. Milestone 2 overall is not accepted. The next action is an owner-directed Milestone 2 overall acceptance review, or another explicitly authorized decision. Do not start Milestone 3.

## Not authorized

Milestone 3 package exports, Lyricist PNG packages, Markdown reference packages, narrative AI, Album QC, T11, and unrelated technical debt are not authorized. M2-C acceptance is not a license to extend that work. Milestone 2 overall acceptance is a separate owner decision.

## Cursor handoff

1. Run `git status --short --branch`, `git rev-parse HEAD`, and `git log -5 --oneline --decorate` in the local checkout. Preserve unrelated work.
2. Wait for an owner-directed Milestone 2 overall acceptance review or another explicit scope decision. Do not start Milestone 3.
3. Keep the M2-A, M2-B, M2-C, Pass 2, and Pass 3 acceptance records intact.

Protect `m1-v3`, T01–T10 stored data and methods, the original WAV bytes, waveform/transport continuity, lyric draft and revision semantics, evidence labels, and the independent use of each workspace.

## If the owner requests a baseline reproduction

Use the [local startup and check commands](README.md#install-and-run) and the test sections in [Project status](PROJECT_STATUS.md#verification-history). Record SHA, environment, command, result, warnings, and scenarios skipped. For a browser baseline, record playback across workspace and chart changes, one waveform instance, draft retention, hidden-workspace keyboard exclusion, notes, and widths 1440, 1280, 1000 and 390 pixels. Use synthetic or owner-approved local recordings. Inspect playback and annotations without modifying masters or the analysis cache. A passing check supplies evidence for review.
