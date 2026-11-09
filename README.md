# Audio Reference Studio

Local-first audio analysis, interactive diagnostics, and evidence-driven musical inspiration.

A listening session does not leave a durable record of level, spectrum, timing, or written structure. Audio Reference Studio stores the original WAV, measures it with a named method, and places those measurements on the same playhead used for listening. A measurement describes the file under that method. It is not a claim about what a listener would hear.

**Technical Analysis** and **Lyrics & Inspiration** are equal workflows for a single recording. Technical Analysis stands on its own with a WAV. Lyrics & Inspiration adds optional text and timing when you want to inspect phrasing, repetition, and structure beside the audio. **Album QC**, for comparing several recordings, is planned and not built.

Local-first. No account. Analysis stays on this machine.

## Contents

- [Features](#features)
- [Quick start](#quick-start)
- [Recordings, playback, and evidence](#recordings-playback-and-evidence)
- [Technical Analysis](#technical-analysis)
- [Lyrics & Inspiration](#lyrics--inspiration)
- [Export packages](#export-packages)
- [Album QC](#album-qc)
- [Architecture](#architecture)
- [Configuration and development](#configuration-and-development)
- [Scientific integrity](#scientific-integrity)
- [Status and documentation](#status-and-documentation)

## Features

The two primary workflows are available today. Album QC is not.

| Workflow | State | What you can do |
| --- | --- | --- |
| Technical Analysis | Available | Study a WAV with no lyrics. Measurements use `m1-v3`. Charts T01–T10 are interactive, seek with playback, and can be saved as technical PNGs and a Technical ZIP. |
| Lyrics & Inspiration | Available | Attach TXT, Markdown, or SRT evidence, time it by hand, and revise it without losing the prior revision. Charts L01–L05 read that document. Explore is the default; Edit is explicit. Lyricist and Combined packages use the saved lyric revision. |
| Shared studio | Available | Keep the original WAV bytes, store versioned evidence locally, use one playback transport across both workspaces, and build packages from stored results. |
| Album QC | Planned | Compare level, spectrum, and dynamics across several recordings. The screen is an empty state. Chart T11 is not built. |

These workflows are not at the same stage. Technical Analysis and Lyrics & Inspiration are implemented. Album QC is only a placeholder. The optional narrative integration is specified and not installed.

## Quick start

### Install and run

Three local processes: the API, the analysis worker, and the Vite app. Start each one in its own terminal.

### Required software

- Python 3.12 (`backend/.python-version`, `requires-python` in `backend/pyproject.toml`)
- [uv](https://docs.astral.sh/uv/)
- Node.js `^20.19.0` or `>=22.12.0` (the range required by the pinned Vite 8.3.4)
- pnpm (the frontend lockfile is `frontend/pnpm-lock.yaml`)
- FFmpeg on `PATH`. The health check reports its version, or `unavailable`.

### Install dependencies

From the repository root:

```bash
cd backend
uv sync
```

```bash
cd frontend
pnpm install
```

### Start the API, the worker, and the UI

Use three terminals, each from the repository root. The API and the worker both run in `backend/`. The app runs in `frontend/`.

```bash
cd backend
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

```bash
cd backend
uv run python -m app.worker
```

```bash
cd frontend
pnpm dev
```

Open `http://127.0.0.1:5173/`. A new analysis stays `queued` until the worker is running. `GET http://127.0.0.1:8000/api/health` reports the database and the FFmpeg version.

Environment variables, the data directory, PNG refresh, and test commands are in [Configuration and development](#configuration-and-development).

## Recordings, playback, and evidence

### Import and storage

- Accepted audio is 16-bit or 24-bit integer PCM WAV, including supported PCM extensible WAV with matching container and valid bit depths. Float WAV and other formats are refused.
- The upload is hashed with SHA-256 while it streams. The stored master, `blobs/{sha256}`, is the original bytes. The display name is not a filesystem path.
- The same bytes imported again reuse that master.
- Studies and recordings persist in SQLite. The library initially opens the earliest study. The study selector can reopen another study, and imports go to the selected study.
- Default limits are 500 MiB and 900 seconds, both configurable.

### Playback

- A 16-bit master is streamed from the stored blob.
- A 24-bit master is streamed from `derivatives/{sha256}/pcm_s16le-triangular-v1.wav`. FFmpeg writes 16-bit PCM at the master’s sample rate, channel count, and duration, with triangular dither. Analysis still reads the master. If that write fails, the master stays and playback is `unavailable`.
- WaveSurfer uses that stream plus a min/max peak envelope, `playback_minmax_envelope_v1`. That preview is navigation. It is not chart T01.
- The recording deck can stay expanded or collapse to compact playback controls. Both modes, and both workspaces, use the same WaveSurfer instance. Playback, seek, and volume continue across those changes.
- Chart clicks and review markers seek when the x-axis is file time. Zoom on a chart stays on that chart.

### Evidence and status

Evidence class and status are different fields.

| Evidence class | Meaning |
| --- | --- |
| `measured` | Computed from the audio by the named method. |
| `estimated` | A hypothesis from the audio, such as pulse, pitch-class, change, or recurrence. |
| `textual` | Taken from the lyric document. |
| `interpretive` | A principle gated on stored evidence, not a listening impression. |
| `unknown` | No single named class applies. When several classes are combined, a ready chart says this is not missing data. |
| `not_applicable` | The chart does not apply, such as stereo measures on a mono file. |

Asset analysis status is `not_run`, `queued`, `running`, `completed`, or `failed`. Jobs move through `queued`, `running`, `completed`, and `failed`. The job model also allows `canceled`; nothing in this tree writes that value. Chart status is `not_run`, `ready`, `not_available`, or `failed`. Playback status is `ready` or `unavailable`.

Metric records and chart documents are written under `analysis/{sha256}/m1-v3/`. Repeating analysis for the same bytes, `m1-v3`, and parameter hash reuses those metrics. A lyric revision is not part of that key.

## Technical Analysis

Import a WAV with no lyrics. The analyzer plays the file, draws a waveform for navigation, and loads T01–T10 from stored measurements. Time axes seek the shared playhead. The browser does not compute loudness, spectra, or peaks.

Analysis version is `m1-v3`. Requesting analysis returns HTTP 202 and queues a job. A separate worker performs the measurement. If this recording already has a completed `m1-v3` run for the current parameter hash and `metrics.json` is on disk, the API records a completed job and does not measure again. One chart can fail or be unavailable while the others remain.

Interactive charts are ECharts drawings of the stored chart document. A ready chart includes an in-page chart data table of those stored values. The panel shows evidence class, method, `m1-v3`, summary, and caveats beside the plot. Chart containers, multi-panel layout, the T04 axis label, spacing, colors, legends, and narrow-width layout are part of the current presentation.

| Chart | Subject | Evidence when ready |
| --- | --- | --- |
| T01 | Waveform envelope, 100 ms and 1 s RMS, sample-peak marker | Measured |
| T02 | Loudness and dynamics: integrated LUFS, loudness range, true peak, and short-term series | Measured |
| T03 | Long-term spectral balance | Measured |
| T04 | Spectrogram and coarse band traces | Measured |
| T05 | Stereo correlation, mid/side, and mono compatibility | Measured for stereo |
| T06 | Onset-autocorrelation pulse candidates, including half-time and double-time hypotheses | Estimated |
| T07 | Pitch-class distribution and key candidates | Estimated |
| T08 | Spectral-change curve and provisional transitions | Estimated |
| T09 | Within-file self-similarity | Estimated |
| T10 | Ending level, subthreshold gaps, endpoint, and full-scale rail events | Measured |

Mono T05 is `not_available` / `not_applicable`. A right channel is not invented. T10 markers are checkpoints. They are not a finding that a click or a clip is audible. T06–T09 stay estimates: half-time and double-time are hypotheses, pitch-class candidates are not a chord chart, change points are not verified sections, and similar spectra are not the same melody.

The worker writes a PNG for each ready chart when rendering succeeds. Current images use renderer `png-r1` at `analysis/{sha256}/m1-v3/presentation/png-r1/`. A failed render leaves the chart data in place. A missing or invalid `png-r1` file is `png_unavailable`. The image route does not substitute an older PNG, and export does not invent one. Refresh instructions are under [Configuration and development](#configuration-and-development).

Stored T03 power is still labeled `dB`, not dB/Hz. Some `png-r1` figures omit bar panels when a line series is present; the chart JSON still contains those series. Those gaps are G3 and G6 in the [decision register](docs/OPEN_DECISIONS_AND_UNCERTAINTIES.md). Chart zoom remaining local to the chart is G4.

## Lyrics & Inspiration

Attach a `.txt`, `.md`, or `.srt` file to a recording in a study. Plain text and Markdown stay untimed until you place them. SRT cues keep the times written in the subtitle file. Sung timing is not guessed.

Explore is the default. It is for reading, searching, and listening. Edit is explicit and uses the same draft map, so an unsaved line survives a return to Explore and a switch to Technical Analysis. The cue list has a find field, which keeps a long SRT navigable. The waveform labels only the selected or playing cue.

- Uploads are limited to 1 MiB. The original lyric bytes are kept under `lyrics/{sha256}`.
- Text and Markdown lines start `unplaced`. SRT cues that parse into a forward interval start as `subtitle_supplied`. Reversed, malformed, or out-of-range cues are kept and left off the time axis.
- You can edit line text, set start and end, and drag a WaveSurfer region for a usable interval. Saving a time marks the line `manual_edit`. Confirming a usable interval marks it `manual_verified`.
- A save sends the revision it was based on. If another revision landed first, the API returns 409 `stale_revision` and does not overwrite it. The workspace reloads the saved lines and keeps the unsaved edit so it can be written onto the newer revision.
- Notes are timed artist observations. They are not measured evidence and not an Album QC verdict.
- Lyric edits do not rewrite the `m1-v3` analysis cache.

L01–L05 read the current lyric document and the stored `m1-v3` measurements. They do not decode the WAV or remeasure it.

| Chart | Subject |
| --- | --- |
| L01 | Unified music-and-lyrics timeline. Usable lyric intervals sit on a separate lane. Lyric names stay in the cue list. |
| L02 | Written phrasing and density. Written-word counts and words-per-second rates are separate series. |
| L03 | Energy and dynamic contrast of the full mix. dBFS and LUFS stay on separate scales. |
| L04 | Spectral similarity and written repetition. Spectral similarity is not the same lyric or the same melody. |
| L05 | Evidence-cited musical DNA and transferable principles, with the selection rule, the shown count, and the total count. |

Each lyric chart shows its evidence class. A ready chart whose class is `unknown` because several classes were combined says that this is not missing data. The stored class is unchanged. Short recordings may lack T08 and T09. L04 then records that the recurrence chart is unavailable. L01 can extend its vertical scale toward −150 dBFS when the stored ending level is that low.

Waveform zoom and chart zoom are not synchronized. A selected lyric region is sought and followed by the playhead. L01 and L03 draw every usable region and do not mark one of them as the selected region.

## Export packages

From a recording opened in a study, expand the recording deck and use the export bar. Choose how lyric text is handled, then download one profile. The page builds the package from stored evidence and downloads `{profile}-{export_id}.zip`.

A Technical ZIP is the measurements and technical figures for a WAV, including a recording with no lyrics. A Lyricist ZIP is the five inspiration figures plus a written reference brief. A Combined ZIP is both, without running analysis a second time. The original WAV is not in the package. Unsaved editor text is not included. The package uses the saved lyric revision.

Export does not decode the WAV, remeasure, or rewrite the analysis cache. A recording that has not been analyzed can still export: every technical chart is `not_run` or `not_available`, and no PNG is invented.

| Profile | Requires | What you take away |
| --- | --- | --- |
| Technical ZIP | A supported WAV in a study. Lyrics are optional. | Stored `m1-v3` metrics and evidence, T01–T10 chart JSON, and each technical PNG whose `png-r1` manifest validates. Missing or invalid images are listed as `png_unavailable`. |
| Lyricist ZIP | That recording plus a saved lyric document. | L01–L05 chart JSON, static L01–L05 figures, and a Markdown reference brief rendered from those documents. |
| Combined ZIP | That recording plus a saved lyric document. | Technical chart JSON and valid `png-r1` images under `technical/charts/`, plus the lyricist charts, figures, and brief. `metrics.json`, once at the archive root, is the stored technical metrics. `evidence.json`, once at the root, is the lyric evidence bundle for that revision. |

The lyric-text control has three modes. The default is `summarized`.

| Mode | Lyric text in a Lyricist or Combined package |
| --- | --- |
| `summarized` | Counts, timing origins, and citation ids. Original lyric lines are left out. |
| `included` | The stored line text is added to the evidence and the brief. |
| `omitted` | Original lyric lines and written-repetition strings are left out. |

A Technical ZIP does not contain lyric charts or lyric lines. The selected mode is still recorded on its manifest.

New lyric figures declare `lyric-png-v2`. New briefs declare `lyric-brief-v2`. Technical images stay `png-r1`. The manifest records `narrative: none`. Package READMEs name `m1-v3` when metrics exist, the source SHA-256, the lyric revision, the lyric-text mode, and the open T03 unit and mixed-panel PNG limits.

A published ZIP is left as stored. A later lyric save creates a new export at the new revision and leaves the previous file unchanged. Packages already published as `lyric-png-v1` are not rewritten to `lyric-png-v2`.

The manifest `content_sha256` covers the sorted chart JSON, evidence JSON, metrics JSON, and brief. It excludes `created_at`, the export id, README files, and PNG bytes. Repeating an export from the same stored inputs keeps that hash. Lyric PNGs are drawn when the package is built, so the hash does not promise pixel-identical figures, and the ZIP bytes are not claimed to match across machines or Matplotlib builds. Technical PNGs that are included are copies of the stored `png-r1` files.

If publication is interrupted after the ZIP file is written and before the database row is stored, `exports/{id}.zip` can exist without being listed. That file is not a completed export.

The page calls the membership API:

- `POST /api/projects/{project_id}/assets/{asset_id}/exports` with `profile` of `technical`, `lyricist`, or `combined`, and `lyrics` of `summarized`, `included`, or `omitted`.
- `GET` the same path plus `/{export_id}` returns the ZIP. The id is generated by the server.

`lyricist` or `combined` without a current lyric document returns 409 `no_lyrics`. Those two buttons stay disabled until a document is attached. Technical export stays available. Export from a recording that was not opened inside a study is refused in the page.

## Album QC

Album QC is the planned place to compare several recordings. The Album QC screen tells you comparison is not in this milestone and points you back to a single recording. Chart T11 is not implemented. An [implementation-ready plan](docs/superpowers/plans/2026-11-08-milestone-4-album-qc.md) exists. That plan is not authorization to build it.

## Architecture

The repository is a local monorepo. The frontend owns `frontend/**`. The backend owns `backend/**`. The UI reads generated API shapes in `frontend/src/api/types.ts`. Measurement, lyric charts, and export all read the same stored evidence. Nothing in the analysis path calls a hosted model.

| Layer | Role |
| --- | --- |
| Frontend | React 19.3, TypeScript 7, Vite 8.3 on `127.0.0.1:5173`. Tailwind 4, Lucide, WaveSurfer 8.0.2, ECharts 6.1. Vitest and Testing Library. |
| API | Python 3.12, FastAPI 0.143, Pydantic 2.14, Uvicorn 0.54 on `127.0.0.1:8000`. |
| Measurement | NumPy, SciPy, and FFmpeg. `backend/app/measure.py` measures the master. `backend/app/charts.py` builds T01–T10. Matplotlib writes PNGs from those documents. |
| Lyric charts and packages | `backend/app/lyric_charts.py` builds L01–L05 on read. `backend/app/lyric_png.py` draws `lyric-png-v2`. `backend/app/exports.py` writes the three ZIP profiles. |
| Worker | `python -m app.worker` claims queued jobs, writes `m1-v3`, and marks an abandoned `running` job failed with error `interrupted`. |
| Storage | SQLite file `studio.sqlite3` plus content-addressed files under the data root. |
| Tests | pytest and Ruff in `backend/`. Vitest, `tsc`, and Vite build in `frontend/`. |

Loudness uses FFmpeg’s EBU R128 filter and is labeled as that measurement. Integer PCM is scaled by its own full scale: 32768 for 16-bit and 8388608 for 24-bit.

Product boundaries are in the [technical MVP specification](docs/01_TECHNICAL_MVP_SPEC.md). Chart contracts are in the [technical chart requirements](docs/04_TECHNICAL_CHART_REQUIREMENTS.md).

## Configuration and development

### Environment

Copy `.env.example` to `.env` at the repository root to override API settings. On startup the API reads a `.env` file from the process working directory and from the repository root. It fills only variables that are not already set. Quote marks around a value are stripped.

`ARS_API_ORIGIN` is not one of those API settings. The Vite config reads it from the process environment while `frontend/vite.config.ts` is evaluated, which is before Vite loads `.env` files. Put it in the shell that starts `pnpm dev`. A line in the repository `.env` does not change the proxy.

| Variable | Read by | Behavior |
| --- | --- | --- |
| `ARS_DATA_ROOT` | API | Directory for the database, masters, derivatives, peaks, analysis, lyric files, and exports. Unset or empty uses `~/Library/Application Support/AudioReferenceStudio`. A non-empty value is expanded with `~`. |
| `ARS_MAX_BYTES` | API | Upload limit in bytes. Default `524288000` (500 MiB). |
| `ARS_MAX_DURATION_S` | API | Maximum duration in seconds. Default `900`. |
| `ARS_CORS_ORIGIN` | API | Browser origin allowed to call the API directly. Default `http://127.0.0.1:5173`. |
| `ARS_API_ORIGIN` | Vite dev server | Where the dev server proxies `/api`. Default `http://127.0.0.1:8000`. |

The proxy is a development convenience: the page on port 5173 forwards `/api` to the API process. The data root is where files are stored. Changing one does not change the other. Point `ARS_API_ORIGIN` at the API if it is not on port 8000, and point `ARS_CORS_ORIGIN` at the page if the UI is not on port 5173.

Under the data root the API uses `studio.sqlite3`, `blobs/{sha256}`, `derivatives/{sha256}/`, `peaks/{sha256}/`, `analysis/{sha256}/m1-v3/`, `lyrics/{sha256}`, `exports/{id}.zip`, and `tmp/`.

### Technical PNG refresh

Rebuild current images from stored chart JSON. The application does not do this on startup.

From the repository root:

```bash
cd backend
uv run python -m app.refresh_png --data-root PATH
```

`--dry-run`, `--sha256`, and repeatable `--kind` are optional. A current image response sends `X-Renderer-Version: png-r1` and `Cache-Control: no-cache`.

### Checks

From `backend/`:

```bash
uv run ruff check . && uv run pytest -q
```

From `frontend/`:

```bash
pnpm typecheck && pnpm test && pnpm build
```

`pnpm typecheck` is `tsc --noEmit`. `pnpm build` typechecks and then runs the Vite production build. After an API schema change, regenerate the frontend types from `backend/` with:

```bash
uv run python scripts/export_openapi_types.py
```

That script writes `frontend/src/api/types.ts`. Do not hand-edit that file.

If a frontend check stalls or reports a missing export from a file that is intact on disk, see [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md).

## Scientific integrity

Charts are statements about a file under a named method. They are not a validated listening test, and they do not decide whether a recording sounds good.

- T01–T05 and T10 are measured when ready. T06–T09 are estimates. Tempo, pitch-class, structure, and recurrence stay estimated.
- SRT times are the cue times in the file. The application does not move them onto sung phonemes. Text and Markdown gain times only when you set them. Confirming alignment records that you did so.
- Ending, gap, and full-scale markers are technical checkpoints. They are not a finding that a defect is audible.
- The application does not identify instruments, vocals, mood, or audible defects, and it does not align words to singing automatically.
- Offline analysis does not call a model. No narrative client is installed. Imported audio is not uploaded for interpretation. Milestone 3 is accepted with that narrative requirement deferred, not removed. NVIDIA NIM is not authorized. The technical package does not need it.
- A 24-bit playback derivative is separate from the master. A failed conversion leaves the master in place.
- Each chart document names its method and `method_version`. Builders fill sample rate and hop on the charts that have them. T02 leaves `hop_s` empty and names its windows on the series.
- The export content hash does not promise identical PNG pixels. See [Export packages](#export-packages).

Native keyboard activation of the chart data tables was not fully verified in browser review. Short recordings may omit T08 and T09. The unlisted-ZIP window is described with the export profiles. Engineering discrepancies, including G3, G4, and G6, are tracked in the [decision register](docs/OPEN_DECISIONS_AND_UNCERTAINTIES.md) and [project status](PROJECT_STATUS.md).

## Status and documentation

Implemented for one recording: WAV import and playback, `m1-v3` charts T01–T10, lyric evidence with L01–L05, and Technical, Lyricist, and Combined ZIP packages.

Milestone 2 is accepted with two deferred synchronization requirements: shared waveform and chart zoom, and a selected lyric region marked on the waveform and on L01 and L03 together. Milestone 3 is accepted with one exception. The evidence-grounded narrative integration remains a requirement and is not implemented. Album QC and Milestone 4 are planned. The Album QC plan is not authorization to build them.

[PROJECT_STATUS.md](PROJECT_STATUS.md) owns implementation and acceptance status. [NEXT_SESSION.md](NEXT_SESSION.md) is the current handoff. The [documentation index](docs/README.md) says which document owns each subject.

- [Technical MVP specification](docs/01_TECHNICAL_MVP_SPEC.md) — product boundaries, screens, and milestone gates
- [Technical chart requirements](docs/04_TECHNICAL_CHART_REQUIREMENTS.md) — T01–T11, evidence labels, and validation intent
- [Decision register](docs/OPEN_DECISIONS_AND_UNCERTAINTIES.md) — locked decisions and open contract gaps
- [Milestone 2 plan](docs/superpowers/plans/2026-10-13-milestone-2.md) — lyric evidence and L01–L05
- [Milestone 3 export scope](docs/superpowers/plans/2026-11-07-milestone-3-exports.md) — Technical, Lyricist, and Combined packages
- [Milestone 4 Album QC scope](docs/superpowers/plans/2026-11-08-milestone-4-album-qc.md) — comparison plan, not an authorization to build T11
- [Implementation audit](docs/album_observatory_followup_audit.md) — snapshot from before acceptance of M2-A and M2-B, not an acceptance decision
- [Local toolchain note](docs/ENVIRONMENT.md) — recovering a stalled Vite or Vitest run
