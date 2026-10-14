# Album Observatory reference review

Research only. No application code was changed. The package is at `references/album-observatory/`. The path named in the request, `research/references/album-observatory/`, is not in the tree. `.gitignore` ignores only that missing path, so the real package is still committable. Do not commit it: it contains personal lyrics, hashes, and analysis prose.

This review did not open the observatory in a browser and does not quote lyrics, titles, hashes, or findings. Layout and accessibility notes come from `index.html`, `src/app.js`, `src/charts.js`, and `src/style.css`. The package’s own `VALIDATION.md` already says real-browser QA was not run.

## Executive assessment

Album Observatory is a buildless viewer for one finished eight-song synthesis. It loads a versioned JSON envelope, draws dependency-free SVG charts, and keeps six views over the same in-memory selection: overview, track explorer, pairwise comparison, lyrics and events, research reports, and a PNG atlas. It has no WAV masters, no playback, and no new measurements.

The useful part is the inspection habit: a plotted point is a stored sample, the unit stays visible, a short explanation refuses a perceptual reading, and an annotation can jump to that interval without becoming musical form. The weaker part is the evidence vocabulary. Confidence, timing doubt, and interpretation are free-text phrases. That is more expressive than a single badge and less safe than this project’s closed `evidence_class` and separate `status`.

Audio Reference Studio is already the system the observatory’s own frontend notes say to build next: local WAV identity, playback, a shared playhead, and method-versioned chart documents. Milestone 1 charts T01–T10 and the M2-A/M2-B lyric workspace cover that. Album comparison, L01–L05, and ZIP export are specified and not started. The reference does not replace those decisions.

## Existing-project compatibility

| Observatory idea | Fit |
|---|---|
| One selected recording survives view changes | Already true for one asset (`/analyzer?asset=&project=`). An album order that is not the source id is a Milestone 4 concern. |
| Click a time and inspect a stored sample | Compatible. Charts already seek when the axis is file time. The missing piece is a readout of the nearest stored point. |
| Plain-language metric explanation next to the control | Compatible. Use the chart document’s unit, `evidence_class`, and `caveats`. Do not compute a series in the browser. |
| Lyric or section interval that seeks | Partly done. WaveSurfer regions and review-marker buttons already seek. Chart interval overlays are M2-C (`regions` / `markArea` on L01–L05), not a new product. |
| Duration-normalized versus clock-time comparison, y units unchanged | Compatible with T11 later. Do not add it on the Album QC placeholder. |
| Expandable claim with source, interval, and a verification action | Compatible with `EvidenceRef`, `ReviewMarker`, and lyric `timing_origin`. Do not replace those fields with prose categories. |
| Static PNG when the numeric series was never stored | Poor fit. This app’s PNGs are renders of the same chart document. An image-only atlas is a fallback for a package that dropped series, not a chart type to add. |
| Narrative, motif, emotional-arc, and originality views | Conflict. Spec non-goals. The observatory labels them as text-supported interpretation; they still do not belong in the analyzer. |
| Client-held 4 MB album payload and SVG charts | Conflict. Measurements stay in `m1-v3` documents. ECharts stays the chart renderer. |

Current product, for orientation:

- Accepted: WAV ingest, playback from the master or the 24-bit dithered derivative, T01–T10 from API chart documents, evidence class separate from status, job cache at `m1-v3`.
- In the working tree, not a new milestone: lyric documents (TXT, Markdown, SRT), timing origins, manual verification, annotations, and waveform regions tied to the same transport.
- Specified and not started: L01–L05 (M2-C), ZIP export and optional narrative (Milestone 3), Album QC / T11 (Milestone 4). The Album QC route is an empty state on purpose.

## Features worth adopting

Ranked by value to the current analyzer, then cost, then how cleanly they sit on the existing contract.

1. **Nearest stored sample, with its unit and a non-perceptual sentence.** High value, low complexity, already compatible. The observatory’s explorer is a one-second series plus a range slider and a tooltip that names the actual point. This app already moves a playhead and zooms with ECharts, but the evidence pane is still class, method, summary, and caveats. A readout of the nearest document point at the playhead would make T01/T02 inspection concrete without a new measurement.

2. **A claim receipt that keeps three uncertainties apart.** High value, low complexity. Observatory findings expand into evidence, impact, what to verify, what not to conclude, and a time interval. Confidence there is a sentence, not a score. This project should keep `evidence_class` and `status` as they are. The presentation gap is that a review marker or lyric cue does not yet show, in one place, the class, the timing origin, the caveat, and the listening action. `EvidenceRef` and `ReviewMarker` already have the fields.

3. **Interval controls that seek and, later, share a zoom window.** Medium value now, higher once L01 exists. Section strips in the reference zoom the chart to a provisional text interval and say the interval is not formal structure. Review-marker buttons already seek. Sharing the chart zoom with the waveform zoom is in the analyzer spec and is not implemented. Do not invent section labels to get the strip.

4. **Capability gate before any comparison.** High value at Milestone 4, wrong to build now. The reference refuses to plot phrase occupancy beside word occupancy, leaves nulls null, and states that duration normalization changes only the x-axis. T11 should copy that rule: an allow-list of comparable features, original units on y, and an explicit raw-seconds versus progress mode. No interpolation and no beat alignment.

5. **Album position separate from asset identity.** Medium value, Milestone 4 only. Source track ids in the reference are not the approved sequence. This app already has `project_assets` ordering and content hashes. A later comparison view should display order as order and identity as hash plus analysis version, not as a filename.

6. **Keyboard path to the same sample the pointer sees.** Medium value, low complexity, pairs with item 1. The reference uses a native range input and `aria-live` because the SVG hit targets are not a data table. Chart requirements already ask for a keyboard seek and an alternative to color. A readout satisfies more of that than another hover tooltip.

Visual system: both apps are dark, side-navigated, serif-titled, and stack under a narrow viewport. The observatory adds a skip link, `aria-current`, and a native image dialog. This app already has visible focus, a 860 px stack, and reduced motion. Restyling to the observatory palette would not add a capability.

## Features to avoid

- Importing the observatory runtime, `album.json`, or `album-data.js`. The envelope is one album’s editorial synthesis, duplicated as JSON and a global script so a file URL can open it.
- Replacing ECharts with the SVG helpers in `src/charts.js`. Those helpers fit a few thousand one-second points. They do not do linked axes, heatmaps, or the decimated waveform T01 already draws. The observatory’s own architecture note says a full chart library is the right replacement for denser data.
- Free-text evidence categories and confidence strings as stored fields. The reference mixes method, timing doubt, and interpretation in one phrase (`medium temporal / low musical`, and similar). That is the failure mode its own research list warns about. Map nothing from that vocabulary onto `evidence_class`.
- Whole-file similarity, PCA coordinates, motif lexicons, narrative labels, and “emotional journey” charts. Cross-song feature distance is not melodic or creative similarity. T11’s caveat already says so. Narrative charts are outside v0.1.
- Treating a one-second RMS bin as a waveform, or a text heading as a verse. The reference captions this. T01 and T08 already make the stricter distinction.
- Gapless album time. The reference offsets tracks by duration and says assembly gaps are unknown. Do not draw an album timeline until a project stores order and an explicit gap policy.
- A second chart path that plots in the browser from raw metrics. Chart documents stay the source. Matplotlib PNGs stay renders of those documents.
- Marked-rendered research reports inside the product. Useful as a personal archive. The app’s report is `evidence.json` plus chart caveats, later a ZIP README.

## Important architectural differences

**Runtime.** Observatory: one HTML file, classic scripts, no build, no network, no database. This app: React 19, Vite, FastAPI, a worker, SQLite, content-addressed blobs. The split exists so analysis does not run in the page and so a chart can be regenerated from a versioned cache.

**What “data” means.** Observatory normalizes existing CSV/JSON into `schemaVersion`, `tracks`, `tables`, `reports`, `provenance`. A track carries identity, whole-file metrics, a 1 s series, text sections, lyric line spans, hooks, density bins, and a narrative record. Tables keep matrices and registers. This app stores a master blob, an `m1-v3` analysis cache, and a separate lyric document whose revision is not part of the analysis cache key. Chart JSON is per chart, not one album document.

**Time resolution.** Observatory plots one-second bins and says it cannot resolve sub-second events. Short-term loudness exists only as a PNG. This app’s T01 is a min/max envelope plus 100 ms and 1 s RMS, with the sample peak as its own marker. Playback peaks are a different series from T01.

**Evidence.** Observatory: prose class on a metric descriptor (`measured`, `estimate`, `text`, `interpretation`) plus a separate confidence sentence on each annotation. This app: `measured | estimated | textual | interpretive | unknown | not_applicable`, and status `not_run | ready | not_available | failed` (jobs add `queued | running | canceled`). Tempo, pitch-class, structure, and recurrence stay estimated. Lyric timing is `unplaced | subtitle_supplied | manual_edit | manual_verified`, with validation codes for bad cues. Those two layers should stay split. The reference’s prose is a reminder to show the split, not a schema to copy.

**Playback.** Observatory cannot check a caption against sound. This app can, and it refuses to invent sung times. The reference’s recommended prototype — local WAV plus a synchronized cursor, with alignment notes kept off the original evidence — is the lyric workspace already in the tree.

**Identity.** Observatory joins album position, title, source id, package, and file hashes, and records that WAV bytes were not re-verified. This app hashes the upload on ingest and plays or analyzes that blob. A later album view can show several assets. It should not trust an external synthesis hash as proof the local master is the same file.

## Potential technical risks

- Committing `references/album-observatory/` would publish personal lyrics and analysis. The ignore rule points at a path that is not the folder on disk.
- Copying a similarity kernel, z-score, or PCA loading into T11 would present an eight-song population statistic as a general musical distance. Rankings in that package move when one feature is omitted. Any future distance needs a versioned feature list, a population definition, and the T11 caveat on screen.
- Collapsing “high measurement; audible effect unknown” into `measured`, or into a QC failure, would erase the listening-checkpoint rule T10 already uses.
- Overlaying lyric spans on a 1 s grid, or treating enclosing line spans as word onsets, would look more precise than the data. Phrase-only cues are not comparable to word cues. This app already keeps unusable cues off the time axis; a chart overlay has to do the same.
- A client-side album document would bypass the worker, the cache key, and the rule that the browser does not compute loudness, spectra, or peaks.
- The observatory’s true-peak descriptor is an estimate at 0.1 dB. This app’s true peak is an FFmpeg measurement with an audibility caveat. Do not reclassify it to match the reference.
- SVG viewBox charts will not inherit ECharts zoom, playhead marks, or the heatmap path. A second renderer would split interaction behavior.
- Accessibility is unfinished on both sides. The reference has a skip link, live region, and slider, and no sample table. This app has focus rings and `role="img"` on the chart, and no alternate data table yet. Neither has been checked with assistive technology.

## Top three recommended improvements

1. **Playhead sample inspector on an existing time chart.** When the playhead moves, show the nearest stored x/y, the series unit, `evidence_class`, and one caveat. No interpolation, no new DSP, no album view. This is the reference pattern that the current analyzer does not already have.

2. **One evidence receipt for a review marker and a lyric cue.** Same screen region: what was observed, class or timing origin, interval, caveat, and whether listening is still required. Keep artist annotations labeled as annotations. This approaches the spec’s right-hand inspector without a new table.

3. **Write the Milestone 4 comparison rules down before any album UI.** Comparable metrics only, null stays null, y units stay source units, x may be seconds or progress, album order is not identity, feature distance is not musical similarity. The observatory is the example of those rules. Building the screen now would skip M2-C and the accepted chart baseline.

Items 1 and 2 can land on the current analyzer. Item 3 is a constraint for later, not a feature to start.

## One bounded experiment

**Question.** Does a nearest-sample readout make T02 easier to trust than the summary list alone, without looking like a new measurement?

**Scope.** T02 only, in `ChartView` or a sibling that reads the loaded chart document. Follow the playhead this app already publishes. Display time, the nearest stored RMS (or the documented T02 series actually in view), its unit, `evidence_class`, and the first caveat. If the playhead falls between samples, label the point as the nearest stored sample and show that sample’s time, not the playhead time. Add a native range input only if the pointer tooltip cannot be reached from the keyboard; prefer driving the existing playhead.

**Out of scope.** No new metric, no lyric overlay, no second chart library, no Album QC, no change to `m1-v3` bytes, no observatory data.

**Check.** One Vitest: a fixture document with uneven times yields the nearer stored point, and the readout does not show a linearly interpolated value. Playback behavior stays covered by the existing playhead test.

**Stop rule.** If the readout only repeats the ECharts tooltip, keep the caveat sentence and drop the extra control.
