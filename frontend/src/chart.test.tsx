import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import type { ChartDocument } from "./api/types"
import { ChartView } from "./chart"

const plotted: {
  calls: Record<string, unknown>[]
  inits: number
  events: Record<string, (event?: { start?: number; end?: number }) => void>
  click?: (event: { offsetX: number; offsetY: number }) => void
  point: number[]
} = { calls: [], inits: 0, events: {}, point: [0, 0] }

function chartOption(): Record<string, unknown> {
  const option = [...plotted.calls].reverse().find((item) => item.xAxis)
  if (!option) {
    throw new Error("chart option was not set")
  }
  return option
}

vi.mock("echarts", () => ({
  init: () => {
    plotted.inits += 1
    return {
      setOption(option: Record<string, unknown>) {
        plotted.calls.push(option)
      },
      getZr: () => ({
        on(name: string, handler: (event: { offsetX: number; offsetY: number }) => void) {
          if (name === "click") {
            plotted.click = handler
          }
        },
      }),
      containPixel({ seriesIndex }: { seriesIndex: number }) {
        return seriesIndex === 0
      },
      convertFromPixel() {
        return plotted.point
      },
      getOption() {
        return plotted.calls.find((option) => option.xAxis) ?? {}
      },
      on(name: string, handler: (event?: { start?: number; end?: number }) => void) {
        plotted.events[name] = handler
      },
      resize() {},
      dispose() {},
    }
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

const waveform: ChartDocument = {
  chart_kind: "T01",
  status: "ready",
  title: "Waveform and peak envelope",
  evidence_class: "measured",
  method_id: "frame-rms+master-minmax-envelope-v1",
  method_version: "m1-v3",
  caveats: [],
  summary: [],
  series: {
    lines: [
      { name: "Envelope max", unit: "amplitude", x: [0.1, 0.2], y: [0.2, 0.9] },
      { name: "Envelope min", unit: "amplitude", x: [0.1, 0.2], y: [-0.2, -0.4] },
      { name: "100 ms RMS", unit: "dBFS", x: [0.1, 0.2], y: [-80, -6] },
      { name: "1 s RMS", unit: "dBFS", x: [0.5], y: [-12] },
    ],
    bars: [],
    heatmap: null,
  },
  axis_definitions: { x: "Time (s)", y: "Normalized amplitude", y_scale: "linear" },
  review_markers: [
    {
      time_s: 1.25,
      kind: "sample_peak",
      label: "sample peak channel 1",
      value: "-0.01 dBFS",
      caveat: "Exact sample on the master.",
    },
  ],
}

const spectral: ChartDocument = {
  chart_kind: "T04",
  status: "ready",
  title: "Spectrogram",
  evidence_class: "measured",
  method_id: "stft-peak",
  method_version: "m1-v3",
  caveats: [],
  summary: [],
  series: {
    lines: [
      { name: "bass", unit: "dB rel. median", x: [0, 2, 4], y: [-3, -1, -2] },
      { name: "air", unit: "dB rel. median", x: [0, 2, 4], y: [-20, -18, -19] },
    ],
    bars: [],
    heatmap: {
      x: [0, 2, 4],
      y: [100, 1000],
      z: [
        [1, 2, 3],
        [0, 1, 0],
      ],
    },
  },
  axis_definitions: { x: "Time (s)", y: "Frequency (Hz)", y_scale: "linear" },
  review_markers: [],
}

const recurrence: ChartDocument = {
  chart_kind: "T09",
  status: "ready",
  title: "Recurrence and self-similarity",
  evidence_class: "estimated",
  method_id: "spectral-shape-cosine-v1",
  method_version: "m1-v3",
  caveats: [],
  summary: [],
  series: {
    lines: [],
    bars: [],
    heatmap: {
      x: [1, 3, 5],
      y: [1, 3, 5],
      z: [
        [1, 0, 0],
        [0, 1, 0],
        [0, 0, 1],
      ],
    },
  },
  axis_definitions: { x: "Time (s)", y: "Time (s)", y_scale: "linear" },
  review_markers: [],
}

const pulse: ChartDocument = {
  chart_kind: "T06",
  status: "ready",
  title: "Rhythm and pulse evidence",
  evidence_class: "estimated",
  method_id: "onset-autocorr-v1",
  method_version: "m1-v3",
  caveats: [],
  summary: [],
  series: {
    lines: [{ name: "Onset strength", unit: "score", x: [0, 1], y: [0.2, 0.4] }],
    bars: [
      { label: "120.0 BPM", value: 0.8 },
      { label: "60.0 BPM (half-time)", value: 0.3 },
    ],
    heatmap: null,
  },
  axis_definitions: { x: "Time (s)", y: "Onset strength", y_scale: "linear" },
  review_markers: [],
}

const ending: ChartDocument = {
  chart_kind: "T10",
  status: "ready",
  title: "Ending, gap, and anomaly review",
  evidence_class: "measured",
  method_id: "tail",
  method_version: "m1-v3",
  caveats: [],
  summary: [],
  series: {
    lines: [],
    bars: [{ label: "last 50 ms RMS", value: -40 }],
    heatmap: null,
  },
  axis_definitions: { x: "Last milliseconds", y: "dBFS", y_scale: "linear" },
  review_markers: [
    {
      time_s: 4.5,
      kind: "reconstructed_peak",
      label: "4x reconstructed peak",
      value: "-1.2 dBTP",
    },
  ],
}

function resetPlot() {
  plotted.calls = []
  plotted.inits = 0
  plotted.events = {}
  plotted.click = undefined
  plotted.point = [0, 0]
}

describe("T01 panels", () => {
  it("keeps amplitude and dBFS on separate axes with one zoom and the peak marker", () => {
    const seen: number[] = []
    resetPlot()
    render(<ChartView chart={waveform} onSeek={(seconds) => seen.push(seconds)} />)
    const option = chartOption()
    const yAxis = option.yAxis as { name?: string }[]
    expect(yAxis.map((axis) => axis.name)).toEqual(["Normalized amplitude", "dBFS"])
    const series = option.series as {
      name?: string
      yAxisIndex?: number
      markLine?: { data?: { xAxis?: number }[] }
    }[]
    expect(series.filter((item) => item.name?.startsWith("Envelope")).every((item) => item.yAxisIndex === 0)).toBe(
      true,
    )
    expect(series.filter((item) => item.name?.includes("RMS")).every((item) => item.yAxisIndex === 1)).toBe(true)
    const marked = series.filter((item) => item.markLine)
    expect(marked.map((item) => item.yAxisIndex)).toEqual([0, 1])
    expect(marked.every((item) => item.markLine?.data?.[0]?.xAxis === 1.25)).toBe(true)
    const zoom = option.dataZoom as { xAxisIndex?: number | number[] }[]
    expect(zoom[0]?.xAxisIndex).toEqual([0, 1])
    expect(zoom[1]?.xAxisIndex).toEqual([0, 1])
    expect(screen.getByRole("img", { name: "Waveform and peak envelope" }).className).toContain("stacked")
    fireEvent.click(screen.getByRole("button", { name: /sample peak/i }))
    expect(seen).toEqual([1.25])
  })

  it("draws the coarser envelope until the time window is zoomed", () => {
    const switched: ChartDocument = {
      ...waveform,
      series: {
        ...waveform.series,
        lines: [
          { name: "Envelope max", unit: "amplitude", x: [0.1, 0.2, 0.3], y: [0.2, 0.9, 0.4] },
          { name: "Envelope min", unit: "amplitude", x: [0.1, 0.2, 0.3], y: [-0.2, -0.4, -0.1] },
          { name: "Overview envelope max", unit: "amplitude", x: [0.2], y: [0.9] },
          { name: "Overview envelope min", unit: "amplitude", x: [0.2], y: [-0.4] },
          { name: "100 ms RMS", unit: "dBFS", x: [0.1], y: [-12] },
        ],
      },
    }
    resetPlot()
    render(<ChartView chart={switched} onSeek={() => undefined} />)
    const selected = (chartOption().legend as { selected?: Record<string, boolean> }).selected
    expect(selected?.["Overview envelope max"]).toBe(true)
    expect(selected?.["Envelope max"]).toBe(false)
    plotted.events.datazoom?.({ start: 10, end: 40 })
    const zoomed = plotted.calls.at(-1)?.legend as { selected?: Record<string, boolean> }
    expect(zoomed.selected?.["Envelope max"]).toBe(true)
    expect(zoomed.selected?.["Overview envelope max"]).toBe(false)
    plotted.events.datazoom?.({ start: 0, end: 100 })
    const restored = plotted.calls.at(-1)?.legend as { selected?: Record<string, boolean> }
    expect(restored.selected?.["Envelope max"]).toBe(false)
    expect(restored.selected?.["Overview envelope max"]).toBe(true)
  })
})

describe("shared playback cursor", () => {
  it("moves a playhead on file-time axes without rebuilding the chart", () => {
    resetPlot()
    const seen: number[] = []
    const view = render(<ChartView chart={waveform} playhead={1} onSeek={(seconds) => seen.push(seconds)} />)
    const inits = plotted.inits
    const cursor = plotted.calls.filter((option) => !option.xAxis)
    const series = cursor.at(-1)?.series as { id?: string; markLine?: { lineStyle?: { type?: string }; data?: { xAxis?: number }[] } }[]
    expect(series?.map((item) => item.id)).toEqual(["playback-playhead-0-0", "playback-playhead-1-1"])
    expect(series?.every((item) => item.markLine?.lineStyle?.type === "solid")).toBe(true)
    expect(series?.every((item) => item.markLine?.data?.[0]?.xAxis === 1)).toBe(true)
    const review = (chartOption().series as { markLine?: { lineStyle?: { type?: string } } }[]).filter(
      (item) => item.markLine?.lineStyle?.type === "dashed",
    )
    expect(review.length).toBeGreaterThan(0)
    view.rerender(<ChartView chart={waveform} playhead={2.5} onSeek={(seconds) => seen.push(seconds)} />)
    expect(plotted.inits).toBe(inits)
    const moved = plotted.calls.at(-1)?.series as { markLine?: { data?: { xAxis?: number }[] } }[]
    expect(moved.every((item) => item.markLine?.data?.[0]?.xAxis === 2.5)).toBe(true)
  })

  it("does not place a file-time playhead on the ending axis", () => {
    resetPlot()
    render(<ChartView chart={ending} playhead={4.5} onSeek={() => undefined} />)
    const series = chartOption().series as { id?: string; markLine?: unknown }[]
    expect(series.some((item) => String(item.id).startsWith("playback-playhead"))).toBe(false)
    expect(series.some((item) => item.markLine)).toBe(false)
  })
})

describe("synchronized zoom", () => {
  it("keeps the spectrogram and its band traces on one time window", () => {
    resetPlot()
    render(<ChartView chart={spectral} onSeek={() => undefined} />)
    const option = chartOption()
    const zoom = option.dataZoom as { xAxisIndex?: number | number[]; yAxisIndex?: number | number[] }[]
    expect(zoom[0]?.xAxisIndex).toEqual([0, 1])
    expect(zoom[1]?.xAxisIndex).toEqual([0, 1])
    expect(zoom[0]?.yAxisIndex).toBeUndefined()
    const xAxis = option.xAxis as { min?: number; max?: number; name?: string }[]
    const step = (4 - 0) / 2
    expect(xAxis[1]?.min).toBeCloseTo(0 - step / 2)
    expect(xAxis[1]?.max).toBeCloseTo(4 + step / 2)
    expect(xAxis.every((axis) => axis.name === "Time (s)")).toBe(true)
    const yAxis = option.yAxis as { name?: string; data?: string[] }[]
    expect(yAxis[0]?.name).toBe("Frequency (Hz)")
    expect(yAxis[0]?.data).toEqual(["100", "1000"])
  })

  it("seeks a spectrogram click to the bin time, not the fractional index", () => {
    resetPlot()
    const seen: number[] = []
    render(<ChartView chart={spectral} onSeek={(seconds) => seen.push(seconds)} />)
    plotted.point = [1.6, 0]
    plotted.click?.({ offsetX: 4, offsetY: 4 })
    expect(seen).toEqual([4])
  })

  it("zooms both axes of the similarity matrix across the same times", () => {
    resetPlot()
    render(<ChartView chart={recurrence} onSeek={() => undefined} />)
    const option = chartOption()
    const zoom = option.dataZoom as { xAxisIndex?: number | number[]; yAxisIndex?: number | number[] }[]
    expect(zoom[0]?.xAxisIndex).toEqual(0)
    expect(zoom[0]?.yAxisIndex).toEqual(0)
    expect(zoom[1]?.xAxisIndex).toEqual(0)
    expect(zoom[1]?.yAxisIndex).toEqual(0)
    const xAxis = option.xAxis as { data?: string[]; name?: string }[]
    const yAxis = option.yAxis as { data?: string[]; name?: string }[]
    expect(xAxis[0]?.name).toBe("Time (s)")
    expect(yAxis[0]?.name).toBe("Time (s)")
    expect(xAxis[0]?.data).toEqual(["1.0", "3.0", "5.0"])
    expect(yAxis[0]?.data).toEqual(xAxis[0]?.data)
  })
})

describe("T06 candidate labels", () => {
  it("names the bar axis for autocorrelation and keeps the playhead off the tempo bars", () => {
    resetPlot()
    render(<ChartView chart={pulse} playhead={0.4} onSeek={() => undefined} />)
    const option = chartOption()
    const yAxis = option.yAxis as { name?: string }[]
    expect(yAxis.map((axis) => axis.name)).toEqual(["Onset strength", "Autocorrelation"])
    const series = (option.series as { id?: string; xAxisIndex?: number }[]).filter((item) =>
      String(item.id).startsWith("playback-playhead"),
    )
    expect(series.map((item) => item.xAxisIndex)).toEqual([0])
  })
})
