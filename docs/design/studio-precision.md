# Studio Precision

Approved direction for the frontend. A design pass is not a product milestone.

| Workstream | Status |
|---|---|
| Milestone 0 | Accepted at `e4f1223` |
| Milestone 1 | Accepted at `a387bb2` |
| M2-A | Accepted by the owner on 2026-10-14 at `4d1e71b` |
| M2-B | Accepted by the owner on 2026-10-14 at `d1f29a7` |
| Studio Precision Pass 1 | Accepted by the owner on 2026-11-06 |
| Studio Precision Pass 2 | Accepted by the owner on 2026-11-06 |
| Studio Precision Pass 3 | Not started and not authorized |
| M2-C | Not authorized |
| Milestone 2 overall | Not accepted |

Milestone 0, Milestone 1, M2-A, and M2-B stay on the records in `.cursor/rules/project.mdc`. Accepting Pass 2 does not accept Milestone 2 or M2-C.

## Pass 2 acceptance

**Studio Precision Pass 2 — Accepted by the owner on 2026-11-06.**

The owner reviewed the implementation, QA results, and screenshots. Analysis version stays `m1-v3`. Charts T01–T10 stay on that measurement.

### Recording frame

The open recording keeps its identity, waveform, playback transport, and analysis state. One WaveSurfer instance draws the transport. Playback continues while the workspace or chart changes. Seek and volume stay available. At 390×844, the reviewed mobile navigation and recording deck went from about 510px to 337px.

### Technical Analysis

Chart navigation and the evidence inspector follow the width table below. Plot width is budgeted from the space that remains. The inspector moves under the plot before the chart list collapses. The reviewed widths did not overlap panels. T01–T10 evidence and chart behavior are unchanged.

### Lyrics & Inspiration

Lyric lines use a compact list. One line is open in the editor. An unsaved session draft stays when the line or workspace changes. Stored revisions and the stale-revision conflict stay as they were. Artist notes and timing evidence stay in the inspector. The lyrics workspace is hidden and inert while Technical Analysis is showing.

### Scientific integrity

Pass 2 did not change audio-analysis algorithms, chart-series values, or evidence methods. It did not modify original audio masters. It did not add fabricated measurements or lyric timing.

### Verification

Owner review, including the final refinement:

- Frontend typecheck: PASS.
- Vitest: 40 tests PASS.
- Production build: PASS.
- Browser playback continuity: PASS.
- Lyric draft retention: PASS.
- Hidden workspace keyboard exclusion: PASS.
- Responsive layout checks: PASS.
- Annotation functionality: PASS.
- No console errors or failed requests in the final reported browser check.

The final refinement did not rerun every earlier browser scenario.

The 2026-11-06 checkpoint reran `pnpm typecheck`, `pnpm test` (5 files, 40 tests), and `pnpm build` from `frontend/`. All three passed. Backend tests were not rerun because no backend source files changed.

The production build emits one main JavaScript chunk of 1,460.36 kB. Vite warns that the chunk is over 500 kB. That warning is existing bundle size, not a Pass 2 failure.

## Remaining after Pass 2

Pass 2 does not close every frontend presentation issue.

**Pass 3 candidates.** Not started and not authorized.

- T01 legend density and overlap at narrow widths.
- T04 spectrogram axis labels and frequency-tick presentation.
- Raw numerical labels in chart zoom controls.
- Chart-series color consistency and accessibility.
- Technical axis-title and unit presentation.
- Narrow chart navigation discoverability.
- Dense evidence inspector formatting.
- Responsive chart-specific presentation.

**Separate technical debt.** Not part of Pass 2 acceptance.

- Main JavaScript chunk of about 1.46 MB, and the existing Vite warning.
- A previously observed playback-availability issue on one recording.
- Analyzer navigation when no recording is selected. The Analyzer control opens `/analyzer` without an asset, and that route only tells the reader to choose a recording from the library.

## Pass 2 responsive rule

The plot width is the budget. A side panel stays beside the plot only when the plot would still be at least 720px wide. Remove the inspector from the side first. If the plot is still under 720px, the chart list becomes one horizontal row. The earlier three-column workspace (`15rem` + plot + `17rem`, stacked below 860px) left the plot about 696px wide at 1440×900.

| Viewport | Rail | Chart list | Inspector | Plot |
|---|---|---|---|---|
| ≥1332 | 176px | vertical, 160px | beside the plot, 220px | remainder, 828px at 1440 |
| 1100–1331 | 176px | vertical, 160px | under the plot | 900px at 1280 |
| 928–1099 | 176px | one horizontal row | under the plot | at least 720px |
| ≤927 | top bar | one select | under the plot | content width minus 32px of padding |

Lyric lines follow the same widths: the line list takes the chart-list slot, and the open editor takes the plot slot. One line stays open. Drafts, revision conflicts, and evidence class stay as they are. No drag splitter in these passes.

Pass 2 uses this table.
