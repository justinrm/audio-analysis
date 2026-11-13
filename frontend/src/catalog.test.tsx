import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import type { ChartDocument, ChartSummary } from "./api/types"
import { TechnicalBoard } from "./analyzer"
import { inspectorFitsBeside, playbackCaption, plotBudget, statusLabel, TECHNICAL } from "./catalog"

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

function waitForFocus(element: HTMLElement) {
  return waitFor(() => expect(document.activeElement).toBe(element))
}

const idle = {
  charts: [] as ChartSummary[],
  chartId: "T01",
  document: null as ChartDocument | null,
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
    const technical = screen.getByRole("tab", { name: "Technical Analysis" })
    const lyrics = screen.getByRole("tab", { name: "Lyrics & Inspiration" })
    expect(technical.getAttribute("aria-selected")).toBe("true")
    expect(document.getElementById(technical.getAttribute("aria-controls") || "")).toBeTruthy()
    expect(document.getElementById(lyrics.getAttribute("aria-controls") || "")).toBeTruthy()
    expect(document.querySelectorAll("#study-technical")).toHaveLength(1)
    expect(document.querySelectorAll("#study-lyrics")).toHaveLength(1)
    expect(screen.getAllByText(/not run/i).length).toBeGreaterThan(0)
    expect(screen.queryByRole("progressbar")).toBeNull()
    fireEvent.click(lyrics)
    expect(screen.getByText(/sung timing is not guessed/i)).toBeTruthy()
    expect(screen.getByText(/no evidence yet/i)).toBeTruthy()
    expect(document.querySelectorAll("#study-technical")).toHaveLength(1)
    expect(document.querySelectorAll("#study-lyrics")).toHaveLength(1)
  })

  it("moves study focus from the focused tab and keeps both panels addressable", () => {
    render(
      <TechnicalBoard {...idle} lyricsPanel={<textarea aria-label="Lyric draft" defaultValue="" />} />,
    )
    const technical = screen.getByRole("tab", { name: "Technical Analysis" })
    const lyrics = screen.getByRole("tab", { name: "Lyrics & Inspiration" })
    expect(document.getElementById("study-technical")?.hasAttribute("hidden")).toBe(false)
    expect(document.getElementById("study-lyrics")?.hasAttribute("hidden")).toBe(true)
    expect(document.querySelector("#study-lyrics textarea")).toBeNull()

    technical.focus()
    fireEvent.keyDown(technical, { key: "ArrowRight" })
    expect(document.activeElement).toBe(lyrics)
    expect(technical.getAttribute("aria-selected")).toBe("true")
    expect(lyrics.getAttribute("aria-selected")).toBe("false")

    fireEvent.keyDown(lyrics, { key: "ArrowLeft" })
    expect(document.activeElement).toBe(technical)
    expect(technical.getAttribute("aria-selected")).toBe("true")

    fireEvent.keyDown(technical, { key: "ArrowRight" })
    fireEvent.keyDown(document.activeElement as HTMLElement, { key: "ArrowRight" })
    expect(document.activeElement).toBe(technical)
    expect(technical.getAttribute("aria-selected")).toBe("true")
    fireEvent.keyDown(technical, { key: "ArrowLeft" })
    expect(document.activeElement).toBe(lyrics)
    expect(lyrics.getAttribute("aria-selected")).toBe("false")

    fireEvent.keyDown(lyrics, { key: "Enter" })
    expect(lyrics.getAttribute("aria-selected")).toBe("true")
    expect(document.getElementById("study-technical")).toBeTruthy()
    expect(document.querySelectorAll("#study-lyrics")).toHaveLength(1)
    const draft = screen.getByRole("textbox", { name: "Lyric draft" })
    fireEvent.change(draft, { target: { value: "unsaved line" } })

    fireEvent.keyDown(lyrics, { key: "ArrowLeft" })
    expect(document.activeElement).toBe(technical)
    expect(lyrics.getAttribute("aria-selected")).toBe("true")
    fireEvent.keyDown(technical, { key: " " })
    expect(technical.getAttribute("aria-selected")).toBe("true")
    expect(draft.closest("[hidden]")).toBeTruthy()
    expect(draft.closest("[inert]")).toBeTruthy()
    expect(screen.queryByRole("textbox", { name: "Lyric draft" })).toBeNull()
    draft.focus()
    expect(document.activeElement).not.toBe(draft)
    expect((draft as HTMLTextAreaElement).value).toBe("unsaved line")

    fireEvent.keyDown(technical, { key: "ArrowRight" })
    fireEvent.keyDown(lyrics, { key: "Enter" })
    expect((screen.getByRole("textbox", { name: "Lyric draft" }) as HTMLTextAreaElement).value).toBe("unsaved line")
    expect(document.querySelectorAll("#study-technical")).toHaveLength(1)
    expect(document.querySelectorAll("#study-lyrics")).toHaveLength(1)
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
    expect(screen.getByRole("heading", { name: /Loudness and dynamics/ }).textContent).toMatch(/Measured/)
    expect(screen.getByText("Status: Ready")).toBeTruthy()
    const evidence = screen.getByRole("button", { name: "Evidence" })
    expect(evidence.getAttribute("aria-controls")).toBe("chart-evidence")
    if (evidence.getAttribute("aria-expanded") !== "true") {
      fireEvent.click(evidence)
    }
    expect(screen.getByText("Short files make the loudness range unstable.")).toBeTruthy()
    expect(screen.getByRole("heading", { name: "Limitations" })).toBeTruthy()
    expect(window.document.querySelectorAll("#chart-evidence")).toHaveLength(1)
    const chart = screen.getByRole("combobox", { name: "Chart" })
    expect(chart.textContent).toMatch(/T03 Long-term spectral balance \(Failed\)/)
    expect(screen.queryByRole("progressbar")).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: /sample peak/i }))
    expect(seen).toEqual([1.25])
    fireEvent.change(chart, { target: { value: "T03" } })
    expect(seen).toEqual([1.25, "T03"])
  })

  it("says a ready chart is loading until its document arrives", () => {
    const charts: ChartSummary[] = [
      {
        chart_kind: "T01",
        status: "ready",
        title: "Waveform and peak envelope",
        evidence_class: "measured",
        method_id: "frame",
        method_version: "m1-v3",
        caveats: [],
        summary: [],
        data_url: "/api/assets/a/charts/T01/data",
        png_url: null,
      },
    ]
    render(<TechnicalBoard {...idle} charts={charts} chartId="T01" document={null} />)
    expect(screen.getByText("Loading this chart.")).toBeTruthy()
    const evidence = screen.getByRole("button", { name: "Evidence" })
    if (evidence.getAttribute("aria-expanded") !== "true") {
      fireEvent.click(evidence)
    }
    expect(screen.getByText(/still loading/i)).toBeTruthy()
    expect(screen.queryByText(/No evidence yet/i)).toBeNull()
  })

  it("budgets chart width without a permanent chart list", () => {
    expect(plotBudget(1640)).toBe(1416)
    expect(plotBudget(1640, true)).toBe(1112)
    expect(plotBudget(1440)).toBe(1216)
    expect(plotBudget(1440, true)).toBe(912)
    expect(plotBudget(1328, true)).toBe(800)
    expect(plotBudget(1327, true)).toBe(1103)
    expect(plotBudget(1280)).toBe(1056)
    expect(plotBudget(1280, true)).toBe(1056)
    expect(plotBudget(1024)).toBe(800)
    expect(plotBudget(928)).toBe(704)
    expect(plotBudget(927)).toBe(895)
    expect(plotBudget(390)).toBe(358)
    expect(plotBudget(320)).toBe(288)
    expect(inspectorFitsBeside(1104)).toBe(true)
    expect(inspectorFitsBeside(1103)).toBe(false)
  })

  it("opens one evidence region beside the chart when the measured stage can hold it", async () => {
    const descriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth")
    Object.defineProperty(HTMLElement.prototype, "clientWidth", {
      configurable: true,
      get() {
        return 1200
      },
    })
    try {
      render(<TechnicalBoard {...idle} />)
      await waitFor(() =>
        expect(document.querySelector("[data-evidence-placement]")?.getAttribute("data-evidence-placement")).toBe(
          "side",
        ),
      )
      expect(document.querySelectorAll("#chart-evidence")).toHaveLength(1)
      expect(screen.getByRole("button", { name: "Evidence" }).getAttribute("aria-expanded")).toBe("true")
    } finally {
      if (descriptor) {
        Object.defineProperty(HTMLElement.prototype, "clientWidth", descriptor)
      } else {
        Reflect.deleteProperty(HTMLElement.prototype, "clientWidth")
      }
    }
  })

  it("returns evidence focus to its trigger and keeps one evidence region", async () => {
    render(<TechnicalBoard {...idle} />)
    const evidence = screen.getByRole("button", { name: "Evidence" })
    expect(document.querySelector("[data-evidence-placement]")?.getAttribute("data-evidence-placement")).toBe("closed")
    fireEvent.click(evidence)
    expect(evidence.getAttribute("aria-expanded")).toBe("true")
    expect(document.querySelector("[data-evidence-placement]")?.getAttribute("data-evidence-placement")).toBe("below")
    expect(document.querySelectorAll("#chart-evidence")).toHaveLength(1)
    fireEvent.click(screen.getByRole("button", { name: "Close evidence" }))
    expect(evidence.getAttribute("aria-expanded")).toBe("false")
    await waitForFocus(evidence)
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
