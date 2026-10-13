# Next session

Milestone 1 is complete. Stop here. Do not start Milestone 2 until the human accepts this gate.

## What Milestone 1 completed

- Analysis runs in a separate worker (`python -m app.worker`), one job at a time. `POST /api/assets/{id}/analyze` returns 202 and does not measure inside the request. Status words are `queued`, `running`, `completed`, `failed`, and `canceled`. An abandoned `running` job is marked `interrupted` and can be retried.
- Measurements read the stored master, not the 16-bit playback derivative. Algorithm version `m1-v1`. Results cache by asset hash plus that version. A cache hit returns a completed job and does not rewrite the files.
- Charts T01–T10. T01–T05 and T10 are measured. T06–T09 are estimated and say so. A mono file makes T05 `not_available`. A file too short for 2 s structure bins makes T08 and T09 `not_available`. One chart failing leaves the others in place.
- Each ready chart has JSON, a PNG, and a place in `metrics.json` and `evidence.json`. The screen plots server series with ECharts. Clicking a time axis seeks the transport. Switching charts does not remount playback.
- Legacy `metrics.json` is a schema comparison only. The original WAVs are absent, so there is no numerical parity claim. Decoder scale is 16-bit / 32768 and 24-bit / 8388608.

## Commands

From `backend/`, in two terminals:

```bash
uv run uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
uv run python -m app.worker
```

From `frontend/`:

```bash
pnpm dev
```

Open `http://127.0.0.1:5173/`. Without the worker, Analyze stays `queued`. The default data root is `~/Library/Application Support/AudioReferenceStudio/` unless `ARS_DATA_ROOT` is set.

Checks:

```bash
cd backend && uv run ruff check app tests && uv run pytest -q
cd frontend && pnpm typecheck && pnpm test && pnpm build
```

## What was tested

- `uv run ruff check app tests` — all checks passed.
- `uv run pytest -q` — 24 passed, 1 warning in 5.43s. The warning is Starlette's deprecation of `httpx` in `TestClient` (httpx 0.28.1 stays pinned). New coverage includes 16/24-bit scale, a 440 Hz band, stereo and mono, oversampled peak above the sample peak, a 5 s worker run (master hash unchanged, T02 and T05 ready, T08 not available, PNG header, cache hit does not rewrite metrics), a failed T03 leaving T02 ready, and interrupted-job retry.
- `pnpm typecheck` — exit 0.
- `pnpm test` — Test Files 1 passed (1), Tests 4 passed (4).
- `pnpm build` — exit 0. Vite warns that the ECharts bundle is over 500 kB.
- Browser, with the API and worker running: a 5 s 44.1 kHz stereo 16-bit tone (`m1-tone.wav`) analyzed to completion. T01–T07 and T10 ready. T08 and T09 not available. T02 evidence: integrated loudness -6.9 LUFS, sample peak -6.23 dBFS, true peak -6.2 dBTP, with the short-file LRA caveat. No progress bar. Clicking the T01 plot moved the transport to 1.44 s. The same audio element stayed mounted across a chart change. Play ran to the end of the file. Lyrics still says text upload is not in this milestone. At 390 px the workspace is one column and the page does not scroll sideways.

## What was not tested

- The operating-system file dialog. The tone was uploaded through the API into the existing "Reference study" project.
- A 24-bit master played in the browser during this milestone. Derivative behavior remains covered by the Milestone 0 tests.
- A click-train tempo or a file long enough for T08 and T09. Those charts are estimated and were not checked against a known BPM or section.
- Listening quality, or numerical equality with `references/legacy-audit/analysis/metrics.json`.

## Deferred

Lyric text and SRT upload, lyric timing, the five lyricist charts, album comparison, ZIP export, and AI interpretation. Do not add Playwright, Alembic, Redis, Celery, auth, or a model client unless a later approved milestone requires one.

## Risks

- The verification tone `m1-tone.wav` is in the default Application Support data root, project "Reference study", beside the earlier `browser-tone.wav`. That directory is outside git.
- Humans must start the worker or Analyze never leaves `queued`.
- T06 tempo and T07 key names are estimates. Do not describe them as a verified grid or key.

## Smallest Milestone 2 target

TXT and SRT upload with timing provenance: plain text stays unplaced, and SRT cues keep their own times. Do not guess sung timestamps. Do not add another DSP chart.
