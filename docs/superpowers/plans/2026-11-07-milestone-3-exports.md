# Milestone 3 export scope

> **Implementation reference.** On November 7, 2026, the owner accepted M3-A and M3-B. Milestone 3 overall remains open. [PROJECT_STATUS.md](../../../PROJECT_STATUS.md) owns acceptance. [NEXT_SESSION.md](../../../NEXT_SESSION.md) owns the current handoff. The narrative client is not authorized.

**Goal:** Produce a per-recording Technical ZIP from stored `m1-v3` evidence, then a Lyricist ZIP and a Combined ZIP from that same evidence plus the current lyric document, without a network client.

**Architecture:** Export reads the accepted stores and writes a new snapshot under `exports/{id}/`. It does not decode the WAV, remeasure, or rewrite `analysis/{sha256}/m1-v3/`. Technical PNGs are copies of valid `png-r1` files. Lyric PNGs are a new drawing of the existing lyric-chart documents. The deterministic Markdown brief is a template over those documents. A model provider is not required for either ZIP.

**Tech stack:** FastAPI, Pydantic, SQLite, stdlib `zipfile`, Matplotlib already used by `backend/app/png.py`. No new dependency.

**Spec:** `docs/01_TECHNICAL_MVP_SPEC.md` sections 3F, 4B, 5, 7, 9, and Milestone 3; `docs/04_TECHNICAL_CHART_REQUIREMENTS.md` sections 1, 4, and validation items 7–9.

**Inspected baseline:** `ee7258152a401147d1099a35b87c842115a63e99`.

## What already exists

| Need | Reuse |
| --- | --- |
| Asset hash, duration, sample rate, channels | `assets` row and `blobs/{sha256}` |
| Technical numbers | `analysis/{sha256}/m1-v3/metrics.json`, `evidence.json`, `T01.json`–`T10.json` |
| Technical PNG | `analysis/{sha256}/m1-v3/presentation/png-r1/{kind}.png` when `rendered_png()` accepts the manifest |
| Unavailable technical chart | chart `status` and `not_available_reason`; image route already returns `png_unavailable` until `png-r1` exists |
| Lyric charts | `build_lyric_chart()` in `backend/app/lyric_charts.py` |
| Provenance | `canonical_evidence()` returns `analysis_version`, `lyric_document_id`, `lyric_revision`, and cited records |
| Original lyric bytes | `GET .../lyrics/source` and `lyrics/{sha256}` |
| Atomic replace | `publish_png()` and `write_manifest()` write a temp file, check it, then `os.replace` |
| AI off | Settings copy says interpretation is off. `POST /api/projects/{id}/narratives` and `POST /api/projects/{id}/exports` are absent and tested |

Do not copy the WAV into a package. Do not call `measure.py`. Do not import a new HTTP client.

## Recommended division

Two implementation slices, reviewed in order. One assignment may contain both only after the owner authorizes both. The optional narrative client is a third, later authorization and is not required to accept the packages.

| Slice | Delivers | Depends on |
| --- | --- | --- |
| M3-A | Technical ZIP for one recording, including a recording with no lyrics | Nothing beyond the accepted baseline |
| M3-B | Lyric PNG drawings, Lyricist ZIP, Combined ZIP | M3-A layout, manifest, and route |
| Later, separate | Optional provider client | Accepted packages. Export must already succeed with the provider unset |

Cursor Multitask stays off. The route, manifest, and ZIP writer are one path.

## 1. Order

1. M3-A storage, manifest, Technical ZIP, and download route.
2. Tests for hash stability, missing PNGs, mono `T05`, and an unchanged analysis cache.
3. Owner review of M3-A before M3-B, unless both were authorized together.
4. Lyric figure renderer and Lyricist ZIP.
5. Combined ZIP as a composition of the two trees with one metrics file and one evidence file.
6. A recording-page control that downloads the ZIP the API already built.

## 2. API and records

Use the membership path, matching lyrics rather than the spec's project-only sketch:

- `POST /api/projects/{project_id}/assets/{asset_id}/exports`
- Body: `profile` of `technical`, `lyricist`, or `combined`; `lyrics` of `summarized`, `included`, or `omitted`. Default `summarized`.
- `GET` the same path plus `/{export_id}` returns the ZIP. `export_id` is a generated id, never a caller path.

`lyricist` without a current lyric document returns 409 `no_lyrics`. `technical` is valid with no lyric document. `combined` requires membership and a current lyric document. Analysis that has not been run still exports: every chart is `not_run` or `not_available`, and no PNG is invented.

SQLite migration `backend/migrations/004_exports.sql`: `export_runs(id, project_id, asset_id, profile, lyrics_mode, lyric_revision, source_sha256, algorithm_version, params_hash, content_sha256, created_at)`. The ZIP path is `exports/{id}.zip` under the data root. A failed build leaves no row and no published ZIP.

Response JSON is the manifest. Regenerate `frontend/src/api/types.ts` from OpenAPI. Do not hand-edit it.

## 3. Package layout

Technical:

```text
technical/README.md
technical/manifest.json
technical/metrics.json
technical/evidence.json
technical/charts/T01.json … T10.json
technical/charts/T01.png …   # only kinds rendered_png() accepts
```

Lyricist:

```text
lyricist/README.md
lyricist/brief.md
lyricist/manifest.json
lyricist/evidence.json
lyricist/charts/L01.json … L05.json
lyricist/charts/L01.png … L05.png
```

Combined puts `metrics.json` and `evidence.json` at the ZIP root once. Technical charts live under `technical/charts/`. Lyric charts and `brief.md` live under `lyricist/`. There is no second metrics file and no WAV.

`evidence.json` in a lyricist or combined package is the canonical bundle for that membership at `lyric_revision`. The technical package copies the stored technical `evidence.json` only.

README files state method `m1-v3`, renderer versions, the source SHA-256, lyric revision, lyrics mode, and the open G3 and G6 limits. They do not add listening judgments.

`brief.md` is rendered from L01–L05 summaries, caveats, findings, insufficient rows, and citations. `lyrics=omitted` drops line text and repetition strings. `summarized` keeps counts, timing origins, and citation ids, and drops line text. `included` adds the stored line text. The default is `summarized`.

## 4. Renderer

Technical PNGs are byte copies of valid `png-r1` files. The export does not call `write_png()` for T01–T10. A missing or legacy file is `png_unavailable` in the manifest. `python -m app.refresh_png` remains the way to create those files.

Add lyric drawing beside the technical renderer, version `lyric-png-v1`. Input is the dict from `build_lyric_chart()`. Output is one PNG per L01–L05 document, including a `not_available` chart as a caption-only figure that states the reason.

Required drawings the current `render_figure()` does not make:

- L01 and L03 time series plus `regions` and review markers.
- L02 word-count bars and the words/s line on the same figure.
- L04 heatmap plus the textual repeat rows.
- L05 findings, principles, citations, and insufficient rows as text.

Do not change T01–T10 drawing in that work. L02's two series are new lyric drawing, not a fix for technical G6.

## 5. Identity

Manifest fields, all taken from stored records:

- `source_sha256` of the WAV blob
- `algorithm_version` `m1-v3` and the stored `params_hash` when metrics exist
- technical `renderer_version` `png-r1`
- lyric `renderer_version` `lyric-png-v1` when those figures exist
- `lyric_document_id`, `lyric_revision`, and the lyric-source SHA-256 when a document exists
- `content_sha256` over the sorted chart JSON, evidence JSON, metrics JSON, and brief bytes, excluding `created_at` and `export_id`

`created_at` may differ between runs. `content_sha256` must not. A later lyric save creates a new export at the new revision and does not alter the previous ZIP or `m1-v3`.

## 6. Atomic publish

Build in `exports/.{id}.tmp/`. Write the ZIP to `exports/.{id}.zip.tmp`. Validate the ZIP entries and the PNG signatures. Insert the SQLite row and `os.replace` the ZIP into `exports/{id}.zip` in that order only after validation. Delete the temp directory on success and on failure. Store no caller-supplied filename.

## 7. Independent workflows

`technical` never reads lyric tables except to ignore them. `lyricist` reads the current document and stored T02, T08, and T09 through the existing builders. `combined` calls the same two builders and merges the trees. Settings stay "AI interpretation is off." Package generation does not open a socket.

## 8. Tests

Backend, in `backend/tests/test_exports.py`:

- WAV with a completed `m1-v3` run and no lyrics: Technical ZIP, no lyric paths, blob hash unchanged, analysis files byte-identical.
- Same inputs twice: equal `content_sha256`.
- Chart not ready: JSON status copied, no PNG entry.
- `png-r1` absent: `png_unavailable`, chart JSON still present.
- Mono recording: T05 `not_available` / `not_applicable`.
- Lyricist without a document: 409 `no_lyrics`.
- `summarized` ZIP has no lyric line text; `included` has the stored line.
- Reversed cue stays out of L01 `regions`.
- Export, then edit the lyric: the first ZIP's `lyric_revision` is unchanged and `m1-v3` bytes are unchanged.
- Combined ZIP contains one `metrics.json`.
- Export path rejects an id that is not the stored id.
- The export module does not import `app.measure` or an HTTP client.

Frontend: one Vitest that the recording offers Technical, Lyricist, and Combined actions and does not send a lyricist export when no document is loaded. One browser check after implementation: download a Technical ZIP for a synthetic analyzed WAV, then a Lyricist ZIP after an SRT attach. Widths already covered by Milestone 2 do not need a new pass unless the control overflows.

## 9. Owner decisions already applied by this proposal

These are recommendations. Authorizing a slice accepts them for that slice. Rejecting one needs a one-line replacement, not a new planning session.

| Decision | Recommendation | If rejected |
| --- | --- | --- |
| Route shape | Membership path above | Say the exact path before coding |
| G3 | Copy stored T03 unit `dB`. Do not relabel dB/Hz | A unit change is a measurement change, outside this milestone |
| G6 | Keep technical PNGs as `png-r1`, bars omitted where lines exist. Full series remain in chart JSON | Require a renderer fix as its own authorized change before M3-A |
| Default lyric text | `summarized` | Name `included` or `omitted` |
| Narrative client | Not in M3-A or M3-B. Manifest `narrative` is `none` | Authorize a later slice with a provider interface and a test that a disabled provider performs no HTTP |
| Praise Kink pixels | Match L01–L05 information already accepted. No private layout file is in the tree | Supply the reference images and name the differences that matter |
| Not-yet-run analysis | Export explicit `not_run` charts and no invented PNG | Require 409 until analysis completes |

## Files an authorized slice may touch

M3-A: `backend/app/exports.py`, `backend/migrations/004_exports.sql`, `backend/app/main.py`, `backend/tests/test_exports.py`, the OpenAPI type generator output, and a small download control in `frontend/src/analyzer.tsx`.

M3-B: `backend/app/lyric_png.py`, lyric entries in the same export module and tests, and the Lyricist/Combined actions on that control.

Neither slice edits `backend/app/measure.py`, `backend/app/charts.py`, `ALGORITHM_VERSION`, or the T01–T10 branch of `render_figure()`.
