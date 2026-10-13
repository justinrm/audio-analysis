# Audio Reference Studio — Technical MVP Specification

**Status:** Revised proposed v0.1 implementation baseline; technical diagnostics and lyricist references are equally first-class; not an existing implementation  
**Prepared:** 2026-10-12  
**Ownership:** Local, single-user, human-in-the-loop. Cursor is the implementation environment.  
**Source authority:** User-provided four-song audit scripts/data and five-chart `Praise Kink` reference. Protect source audio and preserve evidence/uncertainty distinctions.

## 1. Product and product boundaries

### Co-equal primary goal A — Technical audio laboratory
Build a polished interactive **Technical Analysis** workspace for single recordings, providing numeric measurements, detailed diagnostic charts, time-linked inspection, method disclosures, and standalone technical exports. No lyrics or AI account are required. The original four-song Work audit and `Little Mouse` technical charts are the visual/measurement baseline. Preserve the distinction between signal evidence and audible defects.

### Co-equal primary goal B — Musical inspiration references
Convert a WAV plus optional TXT/MD lyrics or SRT subtitles into a structured **Musical Inspiration Reference Package**: synchronized audio and lyric evidence, useful images, and a self-contained Markdown brief for a text-and-image-only lyricist agent.

### Complementary goal — Album / Master QC
Compare multiple recordings' objective metrics and generate focused human listening checkpoints (peak overshoot, mono review, endpoint checks, dynamic differences). Do not conflate this with songwriting inspiration. Technical diagnostics should not be hidden behind album mode.

### Non-goals for v0.1
- No autonomous songwriting, music generation, Suno integration, remix, or changes to audio masters.
- No cloud deployment, sign-in, payments, shared libraries, team collaboration, or public uploads.
- No guaranteed recognition of vocals/instruments, specific keys, chord progressions, listening emotions, or AI artifacts.
- No mandatory audio ML models, GPU, NIM account, or external API.
- No claims that subtitle boundaries equal word-level singing alignment.

### Success condition
One person can import a WAV **without lyrics**, inspect an interactive technical analysis dashboard, and export a reproducible **Technical Analysis Package** (diagnostic PNGs + metrics/data + methodology). With optional lyrics, they can also explore synchronization and export the **five-chart Lyricist Reference Package**. They can select **Technical**, **Lyricist**, or **Combined** exports and can compare multiple songs in Album QC. All baseline features work offline with NIM disabled.

## 2. Recommended stack — deliberately selected

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | **React + TypeScript + Vite** | Real web-app separation; can later deploy UI independently of the analysis API |
| UI | Tailwind CSS + shadcn/ui primitives; Lucide icons | Accessible components with restrained, polished styling |
| Playback | wavesurfer.js; backend-generated waveform peaks when necessary | Seeking, regions, cursor, time ruler and selected-range audition |
| Analysis graphs | Apache ECharts | Linked time cursors, zoom, repetition heatmaps, timelined annotations |
| API | **FastAPI + Pydantic** | Typed contracts, file upload endpoints and generated OpenAPI schemas |
| Job processing | Local worker **separate process** + SQLite job status | CPU-bound analysis should not block request processing; no Redis required |
| Metrics | FFmpeg/FFprobe, NumPy, SciPy, SoundFile | Match audited methods where validated; precise waveform and metadata handling |
| Music features | Initially port audited SciPy heuristics; optionally add librosa/Essentia after validation | Avoid swapping algorithms and silently changing old findings |
| Package visuals | Matplotlib (headless) | PNG generation independent of a browser, reproducible |
| Persistence | SQLite + filesystem content-addressed blobs | Local, easy backup, avoids databases/services initially |
| Reports | Markdown templates + optional local text LLM | Deterministic fallback, citation to evidence IDs |
| Optional model | Provider adapter for **NVIDIA NIM** OpenAI-compatible chat completion | Text-only interpretation when enabled and supported |
| Tooling | uv or venv + pytest + ruff; npm/pnpm + Vitest + React Testing Library + Playwright | Repeatable local development and validation |

Support macOS Apple Silicon and Python 3.12 as initial target; pin dependency versions during implementation, then verify actual wheel availability on the developer's Mac. Use no local CUDA requirement.

## 3. Screens, workflows and UI behavior

### Screen A — Library / projects
- New **Audio Study** (Technical + optional Lyrics tabs) or **Album QC** project. A WAV-only study is fully supported.
- Imported items with filename, duration, media format, timestamp, processing status and evidence-version tag.
- Reopen previous analyses without recomputing when the audio hash and algorithm version match.
- Delete a project and its owned copies/caches with confirmation; leave external originals untouched.

### Screen B — Audio Analyzer (main screen)
**Three-pane desktop workspace, responsive stacked mobile layout. The same song has two clear analysis tabs: `Technical` (default for WAV-only) and `Lyrics & Inspiration` (requires or invites text); the waveform and transport remain visible.**

1. **Top transport:** title, playback, seek, elapsed/duration, playback volume, selected-loop region, local/offline indicator.
2. **Left navigation:** Technical categories (Overview, Dynamics, Spectrum, Stereo, Rhythm & Tonality, Structure & Recurrence, Events/QC), Lyrics & Inspiration, Evidence; visible `measured / estimated / unavailable` labels.
3. **Center workspace:** synchronized waveform and selected interactive technical or lyric chart; zoom and click any timestamp to seek; highlighted time marker is shared.
4. **Right evidence inspector:** observation, exact time interval, source metric/lyric lines, confidence, explanation, artist annotation, and “needs listening” status.
5. **Bottom package actions:** Export Technical ZIP, Export Lyricist ZIP (when applicable), Export Combined ZIP, Reanalyze using updated algorithm, Regenerate narrative only.

**Visual direction:** dark neutral workspace, legible technical typography, one subdued accent, high-contrast charts, compact panels, generous spacing, responsive resizing. Do not mimic ChatGPT or Suno. Avoid decorative mock dashboards without functional controls. Charts need meaningful axis units and accessible alternative summaries.

### Screen C — Technical Analysis (core; works without lyrics)
- Provide real charts from measured/estimated features, not only tables, badges, or summary cards.
- Support time-based cursor synchronization, chart selection, units, tooltips, evidence citations, region playback, and chart-specific PNG/data export.
- Present **measurement** versus **estimate** versus **listening checkpoint** separately. A reconstructed true-peak event is *not* automatically audible clipping; spectral shape is *not* vocal intelligibility; a change point is *not* a verified chorus.
- Provide both overview and detailed plots, especially spectral and stereo evolution over time—not just whole-file averages.
- The core/chart list, method contracts, and acceptance tests are specified in `04_TECHNICAL_CHART_REQUIREMENTS.md`.

### Screen D — Lyrics + alignment
- Accept `.txt`, `.md`, or `.srt` alongside WAV. Plain lyrics have **line order** but **no verified timing**.
- Parse SRT into cues. Store original start/end, line text and cue IDs; normalize and show overlap/out-of-range errors.
- Display editable lyric segments alongside waveform regions; allow correcting timing manually.
- Track provenance: `subtitle_supplied`, `manual_verified`, `heuristic_proposed`, or `unplaced`. A manual edit does not claim it was acoustically verified unless the artist explicitly marks it verified after listening.
- Counts: words/line, approximate syllables if a deterministic estimator is added, repeated strings, phrase lengths and estimated words/second **only where timestamps truly exist**.
- Preserve original input text and add corrected versions separately; keep explicit notes on uncertain transcription.

### Screen E — Album QC
- Multi-select imported songs, order/reorder them for a listening sequence.
- Compare LUFS, LRA, sample and true peaks, RMS, crest factor, spectrum, stereo width/correlation, rhythm candidate families and endings.
- Click metrics to audition corresponding regions in a player; provide human checklist with `unchecked / confirmed issue / intentional / not audible`.
- Flag verified measurements for review, *not* automatic verdicts of defective mastering.

### Screen F — Package Preview and Export
- Choose **Technical**, **Lyricist**, or **Combined**. Technical is available with WAV alone; Lyricist requires or explicitly marks absent lyric evidence.
- Technical exports include reproducible mastering/level, spectral, stereo, rhythmic/tonal-estimate, structure/recurrence and event charts (per the core chart gate), metric tables, selected time-series data, methods/caveats, `evidence.json`, `manifest.json`, and ZIP.
- Lyricist exports include the five individually downloadable reference PNG images, a concise Markdown reference brief, `evidence.json`, `manifest.json`, and ZIP. Combined includes both namespaces without chart/data duplication.
- Export README with methodology, analysis version, source hash, confidence rules, timing status, and known capability limits.
- Choose **lyrics included**, **lyrics summarized**, or **lyrics omitted**. Default to summarized for third-party reference tracks (copyright-aware sharing).
- Export is a deterministic snapshot; no raw WAV in default ZIP. Allow re-export after manual alignment updates without repeating audio analysis. Export the same numbers shown in the interactive dashboard (within explicit rendering/downsampling tolerance).

## 4. Chart and analysis deliverables

### 4A. Required Technical Analysis charts
Technical inspection is a primary use case, not an optional QC sidebar. Implement the **core technical views** using the requirements and method/format contracts in `04_TECHNICAL_CHART_REQUIREMENTS.md`:

1. Waveform and time-indexed RMS/peak envelope with clipping/rail/reconstructed-peak annotations.
2. Integrated and time-varying loudness/dynamics (LUFS, LRA, true/sample peaks; time series with correct units).
3. Spectral distribution (Welch PSD, band powers, spectrogram/time-frequency overview).
4. Stereo and phase behavior (L/R correlation, mid/side, sub-bass compatibility; mono-listening markers), conditionally available for stereo.
5. Pulse/tempo evidence and tentative tonal/pitch-class analysis (explicit half/double-time and low-confidence caveats).
6. Provisional section novelty and structural change timeline.
7. Within-song recurrence/self-similarity heatmap, clearly distinct from exact melody matching.
8. Endings, near-silence, potential clicks and other inspectable technical events; these are **review flags**, not proven faults.

A technical export contains all **available core chart types** as individually labeled PNGs, with metrics/data and method versions. Surface algorithmically unavailable graphs as `not_available` with reasons rather than inventing results. The MVP gate does not require advanced ML-based instrument recognition, isolated vocals, or automatic chord transcription.

### 4B. Five required Lyricist Reference Package charts

1. **Unified music-and-lyrics timeline** — objective energy profile and provisional musical boundaries above; timed SRT/manual lyric regions below. Plain TXT-only lyrics remain **unplaced** until aligned: never invent exact sung timestamps.
2. **Phrasing and written density** — lyrics word/line profiles and interval-based written word rates (SRT/manually aligned only). Caption explicitly says word counts are not vocal delivery or breaths.
3. **Energy and dynamic contrast** — full-mix RMS/short-term LUFS, regional comparisons and transitions; no automatic labeling of emotions.
4. **Repetition map** — timbral/pitch-class feature similarity plus repeated textual patterns on separate axes. No conclusion that matching spectral patterns prove identical melodies.
5. **Musical DNA and transferable principles** — visual evidence summary with measured / estimated / textual / interpretive / unknown badges, citations to timestamp or line IDs; original reference mechanisms, no copied hook or lyrical identity.

**Important separation:** mastering metrics, spectral distribution, stereo evolution, and pulse/tonality estimates are first-class **technical** views, not merely optional QC charts. The Lyricist charts selectively reuse their evidence and add textual context; they must not replace the complete technical visualizations. Both interactive and exported charts derive from the same canonical analysis data.

## 5. Backend pipeline

**Ingest → Validate → Analyze → Normalize Evidence → (Optional Align/Annotate) → Generate Text → Render Charts → Export**

- **Ingest:** accept one or more WAVs, optional text/subtitle companion. Save uploaded bytes to managed local area; compute SHA-256 while streaming, do not `read_bytes()` entire large files merely to hash.
- **Validate:** probe codec/PCM subtype, duration, sample rate, channels, bit depth; refuse corrupted/unreasonably large inputs. Support integer PCM 16/24/32 and 32-bit float WAV; correctly scale or reject unsupported formats. Mono is allowed; stereo-specific metrics become `not_applicable`.
- **Decode:** control memory with blocks or chunking; preserve original sample rate for time-domain measurements; resample *analysis copies only* for onset/chroma. Never alter imported masters.
- **Measure:** standardized FFmpeg EBU R128 metrics; independent oversampled peak cross-check; RMS, spectral bands, stereo features, silence regions, rhythmic pulse candidates and provisional novelty/recurrence descriptors.
- **Normalize:** produce typed evidence records with time ranges, source, method identifier/version, value/unit, evidence class, confidence and constraints.
- **Interpret:** local deterministic summaries by default. NIM may rewrite prose from a validated *fact bundle only*, not raw WAV. Validate schema, citations and unsupported claims before accepting model output.
- **Render/export:** a canonical per-asset metric/time-series/feature dataset feeds ECharts browser views and Matplotlib PNGs; generate `technical/`, `lyricist/`, or both in ZIP. Markdown templates and manifests contain hashes, methods, generated-at, timing provenance, and unavailable-feature explanations. Atomic write to temp dir then rename to completed export.

### Technical guardrails
- Explicit `measured`, `estimated`, `textual`, `interpretive`, `unknown`; *quality* is not derived from a number.
- Distinguish raw sample peaks (dBFS) from reconstructed true peak (dBTP), and RMS from loudness.
- Fixed DSP defaults documented and versioned; record effective sample rate/hop/window/filter and time coordinate units.
- Bound computation time/memory on long audio; return helpful failure messages for decoding, subprocess and model errors.
- Use hash + algorithm-version + parameters as cache key, and lyric input/edit version separately; model narrative changes never invalidate raw audio metrics.
- Never call an external model when optional AI is disabled or an API key is missing.

## 6. Suggested domain entities (SQLite + schema)

- `Project(id, name, mode, created_at, updated_at)`
- `Asset(id, sha256, managed_path, original_name, media_type, bytes, duration, sample_rate, channels, subtype, created_at)`
- `ProjectAsset(project_id, asset_id, ordering, role)`
- `AnalysisRun(id, asset_id, algorithm_version, params_hash, status, started_at, finished_at, error, metrics_path, features_path)`
- `Evidence(id, run_id, evidence_class, metric, start_s, end_s, numeric_value, unit, text_value, method, confidence, caveat)`
- `LyricDocument(id, project_id, source_kind, source_hash, raw_text, revision)`
- `LyricSegment(id, document_id, line_number, text, start_s?, end_s?, timing_origin, artist_verified, revision)`
- `Annotation(id, project_id, asset_id, start_s, end_s, text, review_status, created_at)`
- `NarrativeRun(id, project_id, provider, model, evidence_hash, output_path, status, generation_settings)`
- `ChartArtifact(id, analysis_run_id, chart_kind, data_path, png_path, method_version, status, unavailability_reason)`
- `ExportRun(id, project_id, profile, manifest_path, zip_path, created_at, analysis_run_ids, lyric_revision)`

Add SQLite migrations early; keep asset IDs and UI URLs independent of filesystem paths.

### Evidence JSON example
```json
{
  "id": "ev:peak:00:94",
  "asset_id": "local-id",
  "kind": "measured",
  "name": "reconstructed_true_peak",
  "interval_s": [93.9, 94.1],
  "value": 1.15,
  "unit": "dBTP",
  "method": "oversampled_peak:scipy:4x:v0.1",
  "confidence": "high",
  "caveat": "Does not by itself establish audible clipping"
}
```

## 7. Local REST API (v0.1)

- `GET /api/health` — dependency and database status.
- `GET /api/projects`, `POST /api/projects`, `GET /api/projects/{id}`, `DELETE /api/projects/{id}`.
- `POST /api/projects/{id}/assets` — streamed WAV upload; returns asset and existing-cache status.
- `POST /api/assets/{id}/analyze` — enqueue analysis, returns `202` and job ID.
- `GET /api/jobs/{id}`, `POST /api/jobs/{id}/cancel` — lifecycle and progress.
- `GET /api/assets/{id}/stream` — seekable local playback, with range-request support and controlled paths.
- `GET /api/assets/{id}/metrics`, `GET /api/assets/{id}/features?kind=...`, `GET /api/assets/{id}/evidence`.
- `GET /api/assets/{id}/charts`, `GET /api/assets/{id}/charts/{chart_kind}/data`, `GET /api/assets/{id}/charts/{chart_kind}/image` — chart registry, bounded plotted arrays and static PNG with source/version metadata.
- `POST /api/projects/{id}/lyrics`, `PUT /api/lyric-segments/{id}` — ingest/edit timing.
- `GET /api/projects/{id}/reference-preview`, `POST /api/projects/{id}/narratives` — model disabled by default.
- `POST /api/projects/{id}/exports` with `profile=technical|lyricist|combined`, `GET /api/exports/{id}` — package creation/download.
- `GET /api/projects/{id}/comparison` — Album QC multi-track view.

Use finite / bounded chart arrays; return summarized/downsampled waveform peaks rather than millions of raw samples. For frontend typing, generate TypeScript definitions from OpenAPI rather than manually maintaining duplicated shapes.

## 8. Job execution, storage, configuration

- Development: Vite frontend on localhost; FastAPI bound to `127.0.0.1`; explicit trusted CORS origin only.
- Worker: separate process from API, **one audio job at a time** initially; persist status to SQLite (`queued`, `running`, `completed`, `failed`, `canceled`). On crash or restart, mark abandoned `running` as interrupted and allow retry.
- Avoid CPU-heavy work in FastAPI's ordinary request handlers/short `BackgroundTasks`; no Redis/Celery for one user.
- Default local data root e.g. `~/Library/Application Support/AudioReferenceStudio/`; project folders use UUIDs and SHA prefixes, never user-supplied filenames as trusted paths.
- Limits: configurable WAV size cap (initial default 500 MB), max length (initial 15 min per reference), analysis timeouts, bounded workers and parallel process threads.
- File hashes: streaming SHA-256. Store originals untouched; chart temp files removed after success/failure.
- Environment variables for provider endpoint/key; keys never sent to browser, logged, saved in exports or committed to repository.
- No public network binding, automatic telemetry or remote access by default. No login needed only because server is local; revisit auth before public access.

## 9. Optional NVIDIA NIM narrative adapter

Provider-neutral interface: `NarrativeProvider.generate(evidence_bundle, output_schema) -> StructuredNarrative`.

- Default provider: `none` (deterministic writing templates).
- Optional provider: NVIDIA API catalog OpenAI-compatible `/v1/chat/completions` with configured `base_url`, `model`, API key, request timeout and token budget. No assumption that any model accepts audio.
- Supply **only** structured metrics, bounded lyric observations, artist notes (optional) and citations; do not upload the WAV unless a separately authorized audio-capable provider is explicitly selected later.
- Require JSON schema/output validation if model supports it; otherwise parse and reject malformed/unsupported claims. Each paragraph/claim references evidence IDs and uses correct uncertainty language.
- 1 request per package by default; cache by model+prompt+evidence hash. Preview before export, editable by user. On model outage/rate limit, deterministic package remains available.
- Check current model terms/quotas before real use; free tiers are not an architectural dependency.

## 10. Progressive releases and acceptance gates

### Milestone 0 — Clean skeleton + real interface
- One monorepo with backend/frontend/scripts/docs. Vite starts, FastAPI `/health` responds, `pytest` and frontend checks run.
- Beautiful functional library page, dark analyzer shell, import dialog, waveform/transport with a real test WAV.
- The analyzer explicitly exposes **Technical Analysis**, **Lyrics & Inspiration**, and access to **Album QC**. Technical is usable with WAV alone; analysis charts show a truthful not-yet-run state until computed.
- One upload imported, decoded and playable end-to-end. NO mock API/simulated progress retained in accepted build.

### Milestone 1 — Reusable analysis core and technical dashboard
- Port **one-song** validated metadata, loudness, RMS, stereo, spectrum, oversampled peaks first; reusable pure functions and worker.
- Deliver working interactive Technical charts for levels/dynamics, loudness, spectral distribution, and stereo with time-linked playback; use recorded features, not fabricated graphics.
- Baseline comparison to provided prior `metrics.json`, allowing documented method/decoder differences. Emit `evidence.json`.
- Add provisional rhythm, tonal, novelty, recurrence and ending/gap diagnostics as explicitly estimated/flagged modules, with corresponding chart panels and method disclaimers.
- Cache duplicate audio and update job status. Chart errors must not mask successful independent metrics.

### Milestone 2 — Timed lyrics + integrated inspiration visualization
- TXT/SRT upload, editing, timing provenance, lyric repetition.
- Complete all five Lyricist chart views with shared playhead/zoom/selected region; explicit unknowns in data and UI.
- Technical and Lyricist tabs share the same evidence/time coordinates and playback transport; neither is hidden by the other.
- Artist annotations persisted across sessions.

### Milestone 3 — Both export profiles + optional API narrative
- Recreate the **five-chart `Praise Kink` layout** in style and informational intent using new generic chart functions; no hardcoded song facts.
- Export **Technical ZIP** (available from WAV alone), **Lyricist ZIP** (five chart PNGs + brief + evidence), and **Combined ZIP**, with independent manifests/methodology and validated filenames. Include chart PNGs, Markdown, structured JSON/selected CSV when useful, and README.
- Verify exports match dashboard chart data and preserve uncertainty/source metadata.
- Add optional NIM adapter behind settings with zero API calls when disabled. Add model-specific evidence validation and fallback templates.

### Milestone 4 — Album QC view + release readiness
- Import/order 2+ tracks and compare numbers and spectral/energy shape.
- Annotated listening checklist (peaks/endpoints/mono) and album report. No arbitrary quality score.

**Final v0.1 acceptance:** all milestones functioning locally on the user's Mac; technical dashboard and technical PNG export work for WAV **without** lyrics; the five-chart Lyricist package works with lyrics/SRT; both can be combined; source audio remains byte-identical; all exported timestamps are in bounds; no hardcoded source-song facts; normal operation makes **zero** paid API calls; 16/24-bit and mono/stereo paths tested; full user E2E smoke test.

## 11. QA and test design

**Unit:** WAV integer/float subtype scaling, silence, sine tone spectral band, identical/anti-phase stereo, 0 dBFS sine/sample peaks, peak oversampling, short files, empty subtitles, repeated lyrics, percent sum, negative/NaN handling.

**Integration:** FFMpeg executable probe, WAV-only upload → job → metrics → **technical charts** → Technical ZIP; lyrics/SRT upload → Lyricist charts → Lyricist ZIP; combined export; interrupted job → retry; duplicate hash cache; unauthorized filename/path traversal impossible; original SHA after run unchanged; disabled API produces no HTTP outbound requests.

**Golden fixtures:** synthetic 16-bit/24-bit WAVs and controlled SRT text committed to tests. Historical four-song `metrics.json` and features are **comparison targets**, not proof of current-run parity; original WAVs were excluded from the ZIP. Have the artist import originals privately to establish golden end-to-end results and numerical tolerances.

**Frontend E2E:** WAV-only technical view, seek from dynamics/spectral/stereo charts, play/pause and wave alignment; plot PNG matches data; edit a lyric cue and see it move; switch Technical/Lyricist modes; preview/download all export profiles; reload persisted project. Accessible keyboard focus and contrast in dark theme.

**Scientific validity:** Mark algorithms as `validated`, `experimental` or `not evaluated`; do not claim recognition of exact chords, singer identity, live instruments or 'emotional arc' from power metrics alone.

## 12. Explicit future extension seams, not MVP commitments

- Source separation, audio text/ML perceptual models, forced alignment for singing, beat-grid extraction, and waveform stem comparison are plugin-like modules with their own evaluation gates.
- Multi-user auth, per-user storage, entitlement checks, rate limiting, deployment worker queue and licensing rights checks before publishing.
- If later open sourced, audit dependency licenses (especially Essentia and learned models), offer user-provided model keys, and prohibit automatic distribution of copyrighted third-party WAVs/lyrics.

## 13. User validation script (minimum)

1. Import a short synthetic WAV and a real reference WAV. Confirm format / playback.
2. Without adding lyrics, inspect technical loudness/dynamics, spectral and stereo charts with accurate units and seek to one flagged event; export Technical ZIP.
3. Upload matching TXT lyrics, verify they are unplaced; replace with SRT and confirm estimated/typed cue placement.
4. Click chart timestamps and listen; manually mark one lyric segment verified and persist it.
5. Inspect all Technical PNGs and the five Lyricist PNGs plus Markdown/manifests; verify each makes no unsupported listening claim and combined exports do not duplicate evidence unnecessarily.
6. Import the four accepted masters into Album QC; compare loudness/peak/energy against the prior report within disclosed tolerance.
7. Turn NIM off; both export profiles work without a key. Optionally enable NIM and test a single evidence-grounded brief.
8. Restart services; confirm project persistence, file integrity and no phantom jobs.

## 14. Official technical references

- FastAPI upload API: https://fastapi.tiangolo.com/reference/uploadfile/
- FastAPI note on heavy background computation: https://fastapi.tiangolo.com/tutorial/background-tasks/
- Vite/production build: https://vite.dev/guide/build
- wavesurfer.js: https://github.com/katspaugh/wavesurfer.js
- Apache ECharts: https://echarts.apache.org/en/feature.html
- NVIDIA NIM LLM API: https://docs.nvidia.com/nim/large-language-models/latest/reference/api-reference.html
- Essentia descriptors/extractor: https://essentia.upf.edu/documentation.html
