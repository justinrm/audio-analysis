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
    expect(yAxis[0]?.data).toEqual(["100 Hz", "1 kHz"])
    const map = option.visualMap as { show?: boolean }
    expect(map.show).toBe(true)
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
    expect(xAxis[0]?.data).toEqual(["0:01", "0:03", "0:05"])
    expect(yAxis[0]?.data).toEqual(xAxis[0]?.data)
    expect(xAxis[0]?.data).toHaveLength(3)
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
    const labels = (option.xAxis as { data?: string[] }[])[1]?.data
    expect(labels).toEqual(["120.0 BPM", "60.0 BPM (half-time)"])
  })
})

describe("coordinated presentation", () => {
  it("keeps stored numbers unchanged while formatting the display", () => {
    const snapshot = JSON.stringify(waveform)
    resetPlot()
    render(<ChartView chart={waveform} onSeek={() => undefined} />)
    expect(JSON.stringify(waveform)).toBe(snapshot)
    const series = chartOption().series as { name?: string; data?: [number, number][] }[]
    const rms = series.find((item) => item.name === "100 ms RMS")
    expect(rms?.data).toEqual([
      [0.1, -80],
      [0.2, -6],
    ])
  })

  it("splits dBFS and LUFS onto separate axes without converting values", () => {
    const loudness: ChartDocument = {
      ...waveform,
      chart_kind: "T02",
      title: "Loudness and dynamics",
      series: {
        lines: [
          { name: "1 s RMS", unit: "dBFS", x: [1, 2], y: [-20, -10] },
          { name: "3 s short-term LUFS", unit: "LUFS", x: [1, 2], y: [-16, -9] },
        ],
        bars: [{ label: "0.0–1.0 s", value: 0.4 }],
        heatmap: null,
      },
      axis_definitions: { x: "Time (s)", y: "Relative RMS-power level (dB)", y_scale: "linear" },
    }
    resetPlot()
    render(<ChartView chart={loudness} onSeek={() => undefined} />)
    const yAxis = chartOption().yAxis as { name?: string }[]
    expect(yAxis.map((axis) => axis.name)).toEqual(["dBFS", "LUFS", "Relative RMS-power level (dB)"])
    const series = chartOption().series as { name?: string; data?: [number, number][]; yAxisIndex?: number }[]
    expect(series.find((item) => item.name === "3 s short-term LUFS")?.data).toEqual([
      [1, -16],
      [2, -9],
    ])
    expect(series.find((item) => item.name === "1 s RMS")?.yAxisIndex).toBe(0)
    expect(series.find((item) => item.name === "3 s short-term LUFS")?.yAxisIndex).toBe(1)
    expect(loudness.axis_definitions.y_scale).toBe("linear")
  })

  it("shows the stored Welch samples on a log frequency axis and does not seek", () => {
    const spectrum: ChartDocument = {
      ...waveform,
      chart_kind: "T03",
      title: "Long-term spectral balance",
      series: {
        lines: [{ name: "Welch PSD", unit: "dB", x: [20, 1000, 8000], y: [-80, -40, -20] }],
        bars: [{ label: "20–500 Hz", value: 12.5 }],
        heatmap: null,
      },
      axis_definitions: { x: "Frequency (Hz)", y: "Power share (%)", y_scale: "linear" },
      review_markers: [],
    }
    const snapshot = JSON.stringify(spectrum)
    resetPlot()
    const seen: number[] = []
    render(<ChartView chart={spectrum} onSeek={(seconds) => seen.push(seconds)} />)
    const xAxis = chartOption().xAxis as { type?: string; min?: number; max?: number }[]
    expect(xAxis[0]?.type).toBe("log")
    expect(xAxis[0]?.min).toBe(20)
    expect(xAxis[0]?.max).toBe(8000)
    const series = chartOption().series as { name?: string; data?: [number, number][] }[]
    expect(series.find((item) => item.name === "Welch PSD")?.data).toEqual([
      [20, -80],
      [1000, -40],
      [8000, -20],
    ])
    plotted.point = [1000, -40]
    plotted.click?.({ offsetX: 8, offsetY: 8 })
    expect(seen).toEqual([])
    expect(JSON.stringify(spectrum)).toBe(snapshot)
    expect(spectrum.axis_definitions.y_scale).toBe("linear")
    expect(spectrum.series.lines?.[0]?.unit).toBe("dB")
  })

  it("gives correlation and side/mid their own bounds", () => {
    const stereo: ChartDocument = {
      ...waveform,
      chart_kind: "T05",
      title: "Stereo and mono compatibility",
      series: {
        lines: [
          { name: "1 s correlation", unit: "ratio", x: [0, 1], y: [0.2, 0.9] },
          { name: "1 s side/mid", unit: "dB", x: [0, 1], y: [-30, -4] },
        ],
        bars: [],
        heatmap: null,
      },
      review_markers: [],
    }
    resetPlot()
    render(<ChartView chart={stereo} onSeek={() => undefined} />)
    const yAxis = chartOption().yAxis as { name?: string; min?: number; max?: number }[]
    expect(yAxis.map((axis) => axis.name)).toEqual(["Correlation", "Side/mid (dB)"])
    expect(yAxis[0]?.min).toBe(-1)
    expect(yAxis[0]?.max).toBe(1)
    const series = chartOption().series as { name?: string; data?: [number, number][] }[]
    expect(series.find((item) => item.name === "1 s side/mid")?.data?.[1]).toEqual([1, -4])
  })

  it("keeps pitch-class shares on a 0 to 1 axis", () => {
    const pitch: ChartDocument = {
      ...ending,
      chart_kind: "T07",
      title: "Pitch-class and tonal estimates",
      evidence_class: "estimated",
      series: {
        lines: [],
        bars: [
          { label: "C", value: 0.08 },
          { label: "D", value: 0.1 },
        ],
        heatmap: null,
      },
      axis_definitions: { x: "Pitch class", y: "Share", y_scale: "linear" },
      review_markers: [],
    }
    resetPlot()
    render(<ChartView chart={pitch} onSeek={() => undefined} />)
    const yAxis = chartOption().yAxis as { min?: number; max?: number; name?: string }[]
    expect(yAxis[0]?.name).toBe("Share")
    expect(yAxis[0]?.min).toBe(0)
    expect(yAxis[0]?.max).toBe(1)
    const series = chartOption().series as { data?: number[] }[]
    expect(series[0]?.data).toEqual([0.08, 0.1])
  })

  it("captions the ending chart without drawing checkpoints on the bars", () => {
    resetPlot()
    render(<ChartView chart={ending} onSeek={() => undefined} />)
    expect(screen.getByText(/technical review checkpoints/i)).toBeTruthy()
  })
})

describe("lyric regions", () => {
  it("seeks a timed region and leaves a technical chart without lyric areas", () => {
    resetPlot()
    const seen: number[] = []
    const timeline = {
      ...ending,
      chart_kind: "L01",
      title: "Unified music-and-lyrics timeline",
      evidence_class: "unknown",
      method_id: "lyrics-v1",
      method_version: "lyrics-v1",
      series: {
        lines: [{ name: "1 s RMS", unit: "dBFS", x: [0.5], y: [-12] }],
        bars: [],
        heatmap: null,
      },
      axis_definitions: { x: "Time (s)", y: "dBFS", y_scale: "linear" as const },
      review_markers: [],
      regions: [
        {
          evidence_id: "ly:a",
          segment_id: "a",
          label: "Hello",
          start_s: 0.25,
          end_s: 0.75,
          evidence_class: "textual" as const,
        },
      ],
    }
    render(<ChartView chart={timeline} playhead={0.4} onSeek={(seconds) => seen.push(seconds)} />)
    fireEvent.click(screen.getByRole("button", { name: /Hello/ }))
    expect(seen).toEqual([0.25])
    const series = chartOption().series as { markArea?: { data?: { xAxis?: number }[][] }; id?: string }[]
    expect(series.some((item) => item.markArea?.data?.[0]?.[0]?.xAxis === 0.25)).toBe(true)
    expect(series.some((item) => item.markArea?.data?.[0]?.[1]?.xAxis === 0.75)).toBe(true)
    resetPlot()
    render(<ChartView chart={ending} onSeek={() => undefined} />)
    const technical = chartOption().series as { markArea?: unknown }[]
    expect(technical.every((item) => item.markArea == null)).toBe(true)
  })

  it("does not add a file-time playhead on a line-index chart", () => {
    resetPlot()
    const density: ChartDocument = {
      ...ending,
      chart_kind: "L02",
      title: "Phrasing and written density",
      evidence_class: "textual",
      series: {
        lines: [{ name: "Written words per second", unit: "words/s", x: [1], y: [null] }],
        bars: [{ label: "1", value: 2 }],
        heatmap: null,
      },
      axis_definitions: { x: "Line", y: "Written words", y_scale: "linear" },
      review_markers: [],
    }
    render(<ChartView chart={density} playhead={1.5} onSeek={() => undefined} />)
    const series = chartOption().series as { id?: string }[]
    expect(series.some((item) => String(item.id ?? "").startsWith("playback-playhead"))).toBe(false)
    const xAxis = chartOption().xAxis as { name?: string }[]
    expect(xAxis.some((axis) => axis.name === "Line")).toBe(true)
  })

  it("shows stored window labels when a lyric energy chart has no regions", () => {
    resetPlot()
    const energy: ChartDocument = {
      ...ending,
      chart_kind: "L03",
      title: "Energy and dynamic contrast",
      series: {
        lines: [{ name: "1 s RMS", unit: "dBFS", x: [0.5], y: [-12] }],
        bars: [{ label: "0.0–1.0 s", value: 1.25 }],
        heatmap: null,
      },
      axis_definitions: { x: "Time (s)", y: "dBFS or LUFS", y_scale: "linear" },
      review_markers: [],
    }
    render(<ChartView chart={energy} onSeek={() => undefined} />)
    const xAxis = chartOption().xAxis as { data?: string[] }[]
    expect(xAxis.some((axis) => axis.data?.includes("0.0–1.0 s"))).toBe(true)
  })
})
