# Document reconciliation changelog

November 6, 2026 Pacific. Based on GitHub `main` at `260cb677`. The [source-of-truth audit](SOURCE_OF_TRUTH_AUDIT.md) identifies the evidence for each finding. This change set is documentation only.

| Changed document | What changed and why | Classification and evidence | Remaining issue |
| --- | --- | --- | --- |
| [Root README](../README.md) | Routed checkpoint status to one file. Clarified study switching, matching-width extensible PCM, and per-chart PNG render failure. Removed wording that gave code precedence over approved requirements. | Factual/editorial. A4, A6, A9. | Application runtime and full format matrix were not reproduced here. |
| [PROJECT_STATUS.md](../PROJECT_STATUS.md) | Added a single record for implementation, acceptance, historical tests, and limits. Recorded Pass 2 acceptance and commit, and the later proposal-only head. | Factual. A1, A2, A4, A10. | Local worktree, some original approvals, raw run logs, and real-master parity unavailable. |
| [NEXT_SESSION.md](../NEXT_SESSION.md) | Replaced the superseded Pass 3 planning prompt with checkout comparison and review of the existing proposal. Routed acceptance and test history to status. Linked protected boundaries and reproduction criteria. | Factual/editorial. A2, A4, A5, A10. | Owner scope decision after local verification. |
| `.cursor/rules/project.mdc` | Routed status and scope to their canonical files. Preserved technical boundaries, API type generation, and tests. Updated Git guidance to require local evidence and explicit mutation authorization. | Editorial, based on owner brief and A4. Original acceptance record remains linked by pinned revision. | Local Git and tools must be checked in Cursor. |
| [Documentation index](README.md) | Added a singular ownership map and authority order. Indexed supporting QA and design records and identified historical prompts and references. | Editorial. A1, A4, A11. | None within the audited sources. |
| [MVP specification](01_TECHNICAL_MVP_SPEC.md) | Labeled product targets, distinguished accepted decoder scope, clarified exact size units, kept approved stack and provider neutrality, and made shared evidence and future public options explicit. | Factual/editorial. Owner brief and A6–A8. Requirements for additional decoder targets and validation were retained. | Format expansion, memory targets, route gaps, and scope changes remain review items. |
| [Technical chart requirements](04_TECHNICAL_CHART_REQUIREMENTS.md) | Distinguished shipped chart statuses from the original registry target and linked the discrepancies. Chart catalog, data obligations and test gates are retained. | Factual/editorial. A7–A8. | Units, metadata, rendering, and accessibility differences remain open. |
| [First-session prompt](03_CURSOR_AGENT_FIRST_SESSION.md) | Added a historical banner and noted the M0-only gate and HTTP 501 contract. The original wording remains for provenance. | Factual/editorial. A3. | Standalone M0 acceptance artifacts unavailable. |
| [Milestone 2 plan](superpowers/plans/2026-10-13-milestone-2.md) | Marked old task order, checkboxes and agent directives as historical planning. Preserved lyric evidence and L01–L05 references. | Editorial. A4, A10. | M2-C still requires explicit authorization. |
| [Studio Precision record](design/studio-precision.md) | Replaced the repeated status table with a pointer. Preserved the Pass 2 acceptance text, verification record and responsive contract. Linked the later proposal. | Editorial. A2, A4, A10. | Older playback case remains unverified at this head. |
| [Pass 3 readiness proposal](design/studio-precision-pass3.md) | Removed premature acceptance of a browser/PNG presentation difference, qualified the old playback observation, and labeled the criteria as proposed. | Factual/editorial. A5, A7, A10. The proposed temporary exception remains pending. | Pass 3 scope and any exception require explicit approval. |
| [Source-of-truth audit](SOURCE_OF_TRUTH_AUDIT.md) | Added findings, source locations, severity, and resolutions for the pinned snapshot. | Factual audit record. A1–A11. | Owner checkout unavailable. |
| [Decision and uncertainty register](OPEN_DECISIONS_AND_UNCERTAINTIES.md) | Added a locked-decision index, missing evidence, implementation differences, and pending proposals. | Factual/editorial. G1–G8. Pending decisions are labeled proposals. | Owner decisions are limited to the live review gate and any proposed chart-presentation exception. |
| `Audio_Reference_Studio_Project_Context.md` (project attachment replacement) | Removed the stale implementation phase and first-session directives. Replaced duplicated chart/status catalogs with canonical references. Preserved product purpose, workflow and scientific history. | Factual/editorial. A1, A6, A11 and the latest owner brief. | Replace the old project attachment after review. The attachment is separate from the Git patch. |

The legacy script review, original QA report, Album Observatory reviews, local environment note, and backend/frontend Cursor rules were retained unchanged. The patch does not include application code, tests, migrations, dependencies, Git configuration, or private material.

## Later addition — documentation-update rule

This repository integration, after the reviewed patch above, added `## Documentation and milestone continuity` to `.cursor/rules/project.mdc`. That rule was not part of the original reconciliation. It requires `PROJECT_STATUS.md`, `NEXT_SESSION.md`, and any affected decision records to be reconciled after an explicit owner acceptance or scope decision, before later implementation. It is there to prevent status drift after owner approvals. Passing tests, commits, or an agent success report do not constitute acceptance, and the next milestone is never inferred.

The patch was applied on local `main` at `260cb677`, which matched the audited revision with a clean worktree and no divergence from `origin/main`. That local check does not change the audit snapshot's original evidence limits.

## Final editorial pass

These edits follow the documentation-update rule. They do not change the audit findings, accepted checkpoints, or authorization boundaries.

| Document | Change |
| --- | --- |
| [PROJECT_STATUS.md](../PROJECT_STATUS.md) | Kept the November 6 audit's unknown-checkout record. Added the later verified baseline: local `main`, clean before the patch, synchronized with `origin/main`, at `260cb677`. At the time of this pass, HEAD remained that commit and the reconciliation was staged, not committed. See the November 7 correction below. |
| [NEXT_SESSION.md](../NEXT_SESSION.md) | Made the same distinction between the audit record and the verified baseline. The handoff still requires a fresh Git inspection and an explicit owner decision. |
| [MVP specification](01_TECHNICAL_MVP_SPEC.md) | Separated **Role** and **Prepared** with a blank line so they do not render as one line. No trailing whitespace was added. |
| [Root README](../README.md) | Removed one extra blank line at the end of the file introduced by the supplied patch, so the diff has no end-of-file whitespace error. Wording is unchanged. |

## November 7, 2026 — reconciliation commit

`PROJECT_STATUS.md` and `NEXT_SESSION.md` still described the reconciliation as staged, with HEAD at `260cb677`. That described the worktree before commit `b35cdb1`. Those two files now label the November 6 audit and the pre-integration check as historical, and they record `b35cdb1` on local `main` and `origin/main` with a clean worktree on November 7, 2026. That wording correction does not itself accept a milestone. It is included with the later Pass 3 acceptance commit.
