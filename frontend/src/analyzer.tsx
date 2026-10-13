import { Pause, Play } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import WaveSurfer from "wavesurfer.js"
import { api, streamUrl } from "./api/client"
import type { Asset, Peaks } from "./api/types"
import { clock, playbackCaption, TECHNICAL, toWavePeaks } from "./catalog"

export function TechnicalBoard({
  notice,
  onAnalyze,
}: {
  notice: string
  onAnalyze: () => void
}) {
  const [tab, setTab] = useState<"technical" | "lyrics">("technical")
  const [chartId, setChartId] = useState(TECHNICAL[0].id)
  const chart = TECHNICAL.find((item) => item.id === chartId) ?? TECHNICAL[0]

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
        <button type="button" role="tab" aria-selected={tab === "lyrics"} onClick={() => setTab("lyrics")}>
          Lyrics & Inspiration
        </button>
      </div>
      <div className="workspace">
        {tab === "technical" ? (
          <div role="tabpanel">
            {TECHNICAL.map((item) => (
              <button
                key={item.id}
                type="button"
                className="category"
                aria-current={item.id === chart.id ? "true" : undefined}
                onClick={() => setChartId(item.id)}
              >
                {item.id} {item.title}
                <br />
                <small>not run</small>
              </button>
            ))}
          </div>
        ) : (
          <div role="tabpanel">
            <p>Text</p>
            <p className="quiet">No lyric file is attached.</p>
          </div>
        )}
        <div>
          {tab === "technical" ? (
            <>
              <h2 className="m-0 font-serif text-3xl font-medium">
                {chart.id} {chart.title}
              </h2>
              <p>{chart.note}</p>
              <p>Status: not run</p>
              <button type="button" className="action" onClick={onAnalyze}>
                Analyze
              </button>
              {notice ? (
                <p className="notice" role="status">
                  {notice}
                </p>
              ) : null}
            </>
          ) : (
            <>
              <h2 className="m-0 font-serif text-3xl font-medium">Lyrics & Inspiration</h2>
              <p>Text upload is not in this milestone. Sung timing is not guessed.</p>
            </>
          )}
        </div>
        <aside>
          <h2 className="m-0 font-serif text-2xl font-medium">Evidence</h2>
          <p>No evidence yet.</p>
        </aside>
      </div>
    </section>
  )
}

function Transport({ asset, peaks }: { asset: Asset; peaks: Peaks }) {
  const host = useRef<HTMLDivElement>(null)
  const player = useRef<WaveSurfer | null>(null)
  const [time, setTime] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [error, setError] = useState("")
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
      waveColor: "#8d8478",
      progressColor: "#b08d57",
      cursorColor: "#e6e0d4",
      cursorWidth: 1,
      barWidth: 2,
      barGap: 1,
      interact: true,
      dragToSeek: true,
      normalize: false,
    })
    player.current = wave
    const unsubscribers = [
      wave.on("timeupdate", (value) => setTime(value)),
      wave.on("play", () => setPlaying(true)),
      wave.on("pause", () => setPlaying(false)),
      wave.on("finish", () => setPlaying(false)),
      wave.on("error", (err) => setError(err instanceof Error ? err.message : "Playback failed.")),
    ]
    return () => {
      unsubscribers.forEach((unsubscribe) => unsubscribe())
      wave.destroy()
      player.current = null
    }
  }, [asset.id, duration, peaks.buckets])

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

export function Analyzer({ assetId }: { assetId: string }) {
  const [asset, setAsset] = useState<Asset | null>(null)
  const [peaks, setPeaks] = useState<Peaks | null>(null)
  const [loadError, setLoadError] = useState("")
  const [notice, setNotice] = useState("")

  useEffect(() => {
    let cancelled = false
    setAsset(null)
    setPeaks(null)
    setLoadError("")
    setNotice("")
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

  async function onAnalyze() {
    setNotice("")
    try {
      await api.analyze(assetId)
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
          <p>{`${asset.original_name}. Analysis ${asset.analysis_status}.`}</p>
          {asset.playback_status === "unavailable" ? <p>{playbackCaption(asset)}</p> : null}
          {peaks ? <Transport asset={asset} peaks={peaks} /> : null}
          {asset.playback_status === "ready" && !peaks && !loadError ? <p>Loading playback.</p> : null}
          <TechnicalBoard notice={notice} onAnalyze={() => void onAnalyze()} />
        </>
      ) : null}
    </>
  )
}
