import { fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { Asset, ComparisonDocument, ProjectDetail, ReviewRecord } from "./api/types"
import { AlbumWorkspace } from "./album"

const waves = vi.hoisted(() => ({
  autoReady: true,
  created: [] as {
    url: string
    duration: number
    setTime: ReturnType<typeof vi.fn>
    emitReady: () => void
  }[],
}))

const api = vi.hoisted(() => ({
  project: vi.fn(),
  assets: vi.fn(),
  comparison: vi.fn(),
  reviews: vi.fn(),
  peaks: vi.fn(),
  addMember: vi.fn(),
  analyze: vi.fn(),
  projects: vi.fn(),
  orderAlbum: vi.fn(),
  saveReview: vi.fn(),
  createAlbumExport: vi.fn(),
  downloadAlbumExport: vi.fn(),
}))

vi.mock("./api/client", () => ({ api, streamUrl: (id: string) => `/api/assets/${id}/stream` }))

vi.mock("wavesurfer.js", () => ({
  default: {
    create(options: { url: string; duration: number }) {
      const setTime = vi.fn()
      let onReady: (() => void) | undefined
      const wave = {
        url: options.url,
        duration: options.duration,
        setTime,
        emitReady() {
          onReady?.()
        },
      }
      waves.created.push(wave)
      return {
        on(name: string, handler: () => void) {
          if (name === "ready") {
            onReady = handler
            if (waves.autoReady) {
              handler()
            }
          }
          return () => undefined
        },
        destroy() {},
        playPause() {},
        setTime,
        setVolume() {},
        setOptions() {},
      }
    },
  },
}))

vi.mock("echarts", () => ({
  init: () => ({
    setOption() {},
    getZr: () => ({ on() {} }),
    resize() {},
    dispose() {},
    containPixel() {
      return false
    },
    convertFromPixel() {
      return [0, 0]
    },
  }),
}))

vi.stubGlobal(
  "ResizeObserver",
  class {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
)

function asset(id: string, name: string, channels: number): Asset {
  return {
    id,
    sha256: `${id}${"ab".repeat(32)}`.slice(0, 64),
    original_name: name,
    byte_length: 80,
    duration_s: 4,
    sample_rate: 44100,
    channels,
    subtype: "pcm_16",
    analysis_status: "completed",
    playback_status: "ready",
    created_at: "2026-11-11T00:00:00Z",
  }
}

function scalar(name: string, unit: string, value: number | null, evidence: string) {
  return { name, unit, evidence_class: evidence, value, method_id: "stored", metrics_value: null }
}

function track(id: string, name: string, channels: number, evidence: string, value: number | null) {
  return {
    ordering: id === "left" ? 0 : 1,
    asset_id: id,
    original_name: name,
    sha256: `${id}${"cd".repeat(32)}`.slice(0, 64),
    duration_s: 4,
    sample_rate: 44100,
    channels,
    analysis_status: "completed",
    playback_status: "ready",
    algorithm_version: "m1-v3",
    params_hash: "hash",
    included: true,
    omit_reason: null,
    scalars: [
      scalar("integrated_loudness", "LUFS", -14, "measured"),
      scalar("sample_peak", "dBFS", -1, "measured"),
      scalar("ffmpeg_true_peak", "dBTP", -0.4, "measured"),
      scalar("correlation", "ratio", value, evidence),
    ],
    bands: [{ label: "20–60 Hz", value: 10 }],
    below_20_hz: 1,
    pulse: [{ label: "120.0 BPM", value: 0.4, evidence_class: "estimated" }],
    endings: {
      endpoint: "zero",
      tails: [{ label: "last 50 ms RMS", value: -70 }],
      silence: [{ start_s: 0.2, end_s: 0.4 }],
      rail_count: 0,
      reconstructed_peak: -0.2,
      reconstructed_peak_time_s: 1.5,
    },
    sample_peak_time_s: 1.25,
    caveats: [],
  }
}

const left = asset("left", "Left.wav", 2)
const mono = asset("mono", "Mono.wav", 1)

const comparison: ComparisonDocument = {
  comparison_version: "album-qc-v1",
  project_id: "album-1",
  name: "Night album",
  status: "ready",
  not_available_reason: null,
  x_mode: "seconds",
  tracks: [
    track("left", "Left.wav", 2, "measured", 0.8),
    track("mono", "Mono.wav", 1, "not_applicable", null),
  ],
  pairs: [
    {
      left_asset_id: "left",
      right_asset_id: "mono",
      deltas: [
        { name: "integrated_loudness", unit: "LU", method_id: "ffmpeg-ebur128", delta: 1, reason: null },
        { name: "sample_peak", unit: "dBFS", method_id: "sample-peak", delta: null, reason: "missing_value" },
        { name: "ffmpeg_true_peak", unit: "dBTP", method_id: "ffmpeg-ebur128", delta: 0.25, reason: null },
      ],
    },
  ],
  spectral_distances: [
    {
      left_asset_id: "left",
      right_asset_id: "mono",
      status: "not_available",
      reason: "band_edges_differ",
      value: null,
      unit: "percentage points",
      method_id: "band-share-l1-v1",
      evidence_class: null,
    },
  ],
  panel: {
    chart_kind: "T11",
    status: "ready",
    title: "Album comparison",
    evidence_class: "measured",
    method_id: "stored-m1-v3-series",
    method_version: "album-qc-v1",
    caveats: ["The Welch PSD line is not overlaid."],
    summary: [],
    series: {
      lines: [
        { name: "1. Left.wav — 1 s RMS", unit: "dBFS", x: [0, 2], y: [-20, -10] },
        { name: "1. Left.wav — 3 s short-term LUFS", unit: "LUFS", x: [0, 2], y: [-16, -15] },
      ],
      bars: [],
      heatmap: null,
    },
    axis_definitions: { x: "Time (s)", y: "dBFS or LUFS", y_scale: "linear" },
    review_markers: [],
  },
  caveats: ["The Welch PSD line is not overlaid."],
}

const progress: ComparisonDocument = {
  ...comparison,
  x_mode: "progress",
  panel: comparison.panel
    ? {
        ...comparison.panel,
        axis_definitions: { ...comparison.panel.axis_definitions, x: "Progress (fraction of duration)" },
        series: {
          ...comparison.panel.series,
          lines: (comparison.panel.series.lines ?? []).map((line) => ({
            ...line,
            x: line.x.map((value) => (value === null ? null : value / 4)),
          })),
        },
      }
    : null,
}

const detail: ProjectDetail = {
  id: "album-1",
  name: "Night album",
  mode: "album",
  created_at: "2026-11-11T00:00:00Z",
  updated_at: "2026-11-11T00:00:00Z",
  assets: [left, mono],
}

const review: ReviewRecord = {
  asset_id: "left",
  checkpoint_id: "sample_peak",
  status: "unchecked",
  note: "",
  value: -1,
  unit: "dBFS",
  time_s: 1.25,
  fact: "Sample peak -1 dBFS at 1.25 s.",
}

async function openPicker() {
  fireEvent.click(await screen.findByRole("button", { name: "Add recordings" }))
  return screen.findByRole("dialog", { name: "Add recordings" })
}

async function openTab(name: string) {
  fireEvent.click(await screen.findByRole("tab", { name }))
}

function named(id: string, status: Asset["analysis_status"] = "not_run", playback: Asset["playback_status"] = "ready"): Asset {
  return { ...asset(id, `${id}.wav`, 1), analysis_status: status, playback_status: playback }
}

function peaksFor(id: string) {
  return {
    duration_s: id === "mono" ? 8 : 4,
    sample_rate: 44100,
    channels: id === "mono" ? 1 : 2,
    method_id: "playback",
    buckets: [{ min: -0.1, max: 0.1 }],
  }
}

function deferredPeaks() {
  const pending = new Map<string, (value: ReturnType<typeof peaksFor>) => void>()
  api.peaks.mockImplementation(
    (id: string) => new Promise((resolve) => pending.set(id, resolve)),
  )
  return pending
}

const monoReview: ReviewRecord = {
  ...review,
  asset_id: "mono",
  time_s: 1.5,
  fact: "Sample peak -1.00 dBFS at 1.500 s.",
}

beforeEach(() => {
  waves.autoReady = true
  waves.created.length = 0
  api.project.mockReset()
  api.assets.mockReset()
  api.comparison.mockReset()
  api.reviews.mockReset()
  api.peaks.mockReset()
  api.saveReview.mockReset()
  api.addMember.mockReset()
  api.analyze.mockReset()
  api.projects.mockReset()
  api.project.mockResolvedValue(detail)
  api.projects.mockResolvedValue([])
  api.addMember.mockResolvedValue({ asset_id: "left", ordering: 2 })
  api.analyze.mockResolvedValue({
    id: "job",
    asset_id: "left",
    status: "queued",
    created_at: "2026-11-11T00:00:00Z",
    updated_at: "2026-11-11T00:00:00Z",
    error: null,
  })
  api.assets.mockResolvedValue([left, mono])
  api.comparison.mockImplementation(async (_id: string, x: string) => (x === "progress" ? progress : comparison))
  api.reviews.mockResolvedValue([review])
  api.peaks.mockImplementation(async (id: string) => peaksFor(id))
  api.saveReview.mockImplementation(async (_id: string, body: { status: string; note?: string }) => ({
    ...review,
    status: body.status,
    note: body.note ?? "",
  }))
})

describe("album workspace", () => {
  it("keeps units apart, shows mono as not applicable, and leaves the checkpoint unchecked", async () => {
    const inspected: string[] = []
    render(<AlbumWorkspace projectId="album-1" onInspect={(assetId) => inspected.push(assetId)} />)
    expect(document.querySelector("input[type=file]")).toBeNull()
    await openTab("Comparisons")
    expect(await screen.findByRole("heading", { name: "LUFS" })).toBeTruthy()
    expect(screen.getByRole("heading", { name: "dBFS" })).toBeTruthy()
    expect(screen.getByRole("heading", { name: "dBTP" })).toBeTruthy()
    expect(screen.getAllByText("-14.0 LUFS").length).toBeGreaterThan(0)
    expect(screen.getAllByText("-1.00 dBFS").length).toBeGreaterThan(0)
    const stereo = screen.getByRole("region", { name: "Stereo" })
    expect(stereo.textContent).toContain("Not applicable")
    expect(stereo.textContent).not.toBe("0")
    const pairs = screen.getByRole("table", { name: "Shown pair differences" })
    expect(within(pairs).getByText("Integrated loudness")).toBeTruthy()
    expect(within(pairs).getByText("1.0")).toBeTruthy()
    expect(within(pairs).getByText("LU")).toBeTruthy()
    expect(within(pairs).getAllByText("1. Left.wav").length).toBeGreaterThan(0)
    expect(within(pairs).getAllByText("2. Mono.wav").length).toBeGreaterThan(0)
    expect(within(pairs).getByText("FFmpeg true peak")).toBeTruthy()
    expect(within(pairs).getByText("0.25")).toBeTruthy()
    expect(within(pairs).getAllByText("dB").length).toBeGreaterThan(0)
    expect(within(pairs).queryByText("dBTP")).toBeNull()
    expect(screen.getAllByText("-0.40 dBTP").length).toBeGreaterThan(0)
    expect(within(pairs).getByText("Missing value")).toBeTruthy()
    expect(within(pairs).queryByText("integrated_loudness")).toBeNull()
    expect(within(pairs).queryByText("dBFS")).toBeNull()
    expect(screen.getByRole("region", { name: "Bands" }).textContent).toContain("20–60 Hz")
    expect(screen.getByText(/does not audition a recording/i)).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Data table" }))
    expect(screen.getByText("-20")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Progress" }))
    expect(await screen.findByText("-20")).toBeTruthy()
    expect(screen.getByText("-10")).toBeTruthy()
    await openTab("Endings and rhythm")
    expect(screen.getAllByText(/Endpoint zero/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/not the FFmpeg true peak/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/not a probability or a confirmed tempo/).length).toBeGreaterThan(0)
    await openTab("Listening review")
    expect(screen.getByText(/1\. Left\.wav\. Unchecked/)).toBeTruthy()
    expect(screen.getByText("Sample peak -1 dBFS at 1.25 s.")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Intentional" }))
    await waitFor(() =>
      expect(api.saveReview).toHaveBeenCalledWith(
        "album-1",
        expect.objectContaining({ status: "intentional", asset_id: "left" }),
      ),
    )
    expect(screen.getByText("Sample peak -1 dBFS at 1.25 s.")).toBeTruthy()
    fireEvent.change(screen.getByLabelText("Note for 1. Left.wav, Sample peak"), { target: { value: "hot ending" } })
    fireEvent.blur(screen.getByLabelText("Note for 1. Left.wav, Sample peak"))
    await waitFor(() =>
      expect(api.saveReview).toHaveBeenCalledWith(
        "album-1",
        expect.objectContaining({ note: "hot ending", status: "intentional", checkpoint_id: "sample_peak" }),
      ),
    )
    await openTab("Recordings")
    fireEvent.click(screen.getByRole("button", { name: "Inspect Left.wav" }))
    expect(inspected).toEqual(["left"])
  })

  it("seeks the recording named by the checkpoint", async () => {
    api.reviews.mockResolvedValue([review, monoReview])
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    await screen.findByRole("button", { name: "Play" })
    await openTab("Listening review")
    fireEvent.click(screen.getAllByRole("button", { name: "Play checkpoint" })[1])
    await waitFor(() =>
      expect(waves.created.some((wave) => wave.url.includes("mono") && wave.setTime.mock.calls[0]?.[0] === 1.5)).toBe(
        true,
      ),
    )
    const monoWave = waves.created.find((wave) => wave.url.includes("mono"))
    expect(monoWave?.duration).toBe(8)
  })

  it("ignores a stale peaks response when the checkpoint changes", async () => {
    const pending = new Map<string, (value: ReturnType<typeof peaksFor>) => void>()
    api.peaks.mockImplementation((id: string) => new Promise((resolve) => pending.set(id, resolve)))
    api.reviews.mockResolvedValue([review, monoReview])
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    await waitFor(() => expect(pending.has("left")).toBe(true))
    pending.get("left")?.(peaksFor("left"))
    await screen.findByRole("button", { name: "Play" })
    await openTab("Listening review")
    fireEvent.click(screen.getAllByRole("button", { name: "Play checkpoint" })[1])
    await waitFor(() => expect(pending.has("mono")).toBe(true))
    const stale = pending.get("mono")
    fireEvent.click(screen.getAllByRole("button", { name: "Play checkpoint" })[0])
    stale?.(peaksFor("mono"))
    await waitFor(() => expect(waves.created.at(-1)?.setTime).toHaveBeenCalledWith(1.25))
    expect(waves.created.some((wave) => wave.duration === 8)).toBe(false)
  })

  it("seeks the selected recording after its peaks load", async () => {
    waves.autoReady = false
    const pending = deferredPeaks()
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    await waitFor(() => expect(pending.has("left")).toBe(true))
    await openTab("Listening review")
    fireEvent.click(screen.getByRole("button", { name: "Play checkpoint" }))
    expect(waves.created).toHaveLength(0)
    pending.get("left")?.(peaksFor("left"))
    const wave = await waitFor(() => {
      expect(waves.created).toHaveLength(1)
      return waves.created[0]
    })
    expect(wave?.setTime).not.toHaveBeenCalled()
    wave?.emitReady()
    expect(wave?.setTime).toHaveBeenCalledTimes(1)
    expect(wave?.setTime).toHaveBeenCalledWith(1.25)
    wave?.emitReady()
    expect(wave?.setTime).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole("button", { name: "Play checkpoint" }))
    expect(wave?.setTime).toHaveBeenCalledTimes(2)
  })

  it("seeks a different recording after that recording loads", async () => {
    waves.autoReady = false
    const pending = deferredPeaks()
    api.reviews.mockResolvedValue([review, monoReview])
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    await waitFor(() => expect(pending.has("left")).toBe(true))
    pending.get("left")?.(peaksFor("left"))
    const leftWave = await waitFor(() => {
      expect(waves.created[0]).toBeTruthy()
      return waves.created[0]
    })
    leftWave?.emitReady()
    await openTab("Listening review")
    fireEvent.click(screen.getAllByRole("button", { name: "Play checkpoint" })[1])
    await waitFor(() => expect(pending.has("mono")).toBe(true))
    expect(waves.created.some((wave) => wave.url.includes("mono"))).toBe(false)
    pending.get("mono")?.(peaksFor("mono"))
    const monoWave = await waitFor(() => {
      const found = waves.created.find((wave) => wave.url.includes("mono"))
      expect(found).toBeTruthy()
      return found
    })
    expect(monoWave?.setTime).not.toHaveBeenCalled()
    monoWave?.emitReady()
    expect(monoWave?.setTime).toHaveBeenCalledTimes(1)
    expect(monoWave?.setTime).toHaveBeenCalledWith(1.5)
    expect(leftWave?.setTime).not.toHaveBeenCalled()
  })

  it("does not let a stale peaks response seek the wrong recording", async () => {
    waves.autoReady = false
    const pending = deferredPeaks()
    api.reviews.mockResolvedValue([review, monoReview])
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    await waitFor(() => expect(pending.has("left")).toBe(true))
    const staleLeft = pending.get("left")
    await openTab("Listening review")
    fireEvent.click(screen.getAllByRole("button", { name: "Play checkpoint" })[1])
    await waitFor(() => expect(pending.has("mono")).toBe(true))
    staleLeft?.(peaksFor("left"))
    pending.get("mono")?.(peaksFor("mono"))
    const monoWave = await waitFor(() => {
      const found = waves.created.find((wave) => wave.duration === 8)
      expect(found).toBeTruthy()
      return found
    })
    expect(waves.created.some((wave) => wave.duration === 4)).toBe(false)
    monoWave?.emitReady()
    expect(monoWave?.setTime).toHaveBeenCalledTimes(1)
    expect(monoWave?.setTime).toHaveBeenCalledWith(1.5)
  })

  it("ignores a previous player's ready callback", async () => {
    waves.autoReady = false
    const pending = deferredPeaks()
    api.reviews.mockResolvedValue([review, monoReview])
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    await waitFor(() => expect(pending.has("left")).toBe(true))
    pending.get("left")?.(peaksFor("left"))
    const first = await waitFor(() => {
      expect(waves.created[0]).toBeTruthy()
      return waves.created[0]
    })
    await openTab("Recordings")
    fireEvent.click(screen.getByRole("button", { name: "Select Mono.wav" }))
    await openTab("Listening review")
    fireEvent.click(screen.getAllByRole("button", { name: "Play checkpoint" })[0])
    const second = await waitFor(() => {
      const found = waves.created.filter((wave) => wave.url.includes("left")).at(-1)
      expect(found).toBeTruthy()
      expect(found).not.toBe(first)
      return found
    })
    first?.emitReady()
    expect(first?.setTime).not.toHaveBeenCalled()
    expect(second?.setTime).not.toHaveBeenCalled()
    second?.emitReady()
    expect(second?.setTime).toHaveBeenCalledTimes(1)
    expect(second?.setTime).toHaveBeenCalledWith(1.25)
    expect(first?.setTime).not.toHaveBeenCalled()
  })

  it("applies only the latest checkpoint requested before the player is ready", async () => {
    waves.autoReady = false
    const pending = deferredPeaks()
    api.reviews.mockResolvedValue([
      review,
      { ...review, checkpoint_id: "ending_peak", time_s: 3.5, fact: "Ending peak at 3.50 s." },
    ])
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    await waitFor(() => expect(pending.has("left")).toBe(true))
    await openTab("Listening review")
    const checkpoints = screen.getAllByRole("button", { name: "Play checkpoint" })
    fireEvent.click(checkpoints[0])
    fireEvent.click(checkpoints[1])
    pending.get("left")?.(peaksFor("left"))
    const wave = await waitFor(() => {
      expect(waves.created[0]).toBeTruthy()
      return waves.created[0]
    })
    wave?.emitReady()
    expect(wave?.setTime).toHaveBeenCalledTimes(1)
    expect(wave?.setTime).toHaveBeenCalledWith(3.5)
  })

  it("drops a pending seek when a different recording is selected", async () => {
    let monoRequests = 0
    const pending = new Map<string, (value: ReturnType<typeof peaksFor>) => void>()
    api.peaks.mockImplementation((id: string) => {
      if (id === "left") {
        return Promise.resolve(peaksFor("left"))
      }
      monoRequests += 1
      return new Promise((resolve) => pending.set(id, resolve))
    })
    api.reviews.mockResolvedValue([review, monoReview])
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    await screen.findByRole("button", { name: "Play" })
    await openTab("Listening review")
    fireEvent.click(screen.getAllByRole("button", { name: "Play checkpoint" })[1])
    await waitFor(() => expect(monoRequests).toBe(1))
    await openTab("Recordings")
    fireEvent.click(screen.getByRole("button", { name: "Select Left.wav" }))
    fireEvent.click(screen.getByRole("button", { name: "Select Mono.wav" }))
    await waitFor(() => expect(monoRequests).toBe(2))
    pending.get("mono")?.(peaksFor("mono"))
    await screen.findByRole("button", { name: "Play" })
    expect(waves.created.every((wave) => wave.setTime.mock.calls.length === 0)).toBe(true)
  })

  it("says why the overlay was not drawn", async () => {
    api.comparison.mockResolvedValue({
      ...comparison,
      panel: comparison.panel
        ? {
            ...comparison.panel,
            series: { lines: [{ name: "gap", unit: "dBFS", x: [null, 1], y: [-1, -1] }], bars: [], heatmap: null },
          }
        : null,
    })
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    await openTab("Comparisons")
    expect(await screen.findByText("A stored time value is missing, so the overlay was not drawn.")).toBeTruthy()
    expect(screen.queryByText("Two analyzed recordings are required.")).toBeNull()
  })

  it("navigates sections and filters stored pairs without recomputing a difference", async () => {
    const third = asset("right", "Right.wav", 2)
    const rightTrack = {
      ...track("left", "Right.wav", 2, "measured", 0.8),
      ordering: 2,
      asset_id: "right",
      original_name: "Right.wav",
    }
    api.project.mockResolvedValue({ ...detail, assets: [left, mono, third] })
    api.assets.mockResolvedValue([left, mono, third])
    api.comparison.mockResolvedValue({
      ...comparison,
      tracks: [comparison.tracks[0]!, comparison.tracks[1]!, rightTrack],
      pairs: [
        comparison.pairs[0]!,
        {
          left_asset_id: "mono",
          right_asset_id: "right",
          deltas: comparison.pairs[0]!.deltas,
        },
        {
          left_asset_id: "left",
          right_asset_id: "right",
          deltas: [{ name: "sample_peak", unit: "dBFS", method_id: "sample-peak", delta: 9.25, reason: null }],
        },
      ],
    })
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    expect(await screen.findByRole("tab", { name: "Overview", selected: true })).toBeTruthy()
    expect(screen.queryByRole("heading", { name: "LUFS" })).toBeNull()
    expect(screen.getByRole("button", { name: "Analyze Missing" })).toBeTruthy()
    await openTab("Recordings")
    const recordings = screen.getByRole("tabpanel", { name: "Recordings" })
    expect(within(recordings).getByRole("table").textContent).not.toContain(left.sha256)
    fireEvent.click(within(recordings).getByText("Technical details"))
    expect(within(recordings).getByText(new RegExp(left.sha256))).toBeTruthy()
    await openTab("Endings and rhythm")
    expect(screen.getAllByText(/autocorrelation 0\.400/).length).toBeGreaterThan(0)
    fireEvent.click(screen.getByText("Rhythm candidates for Left.wav"))
    expect(screen.getAllByText("0.4").length).toBeGreaterThan(0)
    await openTab("Comparisons")
    expect(screen.getByText(/Showing 2 of 3 stored pairs/)).toBeTruthy()
    expect(within(screen.getByRole("table", { name: "Shown pair differences" })).queryByText("9.25")).toBeNull()
    fireEvent.click(screen.getByText("All stored differences"))
    const stored = screen.getByRole("table", { name: "All stored pair differences" })
    expect(within(stored).getByText("9.25")).toBeTruthy()
    expect(within(stored).getAllByText("dB").length).toBeGreaterThan(0)
    fireEvent.change(screen.getByLabelText("Pairs"), { target: { value: "all" } })
    expect(within(screen.getByRole("table", { name: "Shown pair differences" })).getByText("9.25")).toBeTruthy()
    fireEvent.change(screen.getByLabelText("Pairs"), { target: { value: "left:right" } })
    const onePair = screen.getByRole("table", { name: "Shown pair differences" })
    expect(within(onePair).getByText("9.25")).toBeTruthy()
    expect(within(onePair).queryByText("1.0")).toBeNull()
  })

  it("adds fifteen selected recordings in list order and skips members", async () => {
    const member = named("kept", "completed")
    const extra = Array.from({ length: 15 }, (_, index) => named(`t${index}`))
    api.assets.mockResolvedValue([member, ...extra])
    api.project.mockResolvedValue({ ...detail, assets: [member] })
    api.reviews.mockResolvedValue([])
    const calls: string[] = []
    api.addMember.mockImplementation(async (_projectId: string, assetId: string) => {
      calls.push(assetId)
      return { asset_id: assetId, ordering: calls.length }
    })
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    const dialog = await openPicker()
    expect(within(dialog).queryByRole("button", { name: "Download album report" })).toBeNull()
    const kept = await screen.findByRole("checkbox", { name: "kept.wav. Already in this album. Completed" })
    expect((kept as HTMLInputElement).disabled).toBe(true)
    fireEvent.click(screen.getByRole("button", { name: "Select all visible" }))
    fireEvent.click(screen.getByRole("button", { name: /^Add$/ }))
    await waitFor(() => expect(calls).toEqual(extra.map((item) => item.id)))
    expect(api.analyze).not.toHaveBeenCalled()
    expect(api.createAlbumExport).not.toHaveBeenCalled()
    expect(api.saveReview).not.toHaveBeenCalled()
  })

  it("filters the picker by study and adds one recording", async () => {
    const first = named("one")
    const second = named("two")
    const other = named("three")
    api.assets.mockResolvedValue([first, second, other])
    api.projects.mockResolvedValue([
      {
        id: "study-1",
        name: "Night study",
        mode: "study",
        created_at: "2026-11-11T00:00:00Z",
        updated_at: "2026-11-11T00:00:00Z",
      },
    ])
    api.project.mockImplementation(async (id: string) => {
      if (id === "study-1") {
        return {
          id: "study-1",
          name: "Night study",
          mode: "study",
          created_at: "2026-11-11T00:00:00Z",
          updated_at: "2026-11-11T00:00:00Z",
          assets: [first, second],
        }
      }
      return { ...detail, assets: [] }
    })
    api.reviews.mockResolvedValue([])
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    await openPicker()
    expect(await screen.findByRole("checkbox", { name: /three\.wav/ })).toBeTruthy()
    await waitFor(() => expect(api.project).toHaveBeenCalledWith("study-1"))
    fireEvent.change(screen.getByLabelText("Study"), { target: { value: "study-1" } })
    expect(await screen.findByRole("checkbox", { name: /one\.wav/ })).toBeTruthy()
    expect(screen.queryByRole("checkbox", { name: /three\.wav/ })).toBeNull()
    fireEvent.click(screen.getByRole("checkbox", { name: /one\.wav/ }))
    fireEvent.click(screen.getByRole("button", { name: /^Add$/ }))
    await waitFor(() => expect(api.addMember).toHaveBeenCalledTimes(1))
    expect(api.addMember).toHaveBeenCalledWith("album-1", "one")
    expect(api.analyze).not.toHaveBeenCalled()
  })

  it("queues missing analysis, reuses completed work, and continues after one failure", async () => {
    const rows = [
      named("done", "completed"),
      named("wait", "queued"),
      named("busy", "running"),
      named("fresh", "not_run"),
      named("bad", "not_run"),
      named("silent", "not_run", "unavailable"),
    ]
    let members: Asset[] = []
    api.assets.mockResolvedValue(rows)
    api.project.mockImplementation(async () => ({ ...detail, assets: members }))
    api.reviews.mockResolvedValue([])
    api.comparison.mockResolvedValue({
      ...comparison,
      status: "not_available",
      not_available_reason: "need_two_recordings",
      tracks: [],
      pairs: [],
      spectral_distances: [],
      panel: null,
    })
    api.addMember.mockImplementation(async (_projectId: string, assetId: string) => {
      if (assetId === "bad") {
        throw new Error("rejected")
      }
      const found = rows.find((item) => item.id === assetId)
      if (found) {
        members = [...members, found.id === "fresh" || found.id === "silent" ? { ...found, analysis_status: "queued" } : found]
      }
      return { asset_id: assetId, ordering: members.length }
    })
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    await openPicker()
    await screen.findByRole("checkbox", { name: /silent\.wav/ })
    fireEvent.click(screen.getByRole("button", { name: "Select all visible" }))
    fireEvent.click(screen.getByRole("button", { name: "Clear selection" }))
    expect(screen.getByText("0 selected.")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Select all visible" }))
    fireEvent.click(screen.getByRole("button", { name: "Add & Queue Analysis" }))
    await screen.findByText("Album recordings 5. Completed analysis 1. Queued 3. Running 1. Failed 0. Not yet analyzed 0.")
    expect(api.addMember.mock.calls.map((call) => call[1])).toEqual(["done", "wait", "busy", "fresh", "bad", "silent"])
    expect(api.analyze.mock.calls.map((call) => call[0])).toEqual(["fresh", "silent"])
    expect(screen.getByRole("alert").textContent).toContain("Failed: bad.wav")
    expect(screen.getByRole("alert").textContent).toContain("Submission is not completed analysis.")
    expect(screen.getByText(/Reused completed analysis for 1/)).toBeTruthy()
    expect(screen.getByText(/Left queued or running: wait\.wav, busy\.wav/)).toBeTruthy()
    expect((screen.getByRole("checkbox", { name: /silent\.wav/ }) as HTMLInputElement).disabled).toBe(true)
    await openTab("Recordings")
    expect(screen.getAllByText("silent.wav").length).toBeGreaterThan(1)
    expect((screen.getByRole("checkbox", { name: /bad\.wav/ }) as HTMLInputElement).disabled).toBe(false)
    expect(api.createAlbumExport).not.toHaveBeenCalled()
    expect(api.saveReview).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole("button", { name: "Add & Queue Analysis" }))
    await waitFor(() => expect(api.addMember).toHaveBeenCalledTimes(7))
    expect(api.analyze).toHaveBeenCalledTimes(2)
  })

  it("analyzes album recordings that are missing and retries failed ones", async () => {
    const rows = [named("fresh", "not_run"), named("bad", "failed"), named("done", "completed"), named("wait", "queued")]
    api.assets.mockResolvedValue(rows)
    api.project.mockResolvedValue({ ...detail, assets: rows })
    api.reviews.mockResolvedValue([])
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    expect(await screen.findByText(/Not yet analyzed 1/)).toBeTruthy()
    await openTab("Recordings")
    expect(within(screen.getByRole("tabpanel", { name: "Recordings" })).getByText("fresh.wav")).toBeTruthy()
    await openTab("Overview")
    fireEvent.click(screen.getByRole("button", { name: "Analyze Missing" }))
    await screen.findByText(/Submitted 1 analysis jobs/)
    expect(api.analyze).toHaveBeenCalledWith("fresh")
    fireEvent.click(screen.getByRole("button", { name: "Retry failed" }))
    await waitFor(() => expect(api.analyze).toHaveBeenCalledTimes(2))
    expect(api.analyze).toHaveBeenLastCalledWith("bad")
    expect(api.addMember).not.toHaveBeenCalled()
  })

  it("loads the current job status again after leaving the album", async () => {
    const queued = named("q", "queued")
    api.assets.mockResolvedValue([queued])
    api.project.mockResolvedValue({ ...detail, assets: [queued] })
    api.reviews.mockResolvedValue([])
    const view = render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    expect(await screen.findByText(/Queued 1/)).toBeTruthy()
    view.unmount()
    const running = named("q", "running")
    api.assets.mockResolvedValue([running])
    api.project.mockResolvedValue({ ...detail, assets: [running] })
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    expect(await screen.findByText(/Running 1/)).toBeTruthy()
    expect(screen.getByText(/submitted jobs, not finished measurements/)).toBeTruthy()
  })

  it("keeps selections that the filename or study filter hides", async () => {
    const first = named("one")
    const second = named("two")
    const other = named("three")
    api.assets.mockResolvedValue([first, second, other])
    api.projects.mockResolvedValue([
      {
        id: "study-1",
        name: "Night study",
        mode: "study",
        created_at: "2026-11-11T00:00:00Z",
        updated_at: "2026-11-11T00:00:00Z",
      },
    ])
    api.project.mockImplementation(async (id: string) => {
      if (id === "study-1") {
        return {
          id: "study-1",
          name: "Night study",
          mode: "study",
          created_at: "2026-11-11T00:00:00Z",
          updated_at: "2026-11-11T00:00:00Z",
          assets: [first],
        }
      }
      return { ...detail, assets: [] }
    })
    api.reviews.mockResolvedValue([])
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    const dialog = await openPicker()
    await waitFor(() => expect(api.project).toHaveBeenCalledWith("study-1"))
    fireEvent.click(await screen.findByRole("checkbox", { name: /three\.wav/ }))
    fireEvent.change(screen.getByRole("searchbox", { name: "Filename" }), { target: { value: "one" } })
    expect(screen.queryByRole("checkbox", { name: /three\.wav/ })).toBeNull()
    expect(screen.getByText("1 selected. 1 selected recording is hidden by this filter.")).toBeTruthy()
    fireEvent.click(screen.getByRole("checkbox", { name: /one\.wav/ }))
    fireEvent.click(screen.getByRole("button", { name: "Select all visible" }))
    fireEvent.change(screen.getByRole("searchbox", { name: "Filename" }), { target: { value: "" } })
    expect((screen.getByRole("checkbox", { name: /three\.wav/ }) as HTMLInputElement).checked).toBe(true)
    expect((screen.getByRole("checkbox", { name: /one\.wav/ }) as HTMLInputElement).checked).toBe(true)
    fireEvent.change(within(dialog).getByLabelText("Study"), { target: { value: "study-1" } })
    expect(screen.getByText("2 selected. 1 selected recording is hidden by this filter.")).toBeTruthy()
    expect(screen.queryByRole("checkbox", { name: /three\.wav/ })).toBeNull()
    fireEvent.click(within(dialog).getByRole("button", { name: /^Add$/ }))
    await waitFor(() => expect(api.addMember).toHaveBeenCalledTimes(2))
    expect(api.addMember.mock.calls.map((call) => call[1])).toEqual(["one", "three"])
  })

  it("traps keyboard focus in the recording dialog and restores it on close", async () => {
    render(<AlbumWorkspace projectId="album-1" onInspect={() => undefined} />)
    const opener = await screen.findByRole("button", { name: "Add recordings" })
    opener.focus()
    fireEvent.click(opener)
    const dialog = await screen.findByRole("dialog", { name: "Add recordings" })
    const search = screen.getByRole("searchbox", { name: "Filename" })
    const close = within(dialog).getByRole("button", { name: "Close" })
    expect(document.activeElement).toBe(search)
    fireEvent.keyDown(document, { key: "Tab", shiftKey: true })
    expect(document.activeElement).toBe(close)
    fireEvent.keyDown(document, { key: "Tab" })
    expect(document.activeElement).toBe(search)
    fireEvent.keyDown(document, { key: "Escape" })
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull())
    expect(document.activeElement).toBe(opener)
  })
})
