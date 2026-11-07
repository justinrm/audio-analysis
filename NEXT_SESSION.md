# Next session

## Start here

Read [PROJECT_STATUS.md](PROJECT_STATUS.md) for the accepted baseline, latest published revision, reported test results, and verification limits. Use the [documentation index](docs/README.md) for the approved requirements. The latest accepted implementation checkpoint recorded on GitHub is Pass 2. The published head after it contains the [Pass 3 readiness proposal](docs/design/studio-precision-pass3.md).

The audited GitHub branch is `main` at `260cb677`. That audit recorded the local Cursor branch, HEAD, upstream divergence, and worktree contents as unknown. This audit executed documentation checks only. [Verification history](PROJECT_STATUS.md#verification-history) separates prior recorded test runs from this audit's checks. See [Open items](PROJECT_STATUS.md#open-items) for the separate bundle, playback, assetless Analyzer, and contract issues.

Before the documentation patch was applied, local `main` was clean and synchronized with `origin/main` at `260cb677`. HEAD remains `260cb677`. The reconciliation is staged in the worktree and is not committed. That verification does not rewrite the audit and does not authorize Pass 3, M2-C, or a later milestone.

## Cursor handoff

1. Run `git status --short --branch`, `git rev-parse HEAD`, and `git log -5 --oneline --decorate` in the local checkout. If an upstream is configured, compare local HEAD with it. Inspect staged and unstaged diffs and report relevant untracked paths. Preserve unrelated work.
2. Review the [Pass 3 proposal](docs/design/studio-precision-pass3.md) against the [technical chart contract](docs/04_TECHNICAL_CHART_REQUIREMENTS.md), especially units, accessible chart alternatives, and browser/PNG presentation consistency. Bring any requested exception to the owner with the specific affected chart and acceptance criterion.
3. Return a concise report identifying the local SHA, any drift from the published baseline, acceptance records available locally, exactly which checks were run or merely reported, and the owner decision needed. If a newer local implementation is present without explicit acceptance, review that work for acceptance first. Keep the published Pass 2 record intact.
4. Stop for the owner decision. The authorized work in this handoff is inspection, reconciliation, and proposal review. Owner approval of a later implementation scope must be explicit.

Protect `m1-v3`, T01–T10 stored data and methods, the original WAV bytes, waveform/transport continuity, lyric draft and revision semantics, evidence labels, and the independent use of each workspace. Pass 3 implementation, M2-C/L01–L05, ZIP exports, narrative integration, Album QC/T11, the T02 stored-sample inspector, unrelated debt fixes, and Git commits/pushes/merges require separate authorization.

## If the owner requests a baseline reproduction

Use the [local startup and check commands](README.md#install-and-run) and the test sections in [Project status](PROJECT_STATUS.md#verification-history). Record SHA, environment, command, result, warnings, and scenarios skipped. For a browser baseline, record playback across workspace and chart changes, one waveform instance, draft retention, hidden-workspace keyboard exclusion, notes, and widths 1440, 1280, 1000 and 390 pixels. Use synthetic or owner-approved local recordings. Inspect playback and annotations without modifying masters or the analysis cache. A passing check supplies evidence for review.
