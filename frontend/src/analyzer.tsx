import { Pause, Play } from "lucide-react"
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react"
import WaveSurfer from "wavesurfer.js"
import RegionsPlugin from "wavesurfer.js/dist/plugins/regions.esm.js"
import { api, streamUrl } from "./api/client"
import type { Asset, ChartDocument, ChartSummary, Job, Peaks } from "./api/types"
import { ChartView } from "./chart"
import { clock, playbackCaption, statusLabel, TECHNICAL, toWavePeaks } from "./catalog"
import {
  cueColor,
  cueKey,
  LyricsWorkspace,
  syncLyricRegions,
  type LyricBridge,
  type LyricCue,
  type LyricRegionPlugin,
} from "./lyrics"

export function TechnicalBoard({
  charts,
  chartId,
  document,
  jobStatus,
  notice,
  onAnalyze,
  onSelect,
  onSeek,
  playhead = null,
  assetId,
  lyricsPanel = null,
}: {
  charts: ChartSummary[]
  chartId: string
  document: ChartDocument | null
  jobStatus: string
  notice: string
  onAnalyze: () => void
  onSelect: (chartId: string) => void
  onSeek: (seconds: number) => void
  playhead?: number | null
  assetId?: string
  lyricsPanel?: ReactNode
}) {
  const [tab, setTab] = useState<"technical" | "lyrics">("technical")
  const [holdLyrics, setHoldLyrics] = useState(false)
  const rows = TECHNICAL.map((item) => {
    const live = charts.find((chart) => chart.chart_kind === item.id)
    return { id: item.id, title: live?.title || item.title, status: live?.status ?? "not_run" }
  })
  const selected = rows.find((row) => row.id === chartId) ?? rows[0]
  const active = document?.chart_kind === selected.id ? document : null

  useEffect(() => {
    setTab("technical")
    setHoldLyrics(false)
  }, [assetId])

  return (
    <section>
      <div className="tabs" role="tablist" aria-label="Study">
        <button
          type="button"
          role="tab"
          aria-selected={tab === "technical"}
          onClick={() => setTab("technical")}
        >
          Technical Analysis
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={tab === "lyrics"}
          onClick={() => {
            setHoldLyrics(true)
            setTab("lyrics")
          }}
        >
          Lyrics & Inspiration
        </button>
      </div>
      <div className="workspace">
        {tab === "technical" ? (
          <div role="tabpanel">
            {rows.map((item) => (
              <button
                key={item.id}
                type="button"
                className="category"
                aria-current={item.id === selected.id ? "true" : undefined}
                onClick={() => onSelect(item.id)}
              >
                {item.id} {item.title}
                <br />
                <small>{statusLabel(item.status)}</small>
              </button>
            ))}
          </div>
        ) : null}
        {holdLyrics && lyricsPanel ? (
          <div style={{ display: tab === "lyrics" ? "contents" : "none" }}>{lyricsPanel}</div>
        ) : null}
        {tab === "lyrics" && !lyricsPanel ? (
          <>
            <div role="tabpanel">
              <p>Text</p>
              <p className="quiet">No lyric file is attached.</p>
            </div>
            <div>
              <h2 className="m-0 font-serif text-3xl font-medium">Lyrics & Inspiration</h2>
              <p>Open a recording to attach lyrics. Sung timing is not guessed.</p>
            </div>
            <aside>
              <h2 className="m-0 font-serif text-2xl font-medium">Evidence</h2>
              <p>No evidence yet.</p>
            </aside>
          </>
        ) : null}
        {tab === "technical" ? (
          <div>
            <h2 className="m-0 font-serif text-3xl font-medium">
              {selected.id} {selected.title}
            </h2>
            <p>Status: {statusLabel(active?.status ?? selected.status)}</p>
            {jobStatus ? <p>Analysis {statusLabel(jobStatus)}.</p> : null}
            {active?.status === "ready" ? <ChartView chart={active} onSeek={onSeek} playhead={playhead} /> : null}
            {active && active.status !== "ready" && active.status !== "not_run" ? (
              <p>{active.not_available_reason || active.error}</p>
            ) : null}
            {(active?.status ?? selected.status) === "not_run" ? (
              <p>Not run. Nothing has been measured for this recording.</p>
            ) : null}
            {selected.status !== "not_run" && !active ? <p>Loading this chart.</p> : null}
            <button type="button" className="action" onClick={onAnalyze}>
              Analyze
            </button>
            {notice ? (
              <p className="notice" role="status">
                {notice}
              </p>
            ) : null}
          </div>
        ) : null}
        {tab === "technical" ? (
          <aside>
            <h2 className="m-0 font-serif text-2xl font-medium">Evidence</h2>
            {active && active.status !== "not_run" ? (
              <>
                <p>{active.evidence_class}</p>
                <p>
                  {active.method_id} {active.method_version}
                </p>
                {active.summary.map((item) => (
                  <p key={item.label}>
                    {item.label}: {item.value}
                  </p>
                ))}
                {active.caveats.map((item) => (
                  <p key={item}>{item}</p>
                ))}
              </>
            ) : (
              <p>No evidence yet.</p>
            )}
          </aside>
        ) : null}
      </div>
    </section>
  )
}

function Transport({
  asset,
  peaks,
  seekRef,
  onTime,
  cues,
  activeCueId,
  regionNonce,
  lyricBridge,
}: {
  asset: Asset
  peaks: Peaks
  seekRef: { current: (seconds: number) => void }
  onTime: (seconds: number) => void
  cues: LyricCue[]
  activeCueId: string | null
  regionNonce: number
  lyricBridge: { current: LyricBridge }
}) {
  const host = useRef<HTMLDivElement>(null)
  const player = useRef<WaveSurfer | null>(null)
  const regionsRef = useRef<LyricRegionPlugin | null>(null)
  const [time, setTime] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState("")
  const [regionsReady, setRegionsReady] = useState(0)
  const duration = peaks.duration_s

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
      height: 96,
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
      unsubscribers.forEach((unsubscribe) => unsubscribe())
      regionsRef.current = null
      wave.destroy()
      player.current = null
    }
  }, [asset.id, duration, peaks.buckets, seekRef, onTime])

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
      region.setOptions({ color: cueColor(cue.origin, cue.id === activeCueId) })
    }
  }, [activeCueId, cues, regionsReady])

  return (
    <div>
      <div ref={host} className="wave" />
      <p>{playbackCaption(asset)}</p>
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
        <span>
          {clock(time, true)} / {clock(duration, true)}
        </span>
        <label>
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
        <label>
          Volume
          <input
            type="range"
            min={0}
            max={1}
            step={0.01}
            defaultValue={1}
            aria-label="Volume"
            onChange={(event) => player.current?.setVolume(Number(event.target.value))}
          />
        </label>
      </div>
      {error ? <p role="alert">{error}</p> : null}
    </div>
  )
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
  const [regionNonce, setRegionNonce] = useState(0)
  const lyricBridge = useRef<LyricBridge>({
    commit() {},
    pick() {},
  })
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

  async function onAnalyze() {
    setNotice("")
    try {
      setJob(await api.analyze(assetId))
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Analysis is not available.")
    }
  }

  return (
    <>
      <h1 className="page-title">Analyzer</h1>
      {loadError ? <p role="alert">{loadError}</p> : null}
      {!asset && !loadError ? <p>Loading the recording.</p> : null}
      {asset ? (
        <>
          <p>{`${asset.original_name}. Analysis ${statusLabel(asset.analysis_status)}.`}</p>
          {asset.playback_status === "unavailable" ? <p>{playbackCaption(asset)}</p> : null}
          {peaks ? (
            <Transport
              asset={asset}
              peaks={peaks}
              seekRef={seekRef}
              onTime={onTime}
              cues={cues}
              activeCueId={activeCueId}
              regionNonce={regionNonce}
              lyricBridge={lyricBridge}
            />
          ) : null}
          {asset.playback_status === "ready" && !peaks && !loadError ? <p>Loading playback.</p> : null}
          <TechnicalBoard
            charts={charts}
            chartId={chartId}
            document={document}
            jobStatus={job?.status ?? ""}
            notice={notice || job?.error || ""}
            onAnalyze={() => void onAnalyze()}
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
                bridge={lyricBridge}
                onRegionReset={() => setRegionNonce((count) => count + 1)}
              />
            }
          />
        </>
      ) : null}
    </>
  )
}
