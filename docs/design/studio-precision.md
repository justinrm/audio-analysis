# Studio Precision

Approved direction for the frontend. Pass 1 (shell, language, and library) is accepted by the owner on 2026-11-06 after final visual review. Pass 2 and Pass 3 are not started. Milestone acceptance records are unchanged.

## Pass 2 responsive rule

The plot width is the budget. A side panel stays beside the plot only when the plot would still be at least 720px wide. Remove the inspector from the side first. If the plot is still under 720px, the chart list becomes one horizontal row. Pass 1 still uses the current three-column workspace (`15rem` + plot + `17rem`) and stacks that workspace below 860px. Those column widths are why the plot is about 696px at 1440×900 today.

| Viewport | Rail | Chart list | Inspector | Plot |
|---|---|---|---|---|
| ≥1332 | 176px | vertical, 160px | beside the plot, 220px | remainder, 828px at 1440 |
| 1100–1331 | 176px | vertical, 160px | under the plot | 900px at 1280 |
| 928–1099 | 176px | one horizontal row | under the plot | at least 720px |
| ≤927 | top bar | one select | under the plot | content width minus 32px of padding |

Lyric lines follow the same widths: the line list takes the chart-list slot, and the open editor takes the plot slot. One line stays open. Drafts, revision conflicts, and evidence class stay as they are. No drag splitter in these passes.
