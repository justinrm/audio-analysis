import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import type { ChartDocument } from "./api/types"
import { ChartDataTable } from "./chart-data-table"

function chartDocument(overrides: Partial<ChartDocument> = {}): ChartDocument {
  return {
    chart_kind: "T01",
    status: "ready",
    title: "Waveform and peak envelope",
    evidence_class: "measured",
    method_id: "frame-rms",
    method_version: "m1-v3",
    caveats: ["Exact sample, not the bucket."],
    summary: [],
    series: {
      lines: [
        { name: "Envelope max", unit: "amplitude", x: [0.1, 0.2], y: [0.2, 0.9] },
        { name: "Overview envelope max", unit: "amplitude", x: [0.2], y: [0.4] },
      ],
      bars: [],
      heatmap: null,
    },
    axis_definitions: { x: "Time (s)", y: "Normalized amplitude", y_scale: "linear" },
    review_markers: [],
    ...overrides,
  }
}

describe("chart data table", () => {
  it("opens from the keyboard and names the stored series, unit, and values", () => {
    const chart = chartDocument()
    const snapshot = JSON.stringify(chart)
    render(<ChartDataTable chart={chart} />)
    const control = screen.getByRole("button", { name: "Data table" })
    control.focus()
    expect(document.activeElement).toBe(control)
    fireEvent.click(control)
    expect(control.getAttribute("aria-expanded")).toBe("true")
    expect(screen.getByRole("columnheader", { name: "Time (s)" })).toBeTruthy()
    expect(screen.getByRole("columnheader", { name: "Value (amplitude)" })).toBeTruthy()
    expect(screen.getAllByText("0.2").length).toBeGreaterThan(0)
    expect(screen.getByText(/detail envelope/i)).toBeTruthy()
    fireEvent.change(screen.getByRole("combobox", { name: "Series" }), { target: { value: "line:1" } })
    expect(screen.getByText(/overview resolution/i)).toBeTruthy()
    expect(screen.getByText("0.4")).toBeTruthy()
    expect(screen.queryByText("0.9")).toBeNull()
    expect(JSON.stringify(chart)).toBe(snapshot)
  })

  it("pages stored points without dropping the rest of the series", () => {
    const x = Array.from({ length: 20 }, (_, index) => index)
    const chart = chartDocument({
      series: {
        lines: [{ name: "1 s RMS", unit: "dBFS", x, y: x.map((value) => -value) }],
        bars: [],
        heatmap: null,
      },
    })
    render(<ChartDataTable chart={chart} />)
    fireEvent.click(screen.getByRole("button", { name: "Data table" }))
    expect(screen.getByText(/Showing 1.16 of 20/)).toBeTruthy()
    expect(screen.queryByText("19")).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: "Next page" }))
    expect(screen.getByText(/Showing 17.20 of 20/)).toBeTruthy()
    expect(screen.getAllByText("19").length).toBeGreaterThan(0)
    expect(screen.getByText("-19")).toBeTruthy()
  })

  it("maps heatmap cells to stored coordinates and keeps every cell reachable", () => {
    const chart = chartDocument({
      chart_kind: "T04",
      title: "Spectrogram",
      series: {
        lines: [],
        bars: [],
        heatmap: {
          x: [0, 2],
          y: [100, 1000],
          z: [
            [1, 2],
            [3, 4],
          ],
        },
      },
      axis_definitions: { x: "Time (s)", y: "Frequency (Hz)", y_scale: "linear" },
    })
    const snapshot = JSON.stringify(chart)
    render(<ChartDataTable chart={chart} />)
    fireEvent.click(screen.getByRole("button", { name: "Data table" }))
    const table = screen.getByRole("table")
    const rows = table.querySelectorAll("tbody tr")
    expect(rows).toHaveLength(4)
    expect(rows[0]?.textContent).toContain("0")
    expect(rows[0]?.textContent).toContain("100")
    expect(rows[0]?.textContent).toContain("1")
    expect(rows[3]?.textContent).toContain("2")
    expect(rows[3]?.textContent).toContain("1000")
    expect(rows[3]?.textContent).toContain("4")
    expect(screen.getByText(/Showing 1.4 of 4/)).toBeTruthy()
    expect(JSON.stringify(chart)).toBe(snapshot)
  })

  it("states unavailable, failed, and empty charts without inventing numbers", () => {
    const { rerender } = render(
      <ChartDataTable
        chart={chartDocument({
          chart_kind: "T05",
          status: "not_available",
          evidence_class: "not_applicable",
          not_available_reason: "Mono input has no side channel.",
          series: { lines: [], bars: [], heatmap: null },
        })}
      />,
    )
    expect(screen.getByText(/Not available/)).toBeTruthy()
    expect(screen.getByText(/Mono input has no side channel/)).toBeTruthy()
    expect(screen.getByText(/Not applicable/)).toBeTruthy()
    expect(screen.queryByRole("table")).toBeNull()
    rerender(
      <ChartDataTable
        chart={chartDocument({
          status: "failed",
          error: "spectrum failed",
          series: { lines: [], bars: [], heatmap: null },
        })}
      />,
    )
    expect(screen.getByText(/Failed/)).toBeTruthy()
    expect(screen.getByText(/spectrum failed/)).toBeTruthy()
    rerender(
      <ChartDataTable chart={chartDocument({ series: { lines: [], bars: [], heatmap: null } })} />,
    )
    fireEvent.click(screen.getByRole("button", { name: "Data table" }))
    expect(screen.getByText(/No stored series/)).toBeTruthy()
  })
})
