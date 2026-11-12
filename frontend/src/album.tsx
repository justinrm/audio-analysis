import { useEffect, useRef, useState } from "react"
import WaveSurfer from "wavesurfer.js"
import { api, streamUrl } from "./api/client"
import type {
  AlbumChart,
  Asset,
  ChartDocument,
  ChartLine,
  ComparisonDocument,
  PairRecord,
  Peaks,
  Project,
  ProjectDetail,
  ReviewRecord,
  ScalarRecord,
  TrackRecord,
} from "./api/types"
import { analysisCounts, analysisSummary, batchMessage, runAlbumBatch, type BatchPlan } from "./album-batch"
import {
  checkpointLabel,
  differenceUnit,
  evidenceReason,
  filterPairs,
  formatCount,
  formatMeasure,
  formatNumber,
  formatScore,
  measurementLabel,
  omitLabel,
  pairKey,
  storedNumber,
} from "./album-format"
import { AddRecordingsDialog } from "./album-picker"
import { clock, evidenceLabel, playbackCaption, statusLabel, toWavePeaks } from "./catalog"
import { ChartView } from "./chart"

type Feedback = { role: "status" | "alert"; text: string }

const LEVEL_UNITS = ["LUFS", "dBFS", "dBTP", "LU", "dB"] as const
const REVIEW_STATUSES = ["unchecked", "confirmed_issue", "intentional", "not_audible"] as const
const SECTIONS = [
  ["overview", "Overview"],
  ["recordings", "Recordings"],
  ["comparisons", "Comparisons"],
  ["evidence", "Endings and rhythm"],
  ["listening", "Listening review"],
] as const

type SectionId = (typeof SECTIONS)[number][0]

function reviewLabel(status: string): string {
  switch (status) {
    case "unchecked":
      return "Unchecked"
    case "confirmed_issue":
      return "Confirmed issue"
    case "intentional":
      return "Intentional"
    case "not_audible":
      return "Not audible"
    default:
      return status
  }
}

function recordingLabel(tracks: TrackRecord[], assetId: string): string {
  const track = tracks.find((item) => item.asset_id === assetId)
  if (!track) {
    return assetId || "Album"
  }
  return `${track.ordering + 1}. ${track.original_name}`
}

function scalarText(item: ScalarRecord): string {
  if (item.evidence_class === "not_applicable") {
    return "Not applicable"
  }
  if (item.value === null || !Number.isFinite(item.value)) {
    return "Not stored"
  }
  return formatMeasure(item.value, item.unit)
}

function overlayMessage(document: ComparisonDocument | null, chart: ChartDocument | null): string | null {
  if (!document || chart?.status === "ready") {
    return null
  }
  if (document.status !== "ready") {
    return document.not_available_reason === "need_two_recordings"
      ? "Two analyzed recordings are required."
      : "This album comparison is not available."
  }
  return "A stored time value is missing, so the overlay was not drawn."
}

function asChart(panel: AlbumChart): ChartDocument | null {
  const lines: ChartLine[] = []
  for (const line of panel.series.lines ?? []) {
    if (line.x.some((value) => value === null || !Number.isFinite(value))) {
      return null
    }
    lines.push({
      name: line.name,
      unit: line.unit,
      x: line.x.filter((value): value is number => value !== null),
      y: line.y.map((value) => (value !== null && Number.isFinite(value) ? value : null)),
    })
  }
  const status = panel.status
  const chartStatus =
    status === "ready" || status === "not_run" || status === "not_available" || status === "failed"
      ? status
      : "not_available"
  const scale = panel.axis_definitions.y_scale === "log" ? "log" : "linear"
  return {
    chart_kind: panel.chart_kind,
    status: chartStatus,
    title: panel.title,
    evidence_class: panel.evidence_class,
    method_id: panel.method_id,
    method_version: panel.method_version,
    caveats: panel.caveats,
    summary: panel.summary,
    series: { lines, bars: [], heatmap: null },
    axis_definitions: { x: panel.axis_definitions.x, y: panel.axis_definitions.y, y_scale: scale },
    review_markers: [],
    not_available_reason: panel.not_available_reason ?? null,
    error: panel.error ?? null,
  }
}

export function AlbumHome({ onOpen }: { onOpen: (projectId: string) => void }) {
  const [albums, setAlbums] = useState<Project[]>([])
  const [name, setName] = useState("Album")
  const [message, setMessage] = useState("")

  useEffect(() => {
    let cancelled = false
    api
      .projects()
      .then((list) => {
        if (!cancelled) {
          setAlbums(list.filter((item) => item.mode === "album"))
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setMessage(error instanceof Error ? error.message : "Could not load albums.")
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function createAlbum() {
    setMessage("")
    try {
      const created = await api.createProject(name.trim() || "Album", "album")
      onOpen(created.id)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not create the album.")
    }
  }

  return (
    <section className="album">
      <h1 className="page-title">Album QC</h1>
      <p>Order recordings that are already in the library. Album QC reads stored measurements.</p>
      <form
        className="field"
        onSubmit={(event) => {
          event.preventDefault()
          void createAlbum()
        }}
      >
        <label htmlFor="album-name">Album name</label>
        <input id="album-name" value={name} onChange={(event) => setName(event.target.value)} />
        <button type="submit" className="action">
          Create album
        </button>
      </form>
      {message ? (
        <p className="feedback is-alert" role="alert">
          {message}
        </p>
      ) : null}
      {albums.length === 0 ? <p>No albums yet.</p> : null}
      <ul>
        {albums.map((album) => (
          <li key={album.id}>
            <button type="button" className="ghost" onClick={() => onOpen(album.id)}>
              {album.name}
            </button>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function AlbumWorkspace({
  projectId,
  onInspect,
}: {
  projectId: string
  onInspect: (assetId: string) => void
}) {
  const [detail, setDetail] = useState<ProjectDetail | null>(null)
  const [library, setLibrary] = useState<Asset[]>([])
  const [comparison, setComparison] = useState<ComparisonDocument | null>(null)
  const [reviews, setReviews] = useState<ReviewRecord[]>([])
  const [xMode, setXMode] = useState<"seconds" | "progress">("seconds")
  const [selected, setSelected] = useState("")
  const [loadedPeaks, setLoadedPeaks] = useState<{ assetId: string; peaks: Peaks } | null>(null)
  const [notes, setNotes] = useState<Record<string, string>>({})
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const [studies, setStudies] = useState<Project[]>([])
  const [studyMembers, setStudyMembers] = useState<Record<string, string[]>>({})
  const [picked, setPicked] = useState<Set<string>>(() => new Set())
  const [pickerOpen, setPickerOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [section, setSection] = useState<SectionId>("overview")
  const [pairChoice, setPairChoice] = useState("adjacent")
  const seekRef = useRef<(seconds: number) => boolean>(() => false)
  const pendingSeek = useRef<{ assetId: string; time: number } | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([api.project(projectId), api.assets(), api.reviews(projectId)])
      .then(async ([project, assets, stored]) => {
        if (cancelled) {
          return
        }
        setDetail(project)
        setLibrary(assets)
        setReviews(stored)
        setSelected((current) => current || project.assets[0]?.id || "")
        let projects: Project[] = []
        try {
          projects = await api.projects()
        } catch {
          projects = []
        }
        if (cancelled) {
          return
        }
        const studyList = projects.filter((item) => item.mode === "study")
        setStudies(studyList)
        // ponytail: one project read per study; add a membership index if study lists get large
        const entries = await Promise.all(
          studyList.map(async (study) => {
            try {
              const studyDetail = await api.project(study.id)
              return [study.id, studyDetail.assets.map((asset) => asset.id)] as const
            } catch {
              return [study.id, [] as string[]] as const
            }
          }),
        )
        if (!cancelled) {
          setStudyMembers(Object.fromEntries(entries))
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setFeedback({
            role: "alert",
            text: error instanceof Error ? error.message : "Could not open the album.",
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [projectId])

  useEffect(() => {
    let cancelled = false
    api
      .comparison(projectId, xMode)
      .then((document) => {
        if (!cancelled) {
          setComparison(document)
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setFeedback({
            role: "alert",
            text: error instanceof Error ? error.message : "Could not compare the album.",
          })
        }
      })
    return () => {
      cancelled = true
    }
  }, [projectId, xMode])

  useEffect(() => {
    if (!selected || loadedPeaks?.assetId === selected) {
      return
    }
    const asset = detail?.assets.find((item) => item.id === selected)
    if (!asset || asset.playback_status !== "ready") {
      return
    }
    let cancelled = false
    const requested = selected
    api
      .peaks(requested)
      .then((payload) => {
        if (!cancelled) {
          setLoadedPeaks({ assetId: requested, peaks: payload })
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadedPeaks((current) => (current?.assetId === requested ? null : current))
        }
      })
    return () => {
      cancelled = true
    }
  }, [detail, loadedPeaks, selected])

  async function reload() {
    const [project, assets, stored, document] = await Promise.all([
      api.project(projectId),
      api.assets(),
      api.reviews(projectId),
      api.comparison(projectId, xMode),
    ])
    setDetail(project)
    setLibrary(assets)
    setReviews(stored)
    setComparison(document)
  }

  async function prepare(plan: BatchPlan) {
    if (!detail || busy) {
      return
    }
    const memberIds = new Set(detail.assets.map((item) => item.id))
    const targets =
      plan === "missing" || plan === "retry-failed"
        ? detail.assets.filter((item) =>
            plan === "missing" ? item.analysis_status === "not_run" : item.analysis_status === "failed",
          )
        : library.filter((item) => picked.has(item.id) && !memberIds.has(item.id))
    setBusy(true)
    try {
      const result = await runAlbumBatch({
        projectId,
        targets,
        memberIds,
        plan,
        addMember: api.addMember,
        analyze: api.analyze,
        onStep: (index, total, name) => {
          setFeedback({ role: "status", text: `${index} of ${total}: ${name}` })
        },
      })
      await reload()
      setPicked((current) => {
        const failed = new Set(result.failed.map((item) => item.id))
        return new Set([...current].filter((id) => failed.has(id)))
      })
      setFeedback(batchMessage(result))
    } catch (error) {
      setFeedback({
        role: "alert",
        text: error instanceof Error ? error.message : "Could not prepare the album.",
      })
    } finally {
      setBusy(false)
    }
  }

  async function refreshStatus() {
    setBusy(true)
    try {
      await reload()
    } catch (error) {
      setFeedback({
        role: "alert",
        text: error instanceof Error ? error.message : "Could not refresh the album.",
      })
    } finally {
      setBusy(false)
    }
  }

  async function move(index: number, direction: -1 | 1) {
    if (!detail) {
      return
    }
    const ids = detail.assets.map((item) => item.id)
    const next = index + direction
    if (next < 0 || next >= ids.length) {
      return
    }
    const copy = [...ids]
    const [item] = copy.splice(index, 1)
    if (!item) {
      return
    }
    copy.splice(next, 0, item)
    setFeedback(null)
    try {
      await api.orderAlbum(projectId, copy)
      await reload()
    } catch (error) {
      setFeedback({
        role: "alert",
        text: error instanceof Error ? error.message : "Could not reorder the album.",
      })
    }
  }

  async function save(item: ReviewRecord, status: string, note = item.note) {
    setFeedback(null)
    try {
      const saved = await api.saveReview(projectId, {
        asset_id: item.asset_id,
        checkpoint_id: item.checkpoint_id,
        status,
        note,
      })
      setReviews((current) =>
        current.map((row) =>
          row.asset_id === saved.asset_id && row.checkpoint_id === saved.checkpoint_id ? saved : row,
        ),
      )
      setNotes((current) => {
        const next = { ...current }
        delete next[`${saved.asset_id}:${saved.checkpoint_id}`]
        return next
      })
    } catch (error) {
      setFeedback({
        role: "alert",
        text: error instanceof Error ? error.message : "Could not save the listening status.",
      })
    }
  }

  function audition(assetId: string) {
    if (pendingSeek.current?.assetId !== assetId) {
      pendingSeek.current = null
    }
    setSelected(assetId)
  }

  function listen(item: ReviewRecord) {
    if (!item.asset_id || item.time_s === null) {
      return
    }
    const request = { assetId: item.asset_id, time: item.time_s }
    pendingSeek.current = request
    setSelected(item.asset_id)
    if (item.asset_id === selected && seekRef.current(item.time_s) && pendingSeek.current === request) {
      pendingSeek.current = null
    }
  }

  async function download() {
    setFeedback(null)
    try {
      const manifest = await api.createAlbumExport(projectId)
      await api.downloadAlbumExport(projectId, manifest.export_id, `album-${manifest.export_id}.zip`)
    } catch (error) {
      setFeedback({
        role: "alert",
        text: error instanceof Error ? error.message : "The album export was not created.",
      })
    }
  }

  const tracks = comparison?.tracks ?? []
  const trackById = new Map(tracks.map((track) => [track.asset_id, track]))
  const selectedAsset = detail?.assets.find((item) => item.id === selected) ?? null
  const selectedIndex = detail?.assets.findIndex((item) => item.id === selected) ?? -1
  const selectedTrack = selected ? trackById.get(selected) : undefined
  const peaks = loadedPeaks?.assetId === selected ? loadedPeaks.peaks : null
  const chart = comparison?.panel ? asChart(comparison.panel) : null
  const chartMessage = overlayMessage(comparison, chart)
  const memberIds = new Set((detail?.assets ?? []).map((item) => item.id))
  const counts = analysisCounts(detail?.assets ?? [])
  const pairs = comparison?.pairs ?? []
  const shownPairs = filterPairs(tracks, pairs, pairChoice)
  const distances = comparison?.spectral_distances ?? []
  const shownDistances = filterPairs(tracks, distances, pairChoice)

  return (
    <section className="album">
      <h1 className="page-title">{detail?.name ?? "Album QC"}</h1>
      <section className="album-audition" aria-label="Audition">
        <h2>Audition</h2>
        <p>{selectedAsset ? selectedAsset.original_name : "Select a recording to audition it."}</p>
        {selectedAsset ? (
          <MemberTransport asset={selectedAsset} peaks={peaks} seekRef={seekRef} pendingSeek={pendingSeek} />
        ) : null}
      </section>
      <div className="album-tabs" role="tablist" aria-label="Album sections">
        {SECTIONS.map(([id, label]) => (
          <button
            key={id}
            type="button"
            className="ghost"
            role="tab"
            id={`album-tab-${id}`}
            aria-controls={`album-panel-${id}`}
            aria-selected={section === id}
            onClick={() => setSection(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {feedback && !pickerOpen ? (
        <p className={feedback.role === "alert" ? "feedback is-alert" : "feedback"} role={feedback.role}>
          {feedback.text}
        </p>
      ) : null}
      <div id="album-panel-overview" role="tabpanel" aria-labelledby="album-tab-overview" hidden={section !== "overview"}>
        <h2>Overview</h2>
        <p>Album order is a listening sequence. Measurements stay in the unit stored for each recording.</p>
        <div className="album-bar">
          <button type="button" className="action" onClick={() => setPickerOpen(true)}>
            Add recordings
          </button>
        </div>
        <section aria-label="Analysis">
          <h2>Preparation</h2>
          <p role="status">{analysisSummary(counts)}</p>
          <p>Completed analysis is stored m1-v3. Queued and running are submitted jobs, not finished measurements.</p>
          <div className="album-bar">
            <button
              type="button"
              className="action"
              onClick={() => void prepare("missing")}
              disabled={busy || counts.not_run === 0}
            >
              Analyze Missing
            </button>
            <button
              type="button"
              className="ghost"
              onClick={() => void prepare("retry-failed")}
              disabled={busy || counts.failed === 0}
            >
              Retry failed
            </button>
            <button type="button" className="ghost" onClick={() => void refreshStatus()} disabled={busy}>
              Refresh status
            </button>
          </div>
        </section>
        <div className="album-bar">
          <button type="button" className="ghost" onClick={() => void download()} disabled={comparison?.status !== "ready" || busy}>
            Download album report
          </button>
        </div>
      </div>
      <div id="album-panel-recordings" role="tabpanel" aria-labelledby="album-tab-recordings" hidden={section !== "recordings"}>
        <h2>Recordings</h2>
        <p>Select one recording. Order, inspection, and technical details stay with that recording.</p>
        <div className="log-scroll">
          <table className="log">
            <thead>
              <tr>
                <th scope="col">Order</th>
                <th scope="col">Recording</th>
                <th scope="col">Analysis</th>
                <th scope="col">Duration</th>
              </tr>
            </thead>
            <tbody>
              {(detail?.assets ?? []).map((asset, index) => (
                <tr key={asset.id}>
                  <td data-label="Order">{index + 1}</td>
                  <td className="name" data-label="Recording">
                    <button
                      type="button"
                      className="ghost"
                      aria-label={`Select ${asset.original_name}`}
                      aria-pressed={selected === asset.id}
                      onClick={() => audition(asset.id)}
                    >
                      {asset.original_name}
                    </button>
                  </td>
                  <td data-label="Analysis">{statusLabel(asset.analysis_status)}</td>
                  <td className="num" data-label="Duration">
                    {clock(asset.duration_s)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {selectedAsset ? (
          <div className="album-bar">
            <button type="button" className="ghost" onClick={() => void move(selectedIndex, -1)} disabled={selectedIndex <= 0}>
              Move earlier
            </button>
            <button
              type="button"
              className="ghost"
              onClick={() => void move(selectedIndex, 1)}
              disabled={selectedIndex < 0 || !detail || selectedIndex >= detail.assets.length - 1}
            >
              Move later
            </button>
            <button type="button" className="ghost" onClick={() => onInspect(selectedAsset.id)}>
              Inspect {selectedAsset.original_name}
            </button>
          </div>
        ) : null}
        {selectedAsset ? (
          <details>
            <summary>Technical details</summary>
            <p className="album-hash">SHA-256 {selectedAsset.sha256}</p>
            <p>
              Sample rate {selectedAsset.sample_rate} Hz. Channels {selectedAsset.channels}. Playback{" "}
              {statusLabel(selectedAsset.playback_status)}.
            </p>
            <p>
              {selectedTrack?.included
                ? `Analysis version ${selectedTrack.algorithm_version ?? "m1-v3"}.`
                : omitLabel(selectedTrack?.omit_reason)}
              {selectedTrack?.params_hash ? ` Parameter hash ${selectedTrack.params_hash}.` : ""}
            </p>
          </details>
        ) : null}
      </div>
      <div
        id="album-panel-comparisons"
        role="tabpanel"
        aria-labelledby="album-tab-comparisons"
        hidden={section !== "comparisons"}
      >
        <h2>Comparisons</h2>
        <p>A difference is the later recording minus the earlier one. Levels keep their absolute units.</p>
        {LEVEL_UNITS.map((unit) => (
          <LevelTable key={unit} unit={unit} tracks={tracks} />
        ))}
        <section aria-label="Stereo">
          <h2>Stereo</h2>
          <ScalarTable tracks={tracks} names={["correlation", "side_mid", "mono_fold_down", "sub_bass_correlation"]} />
        </section>
        <section aria-label="Bands">
          <h2>Bands</h2>
          <p>Below 20 Hz stays separate from the band-share distance.</p>
          {tracks
            .filter((track) => track.included)
            .map((track) => (
              <div key={track.asset_id}>
                <h3>{recordingLabel(tracks, track.asset_id)}</h3>
                <p>Below 20 Hz {track.below_20_hz === null ? "not stored" : `${track.below_20_hz.toFixed(1)} %`}</p>
                <div className="log-scroll">
                  <table className="log">
                    <thead>
                      <tr>
                        <th scope="col">Band</th>
                        <th scope="col">Share</th>
                      </tr>
                    </thead>
                    <tbody>
                      {track.bands.map((band) => (
                        <tr key={`${track.asset_id}-${band.label}`}>
                          <td data-label="Band">{band.label}</td>
                          <td data-label="Share">{band.value === null ? "Not stored" : `${band.value.toFixed(1)} %`}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
        </section>
        <section aria-label="Pair differences">
          <h2>Pair differences</h2>
          <p>
            Showing {shownPairs.length} of {pairs.length} stored pairs. Adjacent means the next recording in album order.
          </p>
          <label className="album-pairs">
            Pairs
            <select value={pairChoice} onChange={(event) => setPairChoice(event.target.value)}>
              <option value="adjacent">Adjacent recordings</option>
              <option value="all">All pairs</option>
              {pairs.map((pair) => (
                <option key={pairKey(pair)} value={pairKey(pair)}>
                  {recordingLabel(tracks, pair.left_asset_id)} to {recordingLabel(tracks, pair.right_asset_id)}
                </option>
              ))}
            </select>
          </label>
          {pairs.length > 0 && shownPairs.length === 0 ? (
            <p>No adjacent recordings are both included. Choose another pair or all pairs.</p>
          ) : (
            <PairTable label="Shown pair differences" pairs={shownPairs} tracks={tracks} />
          )}
          <details>
            <summary>All stored differences</summary>
            <PairTable label="All stored pair differences" pairs={pairs} tracks={tracks} />
            <h3>Spectral distances</h3>
            <DistanceTable rows={distances} tracks={tracks} />
          </details>
        </section>
        <section aria-label="Spectrum">
          <h2>Spectrum</h2>
          <p>Band-share distance is not timbral similarity. The Welch PSD line is not overlaid.</p>
          <DistanceTable rows={shownDistances} tracks={tracks} />
        </section>
        <section aria-label="Comparison">
          <h2>Level overlay</h2>
          <p>The overlay does not audition a recording. Progress changes only the time axis.</p>
          <div className="album-bar">
            <button type="button" aria-pressed={xMode === "seconds"} onClick={() => setXMode("seconds")}>
              Seconds
            </button>
            <button type="button" aria-pressed={xMode === "progress"} onClick={() => setXMode("progress")}>
              Progress
            </button>
          </div>
          {chart?.status === "ready" && chart ? <ChartView chart={chart} onSeek={() => undefined} /> : null}
          {chartMessage ? <p>{chartMessage}</p> : null}
        </section>
        <details>
          <summary>Caveats and methods</summary>
          <ul>
            {(comparison?.caveats ?? []).map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <p>
            Comparison version {comparison?.comparison_version ?? "album-qc-v1"}.
            {chart ? ` Chart method ${chart.method_id} ${chart.method_version}. Evidence ${evidenceLabel(chart.evidence_class)}.` : ""}
          </p>
        </details>
      </div>
      <div id="album-panel-evidence" role="tabpanel" aria-labelledby="album-tab-evidence" hidden={section !== "evidence"}>
        <h2>Endings and rhythm</h2>
        <p>4× reconstructed peak is not the FFmpeg true peak. These facts are not listening statuses.</p>
        {tracks.map((track) => (
          <EndingCard key={track.asset_id} track={track} tracks={tracks} />
        ))}
        <h2>Rhythm</h2>
        <p>
          Pulse candidates are provisional onset-autocorrelation estimates, not a beat grid. A score is normalized
          autocorrelation, not a probability or a confirmed tempo.
        </p>
        {tracks.map((track) => (
          <RhythmCard key={track.asset_id} track={track} tracks={tracks} />
        ))}
      </div>
      <div id="album-panel-listening" role="tabpanel" aria-labelledby="album-tab-listening" hidden={section !== "listening"}>
        <h2>Listening review</h2>
        <p>A measurement anomaly is not proof of an audible defect. A checkpoint status is a human attribution.</p>
        <ul>
          {reviews.map((item) => {
            const title = item.asset_id ? recordingLabel(tracks, item.asset_id) : "Album"
            const noteKey = `${item.asset_id}:${item.checkpoint_id}`
            const checkpoint = checkpointLabel(item.checkpoint_id)
            return (
              <li key={noteKey}>
                <p>
                  {title}. {reviewLabel(item.status)}.
                </p>
                <p>
                  {checkpoint}. <span>{item.fact}</span>
                </p>
                <div className="album-bar">
                  {REVIEW_STATUSES.map((status) => (
                    <button
                      key={status}
                      type="button"
                      className="ghost"
                      onClick={() => void save(item, status, notes[noteKey] ?? item.note)}
                    >
                      {reviewLabel(status)}
                    </button>
                  ))}
                  {item.time_s !== null && item.asset_id ? (
                    <button type="button" className="ghost" onClick={() => listen(item)}>
                      Play checkpoint
                    </button>
                  ) : null}
                </div>
                <label>
                  Note for {title}, {checkpoint}
                  <input
                    value={notes[noteKey] ?? item.note}
                    maxLength={500}
                    onChange={(event) => setNotes((current) => ({ ...current, [noteKey]: event.target.value }))}
                    onBlur={(event) => {
                      const note = event.currentTarget.value
                      if (note !== item.note) {
                        void save(item, item.status, note)
                      }
                    }}
                  />
                </label>
              </li>
            )
          })}
        </ul>
      </div>
      {pickerOpen ? (
        <AddRecordingsDialog
          library={library}
          memberIds={memberIds}
          studies={studies}
          studyMembers={studyMembers}
          picked={picked}
          onPickedChange={setPicked}
          busy={busy}
          feedback={feedback}
          onAdd={() => void prepare("add")}
          onQueue={() => void prepare("add-and-queue")}
          onClose={() => setPickerOpen(false)}
        />
      ) : null}
    </section>
  )
}

function LevelTable({ unit, tracks }: { unit: (typeof LEVEL_UNITS)[number]; tracks: TrackRecord[] }) {
  const rows = tracks.flatMap((track) =>
    track.scalars
      .filter((item) => item.unit === unit)
      .map((item) => ({ track, item })),
  )
  if (rows.length === 0) {
    return null
  }
  return (
    <section aria-label={unit}>
      <h2>{unit}</h2>
      <div className="log-scroll">
        <table className="log">
          <thead>
            <tr>
              <th scope="col">Recording</th>
              <th scope="col">Measurement</th>
              <th scope="col">Value</th>
              <th scope="col">Evidence</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ track, item }) => (
              <tr key={`${track.asset_id}-${item.name}`}>
                <td data-label="Recording">{recordingLabel(tracks, track.asset_id)}</td>
                <td data-label="Measurement">{measurementLabel(item.name)}</td>
                <td className="num" data-label="Value">
                  {scalarText(item)}
                </td>
                <td data-label="Evidence">{evidenceLabel(item.evidence_class)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}

function ScalarTable({ tracks, names }: { tracks: TrackRecord[]; names: string[] }) {
  return (
    <div className="log-scroll">
      <table className="log">
        <thead>
          <tr>
            <th scope="col">Recording</th>
            <th scope="col">Measurement</th>
            <th scope="col">Value</th>
            <th scope="col">Evidence</th>
          </tr>
        </thead>
        <tbody>
          {tracks.flatMap((track) =>
            track.scalars
              .filter((item) => names.includes(item.name))
              .map((item) => (
                <tr key={`${track.asset_id}-${item.name}`}>
                  <td data-label="Recording">{recordingLabel(tracks, track.asset_id)}</td>
                  <td data-label="Measurement">{measurementLabel(item.name)}</td>
                  <td data-label="Value">{scalarText(item)}</td>
                  <td data-label="Evidence">{evidenceLabel(item.evidence_class)}</td>
                </tr>
              )),
          )}
        </tbody>
      </table>
    </div>
  )
}

function PairTable({ label, pairs, tracks }: { label: string; pairs: PairRecord[]; tracks: TrackRecord[] }) {
  const rows = pairs.flatMap((pair) => pair.deltas.map((item) => ({ pair, item })))
  if (rows.length === 0) {
    return <p>No stored pair comparison.</p>
  }
  return (
    <div className="log-scroll">
      <table className="log" aria-label={label}>
        <thead>
          <tr>
            <th scope="col">Earlier</th>
            <th scope="col">Later</th>
            <th scope="col">Measurement</th>
            <th scope="col">Later minus earlier</th>
            <th scope="col">Unit</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(({ pair, item }) => {
            const unit = differenceUnit(item.unit)
            return (
              <tr key={`${pair.left_asset_id}-${pair.right_asset_id}-${item.name}`}>
                <td data-label="Earlier">{recordingLabel(tracks, pair.left_asset_id)}</td>
                <td data-label="Later">{recordingLabel(tracks, pair.right_asset_id)}</td>
                <td data-label="Measurement">{measurementLabel(item.name)}</td>
                <td className="num" data-label="Later minus earlier">
                  {item.delta === null ? evidenceReason(item.reason) : formatNumber(item.delta, unit)}
                </td>
                <td data-label="Unit">{unit}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function DistanceTable({
  rows,
  tracks,
}: {
  rows: ComparisonDocument["spectral_distances"]
  tracks: TrackRecord[]
}) {
  return (
    <div className="log-scroll">
      <table className="log">
        <thead>
          <tr>
            <th scope="col">Earlier</th>
            <th scope="col">Later</th>
            <th scope="col">Distance</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={`${row.left_asset_id}-${row.right_asset_id}`}>
              <td data-label="Earlier">{recordingLabel(tracks, row.left_asset_id)}</td>
              <td data-label="Later">{recordingLabel(tracks, row.right_asset_id)}</td>
              <td data-label="Distance">
                {row.value === null ? evidenceReason(row.reason) : formatMeasure(row.value, row.unit)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function EndingCard({ track, tracks }: { track: TrackRecord; tracks: TrackRecord[] }) {
  const truePeak = track.scalars.find((item) => item.name === "ffmpeg_true_peak")
  return (
    <article>
      <h3>{recordingLabel(tracks, track.asset_id)}</h3>
      {track.included ? (
        <>
          <p>
            Endpoint {track.endings.endpoint ?? "not stored"}. Full-scale samples {formatCount(track.endings.rail_count)}.
            Sub-threshold intervals {track.endings.silence.length}.
          </p>
          <p>
            FFmpeg true peak {truePeak ? scalarText(truePeak) : "not stored"}. 4× reconstructed peak{" "}
            {track.endings.reconstructed_peak === null
              ? "not stored"
              : formatMeasure(track.endings.reconstructed_peak, "dBTP")}
            . The reconstructed peak is not the FFmpeg true peak.
          </p>
          <details>
            <summary>Ending measurements for {track.original_name}</summary>
            <ul>
              {track.endings.tails.map((tail) => (
                <li key={tail.label}>
                  {tail.label} {tail.value === null ? "not stored" : formatMeasure(tail.value, "dBFS")}
                </li>
              ))}
              {track.endings.silence.map((interval) => (
                <li key={`${interval.start_s}-${interval.end_s}`}>
                  Sub-threshold {formatMeasure(interval.start_s, "s")} to {formatMeasure(interval.end_s, "s")}
                </li>
              ))}
              <li>
                Reconstructed peak time{" "}
                {track.endings.reconstructed_peak_time_s === null
                  ? "not stored"
                  : formatMeasure(track.endings.reconstructed_peak_time_s, "s")}
                . Stored full-scale sample count{" "}
                {track.endings.rail_count === null ? "not stored" : storedNumber(track.endings.rail_count)}.
              </li>
            </ul>
            {track.caveats.length > 0 ? (
              <ul>
                {track.caveats.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            ) : null}
          </details>
        </>
      ) : (
        <p>{omitLabel(track.omit_reason)}. No ending measurement is stored.</p>
      )}
    </article>
  )
}

function RhythmCard({ track, tracks }: { track: TrackRecord; tracks: TrackRecord[] }) {
  const top = track.pulse[0]
  return (
    <article>
      <h3>{recordingLabel(tracks, track.asset_id)}</h3>
      {!track.included ? (
        <p>{omitLabel(track.omit_reason)}. No rhythm candidate is stored.</p>
      ) : top ? (
        <p>
          Strongest candidate {top.label}, autocorrelation {top.value === null ? "not stored" : formatScore(top.value)}.{" "}
          {evidenceLabel(top.evidence_class)}. This score is not a probability or a confirmed tempo.
        </p>
      ) : (
        <p>No candidate stored. This is not a confirmed tempo.</p>
      )}
      {track.included ? (
        <details>
          <summary>Rhythm candidates for {track.original_name}</summary>
          {track.pulse.length === 0 ? (
            <p>No candidate stored.</p>
          ) : (
            <table className="log">
              <thead>
                <tr>
                  <th scope="col">Candidate</th>
                  <th scope="col">Autocorrelation</th>
                  <th scope="col">Stored value</th>
                  <th scope="col">Evidence</th>
                </tr>
              </thead>
              <tbody>
                {track.pulse.map((item) => (
                  <tr key={item.label}>
                    <td data-label="Candidate">{item.label}</td>
                    <td data-label="Autocorrelation">{item.value === null ? "Not stored" : formatScore(item.value)}</td>
                    <td data-label="Stored value">{item.value === null ? "Not stored" : storedNumber(item.value)}</td>
                    <td data-label="Evidence">{evidenceLabel(item.evidence_class)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </details>
      ) : null}
    </article>
  )
}

function MemberTransport({
  asset,
  peaks,
  seekRef,
  pendingSeek,
}: {
  asset: Asset
  peaks: Peaks | null
  seekRef: { current: (seconds: number) => boolean }
  pendingSeek: { current: { assetId: string; time: number } | null }
}) {
  const host = useRef<HTMLDivElement>(null)
  const player = useRef<WaveSurfer | null>(null)
  const [playing, setPlaying] = useState(false)

  useEffect(() => {
    const container = host.current
    if (!container || !peaks) {
      return
    }
    let disposed = false
    let ready = false
    const wave = WaveSurfer.create({
      container,
      url: streamUrl(asset.id),
      peaks: toWavePeaks(peaks.buckets),
      duration: peaks.duration_s,
      height: 72,
      waveColor: "#8b95a3",
      progressColor: "#c4a36a",
      cursorColor: "#e8e6e1",
      cursorWidth: 1,
      barWidth: 2,
      barGap: 1,
      interact: true,
      dragToSeek: true,
      normalize: false,
    })
    player.current = wave
    const seek = (seconds: number) => {
      if (disposed || !ready || peaks.duration_s <= 0) {
        return false
      }
      wave.setTime(Math.min(Math.max(seconds, 0), peaks.duration_s))
      return true
    }
    seekRef.current = seek
    const applyPending = () => {
      const pending = pendingSeek.current
      if (disposed || !pending || pending.assetId !== asset.id) {
        return
      }
      if (seek(pending.time) && pendingSeek.current === pending) {
        pendingSeek.current = null
      }
    }
    const unsubscribers = [
      wave.on("ready", () => {
        if (disposed) {
          return
        }
        ready = true
        applyPending()
      }),
      wave.on("play", () => setPlaying(true)),
      wave.on("pause", () => setPlaying(false)),
      wave.on("finish", () => setPlaying(false)),
    ]
    return () => {
      disposed = true
      ready = false
      seekRef.current = () => false
      unsubscribers.forEach((unsubscribe) => unsubscribe())
      wave.destroy()
      player.current = null
    }
  }, [asset.id, peaks, pendingSeek, seekRef])

  if (asset.playback_status !== "ready" || !peaks) {
    return <p className="quiet">{playbackCaption(asset)}</p>
  }
  return (
    <div>
      <div ref={host} className="wave" />
      <button type="button" className="action" onClick={() => void player.current?.playPause()}>
        {playing ? "Pause" : "Play"}
      </button>
    </div>
  )
}
