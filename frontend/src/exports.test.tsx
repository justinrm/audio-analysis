import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ApiError } from "./api/client"
import type { LyricDocumentOut } from "./api/types"
import { Analyzer } from "./analyzer"

const api = vi.hoisted(() => ({
  asset: vi.fn(),
  peaks: vi.fn(),
  charts: vi.fn(),
  chart: vi.fn(),
  lyrics: vi.fn(),
  annotations: vi.fn(),
  lyricCharts: vi.fn(),
  lyricChart: vi.fn(),
  updateSegment: vi.fn(),
  createExport: vi.fn(),
  downloadExport: vi.fn(),
}))

vi.mock("./api/client", () => ({
  streamUrl: () => "/api/assets/a/stream",
  lyricSourceUrl: () => "/api/lyrics/source",
  ApiError: class ApiError extends Error {
    status: number
    code: string
    constructor(message: string, status: number, code: string) {
      super(message)
      this.status = status
      this.code = code
    }
  },
  api,
}))

vi.mock("wavesurfer.js", () => ({
  default: {
    create() {
      return {
        on() {
          return () => undefined
        },
        destroy() {},
        playPause() {},
        setTime() {},
        setVolume() {},
        registerPlugin() {
          return {
            on() {
              return () => undefined
            },
            clearRegions() {},
            addRegion() {
              return { setOptions() {}, remove() {} }
            },
            getRegions() {
              return []
            },
          }
        },
      }
    },
  },
}))

vi.mock("echarts", () => ({
  init: () => ({
    setOption() {},
    on() {},
    getZr: () => ({ on() {} }),
    resize() {},
    dispose() {},
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

function lyricDocument(): LyricDocumentOut {
  return {
    id: "doc",
    project_id: "p",
    asset_id: "a",
    upload_id: "up",
    source_kind: "srt",
    source_sha256: "ab".repeat(32),
    original_name: "song.srt",
    revision: 1,
    segments: [
      {
        id: "s",
        ordinal: 0,
        source_cue: "1",
        text: "keep",
        start_s: 0,
        end_s: 1,
        timing_origin: "subtitle_supplied",
        artist_verified: false,
        usable: true,
        note: "",
      },
    ],
    validation: [],
  }
}

describe("recording exports", () => {
  beforeEach(() => {
    api.asset.mockResolvedValue({
      id: "a",
      sha256: "abc",
      original_name: "tone",
      byte_length: 10,
      duration_s: 3,
      sample_rate: 8000,
      channels: 1,
      subtype: "pcm_16",
      analysis_status: "completed",
      playback_status: "ready",
      created_at: "",
    })
    api.peaks.mockResolvedValue({
      duration_s: 3,
      sample_rate: 8000,
      channels: 1,
      method_id: "playback",
      buckets: [{ min: -0.2, max: 0.2 }],
    })
    api.charts.mockResolvedValue({ charts: [] })
    api.chart.mockResolvedValue({
      chart_kind: "T01",
      status: "not_run",
      title: "T01",
      evidence_class: "unknown",
      method_id: "none",
      method_version: "m1-v3",
      caveats: [],
      summary: [],
      series: { lines: [], bars: [], heatmap: null },
      axis_definitions: { x: "Time (s)", y: "", y_scale: "linear" },
      review_markers: [],
    })
    api.annotations.mockResolvedValue([])
    api.lyricCharts.mockResolvedValue({ charts: [] })
    api.lyricChart.mockResolvedValue({
      chart_kind: "L01",
      status: "not_available",
      title: "Unified music-and-lyrics timeline",
      evidence_class: "unknown",
      method_id: "lyrics-v1",
      method_version: "lyrics-v1",
      analysis_version: null,
      lyric_document_id: null,
      lyric_revision: null,
      caveats: [],
      summary: [],
      series: { lines: [], bars: [], heatmap: null },
      axis_definitions: { x: "", y: "", y_scale: "linear" },
      review_markers: [],
      regions: [],
      rows: [],
      insufficient: [],
      not_available_reason: "No lyric document is attached.",
    })
    api.lyrics.mockRejectedValue(new ApiError("No lyric document is attached.", 404, "no_lyrics"))
    api.createExport.mockReset()
    api.createExport.mockResolvedValue({ export_id: "exp-1" })
    api.downloadExport.mockReset()
    api.downloadExport.mockResolvedValue(undefined)
    api.updateSegment.mockReset()
  })

  it("offers three exports and does not send a lyricist export without a document", async () => {
    render(<Analyzer assetId="a" projectId="p" />)
    const technical = await screen.findByRole("button", { name: "Export Technical ZIP" })
    const lyricist = screen.getByRole("button", { name: "Export Lyricist ZIP" })
    const combined = screen.getByRole("button", { name: "Export Combined ZIP" })
    expect(technical).toBeTruthy()
    await waitFor(() => expect((lyricist as HTMLButtonElement).disabled).toBe(true))
    expect((combined as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(/Attach a lyric document/)).toBeTruthy()
    fireEvent.click(lyricist)
    fireEvent.click(combined)
    expect(api.createExport).not.toHaveBeenCalled()
    fireEvent.click(technical)
    await waitFor(() => expect(api.downloadExport).toHaveBeenCalledTimes(1))
    expect(api.createExport).toHaveBeenCalledWith("p", "a", { profile: "technical", lyrics: "summarized" })
    expect(api.downloadExport).toHaveBeenCalledWith("p", "a", "exp-1", "technical-exp-1.zip")
  })

  it("sends the selected lyric mode for a lyricist package", async () => {
    api.lyrics.mockResolvedValue(lyricDocument())
    api.createExport.mockResolvedValue({ export_id: "exp-2" })
    render(<Analyzer assetId="a" projectId="p" />)
    const lyricist = await screen.findByRole("button", { name: "Export Lyricist ZIP" })
    await waitFor(() => expect((lyricist as HTMLButtonElement).disabled).toBe(false))
    fireEvent.change(screen.getByLabelText("Lyric text in export"), { target: { value: "included" } })
    fireEvent.click(lyricist)
    await waitFor(() =>
      expect(api.createExport).toHaveBeenCalledWith("p", "a", { profile: "lyricist", lyrics: "included" }),
    )
    fireEvent.click(screen.getByRole("button", { name: "Export Combined ZIP" }))
    await waitFor(() =>
      expect(api.createExport).toHaveBeenCalledWith("p", "a", { profile: "combined", lyrics: "included" }),
    )
  })

  it("shows an export failure without changing an unsaved lyric draft", async () => {
    api.lyrics.mockResolvedValue(lyricDocument())
    api.createExport.mockRejectedValue(new ApiError("The export was not published.", 500, "export_failed"))
    render(<Analyzer assetId="a" projectId="p" />)
    await screen.findByRole("button", { name: "Play" })
    fireEvent.click(screen.getByRole("tab", { name: "Lyrics & Inspiration" }))
    const line = await screen.findByLabelText("Text for Cue 1")
    fireEvent.change(line, { target: { value: "unsaved line" } })
    fireEvent.click(screen.getByRole("button", { name: "Export Technical ZIP" }))
    expect((await screen.findByRole("alert")).textContent).toContain("The export was not published.")
    expect((screen.getByLabelText("Text for Cue 1") as HTMLTextAreaElement).value).toBe("unsaved line")
    expect(api.updateSegment).not.toHaveBeenCalled()
    expect(api.downloadExport).not.toHaveBeenCalled()
    expect(screen.getByRole("button", { name: "Play" })).toBeTruthy()
  })

  it("disables exports when the recording is not open from a study", async () => {
    render(<Analyzer assetId="a" />)
    const technical = await screen.findByRole("button", { name: "Export Technical ZIP" })
    expect((technical as HTMLButtonElement).disabled).toBe(true)
    expect((screen.getByRole("button", { name: "Export Lyricist ZIP" }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText(/Open this recording from a study/)).toBeTruthy()
    expect(api.lyrics).not.toHaveBeenCalled()
  })
})
