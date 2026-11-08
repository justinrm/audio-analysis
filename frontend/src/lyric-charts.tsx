import { useEffect, useState } from "react"
import { api } from "./api/client"
import type { ChartSummary, LyricChartDocument } from "./api/types"
import { LYRIC, evidenceLabel, statusLabel } from "./catalog"
import { ChartView } from "./chart"

export function LyricCharts({
  projectId,
  assetId,
  documentId,
  revision,
  playhead,
  onSeek,
}: {
  projectId: string | null
  assetId: string
  documentId: string | null
  revision: number | null
  playhead: number | null
  onSeek: (seconds: number) => void
}) {
  const [kind, setKind] = useState<(typeof LYRIC)[number]["id"]>("L01")
  const [chart, setChart] = useState<LyricChartDocument | null>(null)
  const [summaries, setSummaries] = useState<ChartSummary[]>([])
  const [note, setNote] = useState("")

  useEffect(() => {
    if (!projectId) {
      setChart(null)
      setSummaries([])
      setNote("Open a study to load inspiration charts.")
      return
    }
    let cancel = false
    setNote("Loading inspiration charts.")
    api
      .lyricCharts(projectId, assetId)
      .then((body) => {
        if (!cancel) {
          setSummaries(body.charts)
        }
      })
      .catch(() => {
        if (!cancel) {
          setSummaries([])
        }
      })
    api
      .lyricChart(projectId, assetId, kind)
      .then((body) => {
        if (!cancel) {
          setChart(body)
          setNote("")
        }
      })
      .catch((error: unknown) => {
        if (!cancel) {
          setChart(null)
          setNote(error instanceof Error ? error.message : "This chart could not be loaded.")
        }
      })
    return () => {
      cancel = true
    }
  }, [projectId, assetId, documentId, kind, revision])

  const plotted = chart?.status === "ready" && hasPlot(chart)
  return (
    <section className="lyric-charts" aria-label="Inspiration charts">
      <div className="chart-buttons">
        {LYRIC.map((item) => {
          const summary = summaries.find((row) => row.chart_kind === item.id)
          const status = item.id === chart?.chart_kind ? chart.status : summary?.status
          return (
            <button
              key={item.id}
              type="button"
              className="category"
              aria-current={item.id === kind ? "true" : undefined}
              onClick={() => setKind(item.id)}
            >
              {item.id} {item.short}
              <br />
              <small>{status ? statusLabel(status) : "Loading"}</small>
            </button>
          )
        })}
      </div>
      {note ? (
        <p className="feedback" role="status">
          {note}
        </p>
      ) : null}
      {chart ? (
        <>
          <h3>
            {chart.chart_kind} {chart.title}
            <span className="evidence-word"> Chart evidence {evidenceLabel(chart.evidence_class)}</span>
          </h3>
          <p>Status: {statusLabel(chart.status)}</p>
          <p className="quiet">
            Method {chart.method_id} {chart.method_version}
            {chart.analysis_version ? `. Technical evidence ${chart.analysis_version}` : ""}
            {chart.lyric_revision != null ? `. Lyric revision ${chart.lyric_revision}` : ""}
          </p>
          {chart.not_available_reason ? <p>{chart.not_available_reason}</p> : null}
          {chart.caveats.map((caveat) => (
            <p key={caveat}>{caveat}</p>
          ))}
          {plotted ? (
            <ChartView
              chart={chart}
              onSeek={onSeek}
              playhead={chart.axis_definitions.x === "Line" ? null : playhead}
            />
          ) : null}
          {chart.summary.length > 0 ? (
            <dl className="evidence">
              {chart.summary.map((item, index) => (
                <div key={`${index}:${item.label}`}>
                  <dt>{item.label}</dt>
                  <dd>{item.value}</dd>
                </div>
              ))}
            </dl>
          ) : null}
          <Findings chart={chart} />
        </>
      ) : null}
    </section>
  )
}

function hasPlot(chart: LyricChartDocument): boolean {
  const lines = chart.series.lines?.length ?? 0
  const bars = chart.series.bars?.length ?? 0
  const heat = chart.series.heatmap?.z.length ?? 0
  return lines + bars + heat > 0
}

function Findings({ chart }: { chart: LyricChartDocument }) {
  if (chart.rows.length === 0 && chart.insufficient.length === 0) {
    return null
  }
  return (
    <>
      {chart.rows.length > 0 ? (
        <div className="chart-data-scroll">
          <table className="chart-data lyric-findings">
            <caption>Findings and principles for {chart.chart_kind}.</caption>
            <thead>
              <tr>
                <th>Evidence class</th>
                <th>Kind</th>
                <th>Name</th>
                <th>Value</th>
                <th>Cites</th>
                <th>Caveat</th>
              </tr>
            </thead>
            <tbody>
              {chart.rows.map((row) => (
                <tr key={row.evidence_id}>
                  <td>{evidenceLabel(row.evidence_class)}</td>
                  <td>{row.kind}</td>
                  <td>{row.name}</td>
                  <td>{row.unit && !row.value.includes(row.unit) ? `${row.value} ${row.unit}` : row.value}</td>
                  <td>{row.cites.length > 0 ? row.cites.join(", ") : "None"}</td>
                  <td>{row.caveat}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {chart.insufficient.length > 0 ? (
        <div>
          <h3>Insufficient evidence</h3>
          <ul>
            {chart.insufficient.map((item) => (
              <li key={item.code}>
                {item.code}. {item.reason}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
  )
}
