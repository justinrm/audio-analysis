# Cursor Agent — First Implementation Session

> **Historical prompt.** This file preserves the original Milestone 0 draft. Use [NEXT_SESSION.md](../NEXT_SESSION.md) for current work. The draft's Milestone 1 slice and queued-stub suggestion were superseded. The implemented Milestone 0 checkpoint returned HTTP 501 without creating an analysis job. The worker-backed HTTP 202 contract arrived with Milestone 1.

## Authority and boundaries

Read **01_TECHNICAL_MVP_SPEC.md**, **02_SCRIPT_REVIEW.md**, and **04_TECHNICAL_CHART_REQUIREMENTS.md** before making changes. The project is a single-user, local-first audio analysis application with a real React frontend and Python backend. It has **two equal modes:** a complete technical analysis dashboard for WAV alone, and lyricist-focused musical inspiration views for WAV plus optional lyrics/SRT; Album QC compares tracks. It may later become a public product, but **do not add hosting, cloud infra, authentication, payments, telemetry, or paid AI calls now**.

The attached `Four_Song_Audit_Evidence.zip` is a **reference implementation**. **Inspect before copying**. Source WAVs are not included. Archive its four scripts under a legacy/reference area or work from an explicit relative reference path; do not execute it automatically or import report-specific constants into production code. Use the five `Praise Kink` charts as UX/visual examples; their original generating code was not supplied.

Never rewrite source audio or infer exact sung lyric placement from plain text.

## Mission for this bounded session

Deliver **Milestone 0** plus an architecture-ready first vertical slice of **Milestone 1**. The result must look and function like a real application, not a static mockup.

### Required output

1. `frontend/` React + TypeScript + Vite UI with coherent dark palette, responsive layout and functioning navigation.
2. `backend/` Python FastAPI app, typed contracts, health endpoint, upload and asset records.
3. Local SQLite + managed file store; source audio bytes remain unchanged.
4. One real end-to-end workflow: import WAV → metadata validated → asset appears in Library → open Analyzer → play/seek WAV and view duration/basic file information.
5. Minimal local worker process/job contract and analysis service stub that cleanly supports later CPU-heavy computations (do not pretend background analysis completed if it hasn't).
6. Synthetic WAV fixtures and tests for file metadata, original hash integrity, 16-bit PCM, 24-bit PCM and API round-trip.
7. Setup commands for macOS Apple Silicon and `.env.example`; keys ignored by Git.
8. A concise implementation log: completed, tested, blocked, deferred, current risks.

### UI requirements

- Sidebar: Library, Audio Analyzer, Album QC (not-yet-active clearly labeled or functionally empty-state), Settings.
- Analyzer subnavigation: **Technical Analysis** (WAV-only usable) and **Lyrics & Inspiration** (optional text). Technical has category navigation for waveform/levels, mastering/dynamics, spectrum, stereo, rhythm/tonality, novelty/recurrence and events. Future views show honest unavailable/not-run states, never simulated measurements.
- Library grid/list: real records with format, duration, processing status, timestamp, and a usable Import action.
- Analyzer: usable toolbar/transport with waveform, player, timeline seek, **Technical Analysis tab**, empty lyric panel and empty evidence panel; functional visual state/loader/error displays.
- Responsive: desktop three-pane concept; tablet/mobile may stack.
- Visual design: editorial dark slate/ink backgrounds, subtle borders, restrained accent, clear readable charts and ample attention to spacing. No gaudy gradients, no generic AI-dashboard wallpaper.
- Controls should have actions. Do not add inert badges, fabricated waveform charts, or placeholder analysis results as though real.

### API baseline

`GET /api/health`, `POST /api/projects`, `GET /api/projects`, `GET /api/projects/{id}`, `POST /api/projects/{id}/assets`, `GET /api/assets/{id}`, `GET /api/assets/{id}/stream` with Range, `POST /api/assets/{id}/analyze`, `GET /api/jobs/{id}`. The analysis endpoint may return a job in `queued`/`not_implemented` until the worker exists, but may not claim success without metrics.

### Engineering requirements

- Project names/filename strings never become raw paths.
- Stream upload in chunks and hash simultaneously. Configurable max size and no dangerous path traversal.
- Support normal WAV PCM 16 and 24 on metadata inspection. Defer non-PCM analysis, but return a clear diagnostic instead of misreading data.
- Bind backend to localhost; CORS explicit for dev frontend.
- `pytest`, type/lint, React tests and build all runnable. Generate TS API types from OpenAPI if feasible within scope.
- Use function boundaries permitting pure DSP modules later; don't implement source separation, AI perception, lyric auto-alignment or report generation now.
- No third-party hosted audio or model call.

## Execution discipline

1. Inspect any existing repository before writing files. **If it already has code**, prepare a bounded change plan that preserves unrelated files and ask before destructive restructuring.
2. Confirm actual local tools/versions, select pinned compatible dependencies and identify unsupported features.
3. Build one vertical slice completely before implementing more screens.
4. Execute all tests and verify the app in a browser if tools permit; report exactly what was and wasn't tested.
5. Stop when Milestone 0 acceptance is reached. Do not autonomously move through future milestones.

## Acceptance review (artist)

- Start backend/frontend using documented local commands.
- Upload a synthetic WAV and a real song WAV.
- See persisted asset records and correct format/duration.
- Press play, pause and seek using the visible waveform and time ruler.
- Restart both servers: asset and metadata persist, waveform remains functional.
- Verify SHA-256 identical before/after and no surprise API requests.
- View correct behavior on a narrow/mobile browser width.

## Future-session handoff

When finished, write `NEXT_SESSION.md` naming the smallest Milestone 1 target: extracting per-file FFmpeg loudness plus RMS/energy from the legacy scripts and rendering the first real **Technical Analysis** chart (T02), using the canonical chart registry. The subsequent core technical chart gates are specified in `04_TECHNICAL_CHART_REQUIREMENTS.md`. Do not prematurely refactor all 651 lines of old analysis code or build all charts in one agent turn.
