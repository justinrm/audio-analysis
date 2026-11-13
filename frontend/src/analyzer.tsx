import { Pause, Play } from "lucide-react"
import { useCallback, useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react"
import WaveSurfer from "wavesurfer.js"
import RegionsPlugin from "wavesurfer.js/dist/plugins/regions.esm.js"
import { api, streamUrl } from "./api/client"
import type { Asset, ChartDocument, ChartSummary, ExportCreate, Job, LyricDocumentOut, Peaks } from "./api/types"
import { ChartView } from "./chart"
import { ChartDataTable } from "./chart-data-table"
import {
  clock,
  evidenceLabel,
  formatLabel,
  inspectorFitsBeside,
  playbackCaption,
  statusLabel,
  TECHNICAL,
  toWavePeaks,
} from "./catalog"
import {
  cueColor,
  cueKey,
  LyricsWorkspace,
  regionLabel,
  syncLyricRegions,
  type LyricBridge,
  type LyricCue,
  type LyricRegionPlugin,
} from "./lyrics"

const STUDY_TABS = ["technical", "lyrics"] as const
type StudyTab = (typeof STUDY_TABS)[number]

export function TechnicalBoard({
  charts,
  chartId,
  document,
  onSelect,
  onSeek,
  playhead = null,
  assetId,
  lyricsPanel = null,
}: {
  charts: ChartSummary[]
  chartId: string
  document: ChartDocument | null
  onSelect: (chartId: string) => void
  onSeek: (seconds: number) => void
  playhead?: number | null
  assetId?: string
  lyricsPanel?: ReactNode
}) {
  const [tab, setTab] = useState<StudyTab>("technical")
  const [focusedTab, setFocusedTab] = useState<StudyTab>("technical")
  const [holdLyrics, setHoldLyrics] = useState(false)
  const [evidenceOpen, setEvidenceOpen] = useState(false)
  const [stageWidth, setStageWidth] = useState(0)
  const evidenceChosen = useRef(false)
  const frameRef = useRef<HTMLDivElement>(null)
  const evidenceTrigger = useRef<HTMLButtonElement>(null)
  const evidenceHeading = useRef<HTMLHeadingElement>(null)
  const rows = TECHNICAL.map((item) => {
    const live = charts.find((chart) => chart.chart_kind === item.id)
    return {
      id: item.id,
      title: live?.title || item.title,
      short: item.short,
      status: live?.status ?? "not_run",
    }
  })
  const selected = rows.find((row) => row.id === chartId) ?? rows[0]
  const active = document?.chart_kind === selected.id ? document : null

  useEffect(() => {
    setTab("technical")
    setFocusedTab("technical")
    setHoldLyrics(false)
    evidenceChosen.current = false
    setEvidenceOpen(false)
  }, [assetId])

  useEffect(() => {
    const node = frameRef.current
    if (!node || typeof ResizeObserver === "undefined") {
      return
    }
    const measure = () => setStageWidth(node.clientWidth)
    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(node)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (evidenceChosen.current || stageWidth <= 0) {
      return
    }
    setEvidenceOpen(inspectorFitsBeside(stageWidth))
  }, [assetId, stageWidth])

  function setEvidence(next: boolean) {
    evidenceChosen.current = true
    setEvidenceOpen(next)
    const beside = inspectorFitsBeside(stageWidth)
    window.setTimeout(() => {
      if (next && !beside) {
        evidenceHeading.current?.focus()
        return
      }
      if (!next) {
        evidenceTrigger.current?.focus()
      }
    }, 0)
  }

  const loadingChart = selected.status !== "not_run" && !active
  const evidenceBeside = evidenceOpen && inspectorFitsBeside(stageWidth)
  const workspaceClass = tab === "technical"
    ? `workspace technical${evidenceBeside ? " is-evidence-side" : ""}`
    : "workspace lyrics"

  function activateTab(next: StudyTab) {
    if (next === "lyrics") {
      setHoldLyrics(true)
    }
    setFocusedTab(next)
    setTab(next)
  }

  function onTabKey(event: KeyboardEvent<HTMLDivElement>) {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey) {
      return
    }
    const host =
      event.currentTarget instanceof HTMLElement && event.currentTarget.getAttribute("role") === "tablist"
        ? event.currentTarget
        : event.target instanceof Element
          ? event.target.closest<HTMLElement>("[role='tablist']")
          : null
    if (!host) {
      return
    }
    const buttons = STUDY_TABS.flatMap((id) => {
      const button = host.querySelector<HTMLButtonElement>(`#study-tab-${id}`)
      return button ? [button] : []
    })
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      const active = host.ownerDocument.activeElement
      const current = buttons.findIndex((button) => button === active)
      if (current < 0) {
        return
      }
      event.preventDefault()
      const delta = event.key === "ArrowRight" ? 1 : -1
      const nextIndex = (current + delta + buttons.length) % buttons.length
      const next = buttons[nextIndex]
      if (!next) {
        return
      }
      next.tabIndex = 0
      setFocusedTab(STUDY_TABS[nextIndex])
      next.focus()
      if (buttons[current] !== next) {
        buttons[current].tabIndex = -1
      }
      return
    }
    if (event.key !== "Enter" && event.key !== " ") {
      return
    }
    const target = event.target
    if (!(target instanceof HTMLButtonElement)) {
      return
    }
    const index = buttons.indexOf(target)
    if (index < 0) {
      return
    }
    event.preventDefault()
    activateTab(STUDY_TABS[index])
  }

  return (
    <section className="study-frame">
      <div className="tabs" role="tablist" aria-label="Study" onKeyDown={onTabKey}>
        <button
          type="button"
          role="tab"
          id="study-tab-technical"
          aria-selected={tab === "technical"}
          aria-controls="study-technical"
          tabIndex={focusedTab === "technical" ? 0 : -1}
          onFocus={() => setFocusedTab("technical")}
          onClick={() => activateTab("technical")}
        >
          Technical Analysis
        </button>
        <button
          type="button"
          role="tab"
          id="study-tab-lyrics"
          aria-selected={tab === "lyrics"}
          aria-controls="study-lyrics"
          tabIndex={focusedTab === "lyrics" ? 0 : -1}
          onFocus={() => setFocusedTab("lyrics")}
          onClick={() => activateTab("lyrics")}
        >
          Lyrics & Inspiration
        </button>
      </div>
      <div className="study">
        <div
          ref={frameRef}
          className={workspaceClass}
          data-evidence-placement={evidenceOpen ? (evidenceBeside ? "side" : "below") : "closed"}
        >
          <div
            className="technical-panel"
            role="tabpanel"
            id="study-technical"
            aria-labelledby="study-tab-technical"
            hidden={tab !== "technical"}
            inert={tab !== "technical"}
          >
            {tab === "technical" ? (
            <>
              <div className="chart-toolbar">
                <label className="chart-picker">
                  Chart
                  <select aria-label="Chart" value={selected.id} onChange={(event) => onSelect(event.target.value)}>
                    {rows.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.id} {item.title} ({statusLabel(item.status)})
                      </option>
                    ))}
                  </select>
                </label>
                <button
                  type="button"
                  className="quiet-control"
                  ref={evidenceTrigger}
                  aria-expanded={evidenceOpen}
                  aria-controls="chart-evidence"
                  onClick={() => setEvidence(!evidenceOpen)}
                >
                  Evidence
                </button>
              </div>
              <div className="plot">
                <h2>
                  {selected.id} {selected.title}
                  {active && active.status !== "not_run" ? (
                    <span className="evidence-word"> {evidenceLabel(active.evidence_class)}</span>
                  ) : null}
                </h2>
                <p className="quiet plot-status">Status: {statusLabel(active?.status ?? selected.status)}</p>
                {active?.status === "ready" ? <ChartView chart={active} onSeek={onSeek} playhead={playhead} /> : null}
                {active && active.status !== "ready" ? <ChartDataTable chart={active} /> : null}
                {active && active.status !== "ready" && active.status !== "not_run" ? (
                  <p className="feedback is-alert" role="alert">
                    {active.not_available_reason || active.error}
                  </p>
                ) : null}
                {(active?.status ?? selected.status) === "not_run" ? (
                  <p>Not run. Nothing has been measured for this recording.</p>
                ) : null}
                {loadingChart ? (
                  <p className="feedback" role="status">
                    Loading this chart.
                  </p>
                ) : null}
              </div>
              <aside className="inspector" id="chart-evidence" hidden={!evidenceOpen}>
                <div className="inspector-bar">
                  <h2 id="chart-evidence-heading" tabIndex={-1} ref={evidenceHeading}>
                    Evidence
                  </h2>
                  <button type="button" className="quiet-control" onClick={() => setEvidence(false)}>
                    Close evidence
                  </button>
                </div>
                {loadingChart ? <p className="quiet">Evidence for this chart is still loading.</p> : null}
                {!loadingChart && active && active.status !== "not_run" ? (
                  <>
                    <h3>Identity</h3>
                    <dl className="evidence">
                      <div>
                        <dt>Class</dt>
                        <dd>{evidenceLabel(active.evidence_class)}</dd>
                      </div>
                      <div>
                        <dt>Method</dt>
                        <dd>{active.method_id}</dd>
                      </div>
                      <div>
                        <dt>Version</dt>
                        <dd>{active.method_version}</dd>
                      </div>
                    </dl>
                    <h3>Figures</h3>
                    <dl className="evidence">
                      {active.summary.map((item) => (
                        <div key={item.label}>
                          <dt>{item.label}</dt>
                          <dd className="num">{item.value}</dd>
                        </div>
                      ))}
                    </dl>
                    <h3>Limitations</h3>
                    {active.caveats.length > 0 ? (
                      <dl className="evidence">
                        {active.caveats.map((item) => (
                          <div key={item}>
                            <dt>Limitation</dt>
                            <dd>{item}</dd>
                          </div>
                        ))}
                      </dl>
                    ) : (
                      <p className="quiet">None recorded.</p>
                    )}
                  </>
                ) : null}
                {!loadingChart && (!active || active.status === "not_run") ? <p>No evidence yet.</p> : null}
              </aside>
            </>
            ) : null}
          </div>
          {holdLyrics && lyricsPanel ? (
            <div
              className="lyric-mount"
              role="tabpanel"
              id="study-lyrics"
              aria-labelledby="study-tab-lyrics"
              hidden={tab !== "lyrics"}
              inert={tab !== "lyrics"}
            >
              {lyricsPanel}
            </div>
          ) : tab === "lyrics" && !lyricsPanel ? (
            <div role="tabpanel" id="study-lyrics" aria-labelledby="study-tab-lyrics" className="lyric-empty">
              <div className="line-list">
                <p>Text</p>
                <p className="quiet">No lyric file is attached.</p>
              </div>
              <div className="editor">
                <h2>Lyrics & Inspiration</h2>
                <p>Open a recording to attach lyrics. Sung timing is not guessed.</p>
              </div>
              <aside className="inspector">
                <h2>Evidence</h2>
                <p>No evidence yet.</p>
              </aside>
            </div>
          ) : (
            <div role="tabpanel" id="study-lyrics" aria-labelledby="study-tab-lyrics" hidden inert />
          )}
        </div>
      </div>
    </section>
  )
}

function waveHeight(): number {
  const desktop = 52
  const phone = 36
  if (typeof window.matchMedia !== "function") {
    return desktop
  }
  return window.matchMedia("(max-width: 927px)").matches ? phone : desktop
}

function Ruler({ duration }: { duration: number }) {
  return (
    <div className="ruler" aria-hidden="true">
      {[0, 0.25, 0.5, 0.75, 1].map((mark) => (
        <span key={mark}>{clock(duration * mark)}</span>
      ))}
    </div>
  )
}

function Transport({
  asset,
  peaks,
  seekRef,
  onTime,
  cues,
  activeCueId,
  focusCueId,
  regionNonce,
  lyricBridge,
  waveformOpen,
  onWaveform,
}: {
  asset: Asset
  peaks: Peaks
  seekRef: { current: (seconds: number) => void }
  onTime: (seconds: number) => void
  cues: LyricCue[]
  activeCueId: string | null
  focusCueId: string | null
  regionNonce: number
  lyricBridge: { current: LyricBridge }
  waveformOpen: boolean
  onWaveform: (open: boolean) => void
}) {
  const host = useRef<HTMLDivElement>(null)
  const player = useRef<WaveSurfer | null>(null)
  const regionsRef = useRef<LyricRegionPlugin | null>(null)
  const [time, setTime] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState("")
  const [regionsReady, setRegionsReady] = useState(0)
  const duration = peaks.duration_s
  const volumeRef = useRef<HTMLDetailsElement>(null)
  const waveformSeen = useRef(false)

  useEffect(() => {
    const container = host.current
    if (!container) {
      return
    }
    const wave = WaveSurfer.create({
      container,
      url: streamUrl(asset.id),
      peaks: toWavePeaks(peaks.buckets),
      duration,
      height: waveHeight(),
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
    const narrow = typeof window.matchMedia === "function" ? window.matchMedia("(max-width: 927px)") : null
    const fit = () => {
      if (typeof wave.setOptions === "function") {
        wave.setOptions({ height: waveHeight() })
      }
      if (volumeRef.current) {
        volumeRef.current.open = !narrow?.matches
      }
    }
    fit()
    narrow?.addEventListener("change", fit)
    player.current = wave
    regionsRef.current = wave.registerPlugin(RegionsPlugin.create()) as unknown as LyricRegionPlugin
    setRegionsReady((count) => count + 1)
    seekRef.current = (seconds: number) => {
      if (duration <= 0) {
        return
      }
      wave.setTime(Math.min(Math.max(seconds, 0), duration))
    }
    const unsubscribers = [
      wave.on("timeupdate", (value) => {
        setTime(value)
        onTime(value)
      }),
      wave.on("play", () => setPlaying(true)),
      wave.on("pause", () => setPlaying(false)),
      wave.on("finish", () => setPlaying(false)),
      wave.on("error", (err) => setError(err instanceof Error ? err.message : "Playback failed.")),
    ]
    return () => {
      seekRef.current = () => undefined
      narrow?.removeEventListener("change", fit)
      unsubscribers.forEach((unsubscribe) => unsubscribe())
      regionsRef.current = null
      wave.destroy()
      player.current = null
    }
  }, [asset.id, duration, peaks.buckets, seekRef, onTime])

  useEffect(() => {
    if (!waveformSeen.current) {
      waveformSeen.current = true
      return
    }
    if (!waveformOpen) {
      return
    }
    const wave = player.current
    if (wave && typeof wave.setOptions === "function") {
      wave.setOptions({ height: waveHeight() })
    }
    const box = host.current
    const frame = requestAnimationFrame(() => {
      if (box && box.clientWidth === 0) {
        return
      }
      player.current?.setOptions?.({ height: waveHeight() })
    })
    return () => cancelAnimationFrame(frame)
  }, [waveformOpen])

  useEffect(() => {
    const plugin = regionsRef.current
    if (!plugin || regionsReady === 0) {
      return
    }
    return syncLyricRegions(
      plugin,
      cues,
      (id, start, end) => lyricBridge.current.commit(id, start, end),
      (id) => lyricBridge.current.pick(id),
    )
  }, [cues, lyricBridge, regionNonce, regionsReady])

  useEffect(() => {
    const plugin = regionsRef.current
    if (!plugin || regionsReady === 0) {
      return
    }
    for (const region of plugin.getRegions()) {
      const cue = cues.find((item) => item.id === region.id)
      if (!cue) {
        continue
      }
      region.setOptions({
        color: cueColor(cue.origin, cue.id === activeCueId),
        content: regionLabel(cue, activeCueId, focusCueId),
      })
    }
  }, [activeCueId, cues, focusCueId, regionsReady])

  return (
    <div className="recording-transport">
      <div className="transport">
        <button
          type="button"
          className="action inline-flex items-center gap-2"
          onClick={() => {
            void player.current?.playPause()
          }}
        >
          {playing ? <Pause size={16} aria-hidden="true" /> : <Play size={16} aria-hidden="true" />}
          {playing ? "Pause" : "Play"}
        </button>
        <span className="num">
          {clock(time, true)} / {clock(duration, true)}
        </span>
        <label className="transport-seek">
          Seek
          <input
            type="range"
            min={0}
            max={duration || 0}
            step={0.01}
            value={Math.min(time, duration || 0)}
            aria-label="Seek"
            onChange={(event) => player.current?.setTime(Number(event.target.value))}
          />
        </label>
        <div className="transport-tools">
          <details className="transport-volume" ref={volumeRef}>
            <summary>Volume</summary>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              defaultValue={1}
              aria-label="Volume"
              onChange={(event) => player.current?.setVolume(Number(event.target.value))}
            />
          </details>
          <button
            type="button"
            className="quiet-control"
            aria-expanded={waveformOpen}
            aria-controls="recording-waveform"
            onClick={() => onWaveform(!waveformOpen)}
          >
            Waveform
          </button>
        </div>
      </div>
      <div id="recording-waveform" hidden={!waveformOpen}>
        <div ref={host} className="wave" />
        <Ruler duration={duration} />
        <p className="quiet deck-caption">{playbackCaption(asset)}</p>
      </div>
      {error ? (
        <p className="feedback is-alert" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  )
}

function exportName(profile: ExportCreate["profile"]): string {
  switch (profile) {
    case "technical":
      return "Technical"
    case "lyricist":
      return "Lyricist"
    case "combined":
      return "Combined"
    default: {
      const unexpected: never = profile
      return unexpected
    }
  }
}

export function Analyzer({ assetId, projectId = null }: { assetId: string; projectId?: string | null }) {
  const [asset, setAsset] = useState<Asset | null>(null)
  const [peaks, setPeaks] = useState<Peaks | null>(null)
  const [charts, setCharts] = useState<ChartSummary[]>([])
  const [chartId, setChartId] = useState(TECHNICAL[0].id)
  const [document, setDocument] = useState<ChartDocument | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [loadError, setLoadError] = useState("")
  const [notice, setNotice] = useState("")
  const seekRef = useRef<(seconds: number) => void>(() => undefined)
  const onSeek = useCallback((seconds: number) => seekRef.current(seconds), [])
  const [playhead, setPlayhead] = useState<number | null>(null)
  const onTime = useCallback((seconds: number) => setPlayhead(seconds), [])
  const [cues, setCues] = useState<LyricCue[]>([])
  const [activeCueId, setActiveCueId] = useState<string | null>(null)
  const [focusCueId, setFocusCueId] = useState<string | null>(null)
  const [regionNonce, setRegionNonce] = useState(0)
  const lyricBridge = useRef<LyricBridge>({
    commit() {},
    pick() {},
  })
  const lyricEpoch = useRef(0)
  const [lyricDocument, setLyricDocument] = useState<LyricDocumentOut | null>(null)
  const [lyricMode, setLyricMode] = useState<"summarized" | "included" | "omitted">("summarized")
  const [exportState, setExportState] = useState<
    | { kind: "idle" }
    | { kind: "loading"; profile: ExportCreate["profile"] }
    | { kind: "done"; profile: ExportCreate["profile"] }
    | { kind: "error"; message: string }
  >({ kind: "idle" })
  const [waveformOpen, setWaveformOpen] = useState(false)
  const [detailsOpen, setDetailsOpen] = useState(false)
  const [exportsOpen, setExportsOpen] = useState(false)
  const [studyName, setStudyName] = useState<string | null>(null)
  const onCues = useCallback((next: LyricCue[]) => {
    setCues((prev) => (cueKey(prev) === cueKey(next) ? prev : next))
  }, [])
  const onActive = useCallback((id: string | null) => {
    setActiveCueId((prev) => (prev === id ? prev : id))
  }, [])

  useEffect(() => {
    let cancelled = false
    setAsset(null)
    setPeaks(null)
    setCharts([])
    setDocument(null)
    setJob(null)
    setChartId(TECHNICAL[0].id)
    setLoadError("")
    setNotice("")
    setPlayhead(null)
    setCues([])
    setActiveCueId(null)
    setLyricDocument(null)
    setExportState({ kind: "idle" })
    setWaveformOpen(false)
    setDetailsOpen(false)
    setExportsOpen(false)
    setStudyName(null)
    api
      .asset(assetId)
      .then(async (next) => {
        if (cancelled) {
          return
        }
        setAsset(next)
        if (next.playback_status !== "ready") {
          return
        }
        try {
          const envelope = await api.peaks(assetId)
          if (!cancelled) {
            setPeaks(envelope)
          }
        } catch (error) {
          if (!cancelled) {
            setLoadError(error instanceof Error ? error.message : "Peaks are unavailable.")
          }
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : "Recording not found.")
        }
      })
    return () => {
      cancelled = true
    }
  }, [assetId])

  useEffect(() => {
    if (!projectId || typeof api.project !== "function") {
      return
    }
    let cancelled = false
    api
      .project(projectId)
      .then((detail) => {
        if (!cancelled && detail.mode === "study") {
          setStudyName(detail.name)
        }
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [projectId])

  useEffect(() => {
    if (!projectId || typeof api.lyrics !== "function") {
      return
    }
    const epoch = ++lyricEpoch.current
    api
      .lyrics(projectId, assetId)
      .then((document) => {
        if (epoch === lyricEpoch.current) {
          setLyricDocument(document)
        }
      })
      .catch(() => {
        if (epoch === lyricEpoch.current) {
          setLyricDocument(null)
        }
      })
    return () => {
      lyricEpoch.current += 1
    }
  }, [projectId, assetId])

  const onLyricDocument = useCallback((document: LyricDocumentOut | null) => {
    lyricEpoch.current += 1
    setLyricDocument(document)
  }, [])

  useEffect(() => {
    let cancelled = false
    api
      .charts(assetId)
      .then((list) => {
        if (!cancelled) {
          setCharts(list.charts)
        }
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [assetId, job?.status, asset?.analysis_status])

  useEffect(() => {
    let cancelled = false
    api
      .chart(assetId, chartId)
      .then((next) => {
        if (!cancelled) {
          setDocument(next)
        }
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [assetId, chartId, job?.status, asset?.analysis_status])

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed" || job.status === "canceled") {
      return
    }
    const timer = window.setInterval(() => {
      api
        .job(job.id)
        .then((next) => setJob(next))
        .catch(() => undefined)
    }, 1000)
    return () => window.clearInterval(timer)
  }, [job])

  useEffect(() => {
    if (job?.status !== "completed" && job?.status !== "failed") {
      return
    }
    api
      .asset(assetId)
      .then(setAsset)
      .catch(() => undefined)
  }, [assetId, job?.status])

  async function onExport(profile: ExportCreate["profile"]) {
    if (!projectId) {
      return
    }
    if ((profile === "lyricist" || profile === "combined") && !lyricDocument) {
      return
    }
    setExportState({ kind: "loading", profile })
    try {
      const manifest = await api.createExport(projectId, assetId, { profile, lyrics: lyricMode })
      await api.downloadExport(projectId, assetId, manifest.export_id, `${profile}-${manifest.export_id}.zip`)
      setExportState({ kind: "done", profile })
    } catch (error) {
      setExportState({
        kind: "error",
        message: error instanceof Error ? error.message : "The export was not created.",
      })
    }
  }

  async function onAnalyze() {
    setNotice("")
    try {
      setJob(await api.analyze(assetId))
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Analysis is not available.")
    }
  }

  const studyContext = !projectId ? "No study" : (studyName ?? "Study")
  const jobText = notice || job?.error || ""
  const jobFeedback = jobText
    ? { role: "alert" as const, text: jobText }
    : job
      ? { role: "status" as const, text: `Analysis ${statusLabel(job.status)}.` }
      : null

  return (
    <div className={waveformOpen ? "recording is-waveform-open" : "recording"}>
      {loadError ? (
        <p className="feedback is-alert" role="alert">
          {loadError}
        </p>
      ) : null}
      {!asset && !loadError ? <p role="status">Loading the recording.</p> : null}
      {asset ? (
        <>
          <header className="recording-header">
            <div className="recording-id">
              <h1 className="page-title">{asset.original_name}</h1>
              <p className="recording-sub num">
                {studyContext} · {formatLabel(asset)} · {clock(asset.duration_s)}
              </p>
            </div>
            <dl className="evidence recording-status">
              <div>
                <dt>Analysis</dt>
                <dd>{statusLabel(asset.analysis_status)}</dd>
              </div>
              <div>
                <dt>Playback</dt>
                <dd>{statusLabel(asset.playback_status)}</dd>
              </div>
            </dl>
            <div className="recording-actions">
              <button type="button" className="action" onClick={() => void onAnalyze()}>
                Analyze
              </button>
              <button
                type="button"
                className="quiet-control"
                aria-expanded={exportsOpen}
                aria-controls="export-controls"
                onClick={() => setExportsOpen((open) => !open)}
              >
                Export controls
              </button>
              <button
                type="button"
                className="quiet-control"
                aria-expanded={detailsOpen}
                aria-controls="recording-details"
                onClick={() => setDetailsOpen((open) => !open)}
              >
                Details
              </button>
            </div>
          </header>
          <div id="recording-details" className="recording-disclosure" hidden={!detailsOpen}>
            <dl className="evidence">
              <div>
                <dt>Format</dt>
                <dd>{formatLabel(asset)}</dd>
              </div>
              <div>
                <dt>Duration</dt>
                <dd className="num">{clock(asset.duration_s)}</dd>
              </div>
              <div>
                <dt>Study</dt>
                <dd>{studyContext}</dd>
              </div>
              <div>
                <dt>Playback copy</dt>
                <dd>{playbackCaption(asset)}</dd>
              </div>
            </dl>
          </div>
          <div id="export-controls" className="recording-disclosure" hidden={!exportsOpen}>
              <div className="export-bar">
                <label>
                  Lyric text
                  <select
                    aria-label="Lyric text in export"
                    value={lyricMode}
                    disabled={!projectId || exportState.kind === "loading"}
                    onChange={(event) => {
                      const value = event.target.value
                      if (value === "summarized" || value === "included" || value === "omitted") {
                        setLyricMode(value)
                      }
                    }}
                  >
                    <option value="summarized">Summarized</option>
                    <option value="included">Included</option>
                    <option value="omitted">Omitted</option>
                  </select>
                </label>
                <button
                  type="button"
                  className="action"
                  disabled={!projectId || exportState.kind === "loading"}
                  onClick={() => void onExport("technical")}
                >
                  Export Technical ZIP
                </button>
                <button
                  type="button"
                  className="action"
                  disabled={!projectId || !lyricDocument || exportState.kind === "loading"}
                  onClick={() => void onExport("lyricist")}
                >
                  Export Lyricist ZIP
                </button>
                <button
                  type="button"
                  className="action"
                  disabled={!projectId || !lyricDocument || exportState.kind === "loading"}
                  onClick={() => void onExport("combined")}
                >
                  Export Combined ZIP
                </button>
              </div>
              {!projectId ? <p className="quiet">Open this recording from a study to export.</p> : null}
              {projectId && !lyricDocument ? (
                <p className="quiet">Attach a lyric document to export a Lyricist or Combined package.</p>
              ) : null}
              {exportState.kind === "loading" ? (
                <p className="feedback" role="status">
                  Preparing the {exportName(exportState.profile)} ZIP.
                </p>
              ) : null}
              {exportState.kind === "done" ? (
                <p className="feedback" role="status">
                  {exportName(exportState.profile)} ZIP downloaded.
                </p>
              ) : null}
              {exportState.kind === "error" ? (
                <p className="feedback is-alert" role="alert">
                  {exportState.message}
                </p>
              ) : null}
          </div>
          {asset.playback_status === "unavailable" ? <p className="quiet">{playbackCaption(asset)}</p> : null}
          {peaks ? (
            <Transport
              asset={asset}
              peaks={peaks}
              seekRef={seekRef}
              onTime={onTime}
              cues={cues}
              activeCueId={activeCueId}
              focusCueId={focusCueId}
              regionNonce={regionNonce}
              lyricBridge={lyricBridge}
              waveformOpen={waveformOpen}
              onWaveform={setWaveformOpen}
            />
          ) : null}
          {asset.playback_status === "ready" && !peaks && !loadError ? (
            <p className="feedback" role="status">
              Loading playback.
            </p>
          ) : null}
          {jobFeedback ? (
            <p className={jobFeedback.role === "alert" ? "feedback is-alert" : "feedback"} role={jobFeedback.role}>
              {jobFeedback.text}
            </p>
          ) : null}
          <TechnicalBoard
            charts={charts}
            chartId={chartId}
            document={document}
            onSelect={setChartId}
            onSeek={onSeek}
            playhead={playhead}
            assetId={asset.id}
            lyricsPanel={
              <LyricsWorkspace
                projectId={projectId}
                assetId={asset.id}
                durationS={asset.duration_s}
                playhead={playhead}
                onSeek={onSeek}
                onCues={onCues}
                onActive={onActive}
                onFocus={setFocusCueId}
                bridge={lyricBridge}
                onRegionReset={() => setRegionNonce((count) => count + 1)}
                onDocument={onLyricDocument}
              />
            }
          />
        </>
      ) : null}
    </div>
  )
}
