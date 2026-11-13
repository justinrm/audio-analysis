import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { ChartDocument } from "./api/types"
import { Analyzer } from "./analyzer"

const created: number[] = []
const chartCalls: Record<string, unknown>[] = []
const sought: number[] = []
const heights: number[] = []
let onTime: ((seconds: number) => void) | undefined

vi.mock("wavesurfer.js", () => ({
  default: {
    create() {
      created.push(1)
      const handlers = new Map<string, () => void>()
      return {
        on(name: string, handler: (seconds: number) => void) {
          if (name === "timeupdate") {
            onTime = handler
          }
          handlers.set(name, handler as () => void)
          return () => undefined
        },
        destroy() {},
        playPause() {
          handlers.get("play")?.()
        },
        setTime(seconds: number) {
          sought.push(seconds)
        },
        setVolume() {},
        setOptions(options: { height: number }) {
          heights.push(options.height)
        },
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
    setOption(option: Record<string, unknown>) {
      chartCalls.push(option)
    },
    on() {},
    getZr: () => ({ on() {} }),
    resize() {},
    dispose() {},
  }),
}))

vi.mock("./api/client", () => ({
  streamUrl: () => "/api/assets/a/stream",
  api: {
    asset: async () => ({
      id: "a",
      sha256: "abc",
      original_name: "tone",
      byte_length: 10,
      duration_s: 1,
      sample_rate: 8000,
      channels: 1,
      subtype: "pcm_16",
      analysis_status: "completed",
      playback_status: "ready",
      created_at: "",
    }),
    peaks: async () => ({
      duration_s: 1,
      sample_rate: 8000,
      channels: 1,
      method_id: "playback",
      buckets: [{ min: -0.2, max: 0.2 }],
    }),
    charts: async () => ({ charts: [] }),
    chart: async (_id: string, kind: string): Promise<ChartDocument> => ({
      chart_kind: kind,
      status: "ready",
      title: kind,
      evidence_class: "measured",
      method_id: "m",
      method_version: "m1-v3",
      caveats: [],
      summary: [],
      series: {
        lines: [{ name: "Level", unit: "dBFS", x: [0, 1], y: [-12, -6] }],
        bars: [],
        heatmap: null,
      },
      axis_definitions: { x: "Time (s)", y: "dBFS", y_scale: "linear" },
      review_markers: [],
    }),
  },
}))

vi.stubGlobal(
  "ResizeObserver",
  class {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
)

describe("playback cursor", () => {
  beforeEach(() => {
    created.length = 0
    chartCalls.length = 0
    sought.length = 0
    heights.length = 0
    onTime = undefined
  })

  it("keeps the player mounted and moves the chart playhead", async () => {
    render(<Analyzer assetId="a" />)
    const play = await screen.findByRole("button", { name: "Play" })
    expect(play.closest(".recording-transport")).toBeTruthy()
    expect(play.closest(".study")).toBeNull()
    await waitFor(() => expect(created).toEqual([1]))
    await screen.findByRole("img", { name: "T01" })
    onTime?.(1.5)
    await waitFor(() => {
      const moved = [...chartCalls].reverse().find((option) => !option.xAxis)
      const series = moved?.series as { markLine?: { data?: { xAxis?: number }[] } }[]
      expect(series?.[0]?.markLine?.data?.[0]?.xAxis).toBe(1.5)
    })
    expect(screen.getByRole("combobox", { name: "Chart" }).closest(".study")).toBeTruthy()
    fireEvent.change(screen.getByRole("combobox", { name: "Chart" }), { target: { value: "T02" } })
    await screen.findByRole("img", { name: "T02" })
    expect(created).toEqual([1])
  })

  it("expands the waveform without remounting playback or hiding other actions", async () => {
    render(<Analyzer assetId="a" />)
    const play = await screen.findByRole("button", { name: "Play" })
    await waitFor(() => expect(created).toEqual([1]))
    const waveform = screen.getByRole("button", { name: "Waveform" })
    expect(waveform.getAttribute("aria-expanded")).toBe("false")
    expect(waveform.getAttribute("aria-controls")).toBe("recording-waveform")
    expect(screen.getByRole("button", { name: "Analyze" })).toBeTruthy()
    expect(screen.getByRole("button", { name: "Export controls" }).getAttribute("aria-expanded")).toBe("false")
    expect(screen.queryByRole("button", { name: "Export Technical ZIP" })).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: "Export controls" }))
    expect(screen.getByRole("button", { name: "Export Technical ZIP" })).toBeTruthy()
    fireEvent.click(play)
    expect(screen.getByRole("button", { name: "Pause" })).toBeTruthy()
    const drawn = heights.length
    expect(document.getElementById("recording-waveform")?.hasAttribute("hidden")).toBe(true)
    fireEvent.click(waveform)
    expect(waveform.getAttribute("aria-expanded")).toBe("true")
    expect(document.getElementById("recording-waveform")?.hasAttribute("hidden")).toBe(false)
    expect(screen.getByRole("button", { name: "Export Technical ZIP" })).toBeTruthy()
    expect(screen.getByRole("button", { name: "Pause" })).toBeTruthy()
    fireEvent.change(screen.getByRole("slider", { name: "Seek" }), { target: { value: "0.4" } })
    expect(sought).toEqual([0.4])
    expect(created).toEqual([1])
    expect(heights.length).toBe(drawn + 1)
    fireEvent.change(screen.getByRole("combobox", { name: "Chart" }), { target: { value: "T02" } })
    await screen.findByRole("img", { name: "T02" })
    fireEvent.click(screen.getByRole("button", { name: "Details" }))
    fireEvent.click(screen.getByRole("button", { name: "Evidence" }))
    fireEvent.click(waveform)
    expect(screen.getByRole("button", { name: "Pause" })).toBeTruthy()
    expect(created).toEqual([1])
  })
})
