import { useEffect, useState } from "react"
import type { ChartDocument } from "./api/types"
import { evidenceLabel, statusLabel } from "./catalog"
import { formatStored } from "./chart-format"

const PAGE = 16

type Row = {
  key: string
  cells: string[]
}

export function ChartDataTable({ chart }: { chart: ChartDocument }) {
  const [open, setOpen] = useState(false)
  const [page, setPage] = useState(1)
  const [view, setView] = useState(() => initialView(chart))

  useEffect(() => {
    setPage(1)
    setView(initialView(chart))
  }, [chart])

  if (chart.status !== "ready") {
    return (
      <section aria-label="Data table">
        <h3>Data table</h3>
        <p>
          {statusLabel(chart.status)}. {chart.not_available_reason || chart.error || "No stored series."}
        </p>
        <p>Evidence class: {evidenceLabel(chart.evidence_class)}. No values are shown for this chart.</p>
      </section>
    )
  }

  const model = tableModel(chart, view)
  const pages = Math.max(1, Math.ceil(model.rows.length / PAGE))
  const safePage = Math.min(page, pages)
  const start = model.rows.length === 0 ? 0 : (safePage - 1) * PAGE
  const slice = model.rows.slice(start, start + PAGE)
  const controls = `${chart.chart_kind}-data`

  return (
    <section aria-label="Data table">
      <button
        type="button"
        className="chart-data-toggle"
        aria-expanded={open}
        aria-controls={controls}
        onClick={() => setOpen((value) => !value)}
      >
        Data table
      </button>
      {open ? (
        <div id={controls}>
          <p className="quiet">
            Stored chart evidence for {chart.title}. Evidence class {evidenceLabel(chart.evidence_class)}. Method{" "}
            {chart.method_id} {chart.method_version}. This table shows stored chart evidence, not every original audio
            sample.
          </p>
          {model.note ? <p>{model.note}</p> : null}
          {model.options.length > 0 ? (
            <label>
              Series
              <select
                aria-label="Series"
                value={view}
                onChange={(event) => {
                  setView(event.target.value)
                  setPage(1)
                }}
              >
                {model.options.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <p>No stored series in this chart document.</p>
          )}
          {model.rows.length > 0 ? (
            <>
              <div className="chart-data-scroll">
                <table className="chart-data">
                  <caption>
                    {model.caption} Showing {start + 1}–{start + slice.length} of {model.rows.length}.
                  </caption>
                  <thead>
                    <tr>
                      {model.headings.map((heading, index) => (
                        <th key={`${heading}-${index}`} scope="col">
                          {heading}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {slice.map((row) => (
                      <tr key={row.key}>
                        {row.cells.map((cell, index) =>
                          index === 0 ? (
                            <th key={`${model.headings[index]}-${index}`} scope="row">
                              {cell}
                            </th>
                          ) : (
                            <td key={`${model.headings[index]}-${index}`}>{cell}</td>
                          ),
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="chart-data-pages">
                <button type="button" disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>
                  Previous page
                </button>
                <label>
                  Page
                  <input
                    aria-label="Page"
                    type="number"
                    min={1}
                    max={pages}
                    value={safePage}
                    onChange={(event) => {
                      const next = Number(event.target.value)
                      if (Number.isInteger(next)) {
                        setPage(Math.min(pages, Math.max(1, next)))
                      }
                    }}
                  />
                </label>
                <span>
                  of {pages}
                </span>
                <button type="button" disabled={safePage >= pages} onClick={() => setPage(safePage + 1)}>
                  Next page
                </button>
              </div>
            </>
          ) : null}
        </div>
      ) : null}
    </section>
  )
}

function initialView(chart: ChartDocument): string {
  if ((chart.series.heatmap?.z.length ?? 0) > 0) {
    return "heatmap"
  }
  if ((chart.series.lines?.length ?? 0) > 0) {
    return "line:0"
  }
  if ((chart.series.bars?.length ?? 0) > 0) {
    return "bars"
  }
  return "empty"
}

function tableModel(chart: ChartDocument, view: string): {
  options: { value: string; label: string }[]
  headings: string[]
  rows: Row[]
  caption: string
  note: string
} {
  const lines = chart.series.lines ?? []
  const bars = chart.series.bars ?? []
  const heat = chart.series.heatmap
  const options = [
    ...(heat && heat.z.length > 0
      ? [{ value: "heatmap", label: `Heatmap (${heat.z.reduce((sum, row) => sum + row.length, 0)} stored cells)` }]
      : []),
    ...lines.map((line, index) => ({
      value: `line:${index}`,
      label: `${line.name} (${line.unit}, ${line.x.length} stored points)`,
    })),
    ...(bars.length > 0 ? [{ value: "bars", label: `Bars (${bars.length} stored bars)` }] : []),
  ]
  if (view === "heatmap" && heat && heat.z.length > 0) {
    const rows: Row[] = []
    heat.z.forEach((row, yIndex) => {
      row.forEach((value, xIndex) => {
        rows.push({
          key: `${xIndex}-${yIndex}`,
          cells: [String(rows.length + 1), formatStored(heat.x[xIndex] ?? null), formatStored(heat.y[yIndex] ?? null), formatStored(value)],
        })
      })
    })
    return {
      options,
      headings: ["Cell", chart.axis_definitions.x || "X", chart.axis_definitions.y || "Y", "Stored value"],
      rows,
      caption: "Heatmap coordinates are the stored category positions. Every stored cell is reachable by paging.",
      note: "Blank ticks on the chart do not remove coordinates from this table.",
    }
  }
  if (view.startsWith("line:")) {
    const index = Number(view.slice(5))
    const line = lines[index]
    if (!line) {
      return { options, headings: [], rows: [], caption: "", note: "" }
    }
    const xHeading = chart.axis_definitions.x || "X"
    return {
      options,
      headings: ["Point", xHeading, `Value (${line.unit})`],
      rows: line.x.map((x, point) => ({
        key: `${line.name}-${point}`,
        cells: [String(point + 1), formatStored(x), formatStored(line.y[point] ?? null)],
      })),
      caption: `${line.name} in ${line.unit}.`,
      note: seriesNote(line.name),
    }
  }
  if (view === "bars" && bars.length > 0) {
    const unit = chart.chart_kind === "T07" ? "share" : chart.axis_definitions.y || "value"
    return {
      options,
      headings: ["Bar", "Label", `Value (${unit})`],
      rows: bars.map((bar, index) => ({
        key: `${bar.label}-${index}`,
        cells: [String(index + 1), bar.label, formatStored(bar.value)],
      })),
      caption: "Bar labels and values are the stored chart evidence.",
      note: chart.chart_kind === "T07" ? "Shares stay on the stored 0–1 scale. They are not renormalized." : "",
    }
  }
  return { options, headings: [], rows: [], caption: "", note: "" }
}

function seriesNote(name: string): string {
  if (/overview/i.test(name)) {
    return "This is the stored overview resolution, not the detail envelope and not every original audio sample."
  }
  if (/^Envelope /.test(name)) {
    return "This is the stored detail envelope, not an exact sample per audio frame."
  }
  return ""
}
