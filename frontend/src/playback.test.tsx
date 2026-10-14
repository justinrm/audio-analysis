import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { ChartDocument } from "./api/types"
import { Analyzer } from "./analyzer"

const created: number[] = []
const chartCalls: Record<string, unknown>[] = []
let onTime: ((seconds: number) => void) | undefined

vi.mock("wavesurfer.js", () => ({
  default: {
    create() {
      created.push(1)
      return {
        on(name: string, handler: (seconds: number) => void) {
          if (name === "timeupdate") {
            onTime = handler
          }
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
    onTime = undefined
  })

  it("keeps the player mounted and moves the chart playhead", async () => {
    render(<Analyzer assetId="a" />)
    await screen.findByRole("button", { name: "Play" })
    await waitFor(() => expect(created).toEqual([1]))
    await screen.findByRole("img", { name: "T01" })
    onTime?.(1.5)
    await waitFor(() => {
      const moved = [...chartCalls].reverse().find((option) => !option.xAxis)
      const series = moved?.series as { markLine?: { data?: { xAxis?: number }[] } }[]
      expect(series?.[0]?.markLine?.data?.[0]?.xAxis).toBe(1.5)
    })
    fireEvent.click(screen.getByRole("button", { name: /T02/ }))
    await screen.findByRole("img", { name: "T02" })
    expect(created).toEqual([1])
  })
})
