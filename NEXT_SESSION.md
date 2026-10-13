# Next session

Milestone 1 remediation is implemented and is waiting for the owner to accept it. Do not start Milestone 2.

## What changed after `0f7d7aa`

Algorithm version is `m1-v2`. A completed `m1-v1` cache is not reused.

- T01 plots a master min/max envelope at 4000 and 250 buckets, plus 100 ms and 1 s RMS. The sample peak is a separate marker.
- Review markers render on time charts and as buttons. A click seeks playback. Labels stay listening checkpoints.
- T02 compares equal-duration analysis windows against the file's mean RMS. The labels are windows, not song sections.
- T04 stays on linear FFT bins, annotated with Nyquist and the bass/body/presence/air edges.
- T06 shows half-time or double-time only when the autocorrelation has a peak near that period.

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

Open `http://127.0.0.1:5173/`. Without the worker, Analyze stays `queued`.

## Checks last run

- `uv run ruff check app tests` passed. `uv run pytest -q`: 33 passed, 1 httpx deprecation warning.
- `pnpm typecheck`, `pnpm test` (4 passed), and `pnpm build` passed. The production bundle is over 500 kB because of ECharts.

## Not claimed

Tempo, key, and section labels are estimates. The loudness check compares a 1 kHz sine with peak-minus-3.01 dB; it uses FFmpeg as the meter, not as a second opinion about FFmpeg. The operating-system file dialog was not used. Zoom on the chart was not clicked in the browser.
