# Audio Reference Studio

Audio Reference Studio is a local-first audio-analysis application. It keeps each original WAV on this computer, measures it with a versioned method, and shows those measurements beside a shared playhead. An optional lyric file can sit on the same timeline.

The application supports human listening, scientific inspection, and musical inspiration. A measurement describes the file under a named method. It is not a claim about what a listener would hear.

## What the application does

Two workspaces are available for a single recording. Album QC is a planned third workspace.

**Technical Analysis** is a WAV-only measurement and diagnostic workflow. It does not need lyrics or an account.

**Lyrics & Inspiration** is a separate workflow of equal weight. It combines the stored audio measurements with optional textual and timed lyric evidence: phrasing, repetition, energy, and transferable observations you can inspect while you listen.

**Album QC** is the planned place to compare several recordings. It is not built. A study of one file does not wait on it.

## Current capabilities

This tree can:

- Import a 16-bit or 24-bit integer PCM WAV, keep the original bytes, and play it from a local stream.
- Measure one recording as `m1-v3` and show charts T01–T10, with method, units, status, and evidence class.
- Show an accessible in-page data table for each technical chart, and disclose the evidence beside the plot.
- Switch the recording deck between compact playback and an expanded deck. One WaveSurfer instance stays mounted across that switch and across both workspaces.
- Attach a `.txt`, `.md`, or `.srt` lyric file, edit it with revision checks, and draw inspiration charts L01–L05 from the saved lyric document and the stored measurements.
- Download a Technical ZIP, a Lyricist ZIP, or a Combined ZIP from a recording opened in a study. The package is built from stored evidence.

### Not in this build

- The optional evidence-grounded narrative integration. Settings state that AI interpretation is off. Milestone 3 is accepted with that requirement deferred. NVIDIA NIM is not authorized.
- Album comparison and chart T11.
- Vocal, instrument, mood, or defect classification.
- Automatic alignment of words to singing.
- Synchronized waveform and chart zoom.
- A selected lyric region marked at the same time on the waveform and on L01 and L03.

Per-chart technical PNGs and the three ZIP profiles below are part of this build. Milestone 3 is accepted with the narrative exception. The provider is not installed.

## Recordings, playback, and evidence

### Import and storage

- Accepted audio is 16-bit or 24-bit integer PCM WAV, including supported PCM extensible WAV with matching container and valid bit depths. Float WAV and other formats are refused.
- The upload is hashed with SHA-256 while it streams. The stored master, `blobs/{sha256}`, is the original bytes. The display name is not a filesystem path.
- The same bytes imported again reuse that master.
- Studies and recordings persist in SQLite. The library initially opens the earliest study. The study selector can reopen another study, and imports go to the selected study.
- Default limits are 500 MiB and 900 seconds, both configurable.

### Playback and waveform

- A 16-bit master is streamed from the stored blob.
- A 24-bit master is streamed from `derivatives/{sha256}/pcm_s16le-triangular-v1.wav`: FFmpeg writes 16-bit PCM at the master’s sample rate, channel count, and duration, with triangular dither. Analysis still reads the master. If that write fails, the master stays and playback is `unavailable`.
- WaveSurfer uses that stream plus a min/max peak envelope, `playback_minmax_envelope_v1`. That preview is navigation. It is not chart T01.
- Chart clicks and review markers seek when the x-axis is file time.
- The recording deck can collapse to compact playback controls or stay expanded. Both modes use the same WaveSurfer instance. Playback, seek, and volume continue when you change deck mode or move between Technical Analysis and Lyrics & Inspiration.

### Evidence

Every value that claims a source uses an evidence class: `measured`, `estimated`, `textual`, `interpretive`, `unknown`, or `not_applicable`. That field is separate from status. Asset analysis status is `not_run`, `queued`, `running`, `completed`, or `failed`. Jobs move through `queued`, `running`, `completed`, and `failed`. The job model also allows `canceled`; nothing in this tree writes that value. Chart status is `not_run`, `ready`, `not_available`, or `failed`. Playback status is `ready` or `unavailable`.

Metric records and chart documents are written under `analysis/{sha256}/m1-v3/`.

## Technical Analysis

Import a WAV with no lyrics. The analyzer plays the file, draws a waveform for navigation, and loads charts T01–T10 from stored measurements. Time axes seek the same playback position. The goal is a reproducible look at level, spectrum, stereo, pulse, pitch-class, change, recurrence, and the end of the file.

Analysis version is `m1-v3`. Requesting analysis returns HTTP 202 and queues a job. A separate worker process performs the measurement. If this recording already has a completed `m1-v3` run for the current parameter hash and `metrics.json` is on disk, the API records a completed job and does not measure again. One chart can fail or be unavailable while the others remain.

| Chart | What it shows | Evidence when ready |
| --- | --- | --- |
| T01 | Waveform envelope, 100 ms and 1 s RMS, sample-peak marker | Measured |
| T02 | Loudness and dynamics, including integrated LUFS, loudness range, true peak, and short-term series | Measured |
| T03 | Long-term spectral balance | Measured |
| T04 | Spectrogram and coarse band traces | Measured |
| T05 | Stereo correlation, mid/side, and mono compatibility | Measured for stereo. Mono is `not_available` / `not_applicable`. A right channel is not invented. |
| T06 | Onset-autocorrelation pulse candidates, including half-time and double-time hypotheses | Estimated |
| T07 | Pitch-class distribution and key candidates | Estimated |
| T08 | Spectral-change curve and provisional transitions | Estimated |
| T09 | Within-file self-similarity | Estimated |
| T10 | Ending level, subthreshold gaps, endpoint, and full-scale rail events | Measured. These are checkpoints, not a finding that a click or clip is audible. |

Interactive charts are ECharts drawings of the stored chart document. A ready chart includes an accessible in-page data table of those stored values. The panel shows the chart’s evidence class, method, `m1-v3` version, summary, and caveats beside the plot. Accepted presentation work corrected chart-container sizing, multi-panel layout, the T04 axis label, spacing, colors, legends, and responsive behavior. The browser does not compute loudness, spectra, or peaks.

The worker renders a PNG from each ready chart document when rendering succeeds. Current images use renderer version `png-r1` and live at `analysis/{sha256}/m1-v3/presentation/png-r1/`. A failed PNG render leaves the chart and its measurements available. A missing or invalid `png-r1` file is `png_unavailable`. The image route does not serve an older PNG in its place, and export does not invent one. Rebuild current images from stored chart JSON with:

```bash
python -m app.refresh_png --data-root PATH
```

`--dry-run`, `--sha256`, and repeatable `--kind` are optional. The application does not refresh PNGs on startup. A current image response sends `X-Renderer-Version: png-r1` and `Cache-Control: no-cache`.

Some chart-contract differences remain open. Stored T03 power is still labeled `dB`, not dB/Hz. Some `png-r1` figures omit bar panels when a line series is present; the chart JSON still contains those series. Chart zoom stays on that chart and does not move the waveform. Those items are G3, G6, and G4 in the [decision register](docs/OPEN_DECISIONS_AND_UNCERTAINTIES.md).

## Lyrics & Inspiration

Attach a `.txt`, `.md`, or `.srt` file to a recording in a study. Plain text and Markdown stay untimed until you place them. SRT cues keep the times written in the subtitle file. The panel states that sung timing is not guessed.

Explore is the default mode. It is for reading, searching, and listening. Edit is explicit and uses the same draft map, so an unsaved line survives a return to Explore and a switch to Technical Analysis. The cue list is searchable, which keeps a long SRT navigable. The waveform labels only the selected or playing cue.

- `.txt`, `.md`, and `.srt` uploads, up to 1 MiB. The original lyric bytes are kept under `lyrics/{sha256}`.
- Text and Markdown lines start `unplaced`. SRT cues that parse into a forward interval start as `subtitle_supplied`. Reversed, malformed, or out-of-range cues are kept and left off the time axis.
- You can edit line text, set start and end, and drag a WaveSurfer region for a usable interval. Saving a time marks the line `manual_edit`. Confirming a usable interval marks it `manual_verified`.
- A save sends the revision it was based on. If another revision landed first, the API returns 409 `stale_revision` and does not overwrite it. The workspace reloads the saved lines and keeps the unsaved edit so it can be written onto the newer revision.
- Notes are timed annotations. The panel calls them artist observations, not measured evidence and not an Album QC verdict.
- Lyric edits do not rewrite the `m1-v3` analysis cache.

Inspiration charts L01–L05 read the current lyric document and stored `m1-v3` measurements. They do not decode the WAV or remeasure it. Saving lyrics does not rewrite `m1-v3`.

| Chart | What it shows |
| --- | --- |
| L01 | Unified music-and-lyrics timeline. Usable lyric intervals sit on a separate lane, without lyric names printed on the curve. |
| L02 | Written phrasing and density. Written-word counts and words-per-second rates are separate series. |
| L03 | Energy and dynamic contrast. dBFS and LUFS stay on separate scales. |
| L04 | Spectral and textual repetition. Spectral similarity is not treated as the same lyric or the same melody. |
| L05 | Evidence-cited musical DNA and transferable principles, including the selection rule, the shown count, and the total count. |

Each lyric chart shows its evidence class. A ready chart whose class is `unknown` because several classes were combined says that this is not missing data. The stored evidence class is unchanged. Short recordings may lack T08 and T09. L04 then records that the recurrence chart is unavailable. L01 can extend its vertical scale toward −150 dBFS when the stored ending level is that low.

Milestone 2 is accepted with two deferred requirements. Waveform zoom and chart zoom are not synchronized. A selected lyric region is sought and followed by the playhead; L01 and L03 draw every usable region and do not mark one of them as the selected region.

## Export packages

Open a recording from a study, expand the recording deck, and use the export bar there. Choose how lyric text is handled, then download one profile. The page creates the package and downloads `{profile}-{export_id}.zip`.

Export reads stored evidence. It does not decode the WAV, remeasure, or rewrite the analysis cache. The original WAV is not in the package. A recording that has not been analyzed can still export: every technical chart is `not_run` or `not_available`, and no PNG is invented. The package uses the saved lyric revision. Unsaved editor text is not included.

| Profile | When it is available | What it contains |
| --- | --- | --- |
| Technical ZIP | A supported WAV in a study. Lyrics are optional. | Stored `m1-v3` metrics and evidence, T01–T10 chart JSON, and each technical PNG whose `png-r1` manifest validates. Missing or invalid images are listed as `png_unavailable`. |
| Lyricist ZIP | The same recording with a saved lyric document. | L01–L05 chart JSON, static L01–L05 figures, and a deterministic Markdown reference brief. The figures are drawings of the current lyric charts and the stored analysis. |
| Combined ZIP | The same recording with a saved lyric document. | Technical chart JSON and valid `png-r1` images under `technical/charts/`, plus the lyricist charts, figures, and brief. `metrics.json`, at the archive root, is the stored technical metrics. `evidence.json`, also once at the root, is the lyric evidence bundle for that revision. Analysis is not run again. |

The lyric-text control has three modes. The default is `summarized`.

| Mode | Lyric text in a Lyricist or Combined package |
| --- | --- |
| `summarized` | Counts, timing origins, and citation ids. Original lyric lines are left out. |
| `included` | The stored line text is added to the evidence and the brief. |
| `omitted` | Original lyric lines and written-repetition strings are left out. |

A Technical ZIP does not contain lyric charts or lyric lines. The selected mode is still recorded on its manifest.

New lyric figures declare `lyric-png-v2`. New briefs declare `lyric-brief-v2`. Technical images stay `png-r1`. The manifest records `narrative: none`. Package READMEs name `m1-v3` when metrics exist, the source SHA-256, the lyric revision, the lyric-text mode, and the open T03 unit and mixed-panel PNG limits.

A published ZIP is immutable. A later lyric save creates a new export at the new revision and leaves the previous file unchanged. Packages already published as `lyric-png-v1` stay as stored. Nothing in this application rewrites them to `lyric-png-v2`.

The manifest `content_sha256` covers the sorted chart JSON, evidence JSON, metrics JSON, and brief. It excludes `created_at`, the export id, README files, and PNG bytes. Repeating an export from the same stored inputs keeps that hash. Lyric PNGs are drawn when the package is built, so the hash does not promise pixel-identical figures. This README does not claim that ZIP bytes match across machines or Matplotlib builds. Technical PNGs that are included are copies of the stored `png-r1` files.

If publication is interrupted after the ZIP file is written and before the database row is stored, `exports/{id}.zip` can exist without being listed. That file is not a completed export. See [Project status](PROJECT_STATUS.md) for that limitation.

The membership API matches the controls:

- `POST /api/projects/{project_id}/assets/{asset_id}/exports` with `profile` of `technical`, `lyricist`, or `combined`, and `lyrics` of `summarized`, `included`, or `omitted`.
- `GET` the same path plus `/{export_id}` returns the ZIP. The id is generated by the server.

`lyricist` or `combined` without a current lyric document returns 409 `no_lyrics`. The Lyricist and Combined buttons stay disabled until a document is attached. Technical export stays available. Export from a recording that was not opened inside a study is refused in the page, with the note to open it from a study.

## Album QC

Album QC is the planned place to compare several recordings: level, spectrum, dynamics, and listening checkpoints across a set. The Album QC screen is an empty state. Chart T11 is not implemented. Comparison is separate from songwriting notes.

## Architecture

The repository is a local monorepo. The frontend owns `frontend/**`. The backend owns `backend/**`. API shapes used by the UI are generated into `frontend/src/api/types.ts`.

| Layer | Role |
| --- | --- |
| Frontend | React 19.3, TypeScript 7, Vite 8.3 on `127.0.0.1:5173`. Tailwind 4, Lucide, WaveSurfer 8.0.2, ECharts 6.1. Vitest and Testing Library. |
| API | Python 3.12, FastAPI 0.143, Pydantic 2.14, Uvicorn 0.54 on `127.0.0.1:8000`. |
| Measurement | NumPy, SciPy, and FFmpeg. `backend/app/measure.py` measures the master. `backend/app/charts.py` builds T01–T10. Matplotlib writes PNGs from those documents. There is no second DSP library. |
| Lyric charts and packages | `backend/app/lyric_charts.py` builds L01–L05 on read. `backend/app/lyric_png.py` draws `lyric-png-v2`. `backend/app/exports.py` writes the three ZIP profiles. |
| Worker | `python -m app.worker` claims queued jobs, writes `m1-v3`, and marks an abandoned `running` job failed with error `interrupted`. |
| Storage | SQLite file `studio.sqlite3` plus content-addressed files under the data root. |
| Tests | pytest and Ruff in `backend/`. Vitest, `tsc`, and Vite build in `frontend/`. |

Loudness uses FFmpeg’s EBU R128 filter and is labeled as that measurement. Integer PCM is scaled by its own full scale: 32768 for 16-bit and 8388608 for 24-bit.

## Install and run

### Required software

- Python 3.12 (`backend/.python-version`, `requires-python` in `backend/pyproject.toml`)
- [uv](https://docs.astral.sh/uv/)
- Node.js `^20.19.0` or `>=22.12.0` (the range required by the pinned Vite 8.3.4)
- pnpm (the frontend lockfile is `frontend/pnpm-lock.yaml`)
- FFmpeg on `PATH`. The health check reports its version, or `unavailable`.

### Install dependencies

From `backend/`:

```bash
uv sync
```

From `frontend/`:

```bash
pnpm install
```

### Start the API, the worker, and the UI

Use three terminals. From `backend/`:

```bash
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

```bash
uv run python -m app.worker
```

From `frontend/`:

```bash
pnpm dev
```

Open `http://127.0.0.1:5173/`. A new analysis stays `queued` until the worker is running. `GET http://127.0.0.1:8000/api/health` reports the database and the FFmpeg version.

### Configuration

Copy `.env.example` to `.env` at the repository root if you want to override API settings. On startup the API reads a `.env` file from the process working directory and from the repository root. It fills only variables that are not already set. Quote marks around a value are stripped.

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

## Scientific integrity and known limitations

The stored WAV is the upload. Playback of a 24-bit file uses a separate 16-bit derivative, and a failed conversion leaves the master in place.

Repeating analysis for the same bytes, `m1-v3`, and parameter hash reuses the stored metrics. Each chart document names its method and `method_version`. Builders fill sample rate and hop on the charts that have them; T02 leaves `hop_s` empty and names its windows on the series.

A level, a spectrum, a loudness figure, or a stereo coefficient describes the signal under that method. It does not decide whether the recording sounds good, which instrument played, or whether a listener would hear a defect. This repository does not treat the charts as a validated listening test. A technical checkpoint is not an audible defect.

T06–T09 remain estimates. Half-time and double-time are hypotheses. Pitch-class candidates are not a chord chart. Change points are not verified verses or choruses. Similar spectra are not the same melody.

SRT times are the cue times supplied in the file. The application does not move them onto sung phonemes. Text and Markdown gain times only when you set them. Confirming alignment records that you did so. It does not measure the vocal. Lyric text is `textual`. An artist note is an observation stored beside the audio, and it does not enter the measurement cache.

The same WAV and the same `m1-v3` parameter hash reproduce the stored metrics. A lyric revision is not part of that key. Export hashes the stored documents as described above. That hash is not a promise of identical PNG pixels.

Offline analysis does not call a model. No narrative client is installed. Imported audio is not uploaded for interpretation. Milestone 3 is accepted with that narrative requirement deferred, not deleted. Optional AI writing stays off unless a later authorization enables it, and the technical package remains available without it.

Native keyboard activation of the chart data tables was not fully verified in browser review. Other accepted limits, including short-file omissions and the unlisted-ZIP window, are in [PROJECT_STATUS.md](PROJECT_STATUS.md) and the [decision register](docs/OPEN_DECISIONS_AND_UNCERTAINTIES.md).

## Status

[PROJECT_STATUS.md](PROJECT_STATUS.md) owns implementation and acceptance status. [NEXT_SESSION.md](NEXT_SESSION.md) gives the current handoff and authorized scope. The [documentation index](docs/README.md) explains which documents own requirements and decisions.

Milestone 2 is accepted with the two synchronization exceptions above. Milestone 3 is accepted with the narrative exception. M3-A and M3-B, the Technical, Lyricist, and Combined packages, are accepted. Album QC and Milestone 4 are planned. The implementation plan is not authorization.

## Further reading

- [Technical MVP specification](docs/01_TECHNICAL_MVP_SPEC.md) — product boundaries, screens, and milestone gates
- [Technical chart requirements](docs/04_TECHNICAL_CHART_REQUIREMENTS.md) — T01–T11, evidence labels, and validation intent
- [Milestone 2 plan](docs/superpowers/plans/2026-10-13-milestone-2.md) — lyric evidence, the workspace, and L01–L05. Milestone 2 is accepted with two synchronization exceptions.
- [Milestone 3 export scope](docs/superpowers/plans/2026-11-07-milestone-3-exports.md) — Technical, Lyricist, and Combined packages. Milestone 3 is accepted with the narrative exception.
- [Milestone 4 Album QC scope](docs/superpowers/plans/2026-11-08-milestone-4-album-qc.md) — implementation-ready comparison plan. It does not authorize T11.
- [Decision register](docs/OPEN_DECISIONS_AND_UNCERTAINTIES.md) — locked decisions and open contract gaps, including G3, G4, and G6
- [Implementation audit](docs/album_observatory_followup_audit.md) — snapshot from before owner acceptance of M2-A and M2-B. It is not an acceptance decision.
- [Local toolchain note](docs/ENVIRONMENT.md) — recovering a stalled Vite or Vitest run
