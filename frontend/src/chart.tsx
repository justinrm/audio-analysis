import { useEffect, useRef } from "react"
import * as echarts from "echarts"
import type { ChartDocument, ReviewMarker } from "./api/types"

type AxisMode = "value" | "category" | "off"

type PlayheadAxis = {
  id: string
  xAxisIndex: number
  yAxisIndex: number
  x: AxisMode
  y: AxisMode
  xLabels?: number[]
  yLabels?: number[]
}

type BuiltChart = {
  option: echarts.EChartsOption
  playheads: PlayheadAxis[]
  switchResolution: boolean
}

export function ChartView({
  chart,
  onSeek,
  playhead = null,
}: {
  chart: ChartDocument
  onSeek: (seconds: number) => void
  playhead?: number | null
}) {
  const node = useRef<HTMLDivElement>(null)
  const plotRef = useRef<echarts.ECharts | null>(null)
  const playheadsRef = useRef<PlayheadAxis[]>([])
  const seekRef = useRef(onSeek)
  const playheadRef = useRef(playhead)
  seekRef.current = onSeek
  playheadRef.current = playhead

  useEffect(() => {
    const element = node.current
    if (!element || chart.status !== "ready") {
      return
    }
    const plot = echarts.init(element)
    plotRef.current = plot
    const built = optionFor(chart, getComputedStyle(element).color, playheadRef.current)
    playheadsRef.current = built.playheads
    plot.setOption(built.option)
    plot.getZr().on("click", (event) => {
      const pixel: [number, number] = [event.offsetX, event.offsetY]
      const option = plot.getOption()
      const series = Array.isArray(option.series) ? option.series : []
      const axes = Array.isArray(option.xAxis) ? option.xAxis : []
      for (let index = 0; index < series.length; index += 1) {
        const item = series[index] as { id?: string; xAxisIndex?: number }
        if (String(item.id ?? "").startsWith("playback-playhead")) {
          continue
        }
        if (!plot.containPixel({ seriesIndex: index }, pixel)) {
          continue
        }
        const axis = axes[item.xAxisIndex ?? 0] as { type?: string; name?: string } | undefined
        if (!fileTime(axis?.name)) {
          return
        }
        const point = plot.convertFromPixel({ seriesIndex: index }, pixel)
        const raw = Array.isArray(point) ? point[0] : point
        const seconds = axis?.type === "category" ? timeOf(chart, Math.round(Number(raw))) : Number(raw)
        if (seconds !== null && Number.isFinite(seconds)) {
          seekRef.current(seconds)
        }
        return
      }
    })
    if (built.switchResolution) {
      plot.on("datazoom", (event) => {
        const zoom = event as { start?: number; end?: number; batch?: { start?: number; end?: number }[] }
        const batch = zoom.batch?.[0]
        const start = batch?.start ?? zoom.start ?? 0
        const end = batch?.end ?? zoom.end ?? 100
        plot.setOption({ legend: { selected: resolutionSelected(end - start < 99.5) } })
      })
    }
    const observer = new ResizeObserver(() => plot.resize())
    observer.observe(element)
    return () => {
      observer.disconnect()
      plotRef.current = null
      playheadsRef.current = []
      plot.dispose()
    }
  }, [chart])

  useEffect(() => {
    const plot = plotRef.current
    const axes = playheadsRef.current
    if (!plot || axes.length === 0) {
      return
    }
    plot.setOption({
      series: axes.map((axis) => ({
        id: axis.id,
        markLine: playhead === null ? { data: [] } : playheadMark(axis, playhead),
      })),
    })
  }, [playhead])

  if (chart.status !== "ready") {
    return null
  }
  const lines = chart.series.lines?.length ?? 0
  const bars = chart.series.bars?.length ?? 0
  const stacked = (lines > 0 && (bars > 0 || chart.series.heatmap != null)) || splitsLevels(chart)
  return (
    <>
      <div ref={node} className={stacked ? "chart stacked" : "chart"} role="img" aria-label={chart.title} />
      {chart.review_markers.length > 0 ? (
        <ul className="markers">
          {chart.review_markers.map((marker) => (
            <li key={`${marker.kind ?? "event"}-${marker.time_s}-${marker.label}`}>
              <button type="button" onClick={() => onSeek(marker.time_s)}>
                {markerText(marker)}
              </button>
              {marker.caveat ? <span className="quiet">{marker.caveat}</span> : null}
            </li>
          ))}
        </ul>
      ) : null}
    </>
  )
}

function markerText(marker: ReviewMarker): string {
  const value = marker.value ? ` ${marker.value}` : ""
  return `${marker.kind ?? "event"} ${marker.time_s.toFixed(3)} s ${marker.label}${value}`
}

function timeOf(chart: ChartDocument, raw: unknown): number | null {
  const heat = chart.series.heatmap
  const index = Number(raw)
  if (!Number.isFinite(index)) {
    return null
  }
  if (heat && Number.isInteger(index) && heat.x[index] !== undefined) {
    return heat.x[index]
  }
  return index
}

function optionFor(chart: ChartDocument, ink: string, playhead: number | null): BuiltChart {
  const lines = chart.series.lines ?? []
  const bars = chart.series.bars ?? []
  const heat = chart.series.heatmap
  const text = ink || "#1c1917"
  const grids: echarts.GridComponentOption[] = []
  const xAxis: echarts.XAXisComponentOption[] = []
  const yAxis: echarts.YAXisComponentOption[] = []
  const series: echarts.SeriesOption[] = []
  const playheads: PlayheadAxis[] = []
  const panels = [heat && heat.z.length > 0, lines.length > 0, bars.length > 0].filter(Boolean).length
  const band = panels > 1 ? `${Math.floor(70 / panels)}%` : undefined

  if (heat && heat.z.length > 0) {
    const index = grids.length
    const flat = heat.z.flat()
    const yIsTime = fileTime(chart.axis_definitions.y)
    grids.push({ left: 56, right: 16, top: 28, height: band, bottom: band ? undefined : 36 })
    xAxis.push({
      type: "category",
      gridIndex: index,
      name: chart.axis_definitions.x,
      data: timeLabels(heat.x),
    })
    yAxis.push({
      type: "category",
      gridIndex: index,
      name: chart.axis_definitions.y,
      data: yIsTime ? timeLabels(heat.y) : heat.y.map((hz) => String(Math.round(hz))),
    })
    remember(playheads, index, index, chart.axis_definitions.x, chart.axis_definitions.y, heat.x, yIsTime ? heat.y : undefined)
    series.push({
      type: "heatmap",
      xAxisIndex: index,
      yAxisIndex: index,
      data: heat.z.flatMap((row, y) => row.map((value, x) => [x, y, value])),
    })
    if (lines.length > 0) {
      const lineIndex = grids.length
      const extent = valueExtent(heat.x)
      grids.push({ left: 56, right: 16, top: "58%", bottom: 36 })
      xAxis.push({
        type: "value",
        gridIndex: lineIndex,
        name: chart.axis_definitions.x,
        ...(extent ? { min: extent.min, max: extent.max } : {}),
      })
      yAxis.push({ type: "value", gridIndex: lineIndex, name: lines[0]?.unit })
      remember(playheads, lineIndex, lineIndex, chart.axis_definitions.x, lines[0]?.unit)
      for (const line of lines) {
        series.push({
          type: "line",
          xAxisIndex: lineIndex,
          yAxisIndex: lineIndex,
          name: line.name,
          showSymbol: false,
          data: line.x.map((x, i) => [x, line.y[i]]),
        })
      }
    }
    return finish(withMap(text, grids, xAxis, yAxis, series, flat, chart, playheads), playheads, playhead, false)
  }

  if (splitsLevels(chart)) {
    const amplitude = lines.filter((line) => line.unit === "amplitude")
    const levels = lines.filter((line) => line.unit === "dBFS")
    pushLines(chart, grids, xAxis, yAxis, series, playheads, amplitude, "Normalized amplitude", {
      left: 64,
      right: 16,
      top: 32,
      height: "34%",
    })
    pushLines(chart, grids, xAxis, yAxis, series, playheads, levels, "dBFS", {
      left: 64,
      right: 16,
      top: "52%",
      height: "30%",
    })
    const legend: echarts.LegendComponentOption = { top: 0, textStyle: { color: text } }
    const switchResolution = switchesResolution(chart)
    if (switchResolution) {
      legend.selected = resolutionSelected(false)
    }
    return finish(
      {
        animation: false,
        textStyle: { color: text },
        color: [text, "#9a3412", "#1f4b99"],
        legend,
        grid: grids,
        xAxis,
        yAxis,
        series,
        dataZoom: zoomIndexes(playheads),
      },
      playheads,
      playhead,
      switchResolution,
    )
  }

  if (lines.length > 0) {
    const index = grids.length
    const yName = lineAxisName(chart, lines)
    grids.push({ left: 56, right: 16, top: 28, height: band, bottom: band ? undefined : 36 })
    xAxis.push({ type: "value", gridIndex: index, name: chart.axis_definitions.x })
    yAxis.push({ type: "value", gridIndex: index, name: yName })
    remember(playheads, index, index, chart.axis_definitions.x, yName)
    for (const line of lines) {
      series.push({
        type: "line",
        xAxisIndex: index,
        yAxisIndex: index,
        name: line.name,
        showSymbol: false,
        data: line.x.map((x, i) => [x, line.y[i]]),
      })
    }
  }
  if (bars.length > 0) {
    const index = grids.length
    grids.push({
      left: 56,
      right: 16,
      top: lines.length > 0 ? "58%" : 28,
      height: band,
      bottom: 48,
    })
    xAxis.push({
      type: "category",
      gridIndex: index,
      data: bars.map((bar) => bar.label),
      axisLabel: { hideOverlap: true, rotate: bars.length > 6 ? 35 : 0 },
    })
    yAxis.push({ type: "value", gridIndex: index, name: barAxisName(chart) })
    series.push({
      type: "bar",
      xAxisIndex: index,
      yAxisIndex: index,
      data: bars.map((bar) => bar.value),
      itemStyle: { color: "#9a3412" },
    })
  }
  attachMarkers(chart, series)
  return finish(
    {
      animation: false,
      textStyle: { color: text },
      color: [text, "#9a3412", "#1f4b99"],
      legend: lines.length > 1 ? { top: 0, textStyle: { color: text } } : undefined,
      grid: grids,
      xAxis,
      yAxis,
      series,
      dataZoom: zoomIndexes(playheads),
    },
    playheads,
    playhead,
    false,
  )
}

function withMap(
  text: string,
  grid: echarts.GridComponentOption[],
  xAxis: echarts.XAXisComponentOption[],
  yAxis: echarts.YAXisComponentOption[],
  series: echarts.SeriesOption[],
  flat: number[],
  chart: ChartDocument,
  playheads: PlayheadAxis[],
): echarts.EChartsOption {
  attachMarkers(chart, series)
  return {
    animation: false,
    textStyle: { color: text },
    color: [text, "#9a3412", "#1f4b99"],
    legend: series.filter((item) => item.type === "line").length > 1 ? { top: 0, textStyle: { color: text } } : undefined,
    grid,
    xAxis,
    yAxis,
    series,
    dataZoom: zoomIndexes(playheads),
    visualMap: {
      show: false,
      min: Math.min(...flat),
      max: Math.max(...flat),
      seriesIndex: 0,
      inRange: { color: ["#1c2430", "#9a3412", "#e6e0d4"] },
    },
  }
}

function attachMarkers(chart: ChartDocument, series: echarts.SeriesOption[]) {
  const layer = markerLayer(chart)
  const host = series.find((item) => item.type === "line")
  if (!layer || !host || host.type !== "line") {
    return
  }
  host.markLine = layer
}

function markerLayer(chart: ChartDocument): echarts.MarkLineComponentOption | undefined {
  if (!(chart.axis_definitions.x ?? "").toLowerCase().startsWith("time") || chart.review_markers.length === 0) {
    return undefined
  }
  return {
    symbol: "none",
    animation: false,
    lineStyle: { color: "#b08d57", type: "dashed" },
    data: chart.review_markers.map((marker) => ({ xAxis: marker.time_s, name: marker.label })),
  }
}

function splitsLevels(chart: ChartDocument): boolean {
  const lines = chart.series.lines ?? []
  return lines.some((line) => line.unit === "amplitude") && lines.some((line) => line.unit === "dBFS")
}

function pushLines(
  chart: ChartDocument,
  grids: echarts.GridComponentOption[],
  xAxis: echarts.XAXisComponentOption[],
  yAxis: echarts.YAXisComponentOption[],
  series: echarts.SeriesOption[],
  playheads: PlayheadAxis[],
  lines: NonNullable<ChartDocument["series"]["lines"]>,
  name: string,
  grid: echarts.GridComponentOption,
) {
  const index = grids.length
  grids.push(grid)
  xAxis.push({ type: "value", gridIndex: index, name: chart.axis_definitions.x })
  yAxis.push({ type: "value", gridIndex: index, name })
  remember(playheads, index, index, chart.axis_definitions.x, name)
  const layer = markerLayer(chart)
  lines.forEach((line, lineIndex) => {
    const item: echarts.LineSeriesOption = {
      type: "line",
      xAxisIndex: index,
      yAxisIndex: index,
      name: line.name,
      showSymbol: false,
      data: line.x.map((x, i) => [x, line.y[i]]),
    }
    if (lineIndex === 0 && layer) {
      item.markLine = layer
    }
    series.push(item)
  })
}

function zoom(xIndex: number | number[], yIndex?: number | number[]): echarts.DataZoomComponentOption[] {
  const inside: echarts.DataZoomComponentOption = { type: "inside", xAxisIndex: xIndex, filterMode: "none" }
  const slider: echarts.DataZoomComponentOption = {
    type: "slider",
    xAxisIndex: xIndex,
    filterMode: "none",
    height: 16,
    bottom: 4,
  }
  if (yIndex !== undefined) {
    inside.yAxisIndex = yIndex
    slider.yAxisIndex = yIndex
  }
  return [inside, slider]
}

function zoomIndexes(playheads: PlayheadAxis[]): echarts.DataZoomComponentOption[] | undefined {
  const xIndexes = [...new Set(playheads.filter((axis) => axis.x !== "off").map((axis) => axis.xAxisIndex))]
  const yIndexes = [...new Set(playheads.filter((axis) => axis.y !== "off").map((axis) => axis.yAxisIndex))]
  if (xIndexes.length === 0) {
    return undefined
  }
  const x = xIndexes.length === 1 ? xIndexes[0] : xIndexes
  const y = yIndexes.length === 0 ? undefined : yIndexes.length === 1 ? yIndexes[0] : yIndexes
  return zoom(x, y)
}

function finish(
  option: echarts.EChartsOption,
  playheads: PlayheadAxis[],
  playhead: number | null,
  switchResolution: boolean,
): BuiltChart {
  const series = (option.series as echarts.SeriesOption[]) ?? []
  if (playheads.length > 0 && option.legend && !Array.isArray(option.legend)) {
    const legend = option.legend
    if (!legend.data) {
      legend.data = series.flatMap((item) => {
        const name = "name" in item ? item.name : undefined
        return typeof name === "string" && name.length > 0 ? [name] : []
      })
    }
  }
  for (const axis of playheads) {
    const item: echarts.LineSeriesOption = {
      id: axis.id,
      type: "line",
      xAxisIndex: axis.xAxisIndex,
      yAxisIndex: axis.yAxisIndex,
      data: [],
      silent: true,
      showSymbol: false,
      tooltip: { show: false },
    }
    if (playhead !== null) {
      item.markLine = playheadMark(axis, playhead)
    }
    series.push(item)
  }
  option.series = series
  return { option, playheads, switchResolution }
}

function remember(
  playheads: PlayheadAxis[],
  xIndex: number,
  yIndex: number,
  xName: string | undefined,
  yName: string | undefined,
  xLabels?: number[],
  yLabels?: number[],
) {
  const x: AxisMode = fileTime(xName) ? (xLabels ? "category" : "value") : "off"
  const y: AxisMode = fileTime(yName) ? (yLabels ? "category" : "value") : "off"
  if (x === "off" && y === "off") {
    return
  }
  playheads.push({
    id: `playback-playhead-${xIndex}-${yIndex}`,
    xAxisIndex: xIndex,
    yAxisIndex: yIndex,
    x,
    y,
    xLabels,
    yLabels,
  })
}

function playheadMark(axis: PlayheadAxis, seconds: number): echarts.MarkLineComponentOption {
  const data: { xAxis?: number; yAxis?: number }[] = []
  if (axis.x === "value") {
    data.push({ xAxis: seconds })
  }
  if (axis.x === "category" && axis.xLabels) {
    data.push({ xAxis: nearestIndex(axis.xLabels, seconds) })
  }
  if (axis.y === "value") {
    data.push({ yAxis: seconds })
  }
  if (axis.y === "category" && axis.yLabels) {
    data.push({ yAxis: nearestIndex(axis.yLabels, seconds) })
  }
  return {
    symbol: "none",
    animation: false,
    silent: true,
    lineStyle: { color: "#e6e0d4", width: 1.5, type: "solid" },
    label: { show: false },
    data,
  }
}

function nearestIndex(times: number[], seconds: number): number {
  let best = 0
  let bestDist = Number.POSITIVE_INFINITY
  times.forEach((time, index) => {
    const dist = Math.abs(time - seconds)
    if (dist < bestDist) {
      best = index
      bestDist = dist
    }
  })
  return best
}

function fileTime(label: string | undefined): boolean {
  return (label ?? "").toLowerCase().startsWith("time")
}

function timeLabels(times: number[]): string[] {
  return times.map((time) => {
    const tenth = time.toFixed(1)
    const collision = times.some((other) => other !== time && other.toFixed(1) === tenth)
    return collision ? time.toFixed(3) : tenth
  })
}

function valueExtent(times: number[]): { min: number; max: number } | undefined {
  if (times.length < 2) {
    return undefined
  }
  const step = (times[times.length - 1] - times[0]) / (times.length - 1)
  const half = step / 2
  return { min: times[0] - half, max: times[times.length - 1] + half }
}

function resolutionSelected(zoomed: boolean): Record<string, boolean> {
  return {
    "Envelope max": zoomed,
    "Envelope min": zoomed,
    "Overview envelope max": !zoomed,
    "Overview envelope min": !zoomed,
  }
}

function switchesResolution(chart: ChartDocument): boolean {
  const lines = chart.series.lines ?? []
  const detail = lines.find((line) => line.name === "Envelope max")
  const overview = lines.find((line) => line.name === "Overview envelope max")
  if (!detail || !overview) {
    return false
  }
  return overview.x.length < detail.x.length
}

function lineAxisName(chart: ChartDocument, lines: NonNullable<ChartDocument["series"]["lines"]>): string {
  const unit = lines[0]?.unit
  if (!unit || unit === "score") {
    return chart.axis_definitions.y || unit || ""
  }
  return unit
}

function barAxisName(chart: ChartDocument): string {
  if (chart.chart_kind === "T06") {
    return "Autocorrelation"
  }
  return chart.axis_definitions.y || ""
}
