import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { LyricChartDocument } from "./api/types"
import { LYRIC } from "./catalog"
import { LyricCharts } from "./lyric-charts"

const api = vi.hoisted(() => ({
  lyricCharts: vi.fn(),
  lyricChart: vi.fn(),
}))

vi.mock("./api/client", () => ({ api }))

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

function chart(kind: LyricChartDocument["chart_kind"], extra: Partial<LyricChartDocument> = {}): LyricChartDocument {
  return {
    chart_kind: kind,
    status: "ready",
    title: LYRIC.find((item) => item.id === kind)?.title ?? kind,
    evidence_class: "textual",
    method_id: "lyrics-v1",
    method_version: "lyrics-v1",
    analysis_version: null,
    lyric_document_id: "doc",
    lyric_revision: 2,
    caveats: [],
    summary: [],
    series: { lines: [], bars: [], heatmap: null },
    axis_definitions: { x: "", y: "", y_scale: "linear" },
    review_markers: [],
    regions: [],
    rows: [],
    insufficient: [],
    ...extra,
  }
}

describe("inspiration charts", () => {
  beforeEach(() => {
    api.lyricCharts.mockResolvedValue({
      charts: LYRIC.map((item) => ({
        chart_kind: item.id,
        status: "ready",
        title: item.title,
        evidence_class: "textual",
        method_id: "lyrics-v1",
        method_version: "lyrics-v1",
        caveats: [],
        summary: [],
        data_url: `/lyric-charts/${item.id}/data`,
        png_url: null,
      })),
    })
    api.lyricChart.mockImplementation(async (_project: string, _asset: string, kind: LyricChartDocument["chart_kind"]) => {
      if (kind === "L01") {
        return chart("L01", {
          evidence_class: "unknown",
          analysis_version: "m1-v3",
          caveats: ["This chart combines measured, textual."],
          series: {
            lines: [{ name: "1 s RMS", unit: "dBFS", x: [0.5], y: [-12], evidence_class: "measured", evidence_id: "ev:t02:rms-1s" }],
            bars: [],
            heatmap: null,
          },
          axis_definitions: { x: "Time (s)", y: "dBFS", y_scale: "linear" },
          regions: [
            {
              evidence_id: "ly:a",
              segment_id: "a",
              label: "Hello",
              start_s: 0.25,
              end_s: 0.75,
              evidence_class: "textual",
            },
          ],
        })
      }
      if (kind === "L02") {
        return chart("L02", {
          caveats: ["Word counts are written tokens, not vocal delivery or breaths."],
          summary: [{ label: "Unavailable timing", value: "1" }],
          series: {
            lines: [{ name: "Written words per second", unit: "words/s", x: [1], y: [null], evidence_class: "textual", evidence_id: "ly:density" }],
            bars: [{ label: "1", value: 2, evidence_class: "textual", evidence_id: "ly:a" }],
            heatmap: null,
          },
          axis_definitions: { x: "Line", y: "Written words", y_scale: "linear" },
        })
      }
      if (kind === "L05") {
        return chart("L05", {
          evidence_class: "unknown",
          analysis_version: "m1-v3",
          rows: [
            {
              evidence_id: "ly:principle:written-repetition:aa",
              evidence_class: "interpretive",
              kind: "principle",
              name: "written_repetition",
              value: "The written intervals differ by -1.75 dB.",
              unit: "dB",
              cites: ["ly:repeat:aa"],
              caveat: "Not a melody or hook.",
            },
          ],
          insufficient: [
            {
              code: "vocal",
              reason: "No vocal-performance principle. This milestone does not estimate singing, alignment, or delivery.",
              cites: [],
            },
          ],
        })
      }
      if (kind === "L03") {
        return chart("L03", {
          status: "not_available",
          evidence_class: "unknown",
          not_available_reason: "Stored T02 energy is not m1-v3.",
        })
      }
      return chart(kind)
    })
  })

  it("lists L01 through L05 and keeps each chart's evidence class", async () => {
    expect(LYRIC.map((item) => item.id)).toEqual(["L01", "L02", "L03", "L04", "L05"])
    const seen: number[] = []
    render(<LyricCharts projectId="p" assetId="a" documentId="doc" revision={2} playhead={0.4} onSeek={(seconds) => seen.push(seconds)} />)
    expect(await screen.findByRole("heading", { name: /L01 Unified music-and-lyrics timeline/ })).toBeTruthy()
    expect(await screen.findByRole("heading", { name: /Chart evidence Unknown/ })).toBeTruthy()
    expect(screen.getAllByText(/not missing data/).length).toBeGreaterThan(0)
    fireEvent.click(screen.getByRole("button", { name: /Hello/ }))
    expect(seen).toEqual([0.25])
    fireEvent.click(screen.getByRole("button", { name: /L02 Density/ }))
    expect(await screen.findByText("Word counts are written tokens, not vocal delivery or breaths.")).toBeTruthy()
    expect(screen.getByText("Unavailable timing")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: /L03 Energy/ }))
    expect(await screen.findByText("Stored T02 energy is not m1-v3.")).toBeTruthy()
    expect(screen.getByText("Status: Not available")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: /L04 Repetition/ }))
    expect(await screen.findByRole("heading", { name: /L04 Repetition map/ })).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: /L05 Principles/ }))
    expect(await screen.findByText(/Chart evidence Unknown/)).toBeTruthy()
    expect(screen.getByText("Interpretive")).toBeTruthy()
    expect(screen.getByText("The written intervals differ by -1.75 dB.")).toBeTruthy()
    expect(screen.getByText(/No vocal-performance principle/)).toBeTruthy()
    expect(screen.getByText("ly:repeat:aa")).toBeTruthy()
  })

  it("reloads a chart when a new lyric file reuses revision 1", async () => {
    const view = render(
      <LyricCharts projectId="p" assetId="a" documentId="first" revision={1} playhead={null} onSeek={() => undefined} />,
    )
    expect(await screen.findByRole("heading", { name: /L01/ })).toBeTruthy()
    const calls = api.lyricChart.mock.calls.length
    view.rerender(
      <LyricCharts projectId="p" assetId="a" documentId="second" revision={1} playhead={null} onSeek={() => undefined} />,
    )
    await screen.findByRole("heading", { name: /L01/ })
    expect(api.lyricChart.mock.calls.length).toBeGreaterThan(calls)
  })
})