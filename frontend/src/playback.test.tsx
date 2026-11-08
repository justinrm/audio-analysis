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
    expect(play.closest(".deck")).toBeTruthy()
    expect(play.closest(".study")).toBeNull()
    await waitFor(() => expect(created).toEqual([1]))
    await screen.findByRole("img", { name: "T01" })
    onTime?.(1.5)
    await waitFor(() => {
      const moved = [...chartCalls].reverse().find((option) => !option.xAxis)
      const series = moved?.series as { markLine?: { data?: { xAxis?: number }[] } }[]
      expect(series?.[0]?.markLine?.data?.[0]?.xAxis).toBe(1.5)
    })
    expect(screen.getByRole("button", { name: /T01/ }).closest(".study")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: /T02/ }))
    await screen.findByRole("img", { name: "T02" })
    expect(created).toEqual([1])
  })

  it("collapses and restores the deck without remounting playback", async () => {
    render(<Analyzer assetId="a" />)
    const play = await screen.findByRole("button", { name: "Play" })
    await waitFor(() => expect(created).toEqual([1]))
    const toggle = screen.getByRole("button", { name: "Compact player" })
    expect(toggle.getAttribute("aria-expanded")).toBe("true")
    expect(toggle.getAttribute("aria-controls")).toBe("recording-details")
    expect(screen.getByRole("button", { name: "Export Technical ZIP" })).toBeTruthy()
    fireEvent.click(play)
    expect(screen.getByRole("button", { name: "Pause" })).toBeTruthy()
    const drawn = heights.length
    fireEvent.click(toggle)
    const expand = screen.getByRole("button", { name: "Expand recording" })
    expect(expand.getAttribute("aria-expanded")).toBe("false")
    expect(screen.queryByRole("button", { name: "Export Technical ZIP" })).toBeNull()
    expect(screen.queryByRole("button", { name: "Analyze" })).toBeNull()
    expect(document.querySelector(".wave")?.hasAttribute("hidden")).toBe(true)
    expect(screen.getByRole("button", { name: "Pause" })).toBeTruthy()
    fireEvent.change(screen.getByRole("slider", { name: "Seek" }), { target: { value: "0.4" } })
    expect(sought).toEqual([0.4])
    expect(created).toEqual([1])
    expect(heights.length).toBe(drawn)
    fireEvent.click(screen.getByRole("button", { name: /T02/ }))
    await screen.findByRole("img", { name: "T02" })
    expect(screen.getByRole("button", { name: "Expand recording" })).toBeTruthy()
    expect(created).toEqual([1])
    fireEvent.click(screen.getByRole("button", { name: "Expand recording" }))
    expect(screen.getByRole("button", { name: "Compact player" }).getAttribute("aria-expanded")).toBe("true")
    expect(screen.getByRole("button", { name: "Export Technical ZIP" })).toBeTruthy()
    expect(screen.getByRole("button", { name: "Pause" })).toBeTruthy()
    expect(document.querySelector(".wave")?.hasAttribute("hidden")).toBe(false)
    expect(created).toEqual([1])
    expect(heights.length).toBe(drawn + 1)
  })
})
