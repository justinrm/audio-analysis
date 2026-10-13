# Four-Song Audit Evidence — Static Script Review

**Input inspected:** `Four_Song_Audit_Evidence.zip` (37 entries; four Python scripts, metrics/details JSON, four NPZ feature files, charts and report).  
**Scope:** Source reading, AST syntax validation, stored JSON/array manifest check. **Not executed end-to-end:** original four WAV files are not in the archive. All conclusions about runtime behavior outside the archived successful run are static-code judgments.

## 1. What is actually present

| File | Lines | Role | Salvage verdict |
|---|---:|---|---|
| `analysis/analyze.py` | 234 | Four-file ingestion, technical metrics, SciPy audio features, 5 charts | **Port core DSP, separate IO and charts** |
| `analysis/peak_details.py` | 60 | 4x true-peak check, transient/mono/end details and pairwise comparisons | **Port with correct audio subtype handling** |
| `analysis/finish_features.py` | 44 | Refines pulse scores, mono/drop intervals, energy pairwise stats and renders 3 charts | **Fold into feature and renderer stages** |
| `analysis/build_report.py` | 303 | Writes handcrafted four-song prose, Markdown, PDF, CSV and ZIP | **Replace narrative/report layout with generic templates** |

The scripts all parse syntactically. Archived `metrics.json` contains four tracks in order (Good Girl, She Calls Me Back, Nothing Holy Happens, Hold Still), and `details.json` contains six pairwise comparisons. The archived metrics reproduce the positive reconstructed true-peak observations reported by the audit. **This does not independently reproduce the underlying measurements.**

## 2. Detailed assessment

### `analyze.py` — reuse the mathematical intent, not the monolithic form

**Good:** direct signal analysis with NumPy/SciPy, stereo-average Welch spectral statistics, FFmpeg `ebur128` / `loudnorm` cross-checks, independent description of uncertain pulse/key/section extraction, read-only source validation and feature arrays stored in `.npz`. The chart outputs use measured units and caveats.

**Changes required:**
1. `FILES=[...]` and four `COLORS` plus letter IDs hardcode the original album. `ROOT/'upload'/name` assumes local filenames, and output formatting assumes exactly four recordings.
2. Imports, metric extraction, cache writes, chart rendering and summary operations run as top-level script execution. There is no callable `analyze_file(path, config)` API, no exception model and no job state.
3. `wavfile.read` scales int32 by 2**31 and int16 by 2**15, which is suitable for the audited PCM forms but does not intentionally cover floats, mono, all WAV subtypes or streaming decode of very large files. Add validated subtype handling and explicit unsupported-format errors.
4. `hashlib.sha256(p.read_bytes())` holds full WAV bytes in memory during hashing; convert to buffered/chunked hashing.
5. `sr2=sr//4` assumes the downsampled effective rate follows an integer fourth of the native rate. Use explicit rational resampling and actual resulting sample rate.
6. Multiple STFT matrices, chroma, spectrograms and feature maps are retained simultaneously. Benchmark and cap runtime/memory on Apple Silicon; chunk where practical.
7. `np.corrcoef` on extremely low-variance windows and multiple log/division expressions can yield NaN/inf. Define silence semantics and finite-value guards.
8. Feature-transition candidates use an arbitrary top-twelve cutoff and heuristic filters; this is **estimated change**, not 12 true musical sections. Preserve method version and uncertainty.
9. `metrics.json` is rewritten once per track, incorporating raw 0.1-s loudness records, and the script writes figures into `output/` without creating that directory itself. Separate compact metric summary from large frame data and make paths explicit.
10. FFT defaults/thresholds are research heuristics, not calibrated standards for tempo, key, novelty or recurrence; add synthetic fixtures and method comparison tests.

### `peak_details.py` — concrete 16-bit incompatibility

**Good:** chunked 5-s `resample_poly` 4x peak inspection with edge context, timestamps/channels, event candidates, local mono tests, interval-level summary and pairwise distances.

**Changes required:**
1. `x=raw.astype('float64')/2**31` is unconditional. For 16-bit WAV it mis-scales audio by 65,536x. The PCM-rail check for `-2**31` and `2**31-256` also assumes SciPy's left-justified int32 representation of 24-bit samples. Reuse a single validated decoding/scaling function for every script.
2. It loops over existing `metrics.json` and NPZ files. Cannot run standalone and assumes inputs are already populated.
3. Oversampled sample >1 events are not proof of audible clipping; keep the existing caveat and version/filter specifications.
4. Pairwise comparisons and file paths should accept arbitrary selected track lists instead of a four-file corpus.
5. Tail calculations/log10 should guard silence and very short files; output through typed records instead of arbitrary dict mutation.

### `finish_features.py` — valid supplementary work, wrong orchestration

**Good:** pulse-lag interpolation, mono power reductions, threshold gap runs, optional relative-time energy correlations, heatmaps and chart polishing.

**Changes required:**
1. `zip(R,D['details'])`, `for i in range(4)` and four fixed colors assume the archived corpus.
2. Rewrites previously produced JSON and figures. Ordering/invalidation is implicit and fragile.
3. Interpolation divides by a 2nd-order denominator without an explicit near-zero guard.
4. Silence and stereo computations again use unconditional int32 scaling.
5. Move derived metric transforms into pure functions and renderers to idempotent steps.

### `build_report.py` — retain presentation lessons, not content

**Good:** report has clear measurement vs estimation labels, readable tables, illustrated Markdown/PDF, CSV exports, method disclosures, source hashes and evidence ZIP without WAVs.

**Changes required:**
1. Fixed title, specific song names, dates, BPM families, musical judgments and timestamp prose embedded directly in source (e.g. first-page executive summary and fixed track tables). None generalize to new reference songs.
2. Four tracks, 24-bit PCM, pairwise explanations and specific filenames are embedded throughout.
3. Hand-rolled Markdown-to-PDF parser will be brittle for arbitrary lyrics/tables and is not needed to get an MVP working. PDF is optional, after Markdown/PNG/ZIP.
4. Generate report claims from evidence records, approved text templates, and separate optional LLM interpretations. Require review before narrative claims are exported.
5. Avoid reading all originals into memory to verify hashes on export; verify via streamed SHA. Export reproducible manifest + analysis version.

## 3. Extract into the new package

| New Python module | Seed material |
|---|---|
| `core/audio_io.py` | WAV subtype decoding, validation, duration/hash/probe from `analyze.py` — rewritten for generic files |
| `core/loudness.py` | `loudness()` FFmpeg scans, structured return, parser tests |
| `core/levels.py` | RMS, crest, percentile, channel energy, frame/block helpers |
| `core/stereo.py` | L/R correlation, M/S power, mono check, 120-Hz filtered stats |
| `core/spectrum.py` | Welch PSD, spectral bands and centroid |
| `core/peaks.py` | 4x oversampling and short rail-event detection from `peak_details.py` |
| `core/rhythm.py` | onset autocorrelation from `rhythms()`; expose multiple pulse candidates |
| `core/tonality.py` | heuristic chroma and key estimates; do not elevate to facts |
| `core/structure.py` | novelty, transition candidates, recurrence windows and heatmap arrays |
| `core/compare.py` | multi-track spectral distances, conditional energy comparison |
| `lyrics/parse.py` | new TXT/MD/SRT tokenizer, cue parser, source/line IDs, repeated phrases |
| `charts/technical.py` | full technical visualization suite, populated from canonical metric and feature arrays; standalone WAV-only exports |
| `charts/reference.py` | five-chart lyricist package renderer, independent of report prose |
| `charts/qc.py` | album QC graphics |
| `reports/reference.py` | deterministic Markdown + evidence citations |
| `providers/nim.py` | optional text interpretation; no raw audio or hidden API calls |

## 4. Action priorities

**Block before shipping:** valid integer/float WAV normalization; remove fixed names/count; worker handling and robust errors; correct source hash/caching; no invented vocal alignment; render into created output directory; avoid silent nonfinite data; ensure charts show all labels with units.

**Next:** validate algorithms against both synthetic fixtures and original WAVs, input sample rates beyond 48 kHz, mono, short files and long audio. Set measurable tolerances; do not change algorithms solely to improve attractiveness of plots.

**Later:** source separation, actual vocal perception, singing forced alignment, learned embeddings and PDF report renderer.

## 5. Critical caveats and reuse rights

- **Previous algorithm outputs are method-specific.** The four archived examples show it worked once with those files; they do not establish numerical parity on other formats.
- The `Praise Kink` package's five PNGs/Markdown provide the target **output presentation**, but its generating Python source code was not included in the materials reviewed. Treat reproduction of that formatting as a new renderer implementation.
- Technical reporting is not a listening test: no signal-analysis algorithm used here establishes an instrument, melody, vocal delivery, or the emotional meaning of a musical passage.

## 6. Recommended refactoring strategy

1. Write tests for current archived metrics JSON schema and core formulas.
2. Move `analyze.py` DSP into pure, stateless per-track functions, preserving original constants with explicit config/version identifiers.
3. Replace decoder with one robust `AudioData` interface and allow appropriate chunk/window consumers to avoid repeated entire-song copies.
4. Call comparison analysis only for an album of 2+ tracks; per-song analysis runs independently.
5. Build the core technical dashboard/renderers from measured and estimated features (WAV-only), then rebuild the separate five-chart lyricist renderer with optional lyric evidence. Technical and lyricist PNGs must draw from the same canonical feature store.
6. Implement two independent export profiles plus a combined profile, all backed by an evidence manifest.
7. Store `analysis_method_version` and reanalyze explicitly when algorithms change; keep old evidence packages valid and inspectable.
