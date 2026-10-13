# Audio Reference Studio — Technical Analysis & Chart Requirements

**Status:** Required companion to the revised MVP specification. Technical analysis is a **first-class product workflow** and works with WAV alone, independently of the five-chart lyricist package. These are implementation requirements, not proof that any algorithms are already validated.

## 1. Core principles

- **One measurement source of truth:** compute and store numeric observations once; reuse them for browser charts, static PNG exports, reports and album comparison. Never fabricate chart series on the frontend.
- **Scientific labels:** `measured`, `estimated`, `textual`, `interpretive`, `unknown`, or `not_applicable` with methods/versions, units, timing and caveats. Mark tempo/key/section identification as estimated; peak overshoot/correlation changes as a listening checkpoint, not a certified audible problem.
- **Navigation:** Technical Analysis tab in every WAV study; Lyrics & Inspiration is additional. Allow switching charts without stopping playback. One shared seek/playhead and selection model wherever x-axis is time.
- **Images and data:** Every implemented chart has an interactive version where appropriate, an independently exportable PNG, concise caption, and relevant data table/JSON (CSV for tabular series where useful). Indicate missing calculations explicitly.
- **Presentation:** Respect linear vs log axes, frequency limits at Nyquist, dBFS vs dBTP vs LUFS vs LU, measured vs estimated boundary resolution, synchronized time labels and clear legend. Do not interpret band percentages as vocal level, exact instrumentation or perceived mood.
- **Accessibility:** chart alternative data table, readable color contrast, keyboard seek controls, color not sole information channel.

## 2. Chart catalog

| ID | Technical visualization | Evidence & recommended plot | MVP priority | Caveat |
|---|---|---|---|---|
| `T01` | Waveform and peak envelope | Multiresolution waveform + 100-ms / 1-s RMS, sample peak and notable event markers | Core | Peaks plotted at downsampled resolution may hide single-sample transients; show exact numerical markers separately |
| `T02` | Loudness and dynamics | Integrated LUFS/LRA/true peak/sample peak figures; 3-s short-term LUFS + 1-s RMS series; relative sections | Core | LRA is not crest factor; calibrated EBU R128 vs custom measurements must be separate |
| `T03` | Long-term spectral balance | Welch PSD in dB/Hz with correct frequency axis; band power percentages/table (20–60, 60–120, 120–250, 250–500, 0.5–2k, 2–5k, 5–10k, 10k–Nyquist) | Core | Spectrum shape not identical to perceived brightness or instrument identity |
| `T04` | Spectrogram / spectral evolution | Log-frequency or suitably annotated time-frequency energy heatmap; coarse bass/body/presence/air time traces | Core | Use explicit normalization and consistent time/frequency bins; never infer vocals from bands |
| `T05` | Stereo and mono compatibility | 1-s channel correlation, mid/side ratio, sub-120-Hz correlation, mono-vs-stereo power comparisons and review markers | Core, stereo only | Low correlation alone not proof of phase failure; mono returns `not_applicable` |
| `T06` | Rhythm and pulse evidence | Onset-autocorrelation candidates including half-/double-time hypotheses and onset-strength timeline | Core after core signal metrics | Does not prove beat-grid, meter, exact tempo, syncopation or groove feel |
| `T07` | Pitch-class/tonal estimates | Chroma/pitch-class distribution and optional time-dependent chroma; alternate key-candidate results with uncertainty | Core after core signal metrics | No verified chord progression or harmonic modulation |
| `T08` | Structure novelty | Relative spectral/feature-change curve, provisional transition markers and neutral signal regions | Core after core signal metrics | Change points are not verified verses/choruses; don't cap/count as formal complexity |
| `T09` | Recurrence and self-similarity | Within-track feature self-similarity heatmap and likely repeated regions, including score/method description | Core after core signal metrics | Similar textures ≠ matching melody or hook |
| `T10` | Ending, gap and anomaly review | Last-second level trace, subthreshold intervals, nonzero endpoint, short full-scale rail events, highest reconstructed peak timestamps | Core | Listening checkpoints, not established audible clicks/clipping |
| `T11` | Album multi-song comparisons | LUFS/LRA/true peak, spectrum overlays, dynamic curves, coarse spectral distances, tempo candidates and stereo comparison | Album QC milestone | Cross-song descriptor similarity is not creative or melodic similarity |

**MVP completion rule:** `T01–T05` plus `T10` work for supported input formats before calling the core technical analysis screen complete; `T06–T09` must be present by end of Milestone 1 when the existing estimated modules have passed the required basic validation. `T11` is delivered with Album QC Milestone 4. The first Cursor session (Milestone 0) only needs real waveform playback and truthful chart loading/not-run states.

## 3. Shared chart-series contract

A chart registry should expose: `chart_kind`, `status` (`ready|queued|running|not_available|failed`), `title`, `evidence_class`, `method_id`, `method_version`, `units`, `time_start_s`, `time_end_s`, `sample_rate`, `resolution`/`hop_size` where relevant, `axis_definitions`, `series`, `review_markers`, `caveats`, `data_url`, `png_url`, and `not_available_reason` where relevant. Numeric data points must be finite; sanitize silent/undefined correlations explicitly. For long files, decimate in the service with min/max-preserving waveform display buckets and document whether values are smoothed.

Handle mono by showing waveform/levels/spectra and marking stereo charts N/A, not by silently inventing a right channel. Frequency ceilings must respect the sampling rate. For very short clips, omit windows that cannot be computed and explain why.

## 4. Technical package profile

A `technical` export produces a folder such as:

```text
technical/
  README.md                   # methodology, version, confidence, limits
  technical_summary.md       # facts and review points, no hallucinated listening
  metrics.json               # complete per-track numeric metrics
  evidence.json              # typed source/interval/method/units/limitations
  charts/
    T01_waveform_levels.png
    T02_loudness_dynamics.png
    T03_spectral_balance.png
    T04_spectral_evolution.png
    T05_stereo_mono.png       # only if applicable
    T06_rhythm_pulse.png
    T07_tonal_estimates.png
    T08_structure_novelty.png
    T09_recurrence.png
    T10_events_endings.png
  data/                       # bounded JSON or CSV chart series as warranted
  manifest.json               # hashes, chart status, algorithm versions
```

Absent experimental or inapplicable charts should be recorded in the manifest but not replaced with misleading placeholder images. The actual set may vary by stereo/mono and method availability. Default packages exclude raw WAV and full third-party lyrics. The `lyricist` profile has five separate source-grounded charts and a Markdown brief; `combined` includes both namespaces and one shared canonical evidence set.

## 5. Validation fixtures / tests

1. A 16-bit and 24-bit same-amplitude signal produce consistent dBFS after normalization, within declared tolerance. Regression covers the old `peak_details.py` 16-bit scaling bug.
2. Stereo identical-channel tone has correlation near +1 and minimal side component; reversed-polarity channels show the expected negative correlation and mono cancellation; mono input disables stereo metrics.
3. Synthetic sine wave energy concentrates in expected frequency bands; no spectral bin exceeds Nyquist; PSD/band integration convention is documented.
4. Known-loudness/peak fixtures cross-check FFmpeg with explicit tolerance; a narrow oversampled peak test distinguishes dBTP from dBFS without assuming audibility.
5. Silence produces no NaN/Infinity in plots, JSON or PNG labels; zero-length/out-of-range inputs return clear errors.
6. Rhythm/novelty/recurrence are tested for deterministic operation and reasonable synthetic patterns. Do not claim calibrated key/tempo accuracy without external benchmarks.
7. Chart click at time `t` seeks audio to `t` within player tolerance; export time positions agree with interactive data.
8. Same WAV + same analysis version produces cached chart values; lyric text edits do not invalidate technical metrics.
9. WAV without text produces a valid Technical ZIP. Adding TXT/SRT enables Lyricist ZIP without redoing DSP; Combined ZIP carries both without duplicating raw audio/metrics.
10. All outputs disclose direct listening and perceptual limitations. No API key or network request is required for technical exports.

## 6. Defer deliberately

Actual vocal/instrument recognition, drum transcription, singing word alignment, isolated stem diagnosis, music-emotion classification, exact chords, automatic mixing/mastering repair, and automated recommendations to change sound should remain future experiments until evaluated. The engineering charts remain valuable even when these capabilities are absent.
