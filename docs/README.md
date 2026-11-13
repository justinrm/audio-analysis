# Audio Reference Studio documentation

The root [README](../README.md) describes the published application and how to run it. Use this index to find the owner of each kind of information.

| Subject | Canonical document | Scope |
| --- | --- | --- |
| Product and architecture requirements | [Technical MVP specification](01_TECHNICAL_MVP_SPEC.md) | Three workspaces, offline operation, source preservation, local stack, and milestone gates |
| Technical and scientific chart contracts | [Technical chart requirements](04_TECHNICAL_CHART_REQUIREMENTS.md) | T01–T11, units, evidence, rendering and validation. The MVP specification §4B and the linked M2 plan define L01–L05. |
| Current implementation, acceptance and test status | [PROJECT_STATUS.md](../PROJECT_STATUS.md) | Current record with dated source and approval evidence |
| Locked decisions and unresolved discrepancies | [Decision and uncertainty register](OPEN_DECISIONS_AND_UNCERTAINTIES.md) | Decision index with authority links, gaps, and proposals requiring owner review |
| Current handoff and authorized work | [NEXT_SESSION.md](../NEXT_SESSION.md) | First action, limits, and verification expectations |

Apply authority in this order: the latest explicit owner decision, accepted milestone records and approved decisions, current requirements, verified implementation and test evidence, historical engineering references, then exploratory material. Code establishes observed behavior. A difference from an approved requirement goes in the decision register for evaluation. Acceptance and authorization are recorded separately.

## Supporting records

- [Milestone 2 plan](superpowers/plans/2026-10-13-milestone-2.md) — lyric evidence and L01–L05 design. Milestone 2 is accepted with two synchronization exceptions. Task order and checkboxes are historical planning.
- [Milestone 3 export scope](superpowers/plans/2026-11-07-milestone-3-exports.md) — Technical, Lyricist, and Combined packages. Milestone 3 is accepted with exception as of November 8, 2026. M3-A and M3-B are accepted. New lyric figures use `lyric-png-v2` and new briefs use `lyric-brief-v2`. Published `lyric-png-v1` packages stay immutable. The optional evidence-grounded narrative integration is deferred and is not authorized. NVIDIA NIM remains unauthorized.
- [Milestone 4 Album QC scope](superpowers/plans/2026-11-08-milestone-4-album-qc.md) — accepted November 11, 2026. The implementation was published on `milestone-4-album-qc` and merged into `main` on November 12, 2026, by [pull request #1](https://github.com/justinrm/audio-analysis/pull/1) at `dee0ea17c8406400467c8a51d284b5f5887efca3`. Technical Analysis, Lyrics & Inspiration, and Album QC remain independently usable. No next milestone is authorized. The accepted scope is bulk WAV import, batch membership, analysis orchestration through the existing analyze endpoint, stored-evidence comparison, listening reviews, the T11 level overlay, and the album report. Differences of dBFS levels and of one true-peak measurement are labeled dB. Differences of integrated loudness are labeled LU. Absolute levels stay dBFS and LUFS. Absolute true-peak levels stay dBTP. Acceptance does not change `m1-v3`. The T11 Welch PSD overlay remains deferred as G9. A pair-differences layout refinement and a T11 visualization refinement are post-acceptance candidates and are not authorized.
- [M2-A/M2-B QA](qa/m2a-m2b-2026-10-15.md) — dated QA observations, scope limitations, and citation to the original acceptance record.
- [Studio Precision](design/studio-precision.md) — accepted Pass 2 design and verification record. [Pass 3](design/studio-precision-pass3.md) was accepted November 7, 2026. Its readiness sections remain the proposal history. The Analyzer Readability & Compact Recording Deck Pass and the Lyrics & Inspiration quality pass were accepted November 8, 2026, and are recorded in [PROJECT_STATUS.md](../PROJECT_STATUS.md). On November 12, 2026, the owner approved the Evolved Studio Precision direction and accepted Phase 1 control styling. Later the same day the owner authorized Phase 2, Studio Frame, and accepted that implementation on November 13, 2026, including the reviewed task-tab correction. That acceptance does not authorize Phase 3.
- [Local toolchain](ENVIRONMENT.md) — recovery notes for a stalled frontend check.

## Historical references

- [Legacy script review](02_SCRIPT_REVIEW.md) — methods, historical decoder issue and validation caveats.
- [Milestone 0 first-session prompt](03_CURSOR_AGENT_FIRST_SESSION.md) — original bounded-session draft, superseded as a work instruction.
- [Album Observatory reference review](album_observatory_reference_review.md) and [follow-up audit](album_observatory_followup_audit.md) — evaluation snapshots and proposals from before the M2-A/M2-B acceptance record.
