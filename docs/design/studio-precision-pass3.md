# Studio Precision Pass 3 — readiness report

Proposal only. See [NEXT_SESSION.md](../../NEXT_SESSION.md) for the current authorization boundary. This report supplies no approval to implement Pass 3, start M2-C, or change analysis version `m1-v3`.

This report audits the chart renderer in `frontend/src/chart.tsx`, the workspace in `frontend/src/analyzer.tsx` and `frontend/src/styles.css`, the chart documents built by `backend/app/charts.py`, and two existing local `m1-v3` chart documents. One document set is a long stereo file with Nyquist at 24 kHz. The other is a short stereo file with Nyquist at 4 kHz. No private audio, titles, or lyric text are included. This session did not retake screenshots.

## 1. Executive design assessment

The measurements are in place. The presentation is one shared ECharts option with a three-color palette, default ticks, a hidden color scale, and no unit-aware tooltip or zoom labels.

What already holds:

- Series come from the chart document. The browser does not compute loudness, spectra, or peaks.
- T01 keeps normalized amplitude and dBFS on separate grids, switches overview and detail envelopes by zoom, and keeps the sample-peak marker on the file time.
- Playback moves a playhead with `setOption` and does not rebuild the chart. Review markers are brass and dashed. The playhead is cream and solid.
- A chart whose x-axis is not file time, including T10, does not get a file-time playhead.
- Evidence class, method, summary, and caveats render in the inspector. Status and evidence class stay separate.
- Mono T05 becomes chart status `not_available` and evidence class `not_applicable` in `backend/app/charts.py`. The plot is not drawn unless status is `ready`.

Main weaknesses:

- The shared palette uses `#9a3412` and `#1f4b99`. On the page ground `#14171c` those colors have contrast ratios of about 2.5:1 and 2.2:1. They fail ordinary text and line contrast. Color is also the only way to tell series apart.
- Several charts put different units on one value axis. On the long local file, T05 correlation spans about 0.25 to 1.0 while side/mid spans about −40 dB to −2 dB, so the correlation trace occupies a thin strip of the axis.
- T03 draws frequency on a linear axis from a few hertz to Nyquist. `axis_definitions.y_scale` is `linear` on every inspected document. `chart.tsx` never reads `y_scale`. The PNG renderer in `backend/app/png.py` would use a log x-axis only when `y_scale` is `log`.
- T04 labels every heatmap row with a rounded hertz value and then hides overlaps, so the surviving ticks are bin centers such as 70, 4195, and 8109 Hz. The color scale is `visualMap.show: false`.
- The dataZoom slider has no label formatter, so the control shows raw zoom percentages.
- Legends sit at `top: 0` with a fixed grid inset (28px, or 64px when a chart is split). T01 has six series names, including both the overview and detail envelopes.
- The plot `role="img"` exposes the chart title only. There is no tooltip formatter and no text alternative tied to the evidence summary.

Pass 3 should stay inside Studio Precision: graphite, slate, and brass used with restraint. Brass stays on the playhead’s companion role — review markers and the transport progress — and does not become the default series color.

## 2. Chart-by-chart findings

Severity here means what Pass 3 needs for acceptance. “Essential” and “Optional” are proposed acceptance priorities.

### T01 — Waveform and peak envelope

Measured. Local series: detail envelope min/max at 4000 points, overview min/max at 250 points, 100 ms RMS, and 1 s RMS. One sample-peak marker.

| Topic | Finding | Severity |
|---|---|---|
| Rendering | Two grids. Amplitude and dBFS stay apart. Zoom legend selection is tested. | Preserve |
| Legend | Six names share one legend. Unselected overview or detail series still occupy legend space. `grid.top` is 64px. | Essential |
| Axes | Names are “Normalized amplitude” and “dBFS”. Time is a raw value axis. | Essential tick formatting |
| Units | The split matches the series units. | Preserve |
| Tooltip | No unit formatter. | Essential |
| Zoom | Shared across both time axes. Slider labels are the ECharts defaults. | Essential |
| Small screen | Six legend rows compete with a plot that is 18rem tall at ≤927px. | Essential |
| Access | Image name is the title. Marker buttons are keyboard operable. The canvas is not a keyboard seek target; the transport seek slider is. | Essential description; keyboard canvas seek is optional |
| Evidence | Peak time, level, and the “exact sample, not the bucket” caveat are in the marker list and the inspector. | Preserve |
| Risk | A legend rewrite can break `resolutionSelected` names: “Envelope max”, “Envelope min”, “Overview envelope max”, “Overview envelope min”. | Test the existing zoom switch |

### T02 — Loudness and dynamics

Measured. Local long file: 1 s RMS about −21 to −9 dBFS, 3 s short-term LUFS about −17 to −9 LUFS, and four relative-power bars of about −0.9 to +0.7 dB. Integrated LUFS, LRA, sample peak, and true peak are summary fields, not plotted series.

| Topic | Finding | Severity |
|---|---|---|
| Rendering | Time series and window bars are separate grids. Integrated figures are only in the inspector. | Essential to keep integrated figures visually distinct |
| Legend | Two line names, no units in the labels. | Essential |
| Axes | `lineAxisName` uses the first line unit, so the time axis is titled “dBFS” while LUFS is on that same scale. The document `y` name becomes “Relative RMS-power level (dB)” once window bars exist, and that name is used for the bar grid. | Essential |
| Units | LUFS and dBFS are not converted. Their numbers happen to overlap on the inspected files. A quieter file would not. | Essential labeling; do not convert |
| Tooltip | No formatter. | Essential |
| Zoom | Time slider, raw percent labels. | Essential |
| Small screen | Rotated category labels are not used (four bars). The mixed axis title is the problem at every width. | Essential |
| Evidence | Caveats already say LRA is not crest factor and the window bars are not sections. | Preserve the caveat text |
| Risk | Renaming the axis must not move LUFS values onto a dBFS scale or the reverse. | Assert both series keep their stored `y` arrays |

### T03 — Long-term spectral balance

Measured. Welch PSD line, unit stored as `dB`, about −115 to −37 dB on the long file and down to the −160 dB floor on the short file. Eight power-share bars. Frequencies run from under 10 Hz to Nyquist. The line is `10*log10` of SciPy Welch power. The chart document does not call the unit dB/Hz.

| Topic | Finding | Severity |
|---|---|---|
| Rendering | Line and bars are separate grids. Bar color is the low-contrast rust. | Essential color; preserve both grids |
| Legend | One line, so the line panel has no legend. | Fine |
| Axes | PSD x-axis is linear hertz. That compresses 20–500 Hz into a small fraction of a 24 kHz span. | Essential log display of the existing hertz samples |
| Units | Display the stored unit `dB`. Do not relabel it dB/Hz in the browser. A document-unit correction would be a backend change and is out of this pass. | Essential |
| Bars | Labels are full ranges such as `500–2000 Hz` and `10000–24000 Hz`, rotated because there are more than six bars. | Essential at narrow widths; exact ranges stay in the inspector |
| Tooltip / zoom | Same shared gaps. Zoom indexes come from playhead axes. The PSD x-axis is frequency, not file time, so it correctly has no playhead. | Essential frequency formatting |
| Risk | Setting `y_scale` to `log` in the document would also change PNG export, because `png.py` treats that flag as an x-scale. Leave the field `linear`. Apply log only in the ECharts PSD x-axis. | PNG stays linear until an export pass |
| Scientific limit | Band percentages are shares of Welch power. The existing caveat against brightness, vocal level, and instrument identity stays visible. | Preserve |

### T04 — Spectrogram and spectral evolution

Measured. Heatmap is 96 frequency rows by up to 180 time columns. Values are dB relative to the track median, peak-aggregated. Band traces are bass, body, presence, and air, in `dB rel. median`. Air is omitted when Nyquist is below 5 kHz; the short file has no air trace. The method text says the rows are linear FFT bins labeled with the strongest bin, and that the axis is not converted to log frequency.

| Topic | Finding | Severity |
|---|---|---|
| Rendering | Heatmap plus a second grid for band traces. Time zoom is linked. Click seek uses bin time, and that behavior is tested. | Preserve |
| Frequency ticks | Category labels are `Math.round(hz)` for every row, with `hideOverlap`. Surviving labels on the long file include 70, 4195, 8109, 12164, 16172, and 20016 Hz. | Essential |
| Time ticks | `timeLabels` prints one decimal, or three when those collide. | Essential density on small screens |
| Color ramp | Hidden. Range is the min and max of the displayed cells (about −27 to +30 dB, and about −11 to +62 dB, on the two files). | Essential visible scale |
| Legend | One item per band trace, placed above the heatmap. | Essential: keep it out of the heatmap |
| Small screen | 96 row labels cannot be read at 390px. Sparse ticks can. A separate full-bleed mode is optional and needs approval. | Essential ticks; optional mode |
| Risk | Reordering rows or switching the axis to log would contradict the stored bin edges and the caveat. | Do not change `heatmap.y` or `z` |

### T05 — Stereo and mono compatibility

Measured on both local files, so both are stereo. Correlation (`ratio`) and side/mid (`dB`) share one axis named “Correlation or dB”. On the long file the ranges cited above make the correlation series unreadable. Whole-file correlation, side/mid, side energy, mono fold-down, and sub-120 Hz correlation stay in the summary.

| Topic | Finding | Severity |
|---|---|---|
| Rendering | One grid, two line series, no review markers in these documents. | Essential split, using the T01 two-grid pattern |
| Correlation scale | After the split, fix the correlation axis at −1 to 1 so files can be compared. | Essential |
| Side/mid scale | Autoscale in dB. Do not convert to correlation. | Essential |
| Mono | Status `not_available`, evidence `not_applicable`, no invented right channel. | Preserve; no plot |
| Listening claims | Caveats already say low correlation is not a phase failure. | Preserve |
| Risk | A dual axis on one grid is easier to misread than two stacked grids. Use two grids. | Follow `splitsLevels` |

### T06 — Rhythm and pulse evidence

Estimated. Onset-strength line plus autocorrelation bars. Local labels include `61.1 BPM` and `122.3 BPM (double-time)`. The bar axis name “Autocorrelation” and the playhead staying off the bars are tested.

| Topic | Finding | Severity |
|---|---|---|
| Uncertainty | The inspector says Estimated. The plot heading shows the title and “Ready”, which is the status, not the evidence class. | Essential heading |
| Bars | Category labels are the stored candidate strings. Half-time and double-time are hypotheses in the label and the caveat. | Preserve the strings |
| Color | All bars share one rust fill. | Essential contrast; one fill is acceptable if the axis title stays |
| Risk | Do not sort, drop, or rename candidates. | Snapshot the labels in a test |

### T07 — Pitch-class and tonal estimates

Estimated. Twelve pitch-class bars, C through B. Shares on the long file sit between about 0.07 and 0.10. The short file peaks near 0.94. Summary rows are key names with a profile correlation, such as `profile r 0.000` style values from the document (`profile r` plus three decimals).

| Topic | Finding | Severity |
|---|---|---|
| Axis | ECharts autoscales. A nearly even distribution then fills the plot and looks more peaked than it is. | Essential: minimum 0, maximum 1 |
| Labels | Twelve names rotate 35 degrees. Readable on desktop. Tight on 390px. | Optional shorter labels; names are already short |
| Uncertainty | Key names are profile correlations. The caveat says they are not a verified key. | Essential heading, same pattern as T06 |
| Risk | Forcing 0–1 makes a flat distribution look flat. That is the measurement. | Do not renormalize to the tallest bar |

### T08 — Structure novelty

Estimated. One novelty line. The long file has eight `provisional_change` markers. Each marker caveat says it is not a verified section boundary.

| Topic | Finding | Severity |
|---|---|---|
| Markers | Brass dashed lines plus a button list. Eight labels on the plot can collide. | Essential: keep the lines and the list; hide on-plot text when it would collide |
| Heading | Same status-versus-evidence gap as T06. | Essential |
| Risk | Marker times are the stored `time_s` values. Formatting must not move them. | Existing marker seek test pattern |

### T09 — Recurrence and self-similarity

Estimated. Time-by-time cosine similarity. The long file is 48 by 48 bins at 2 s. Values run from about −0.81 to 1.0. Both axes are file time, so the playhead is a crosshair, and zoom is linked on x and y. Those links are tested.

| Topic | Finding | Severity |
|---|---|---|
| Axes | Category labels are the bin times. 48 labels per side will not fit on a phone. | Essential sparse ticks; do not resample the matrix |
| Color | Same hidden ramp as T04. A sequential ramp from the data minimum to 1 is ordered, and it needs a label that says cosine similarity. | Essential scale |
| Meaning | Caveats say a bright cell is not a matching melody or hook. | Preserve |
| Optional | A diverging ramp around 0 would encode negative similarity more clearly. It is not required if the numeric scale is visible. | Optional |
| Risk | Changing `z` or treating either axis as frequency. | Do not |

### T10 — Ending, gap, and anomaly review

Measured. Four bars: last 1000, 500, 100, and 50 ms RMS, in dBFS. The x-axis name is “Last milliseconds”, so there is no playhead and the review markers are not drawn on the bars. The long file’s marker list is one reconstructed peak and six full-scale samples. The list format is `kind`, time to three decimals, label, and value.

| Topic | Finding | Severity |
|---|---|---|
| Rendering | The bars are ending-window levels. The checkpoints are the list. A reader can still treat the bars as the anomalies. | Essential caption from the existing caveat |
| Times | Marker buttons seek to the stored file time. | Preserve |
| Claims | Caveats say the flags are listening checkpoints, not established clicks, dropouts, or audible clipping. | Preserve |
| Small screen | Four horizontal labels fit. The marker sentences wrap in the plot column. | Optional tighter list layout |
| Risk | Drawing marker times onto the millisecond bar axis would place file time on the wrong axis. | Keep the current playhead exclusion |

## 3. Visualization standards

Implement these as pure functions used by `optionFor`, with tests that do not need a canvas. Suggested module: `frontend/src/chart-format.ts`. Keep the functions next to the renderer. Do not add a chart library or a theme framework.

### Color

Plot background is the page ground `#14171c` (the chart element is transparent). Minimum contrast for a one-pixel series against that ground should be 4.5:1. Ink `#e8e6e1` is about 14:1. Brass `#c4a36a` is about 7.5:1. The current rust and blue fail.

| Role | Color | Second channel |
|---|---|---|
| Waveform envelope | `#e8e6e1` | solid |
| RMS and energy | `#8eb4d4` | solid |
| Loudness (LUFS) | `#c5d4c0` | dashed |
| Spectral line and band traces | `#e8e6e1`, `#8eb4d4`, `#d7c4b0`, `#a8b0ba` in series order | solid, and dash after the first |
| Heatmap low to high | `#243044` → `#8eb4d4` → `#e6e0d4` | visible numeric scale |
| Stereo correlation | `#e8e6e1` | solid, on its own grid |
| Stereo side/mid | `#8eb4d4` | dashed, on its own grid |
| Estimated series | `#c5d0dc` | dashed |
| Playhead | `#e6e0d4` | solid, unlabeled |
| Review flags | `#c4a36a` | dashed |

Check the final hex values against `#14171c` before accepting them. Do not paint every series brass. Do not use `#9a3412` or `#1f4b99` for lines or bars.

### Typography

Use the existing system UI stack. Do not add a font.

| Element | Size and color |
|---|---|
| Plot title | Existing `.plot h2`. Add the evidence word on the same line: Measured or Estimated. |
| Axis title | 12px, `#a8b0ba` |
| Tick label | 11px, `#e8e6e1` |
| Legend | 12px, `#e8e6e1`, `type: "scroll"` when the row would wrap |
| Tooltip | 12px, ground background, ink text |
| Evidence heading | Existing inspector `h2` |
| Caveat | Existing `.quiet` / evidence `dd`. Do not shrink caveats below the body size. |

### Numbers

Format for display. Do not write the formatted string back onto the chart document.

| Quantity | Display |
|---|---|
| Time under one hour | `m:ss` |
| Time ticks closer than 2 s, and marker times | `m:ss.s`, markers stay at three decimals (`toFixed(3)` already) |
| Frequency under 1 kHz | integer Hz |
| Frequency at or above 1 kHz | `1.5 kHz`, `4 kHz` |
| Sample peak and reconstructed peak readouts | two decimals, `dBFS` or `dBTP`, matching the summary |
| Axis ticks for dBFS, dB, and LUFS | one decimal when the span is under 20, otherwise integers |
| LUFS and LU summary values | one decimal, as stored |
| Correlation | three decimals |
| Power-share and other percentages | one decimal |
| Pitch-class share | three decimals |
| Cosine similarity | two decimals |
| BPM bar labels | the stored label, unchanged |

### Axes, legends, tooltips, zoom

- Read the series `unit` for each axis title. When two units share a grid, the title lists both, and the legend item includes its unit. Prefer a second grid when the units are not the same quantity. T01 already does this for amplitude and dBFS. T05 needs the same treatment. T02 may keep one time grid because both traces are level-like, with the title `dBFS and LUFS` and units on the legend items.
- T03 PSD x-axis: ECharts `log`, `min` at the first stored positive frequency, `max` at the last stored frequency. No new samples. Bar axis stays category.
- T04 and T09: keep category axes and the stored coordinates. Replace crowded labels with blanks except for a short list of indexes. For T04, choose rows nearest 50, 100, 200, 500, 1k, 2k, 5k, 10k, and 20 kHz, clipped to Nyquist. For T09, aim for about six time labels per side at phone width and about ten on desktop.
- Tooltip: axis trigger, series name, display time or category, stored y to the precision above, and the series unit. The playhead series stays `tooltip.show: false`.
- Zoom slider: when the axis is file time, label the ends as time. When it is frequency, label them as frequency. Do not show a bare percent. Height about 22px so the label is not clipped. Inside-zoom stays.
- Uncertainty: the plot title carries Measured or Estimated from `evidence_class`. Caveat text stays in the inspector. Do not add words such as “detected”, “key”, or “section” that the document does not use.

## 4. Responsive chart strategy

`workspaceMode` and `plotBudget` in `frontend/src/catalog.ts` stay the layout contract. Chart ticks should follow the plot element’s width inside the existing `ResizeObserver`, not `window` width. A resize updates options with `setOption`. It must not dispose the instance, because playback is updating the playhead on that instance.

| Viewport | Layout already shipped | Chart behavior to add |
|---|---|---|
| 1440×900 | Rail 176, list 160, inspector 220, plot about 828 | Legend on one scrolling row. Inspector stays beside the plot. |
| 1280×800 | List beside, inspector under, plot about 900 | Same chart rules. The extra plot width is the reason the inspector moved. |
| 1000×800 | Horizontal chart row, inspector under, plot at least 720 | Legend scroll. No new column. |
| 390×844 | Top bar, one `<select>`, inspector under, plot is the content width minus 32px, chart height 18rem | Sparse ticks, scroll legend, slider labels in time or hertz. |

Desktop plots already dominate once the inspector drops below 1332px. Pass 3 should not put the inspector back beside the plot at 1280 or 1000.

At phone width, do not scale the desktop option down. Use fewer tick labels, a scroll legend, and the existing select. If a heatmap is still illegible after sparse ticks, the fallback to propose — and not to build without approval — is a plot-first disclosure: the inspector collapses to a summary line, and the heatmap uses the freed height. The default remains inspector-under-plot.

A narrow chart stays meaningful when the axis title, the unit, the evidence word, and at least the end ticks are readable. Truncating the series to make the axis look cleaner is out of bounds.

## 5. Inspector and navigation

The 160px list (`10rem`) and 220px inspector (`13.75rem`) are wide enough for the job if the text is structured. Replacing the workspace grid is not justified.

Navigation:

- The plot `h2` already shows `T01` plus the full title. The button can show `T01` and a short name (`Waveform`, `Loudness`, `Spectrum`, `Spectrogram`, `Stereo`, `Pulse`, `Pitch`, `Novelty`, `Recurrence`, `Events`) plus the status. The select on phones already has the full title.
- Keep `aria-current`. The brass inset on `.category` is a clear selection mark.
- From 928 to 1099 the button row scrolls horizontally with no hint that more charts exist. Add a fade or padding at the end of `.chart-buttons` so the clip is visible. Do not switch that range to the phone select; the row is the Pass 2 rule.

Inspector:

- Group the definition list: Identity (class, method, version), Figures (summary), Limitations (caveats).
- Keep every caveat visible. A disclosure may wrap the method id, not the limitation text.
- Summary values stay the API strings. `formatLabel` and `clock` are for transport chrome, not for rewriting summary numbers.
- T03’s eleven summary rows and T02’s window rows are why the inspector feels dense. Grouping is the fix. Dropping rows is not.

## 6. Implementation units

One owner. Four reviewable units on one branch. No second agent. Do not start until the owner authorizes Pass 3.

### Unit A — Shared formatters and series encoding

Files: `frontend/src/chart-format.ts` (new), `frontend/src/chart.tsx`, `frontend/src/chart.test.tsx`.

Objectives: precision helpers, contrast-safe palette, dash patterns, tooltip formatter, zoom-end formatter, sparse category labels, evidence word. Wire them into `optionFor`, `withMap`, `pushLines`, and `zoom` without changing series data.

Depends on: nothing.

Acceptance: existing playhead, zoom-link, T01 resolution, T04 seek, and T06 axis tests still pass. New tests cover time, hertz, dB, LUFS, and correlation formatting, and they assert the document object is unchanged.

Risk: formatter output drifts into `markLine.xAxis` or seek values. Seek must keep using the raw number.

Browser: none beyond a smoke load. Unit tests carry this unit.

Deliverable: formatters in use on every ready chart, data unchanged.

### Unit B — T01–T04, zoom labels, and navigation

Files: `frontend/src/chart.tsx`, `frontend/src/analyzer.tsx`, `frontend/src/styles.css`, `frontend/src/catalog.ts` only if the short nav names live beside `TECHNICAL`, plus the chart and catalog tests.

Objectives:

- T01 legend scrolls or reserves real height so it does not cover the envelope. Resolution names stay.
- T02 axis title and legend units. Integrated summary stays out of the time series.
- T03 log PSD axis in ECharts only. Stored `y_scale` stays `linear`. Bar labels remain readable.
- T04 sparse frequency ticks and a visible color scale whose text matches the existing caveat (dB relative to the track median, peak aggregation).
- Zoom ends formatted from the axis.
- Short chart-nav labels and a scroll hint from 928–1099px.
- Plot title shows Measured or Estimated.

Depends on: Unit A.

Acceptance: the conditions in section 8 for T01–T04. `workspaceMode` boundaries stay 1332, 1100, and 928.

Risk: log axis breaks T03 click-seek. T03 x is frequency, and seek already returns only for file-time axes. Add a test that a frequency axis does not seek. Risk: sparse T04 labels change `yAxis.data` length and break heatmap alignment. Keep one category per row; blank the hidden labels.

Browser: T01, T02, T03, T04 at 1440×900 and 390×844.

Deliverable: those four charts plus the shared zoom and nav treatment.

### Unit C — T05–T10 and the inspector

Files: `frontend/src/chart.tsx`, `frontend/src/analyzer.tsx`, `frontend/src/styles.css`, `frontend/src/chart.test.tsx`, `frontend/src/catalog.test.tsx`.

Objectives:

- T05 two grids. Correlation axis −1 to 1. Side/mid in dB. Mono ready-state still not rendered.
- T06–T08 estimated heading. T07 share axis 0 to 1. T08 on-plot marker text yields to the list.
- T09 sparse time ticks and a labeled cosine scale. Crosshair playhead and linked zoom stay.
- T10 caption that the bars are ending levels and the list is the checkpoints.
- Inspector groups from section 5.

Depends on: Unit A and the zoom/legend behavior from Unit B.

Acceptance: section 8 for T05–T10. Lyric tests in `lyrics.test.tsx` still pass, including hidden and inert.

Risk: T05’s split changes `dataZoom.xAxisIndex` shape. Mirror the T01 expectation (both time axes in one zoom). Risk: T07’s 0–1 scale hides a flat distribution; call that out in the screenshot notes so it is not “fixed” later by stretching the axis.

Browser: T05, T06, T07, T09, T10 at 1440×900 and 390×844. One lyrics tab check that playback does not restart.

Deliverable: the remaining charts and the grouped inspector.

### Unit D — Visual and scientific QA

Files: none in production code unless a screenshot fails and the owner sends it back to A–C. QA notes do not go in the repository if they contain private audio. Use a synthetic fixture or a disposable local recording, and keep the images out of git.

Objectives: run the matrix in section 8. Compare against the Pass 2 appearance. Confirm series arrays and method fields are unchanged.

Depends on: A, B, and C.

Acceptance: the matrix passes, or the failures are listed without a drive-by fix.

Risk: treating a green Vitest run as visual acceptance.

Deliverable: the screenshot set and a short note of pass or fail per cell. The owner accepts or rejects Pass 3 from that note.

## 7. Regression and scientific integrity

Do not change:

- `backend/app/measure.py`, `backend/app/charts.py`, or `ALGORITHM_VERSION`
- Stored series, summaries, caveats, method ids, or `y_scale`
- Master bytes, hashes, or playback derivatives
- WaveSurfer lifetime, seek, volume, lyric drafts, revision conflicts, or `inert` on the hidden lyrics workspace
- Playhead update path (`useEffect` on `playhead` only calls `setOption`)
- T01 overview/detail switch thresholds and series names
- T04 click mapping from category index to `heatmap.x`
- T06 bar-axis name and the playhead’s absence from the bar grid
- T09 linked x/y zoom
- T10’s exclusion from the file-time playhead

PNG export will not match a log T03 or a visible T04 scale after this pass, because `png.py` is unchanged and current documents say `y_scale: linear`. A temporary presentation difference is proposed for Pass 3 and requires an explicit owner decision. The shared evidence and export consistency requirements still apply. See the [decision register](../OPEN_DECISIONS_AND_UNCERTAINTIES.md).

Chart rebuilds today happen when the `chart` object changes, which is a new document, not a playhead tick. Keep it that way. T01 still embeds the 4000-point detail series while the overview is selected. Leave that data in the option. T04’s 96×180 heatmap is about 17k cells and is fine.

The production bundle is one file, `dist/assets/index-*.js`, measured at 1,460.36 kB on the Pass 2 build. `frontend/src/App.tsx` statically imports `Analyzer`, which imports `echarts` as a namespace and imports WaveSurfer. Library, Album QC, and Settings therefore download the chart library too. Splitting the analyzer route would shrink the first load of those screens. The analyzer screen would still pay the cost on first open. That is a routing change with a loading gap and a test-import boundary. It is not part of Pass 3.

## 8. Browser QA and screenshot matrix

A green test run is not visual acceptance. Capture PNGs at the viewport size itself.

| Viewport | Full application | Close-up |
|---|---|---|
| 1440×900 | Technical Analysis with T01, then T04 | T01 legend, T02 axes, T05 grids |
| 1280×800 | T03, inspector under the plot | T03 frequency ticks |
| 1000×800 | Chart row scrolled to T10 | Zoom slider labels |
| 390×844 | Phone select, T01, T04, T09 | Tick labels and the color scale |

Also confirm, without a new product screenshot of private material:

- Playhead stays aligned with the transport time on T01 and T09.
- Seeking from a T04 click and from a T10 marker button uses the stored time.
- Switching T01–T10 does not recreate the WaveSurfer instance or drop the lyric draft.
- The lyrics workspace stays hidden and inert on the technical tab.
- No horizontal page overflow at the four widths.
- No console errors.

Pass 3 acceptance, all required:

- No overlapping legend or axis labels at the four viewports.
- Units and precision follow section 3. Stored values and method metadata match the Pass 2 documents.
- No fabricated samples, markers, or lyric times.
- Zoom and seek controls are fully visible.
- No horizontal page overflow.
- Charts at 390×844 keep a readable axis title, evidence word, and end ticks.
- Measured and Estimated are visible on the plot, and the status line still says Ready, Not available, or Failed separately.
- Playhead and marker timestamps match the transport and the document.
- Inspector figures match the summary strings.
- The plot image points at a text description of evidence class, axes, and summary. Color is not the only series encoding.
- Series colors meet the contrast bar, and hover, selected nav, and playhead states stay consistent with Pass 2.
- Playback and the lyric workspace show no regression in the existing Vitest files plus the browser scenes above.
- Side-by-side comparison with Pass 2 screenshots for T01 and T04.

## 9. Out of scope and technical debt

Out of Pass 3:

- Any change to analysis math, chart JSON, or `m1-v3`
- Relabeling Welch `dB` to dB/Hz
- PNG and ZIP export parity
- A new charting library or a new dependency
- The plot-first mobile disclosure, unless the owner approves it after seeing the 390px heatmaps
- A diverging T09 ramp
- Keyboard seek on the canvas, while the transport slider remains
- M2-C, album comparison, L01–L05, and the T02 stored-sample inspector

Separate debt, not this pass:

- The 1.46 MB chunk and the Vite warning. Address later with a lazy analyzer route if the first-load cost matters.
- Playback unavailable on one previously observed recording. The cause and current reproducibility are unverified. Playback investigation is outside this proposal.
- Analyzer with no asset. `App` sends the Analyzer nav button to `/analyzer` when no recording is open, and that route only says to choose one from the library.

## 10. Recommended order

1. Authorize Pass 3 explicitly, or stop.
2. Unit A, then tests.
3. Unit B, then tests and the T01–T04 screenshots.
4. Unit C, then tests and the T05–T10 screenshots.
5. Unit D against the full matrix.
6. Owner reviews the screenshots. A passing suite does not close the pass.

See [Project status](../../PROJECT_STATUS.md) for accepted checkpoints and [NEXT_SESSION.md](../../NEXT_SESSION.md) for the continuation gate.
