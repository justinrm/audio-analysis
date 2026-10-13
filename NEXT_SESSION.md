# Next session

Milestone 0 is complete. Stop here. Do not start Milestone 1 until the human accepts this gate.

## What Milestone 0 completed

- Local-first studio: React/TypeScript on `127.0.0.1:5173`, FastAPI on `127.0.0.1:8000`, SQLite plus files under the data root. No cloud, auth, telemetry, payments, or API keys.
- Import of 16-bit and 24-bit PCM WAV. The master bytes and SHA-256 stay unchanged. A 24-bit file gets a separate 16-bit playback derivative (`pcm_s16le-triangular-v1`). If FFmpeg fails, the master import still succeeds and `playback_status` is `unavailable`.
- Content-addressed blobs. The original filename is display-only. Re-importing the same bytes is a cache hit and does not duplicate `project_assets`.
- Chunked min/max peak envelope for the WaveSurfer transport (`playback_minmax_envelope_v1`). This is a playback preview, not chart T01. No loudness, spectrum, or dynamics are computed.
- `POST /api/assets/{id}/analyze` returns HTTP 501 and inserts zero jobs. `analysis_status` stays `not_run`. The jobs table and `AnalysisWorker` exist so a later worker can return 202 with `queued|running|completed|failed|canceled`. The worker does not mark anything completed.
- Library, Analyzer, Album QC, and Settings. Technical categories T01–T10 show not-run. Lyrics & Inspiration says text upload is not in this milestone. Album QC says comparison is not in this milestone. Settings says AI interpretation is off and has no API-key field.

## Commands

Backend (from `backend/`):

```bash
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
```

Frontend (from `frontend/`):

```bash
pnpm dev
```

Open `http://127.0.0.1:5173/`. The default data root is `~/Library/Application Support/AudioReferenceStudio/` unless `ARS_DATA_ROOT` is set. Caps and CORS are in `.env.example`.

Checks:

```bash
cd backend && uv run ruff check . && uv run pytest -q
cd frontend && pnpm typecheck && pnpm test && pnpm build
```

## What was tested

- `uv run ruff check .` — all checks passed.
- `uv run pytest -q` — 13 passed, 1 warning in 0.68s. The warning is Starlette's deprecation of `httpx` in `TestClient` (httpx 0.28.1 stays pinned). Covered: 16-bit and 24-bit metadata, original SHA-256 unchanged after import and after the derivative, float and invalid WAV rejected, hostile filename does not become a path, oversized input rejected, interrupted upload removes the temp file, duplicate import reuses the blob and does not duplicate `project_assets`, range request 206, analyze returns 501 and inserts zero jobs, peaks are finite and min/max-preserving on a known square, derivative failure leaves the master imported with playback unavailable.
- `pnpm typecheck` (`tsc --noEmit`) — exit 0.
- `pnpm test` (`vitest run`) — Test Files 1 passed (1), Tests 3 passed (3).
- `pnpm build` — exit 0 (`tsc --noEmit && vite build`, built in 378ms).
- Browser on the fresh Vite server: create/open the study, import a synthetic 16-bit WAV through the Import control's change handler, library row (`browser-tone.wav`, 16-bit PCM, 8 kHz, mono, 0:01, `not_run`, `ready`), Open analyzer, WaveSurfer canvas plus stream URL, seek to 0.35s, play (`paused` false, time advanced), pause (time held). Technical T01–T10 not run, only the selected category is current, Analyze shows "Analysis is not implemented. No job was created." with no progress. Lyrics tab, Album QC, and Settings show the honest milestone copy. At 1400px the analyzer is sidebar plus three panes (`240px 528px 272px`). At 480px both the shell and the workspace are one column. Stream requests logged `206 Partial Content`. Analyze logged `501`.

## What was not tested

- The operating-system file dialog. The browser tools cannot set a file input. Import was exercised by assigning a synthetic WAV to that input and dispatching `change`, which is the same handler as the Import control.
- A 24-bit file played in the browser. Derivative bytes, hash stability, and "stream the derivative, not the master" are covered by pytest.
- Listening quality of the triangular dither.
- A real recording longer than the one-second synthetic tone.

## Deferred

Analysis jobs, loudness, RMS, spectrum, stereo, dynamics, chart T01 as a measured series, lyric text upload, sung timing, album comparison, exports, and AI interpretation. Do not add NumPy, SciPy, ECharts, Playwright, Alembic, Redis, Celery, auth, or a model client unless a later approved milestone requires one.

## Risks

- The verification import wrote `browser-tone.wav` into the default Application Support data root (project "Reference study"). That directory is outside git. Delete the folder if a clean first launch is wanted.
- Playback peaks are a preview envelope. Treating them as T01 would mix a display downsample with a measured chart.
- `GET /api/jobs/{id}` 404s until a real worker creates rows. Do not invent a completed job.

## Smallest Milestone 1 target

Per-file FFmpeg loudness plus RMS/energy from the legacy math, rendered as the first real Technical Analysis chart **T02** through a canonical chart registry.

Do not port the legacy scripts. Do not copy song names or report constants from `references/legacy-audit/`. Do not build T01 or T03–T10 in that first slice. Keep evidence labeled measured, estimated, textual, interpretive, or unknown, and do not invent audible-defect verdicts.
