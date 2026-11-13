import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { ChartDocument } from "./api/types"
import { App } from "./App"

const api = vi.hoisted(() => ({
  projects: vi.fn(),
  project: vi.fn(),
  createProject: vi.fn(),
  upload: vi.fn(),
  analyze: vi.fn(),
  asset: vi.fn(),
  peaks: vi.fn(),
  charts: vi.fn(),
  chart: vi.fn(),
  lyrics: vi.fn(),
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
        setOptions() {},
        registerPlugin() {
          return { clearRegions() {}, addRegion() {}, getRegions: () => [] }
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
    getOption: () => ({}),
  }),
}))

vi.mock("./api/client", () => ({
  streamUrl: (id: string) => `/api/assets/${id}/stream`,
  api,
}))

vi.stubGlobal(
  "ResizeObserver",
  class {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
)

const chart: ChartDocument = {
  chart_kind: "T01",
  status: "not_run",
  title: "Waveform and peak envelope",
  evidence_class: "measured",
  method_id: "frame",
  method_version: "m1-v3",
  caveats: [],
  summary: [],
  series: { lines: [], bars: [], heatmap: null },
  axis_definitions: { x: "Time (s)", y: "dBFS", y_scale: "linear" },
  review_markers: [],
}

describe("analyzer navigation", () => {
  beforeEach(() => {
    api.projects.mockReset()
    api.project.mockReset()
    api.createProject.mockReset()
    api.upload.mockReset()
    api.analyze.mockReset()
    api.asset.mockReset()
    api.peaks.mockReset()
    api.charts.mockReset()
    api.chart.mockReset()
    api.lyrics.mockReset()
    api.projects.mockResolvedValue([
      { id: "p", name: "Night study", mode: "study", created_at: "", updated_at: "" },
    ])
    api.project.mockResolvedValue({
      id: "p",
      name: "Night study",
      mode: "study",
      created_at: "",
      updated_at: "",
      assets: [
        {
          id: "a",
          sha256: "abc",
          original_name: "night.wav",
          byte_length: 44,
          duration_s: 1,
          sample_rate: 8000,
          channels: 1,
          subtype: "pcm_16",
          analysis_status: "not_run",
          playback_status: "unavailable",
          created_at: "",
        },
      ],
    })
    api.asset.mockResolvedValue({
      id: "a",
      sha256: "abc",
      original_name: "night.wav",
      byte_length: 44,
      duration_s: 1,
      sample_rate: 8000,
      channels: 1,
      subtype: "pcm_16",
      analysis_status: "not_run",
      playback_status: "unavailable",
      created_at: "",
    })
    api.charts.mockResolvedValue({ charts: [] })
    api.chart.mockResolvedValue(chart)
    api.lyrics.mockRejectedValue(new Error("No lyric document is attached."))
    window.history.pushState(null, "", "/analyzer")
  })

  it("opens a study recording and restores the chooser with back and forward", async () => {
    render(<App />)
    fireEvent.click(await screen.findByRole("button", { name: "night.wav" }))
    expect(window.location.pathname).toBe("/analyzer")
    expect(window.location.search).toBe("?asset=a&project=p")
    expect(await screen.findByRole("heading", { name: "night.wav" })).toBeTruthy()
    expect(api.createProject).not.toHaveBeenCalled()
    expect(api.upload).not.toHaveBeenCalled()
    expect(api.analyze).not.toHaveBeenCalled()
    window.history.back()
    await waitFor(() => expect(window.location.search).toBe(""))
    expect(await screen.findByRole("button", { name: "Open Library" })).toBeTruthy()
    window.history.forward()
    await waitFor(() => expect(window.location.search).toBe("?asset=a&project=p"))
    expect(await screen.findByRole("heading", { name: "night.wav" })).toBeTruthy()
  })

  it("keeps an asset-only recording out of a guessed study", async () => {
    window.history.pushState(null, "", "/analyzer?asset=a")
    window.dispatchEvent(new PopStateEvent("popstate"))
    render(<App />)
    expect(await screen.findByRole("heading", { name: "night.wav" })).toBeTruthy()
    expect(screen.getByText(/No study ·/)).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Export controls" }))
    expect(screen.getByText(/Open this recording from a study to export/)).toBeTruthy()
    expect(api.lyrics).not.toHaveBeenCalled()
    expect(api.createProject).not.toHaveBeenCalled()
  })
})
