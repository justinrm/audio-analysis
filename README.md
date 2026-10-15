# Audio Reference Studio

Audio Reference Studio is a local application for studying one recording at a time. It keeps the original WAV on this computer, measures it with a versioned method, and shows those measurements as interactive charts beside a shared playhead. An optional lyric file can sit on the same timeline so you can inspect phrasing, repetition, and structure without turning a measurement into a musical verdict.

Two uses have equal weight. Album QC is a planned third workspace and is not built yet.

## Technical Audio Analysis

Import a WAV with no lyrics and no account. The analyzer plays the file, draws a waveform for navigation, and loads charts T01–T10 from stored measurements. Each chart carries its method, version, units, status, and evidence class. Time axes seek the same playback position. The goal is a reproducible look at level, spectrum, stereo, pulse, pitch-class, change, recurrence, and the end of the file.

## Lyrics and musical inspiration

Attach a `.txt`, `.md`, or `.srt` file to a recording in a study. Plain text and Markdown stay untimed until you place them. SRT cues keep the times written in the subtitle file. You can edit text, drag waveform regions, confirm an alignment, and leave notes. The same transport serves the technical charts and the lyric list.

Inspiration charts L01–L05 are specified and not implemented. The lyric panel says so.

## Album QC

Album QC is the planned place to compare several recordings: level, spectrum, dynamics, and listening checkpoints across a set. The Album QC screen is an empty state. Chart T11 is not implemented. Comparison is separate from songwriting notes. A technical study of one file does not wait on it.

## Current capabilities

What follows is what this tree does. Later sections name work that is only specified.

### Import and storage

- Accepted audio is 16-bit or 24-bit integer PCM WAV, including PCM extensible WAV with those valid bit depths. Float WAV and other formats are refused.
- The upload is hashed with SHA-256 while it streams. The stored master, `blobs/{sha256}`, is the original bytes. The display name is not a filesystem path.
- The same bytes imported again reuse that master.
- Studies and recordings persist in SQLite. The library screen opens the earliest study and lists its recordings.
- Default limits are 500 MiB and 900 seconds, both configurable.

### Playback and waveform

- A 16-bit master is streamed from the stored blob.
- A 24-bit master is streamed from `derivatives/{sha256}/pcm_s16le-triangular-v1.wav`: FFmpeg writes 16-bit PCM at the master’s sample rate, channel count, and duration, with triangular dither. Analysis still reads the master. If that write fails, the master stays and playback is `unavailable`.
- WaveSurfer uses that stream plus a min/max peak envelope, `playback_minmax_envelope_v1`. That preview is navigation. It is not chart T01.
- Chart clicks and review markers seek when the x-axis is file time.

### Technical charts

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

Interactive charts are ECharts drawings of the stored chart document. Each ready chart also has a PNG rendered from that document. The browser does not compute loudness, spectra, or peaks.

### Evidence

Every value that claims a source uses an evidence class: `measured`, `estimated`, `textual`, `interpretive`, `unknown`, or `not_applicable`. That field is separate from status. Asset analysis status is `not_run`, `queued`, `running`, `completed`, or `failed`. Jobs move through `queued`, `running`, `completed`, and `failed`. The job model also allows `canceled`; nothing in this tree writes that value. Chart status is `not_run`, `ready`, `not_available`, or `failed`. Playback status is `ready` or `unavailable`.

The technical panel shows the chart’s evidence class, method, `m1-v3` version, summary, and caveats beside the plot. Metric records and chart documents are written under `analysis/{sha256}/m1-v3/`.

### Lyrics workspace

M2-A stores lyric files, parses them, and keeps revisions. M2-B is the workspace on that API. The owner accepted both slices on 2026-10-14. Milestone 2 as a whole is not accepted. See [Status](#status).

- `.txt`, `.md`, and `.srt` uploads, up to 1 MiB. The original lyric bytes are kept under `lyrics/{sha256}`.
- Text and Markdown lines start `unplaced`. SRT cues that parse into a forward interval start as `subtitle_supplied`. Reversed, malformed, or out-of-range cues are kept and left off the time axis.
- You can edit line text, set start and end, and drag a WaveSurfer region for a usable interval. Saving a time marks the line `manual_edit`. Confirming a usable interval marks it `manual_verified`.
- A save sends the revision it was based on. If another revision landed first, the API returns 409 `stale_revision` and does not overwrite it. The workspace reloads the saved lines and keeps the unsaved edit so it can be written onto the newer revision.
- Notes are timed annotations. The panel calls them artist observations, not measured evidence and not an Album QC verdict.
- Lyric edits do not rewrite the `m1-v3` analysis cache.
- The panel states that sung timing is not guessed and that inspiration charts are not in this slice.

## Not in this build

- L01–L05 musical-inspiration charts
- Technical, lyricist, or combined ZIP export
- An optional narrative or other model client
- Album comparison and T11
- Vocal, instrument, mood, or defect classification
- Automatic alignment of words to singing

Per-chart PNG files exist. A downloadable export package does not. Settings state that AI interpretation is off.

## Architecture

The repository is a local monorepo. The frontend owns `frontend/**`. The backend owns `backend/**`. API shapes used by the UI are generated into `frontend/src/api/types.ts`.

| Layer | Role |
| --- | --- |
| Frontend | React 19.3, TypeScript 7, Vite 8.3 on `127.0.0.1:5173`. Tailwind 4, Lucide, WaveSurfer 8.0.2, ECharts 6.1. Vitest and Testing Library. |
| API | Python 3.12, FastAPI 0.143, Pydantic 2.14, Uvicorn 0.54 on `127.0.0.1:8000`. |
| Measurement | NumPy, SciPy, and FFmpeg. `backend/app/measure.py` measures the master. `backend/app/charts.py` builds T01–T10. Matplotlib writes PNGs from those documents. There is no second DSP library. |
| Worker | `python -m app.worker` claims queued jobs, writes `m1-v3`, and marks an abandoned `running` job failed with error `interrupted`. |
| Storage | SQLite file `studio.sqlite3` plus content-addressed files under the data root. |
| Tests | pytest and Ruff in `backend/`. Vitest, `tsc`, and Vite build in `frontend/`. |

Loudness uses FFmpeg’s EBU R128 filter and is labeled as that measurement. Integer PCM is scaled by its own full scale: 32768 for 16-bit and 8388608 for 24-bit.

### Why measurements stay separate from interpretation

A ready chart is a statement about the file under a named method. It is not a statement about taste, arrangement, or what a listener would notice. Tempo, pitch-class, structure, and recurrence stay `estimated`. A low stereo correlation, a true-peak figure, or an ending marker is a number to inspect, not a certified audible problem. Lyric text is `textual`. An artist note is an observation stored beside the audio, and it does not enter the measurement cache.

The same WAV and the same `m1-v3` parameter hash reproduce the stored metrics. A lyric revision is not part of that key.

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
| `ARS_DATA_ROOT` | API | Directory for the database, masters, derivatives, peaks, analysis, and lyric files. Unset or empty uses `~/Library/Application Support/AudioReferenceStudio`. A non-empty value is expanded with `~`. |
| `ARS_MAX_BYTES` | API | Upload limit in bytes. Default `524288000` (500 MiB). |
| `ARS_MAX_DURATION_S` | API | Maximum duration in seconds. Default `900`. |
| `ARS_CORS_ORIGIN` | API | Browser origin allowed to call the API directly. Default `http://127.0.0.1:5173`. |
| `ARS_API_ORIGIN` | Vite dev server | Where the dev server proxies `/api`. Default `http://127.0.0.1:8000`. |

The proxy is a development convenience: the page on port 5173 forwards `/api` to the API process. The data root is where files are stored. Changing one does not change the other. Point `ARS_API_ORIGIN` at the API if it is not on port 8000, and point `ARS_CORS_ORIGIN` at the page if the UI is not on port 5173.

Under the data root the API uses `studio.sqlite3`, `blobs/{sha256}`, `derivatives/{sha256}/`, `peaks/{sha256}/`, `analysis/{sha256}/m1-v3/`, `lyrics/{sha256}`, and `tmp/`.

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

## Reliability and limitations

The stored WAV is the upload. Playback of a 24-bit file uses a separate 16-bit derivative, and a failed conversion leaves the master in place.

Repeating analysis for the same bytes, `m1-v3`, and parameter hash reuses the stored metrics. Each chart document names its method and `method_version`. Builders fill sample rate and hop on the charts that have them; T02 leaves `hop_s` empty and names its windows on the series.

A level, a spectrum, a loudness figure, or a stereo coefficient describes the signal under that method. It does not decide whether the recording sounds good, which instrument played, or whether a listener would hear a defect. This repository does not treat the charts as a validated listening test.

T06–T09 remain estimates. Half-time and double-time are hypotheses. Pitch-class candidates are not a chord chart. Change points are not verified verses or choruses. Similar spectra are not the same melody.

SRT times are the cue times supplied in the file. The application does not move them onto sung phonemes. Text and Markdown gain times only when you set them. Confirming alignment records that you did so. It does not measure the vocal.

Offline analysis does not call a model. No narrative client is installed. Imported audio is not uploaded for interpretation. Optional AI writing, if it is ever added, is specified to stay off unless you enable it, and the technical package is specified to remain available without it.

## Status

Milestone 0, commit `e4f1223`, is the local studio: WAV import, playback, and charts left `not_run`.

Milestone 1 is accepted at `a387bb2`. Analysis version is `m1-v3`. Charts T01–T10 are the accepted technical set. Preserve that measurement behavior.

M2-A, commit `4d1e71b`, adds lyric storage, parsing, revisions, annotations, and evidence reads. `backend/tests/test_lyrics.py` covers that work. The owner accepted M2-A on 2026-10-14.

M2-B, commit `d1f29a7`, is the lyrics workspace, covered by `frontend/src/lyrics.test.tsx`. The owner accepted M2-B on 2026-10-14.

Milestone 2 as a whole is not accepted. M2-C is not accepted.

That acceptance cites [docs/qa/m2a-m2b-2026-10-15.md](docs/qa/m2a-m2b-2026-10-15.md). Backend: Ruff passed; pytest 58 passed. Frontend: typecheck passed; Vitest 31 passed; build passed. Browser QA passed for tested lyric ingestion, editing, persistence, timing, annotations, conflict protection, concurrent reads, playback continuity, and restart behavior. No M2-A or M2-B functional defect was identified in the executed tests. The report's "Not tested" section lists scenarios this acceptance does not cover.

Still ahead, and not started as product behavior:

- M2-C, the five inspiration charts L01–L05 ([plan](docs/superpowers/plans/2026-10-13-milestone-2.md))
- Milestone 3 export packages, and any optional narrative client
- Milestone 4 Album QC

The product contract is [docs/01_TECHNICAL_MVP_SPEC.md](docs/01_TECHNICAL_MVP_SPEC.md) and [docs/04_TECHNICAL_CHART_REQUIREMENTS.md](docs/04_TECHNICAL_CHART_REQUIREMENTS.md). Where an older note disagrees with the accepted Milestone 1 commit, the commit and the current code win.

## Further reading

- [Technical MVP specification](docs/01_TECHNICAL_MVP_SPEC.md) — product boundaries, screens, and milestone gates
- [Technical chart requirements](docs/04_TECHNICAL_CHART_REQUIREMENTS.md) — T01–T11, evidence labels, and validation intent
- [Milestone 2 plan](docs/superpowers/plans/2026-10-13-milestone-2.md) — lyric evidence, the workspace, and L01–L05
- [Implementation audit](docs/album_observatory_followup_audit.md) — snapshot from before owner acceptance of M2-A and M2-B. It is not an acceptance decision.
- [Local toolchain note](docs/ENVIRONMENT.md) — recovering a stalled Vite or Vitest run

`docs/README.md` is the index to the requirements and the running app. `NEXT_SESSION.md` is the current handoff and does not accept a milestone. `docs/03_CURSOR_AGENT_FIRST_SESSION.md` is the historical Milestone 0 session.
