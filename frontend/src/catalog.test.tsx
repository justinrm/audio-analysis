import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import type { ChartDocument, ChartSummary } from "./api/types"
import { TechnicalBoard } from "./analyzer"
import { playbackCaption, statusLabel, TECHNICAL } from "./catalog"

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

const idle = {
  charts: [] as ChartSummary[],
  chartId: "T01",
  document: null as ChartDocument | null,
  jobStatus: "",
  notice: "",
  onAnalyze: () => undefined,
  onSelect: () => undefined,
  onSeek: () => undefined,
}

describe("milestone 1 analysis state", () => {
  it("lists T01 through T10", () => {
    expect(TECHNICAL.map((item) => item.id)).toEqual([
      "T01",
      "T02",
      "T03",
      "T04",
      "T05",
      "T06",
      "T07",
      "T08",
      "T09",
      "T10",
    ])
  })

  it("shows not-run analysis and does not offer a progress control", () => {
    render(<TechnicalBoard {...idle} />)
    expect(screen.getByRole("tab", { name: "Technical Analysis" }).getAttribute("aria-selected")).toBe("true")
    expect(screen.getAllByText(/not run/i).length).toBeGreaterThan(0)
    expect(screen.queryByRole("progressbar")).toBeNull()
    fireEvent.click(screen.getByRole("tab", { name: "Lyrics & Inspiration" }))
    expect(screen.getByText(/sung timing is not guessed/i)).toBeTruthy()
    expect(screen.getByText(/no evidence yet/i)).toBeTruthy()
  })

  it("shows a measured value and keeps a failed chart visible", () => {
    const charts: ChartSummary[] = [
      {
        chart_kind: "T02",
        status: "ready",
        title: "Loudness and dynamics",
        evidence_class: "measured",
        method_id: "ebur128",
        method_version: "m1-v1",
        caveats: [],
        summary: [{ label: "Integrated loudness", value: "-14.2 LUFS" }],
        data_url: "/api/assets/a/charts/T02/data",
        png_url: null,
      },
      {
        chart_kind: "T03",
        status: "failed",
        title: "Long-term spectral balance",
        evidence_class: "measured",
        method_id: "welch",
        method_version: "m1-v1",
        caveats: [],
        summary: [],
        error: "spectrum failed",
        data_url: "/api/assets/a/charts/T03/data",
        png_url: null,
      },
    ]
    const document: ChartDocument = {
      chart_kind: "T02",
      status: "ready",
      title: "Loudness and dynamics",
      evidence_class: "measured",
      method_id: "ebur128",
      method_version: "m1-v1",
      caveats: ["Short files make the loudness range unstable."],
      summary: [{ label: "Integrated loudness", value: "-14.2 LUFS" }],
      series: { lines: [{ name: "Short-term", unit: "LUFS", x: [0, 1], y: [-14.2, -13.5] }], bars: [], heatmap: null },
      axis_definitions: { x: "time (s)", y: "LUFS", y_scale: "linear" },
      review_markers: [
        {
          time_s: 1.25,
          kind: "sample_peak",
          label: "sample peak channel 1",
          value: "-6.02 dBFS",
          caveat: "Exact sample on the master. Not an audible defect.",
        },
      ],
    }
    const seen: Array<string | number> = []
    render(
      <TechnicalBoard
        {...idle}
        charts={charts}
        chartId="T02"
        document={document}
        onSelect={(id) => seen.push(id)}
        onSeek={(seconds) => seen.push(seconds)}
      />,
    )
    expect(screen.getByText(/-14\.2 LUFS/)).toBeTruthy()
    expect(screen.getByRole("button", { name: /T03/i }).textContent).toMatch(/Failed/)
    expect(screen.queryByRole("progressbar")).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: /sample peak/i }))
    expect(seen).toEqual([1.25])
    fireEvent.click(screen.getByRole("button", { name: /T03/i }))
    expect(seen).toEqual([1.25, "T03"])
  })

  it("labels job and playback status without rewriting evidence class", () => {
    expect(statusLabel("not_run")).toBe("Not run")
    expect(statusLabel("not_available")).toBe("Not available")
    expect(statusLabel("completed")).toBe("Completed")
    expect(statusLabel("unavailable")).toBe("Unavailable")
    expect(statusLabel("measured")).toBe("measured")
    expect(statusLabel("textual")).toBe("textual")
  })

  it("distinguishes a 24-bit master from the playback copy", () => {
    const caption = playbackCaption({ subtype: "pcm_24", playback_status: "ready" })
    expect(caption).toContain("16-bit copy")
    expect(caption).toContain("was not changed")
  })
})
