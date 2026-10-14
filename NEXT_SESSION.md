# Next session

Milestone 1 is accepted at `a387bb2`. Analysis version is `m1-v3`. Charts T01–T10 stay on that measurement. Do not change it.

M2-A is implemented and verified at `4d1e71b` and is not accepted. M2-B, the lyrics workspace, is implemented and verified in this tree and is not accepted. Do not start M2-C, ZIP export, album comparison, or a narrative client unless asked. Do not build the T02 stored-sample inspector unless asked.

## What is in place

- WAV import keeps the original bytes at `blobs/{sha256}`. Playback uses that blob for 16-bit PCM and `derivatives/{sha256}/pcm_s16le-triangular-v1.wav` for 24-bit PCM.
- `POST /api/assets/{id}/analyze` returns 202. `python -m app.worker` runs the job. A completed `m1-v3` run with `metrics.json` is reused.
- T01–T05 and T10 are measured when they apply. Mono T05 is `not_available` with evidence class `not_applicable`. T06–T09 stay estimated.
- Lyric `.txt`, `.md`, and `.srt` files are stored, edited, timed by hand, and drawn as waveform regions when the interval is usable. SRT times are the subtitle file’s times. A stale revision returns 409 and does not overwrite the newer text.
- Notes are annotations. Lyric edits do not rewrite `analysis/{sha256}/m1-v3/`.
- L01–L05 are not implemented. Album QC is an empty state. Settings leave AI interpretation off.

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

Open `http://127.0.0.1:5173/`. Without the worker, a new analysis stays `queued`.

`ARS_DATA_ROOT` is the API storage directory. Unset or empty uses `~/Library/Application Support/AudioReferenceStudio`. `ARS_API_ORIGIN` is only the Vite dev proxy for `/api`, read from the shell when `frontend/vite.config.ts` loads. Default `http://127.0.0.1:8000`.

## Checks last run

14 Oct 2026, on this working tree:

- `backend/`: `uv run ruff check .` passed. `uv run pytest -q`: 58 passed. One Starlette warning: `httpx` with `starlette.testclient` is deprecated.
- `frontend/`: `pnpm typecheck` passed. `pnpm test`: 4 files, 31 tests passed. `pnpm build` passed. The main JS chunk is about 1.45 MB, and Vite warned that it is over 500 kB.

## Not claimed

Tempo, pitch-class, structure, and recurrence are estimates. A loudness, peak, or correlation figure is not a judgment that something is audible. Subtitle cues are not sung-word alignment. The lyrics workspace has not been checked in a browser in this handoff. Chart zoom shared with the waveform is not implemented.
