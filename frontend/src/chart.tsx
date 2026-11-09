import { useEffect, useRef } from "react"
import * as echarts from "echarts"
import type { ChartDocument, ChartLine, LyricRegion, ReviewMarker } from "./api/types"
import { combinedEvidenceNote, evidenceLabel } from "./catalog"
import {
  AXIS_TITLE,
  formatCategoryLabel,
  formatFileTime,
  formatFrequency,
  formatLevelTick,
  formatStored,
  formatTooltipValue,
  frequencyTickLabels,
  HEATMAP_COLORS,
  PLOT_GROUND,
  SERIES_ENERGY,
  SERIES_ESTIMATED,
  SERIES_INK,
  SERIES_PLAYHEAD,
  SERIES_REVIEW,
  SERIES_WARM,
  seriesPaint,
  sparseTimeLabels,
  tickBudget,
} from "./chart-format"
import { ChartDataTable } from "./chart-data-table"

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

type LineGroup = {
  lines: ChartLine[]
  yName: string
  yMin?: number
  yMax?: number
  xScale?: "log"
}

const TICK = { color: SERIES_INK, fontSize: 11, hideOverlap: true }
const NAME = { color: AXIS_TITLE, fontSize: 12 }

type PlotDocument = ChartDocument & { regions?: LyricRegion[] }

export function ChartView({
  chart,
  onSeek,
  playhead = null,
}: {
  chart: PlotDocument
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
    let bucket = tickBudget(element.clientWidth)
    const apply = (width: number) => {
      const built = optionFor(chart, playheadRef.current, width)
      playheadsRef.current = built.playheads
      plot.setOption(built.option, { notMerge: true })
      return built
    }
    const built = apply(element.clientWidth)
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
        const zoomEvent = event as { start?: number; end?: number; batch?: { start?: number; end?: number }[] }
        const batch = zoomEvent.batch?.[0]
        const start = batch?.start ?? zoomEvent.start ?? 0
        const end = batch?.end ?? zoomEvent.end ?? 100
        plot.setOption({ legend: { selected: resolutionSelected(end - start < 99.5) } })
      })
    }
    let showRegionLabels = element.clientWidth === 0 || element.clientWidth >= 720
    const observer = new ResizeObserver(() => {
      plot.resize()
      const next = tickBudget(element.clientWidth)
      const nextLabels = element.clientWidth === 0 || element.clientWidth >= 720
      if (next === bucket && nextLabels === showRegionLabels) {
        return
      }
      bucket = next
      showRegionLabels = nextLabels
      apply(element.clientWidth)
    })
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
  const heat = (chart.series.heatmap?.z.length ?? 0) > 0
  const stacked =
    (lines > 0 && (bars > 0 || heat)) ||
    splitsLevels(chart) ||
    heat ||
    chart.chart_kind === "T02" ||
    chart.chart_kind === "T05" ||
    chart.chart_kind === "L03"
  const regions = chart.regions ?? []
  const describedBy = `${chart.chart_kind}-desc`
  return (
    <>
      {chart.chart_kind === "T10" ? (
        <p className="chart-caption">
          Ending bars are RMS levels for the last milliseconds. The list below is technical review checkpoints.
          Those are different information.
        </p>
      ) : null}
      <p className="quiet" id={describedBy}>
        {evidenceCaption(chart)}
      </p>
      <div
        ref={node}
        className={["chart", stacked ? "stacked" : "", chart.chart_kind === "L02" ? "density" : ""].filter(Boolean).join(" ")}
        role="img"
        aria-label={chart.title}
        aria-describedby={describedBy}
      />
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
      {regions.length > 0 ? (
        <ul className="markers">
          {regions.map((region) => (
            <li key={region.evidence_id}>
              <button type="button" onClick={() => onSeek(region.start_s)}>
                {region.label} {formatFileTime(region.start_s, true)}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <ChartDataTable chart={chart} />
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

function optionFor(chart: PlotDocument, playhead: number | null, plotWidth: number): BuiltChart {
  const lines = chart.series.lines ?? []
  const bars = chart.series.bars ?? []
  const heat = chart.series.heatmap
  const grids: echarts.GridComponentOption[] = []
  const xAxis: echarts.XAXisComponentOption[] = []
  const yAxis: echarts.YAXisComponentOption[] = []
  const series: echarts.SeriesOption[] = []
  const playheads: PlayheadAxis[] = []
  const budget = tickBudget(plotWidth)

  if (heat && heat.z.length > 0) {
    const index = grids.length
    const flat = heat.z.flat().filter((value) => Number.isFinite(value))
    const yIsTime = fileTime(chart.axis_definitions.y)
    const traces = lines.length > 0
    const heatRight = plotWidth === 0 || plotWidth >= 720 ? 128 : 84
    grids.push({
      left: yIsTime ? 84 : 96,
      right: heatRight,
      top: traces ? 40 : 32,
      height: traces ? "42%" : undefined,
      bottom: traces ? undefined : 92,
    })
    xAxis.push({
      type: "category",
      gridIndex: index,
      name: chart.axis_definitions.x,
      nameLocation: "middle",
      nameGap: 34,
      nameTextStyle: NAME,
      data: fileTime(chart.axis_definitions.x) ? sparseTimeLabels(heat.x, budget) : heat.x.map(String),
      axisLabel: {
        ...TICK,
        interval: 0,
        alignMinLabel: "left",
        alignMaxLabel: "right",
      },
    })
    yAxis.push({
      type: "category",
      gridIndex: index,
      name: chart.axis_definitions.y,
      nameLocation: "middle",
      nameGap: 52,
      nameTextStyle: NAME,
      data: yIsTime ? sparseTimeLabels(heat.y, budget) : frequencyTickLabels(heat.y),
      axisLabel: { ...TICK, interval: 0, verticalAlignMinLabel: "bottom" },
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
      grids.push({ left: 96, right: heatRight, top: "60%", bottom: 92 })
      xAxis.push({
        type: "value",
        gridIndex: lineIndex,
        name: chart.axis_definitions.x,
        nameLocation: "middle",
        nameGap: 34,
        nameTextStyle: NAME,
        ...(extent ? { min: extent.min, max: extent.max } : {}),
        axisLabel: { ...TICK, formatter: (value: number) => formatFileTime(value) },
      })
      yAxis.push({
        type: "value",
        gridIndex: lineIndex,
        name: lines[0]?.unit,
        nameLocation: "middle",
        nameGap: 52,
        nameTextStyle: NAME,
        axisLabel: TICK,
      })
      remember(playheads, lineIndex, lineIndex, chart.axis_definitions.x, lines[0]?.unit)
      lines.forEach((line, lineIndexOnAxis) => {
        series.push(lineSeries(chart, line, lineIndex, lineIndexOnAxis, line.x.map((x, i) => [x, line.y[i]])))
      })
    }
    return finish(withMap(grids, xAxis, yAxis, series, flat, chart, playheads), playheads, playhead, false)
  }

  if (chart.chart_kind === "L02" && bars.length > 0) {
    return finish(densityOption(chart, bars, lines), [], null, false)
  }

  const groups = lineGroups(chart)
  const panelCount = groups.length + (bars.length > 0 ? 1 : 0)
  groups.forEach((group, groupIndex) => {
    pushLines(
      chart,
      grids,
      xAxis,
      yAxis,
      series,
      playheads,
      group,
      gridBox(groupIndex, panelCount),
      groupIndex === groups.length - 1,
    )
  })
  if (bars.length > 0) {
    const index = grids.length
    const grid = gridBox(groups.length, panelCount)
    grids.push(bars.length > 6 ? { ...grid, bottom: 120 } : grid)
    xAxis.push({
      type: "category",
      gridIndex: index,
      data: bars.map((bar) => formatCategoryLabel(bar.label)),
      axisLabel: { ...TICK, rotate: bars.length > 6 ? 35 : 0, hideOverlap: true },
    })
    yAxis.push({
      type: "value",
      gridIndex: index,
      name: barAxisName(chart),
      nameLocation: "middle",
      nameGap: 52,
      nameTextStyle: NAME,
      min: chart.chart_kind === "T07" ? 0 : undefined,
      max: chart.chart_kind === "T07" ? 1 : undefined,
      axisLabel: {
        ...TICK,
        formatter: (value: number) => (chart.chart_kind === "T07" ? value.toFixed(2) : formatLevelTick(value, 30)),
      },
    })
    series.push({
      type: "bar",
      xAxisIndex: index,
      yAxisIndex: index,
      data: bars.map((bar) => bar.value),
      itemStyle: { color: chart.evidence_class === "estimated" ? SERIES_ESTIMATED : SERIES_ENERGY },
    })
  }
  const switchResolution = switchesResolution(chart)
  const lane = regionLane(chart, series)
  if (lane) {
    const hostX = typeof lane.xAxisIndex === "number" ? lane.xAxisIndex : 0
    const gridIndex = (xAxis[hostX] as { gridIndex?: number } | undefined)?.gridIndex ?? hostX
    lane.yAxisIndex = yAxis.length
    yAxis.push({ type: "value", gridIndex, min: 0, max: 1, show: false })
    series.push(lane)
  }
  return finish(
    {
      animation: false,
      backgroundColor: "transparent",
      textStyle: { color: SERIES_INK, fontSize: 12 },
      legend: legendFor(lines.length > 1 || switchResolution, switchResolution),
      tooltip: tooltipFor(chart),
      grid: grids,
      xAxis,
      yAxis,
      series,
      dataZoom: zoomIndexes(playheads, chart),
    },
    playheads,
    playhead,
    switchResolution,
  )
}

function lineGroups(chart: ChartDocument): LineGroup[] {
  const lines = chart.series.lines ?? []
  if (lines.length === 0) {
    return []
  }
  if (chart.chart_kind === "T05") {
    return [
      { lines: lines.filter((line) => line.unit === "ratio"), yName: "Correlation", yMin: -1, yMax: 1 },
      { lines: lines.filter((line) => line.unit === "dB"), yName: "Side/mid (dB)" },
    ].filter((group) => group.lines.length > 0)
  }
  if (chart.chart_kind === "T02" || chart.chart_kind === "L03") {
    const dbfs = lines.filter((line) => line.unit === "dBFS")
    const lufs = lines.filter((line) => line.unit === "LUFS")
    const rest = lines.filter((line) => line.unit !== "dBFS" && line.unit !== "LUFS")
    const groups: LineGroup[] = []
    if (dbfs.length > 0) {
      groups.push({ lines: dbfs, yName: "dBFS" })
    }
    if (lufs.length > 0) {
      groups.push({ lines: lufs, yName: "LUFS" })
    }
    if (rest.length > 0) {
      groups.push({ lines: rest, yName: lineAxisName(chart, rest) })
    }
    return groups
  }
  if (splitsLevels(chart)) {
    return [
      { lines: lines.filter((line) => line.unit === "amplitude"), yName: "Normalized amplitude" },
      { lines: lines.filter((line) => line.unit === "dBFS"), yName: "dBFS" },
    ].filter((group) => group.lines.length > 0)
  }
  return [
    {
      lines,
      yName: lineAxisName(chart, lines),
      xScale: chart.chart_kind === "T03" ? "log" : undefined,
    },
  ]
}

function withMap(
  grid: echarts.GridComponentOption[],
  xAxis: echarts.XAXisComponentOption[],
  yAxis: echarts.YAXisComponentOption[],
  series: echarts.SeriesOption[],
  flat: number[],
  chart: ChartDocument,
  playheads: PlayheadAxis[],
): echarts.EChartsOption {
  attachMarkers(chart, series)
  const low = Math.min(...flat)
  const high = Math.max(...flat)
  const unit = chart.chart_kind === "T09" ? "cosine" : "dB rel. median"
  const digits = chart.chart_kind === "T09" ? 2 : 1
  return {
    animation: false,
    backgroundColor: "transparent",
    textStyle: { color: SERIES_INK, fontSize: 12 },
    legend: legendFor(series.filter((item) => item.type === "line").length > 1, false),
    tooltip: tooltipFor(chart),
    grid,
    xAxis,
    yAxis,
    series,
    dataZoom: zoomIndexes(playheads, chart, chart.series.heatmap?.x),
    visualMap: {
      show: true,
      min: low,
      max: high,
      seriesIndex: 0,
      calculable: false,
      orient: "vertical",
      right: 8,
      top: (chart.series.lines?.length ?? 0) > 0 ? 40 : 32,
      bottom: (chart.series.lines?.length ?? 0) > 0 ? "52%" : 92,
      text: [`${high.toFixed(digits)} ${unit}`, `${low.toFixed(digits)}`],
      textStyle: { color: SERIES_INK, fontSize: 11 },
      inRange: { color: [...HEATMAP_COLORS] },
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
    lineStyle: { color: SERIES_REVIEW, type: "dashed" },
    label: { show: chart.review_markers.length <= 2, color: SERIES_INK, fontSize: 11 },
    data: chart.review_markers.map((marker) => ({ xAxis: marker.time_s, name: marker.label })),
  }
}

function splitsLevels(chart: ChartDocument): boolean {
  const lines = chart.series.lines ?? []
  return lines.some((line) => line.unit === "amplitude") && lines.some((line) => line.unit === "dBFS")
}

function pushLines(
  chart: PlotDocument,
  grids: echarts.GridComponentOption[],
  xAxis: echarts.XAXisComponentOption[],
  yAxis: echarts.YAXisComponentOption[],
  series: echarts.SeriesOption[],
  playheads: PlayheadAxis[],
  group: LineGroup,
  grid: echarts.GridComponentOption,
  showXLabels: boolean,
) {
  const index = grids.length
  grids.push(grid)
  const xName = chart.axis_definitions.x
  if (group.xScale === "log") {
    const positive = group.lines.flatMap((line) => line.x).filter((value) => value > 0)
    xAxis.push({
      type: "log",
      logBase: 10,
      gridIndex: index,
      name: showXLabels ? xName : "",
      nameLocation: "middle",
      nameGap: 34,
      nameTextStyle: NAME,
      min: Math.min(...positive),
      max: Math.max(...positive),
      axisLabel: { ...TICK, show: showXLabels, formatter: (value: number) => formatFrequency(value) },
    })
  } else {
    xAxis.push({
      type: "value",
      gridIndex: index,
      name: showXLabels ? xName : "",
      nameLocation: "middle",
      nameGap: 34,
      nameTextStyle: NAME,
      axisLabel: {
        ...TICK,
        show: showXLabels,
        formatter: fileTime(xName) ? (value: number) => formatFileTime(value) : undefined,
      },
    })
  }
  const span = spanOf(group.lines)
  yAxis.push({
    type: "value",
    gridIndex: index,
    name: group.yName,
    nameLocation: "middle",
    nameGap: 52,
    nameTextStyle: NAME,
    scale: chart.chart_kind === "T02" || chart.chart_kind === "L03" || undefined,
    min: group.yMin,
    max: group.yMax,
    axisLabel: {
      ...TICK,
      formatter: (value: number) =>
        group.yName === "Correlation" ? value.toFixed(1) : formatLevelTick(value, group.yName === "Normalized amplitude" ? 2 : span),
    },
  })
  remember(playheads, index, index, xName, group.yName)
  const layer = markerLayer(chart)
  group.lines.forEach((line, lineIndex) => {
    const item = lineSeries(
      chart,
      line,
      index,
      lineIndex,
      line.x.map((x, i) => [x, line.y[i]]),
    )
    if (lineIndex === 0 && layer) {
      item.markLine = layer
    }
    series.push(item)
  })
}

function densityOption(chart: ChartDocument, bars: { label: string; value: number }[], lines: ChartLine[]): echarts.EChartsOption {
  const labels = bars.map((bar) => formatCategoryLabel(bar.label))
  const rate = lines.find((line) => line.unit === "words/s")
  const rateByLine = new Map((rate?.x ?? []).map((x, index) => [String(x), rate?.y[index] ?? null]))
  const rateData = labels.map((label, index) => (rateByLine.has(label) ? (rateByLine.get(label) ?? null) : (rate?.y[index] ?? null)))
  const interval = labelInterval(labels.length)
  const categoryLabel = { ...TICK, interval, showMinLabel: true, showMaxLabel: true, hideOverlap: true }
  return {
    animation: false,
    backgroundColor: "transparent",
    textStyle: { color: SERIES_INK, fontSize: 12 },
    legend: { ...legendFor(true, false), top: 2 },
    tooltip: tooltipFor(chart),
    grid: [
      { left: 78, right: 18, top: 36, height: "34%" },
      { left: 78, right: 18, top: "52%", bottom: 42 },
    ],
    xAxis: [
      { type: "category", gridIndex: 0, data: labels, axisLabel: { show: false } },
      {
        type: "category",
        gridIndex: 1,
        name: chart.axis_definitions.x || "Line",
        nameLocation: "middle",
        nameGap: 26,
        nameTextStyle: NAME,
        data: labels,
        axisLabel: categoryLabel,
      },
    ],
    yAxis: [
      {
        type: "value",
        gridIndex: 0,
        name: "Written words/s",
        nameLocation: "middle",
        nameGap: 48,
        nameTextStyle: NAME,
        min: 0,
        axisLabel: TICK,
      },
      {
        type: "value",
        gridIndex: 1,
        name: "Written words",
        nameLocation: "middle",
        nameGap: 48,
        nameTextStyle: NAME,
        min: 0,
        axisLabel: TICK,
      },
    ],
    series: [
      {
        type: "line",
        name: rate?.name || "Written words per second",
        xAxisIndex: 0,
        yAxisIndex: 0,
        data: rateData,
        showSymbol: false,
        connectNulls: false,
        lineStyle: { color: SERIES_WARM, width: 1.75 },
        itemStyle: { color: SERIES_WARM },
      },
      {
        type: "bar",
        name: "Written word count",
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: bars.map((bar) => bar.value),
        itemStyle: { color: SERIES_ENERGY },
      },
    ],
  }
}

function labelInterval(count: number): number {
  if (count <= 8) {
    return 0
  }
  return Math.ceil(count / 7) - 1
}

function regionLane(chart: PlotDocument, series: echarts.SeriesOption[]): echarts.CustomSeriesOption | undefined {
  const regions = (chart.regions ?? []).filter((region) => region.end_s > region.start_s)
  if (regions.length === 0 || !fileTime(chart.axis_definitions.x)) {
    return undefined
  }
  const host = series.find((item): item is echarts.LineSeriesOption => item.type === "line")
  if (!host) {
    return undefined
  }
  return {
    type: "custom",
    silent: true,
    xAxisIndex: host.xAxisIndex ?? 0,
    yAxisIndex: host.yAxisIndex ?? 0,
    encode: { x: [0, 1] },
    data: regions.map((region) => [region.start_s, region.end_s]),
    renderItem(params, api) {
      const start = api.coord([api.value(0) as number, 0])
      const end = api.coord([api.value(1) as number, 0])
      const raw = params.coordSys as { x?: unknown; y?: unknown; width?: unknown; height?: unknown }
      if (typeof raw.x !== "number" || typeof raw.y !== "number" || typeof raw.width !== "number" || typeof raw.height !== "number") {
        return
      }
      const box = { x: raw.x, y: raw.y, width: raw.width, height: raw.height }
      const height = 7
      const shape = clipRect(
        {
          x: Math.min(start[0], end[0]),
          y: box.y + box.height - height - 2,
          width: Math.max(Math.abs(end[0] - start[0]), 1),
          height,
        },
        box,
      )
      if (!shape) {
        return
      }
      return { type: "rect", shape, style: { fill: "rgba(196, 163, 106, 0.9)" } }
    },
    z: 3,
  }
}

function clipRect(
  rect: { x: number; y: number; width: number; height: number },
  box: { x: number; y: number; width: number; height: number },
) {
  const x = Math.max(rect.x, box.x)
  const y = Math.max(rect.y, box.y)
  const right = Math.min(rect.x + rect.width, box.x + box.width)
  const bottom = Math.min(rect.y + rect.height, box.y + box.height)
  if (right <= x || bottom <= y) {
    return undefined
  }
  return { x, y, width: right - x, height: bottom - y }
}

function lineSeries(
  chart: ChartDocument,
  line: ChartLine,
  axisIndex: number,
  lineIndex: number,
  data: [number, number | null][],
): echarts.LineSeriesOption {
  const paint = seriesPaint(line.unit, lineIndex, chart.evidence_class, chart.chart_kind)
  return {
    type: "line",
    xAxisIndex: axisIndex,
    yAxisIndex: axisIndex,
    name: line.name,
    showSymbol: false,
    data,
    lineStyle: { color: paint.color, width: 1.75, type: paint.dash },
    itemStyle: { color: paint.color },
  }
}

function gridBox(index: number, count: number): echarts.GridComponentOption {
  const base = { left: 96, right: 28 }
  const foot = 92
  if (count <= 1) {
    return { ...base, top: 40, bottom: foot }
  }
  if (count === 2) {
    return index === 0 ? { ...base, top: 36, height: "40%" } : { ...base, top: "50%", bottom: foot }
  }
  if (index === 0) {
    return { ...base, top: 36, height: "24%" }
  }
  if (index === 1) {
    return { ...base, top: "34%", height: "24%" }
  }
  return { ...base, top: "64%", bottom: foot }
}

function zoom(
  xIndex: number | number[],
  yIndex: number | number[] | undefined,
  mode: "time" | "time-category" | "frequency",
  times?: number[],
): echarts.DataZoomComponentOption[] {
  const label = (value: number) => {
    if (mode === "frequency") {
      return formatFrequency(value)
    }
    if (mode === "time-category" && times) {
      const time = times[Math.round(value)]
      return time === undefined ? "" : formatFileTime(time)
    }
    return formatFileTime(value)
  }
  const inside: echarts.DataZoomComponentOption = { type: "inside", xAxisIndex: xIndex, filterMode: "none" }
  const slider: echarts.DataZoomComponentOption = {
    type: "slider",
    xAxisIndex: xIndex,
    filterMode: "none",
    height: 26,
    bottom: 6,
    labelFormatter: label,
    textStyle: { color: SERIES_INK, fontSize: 11 },
    borderColor: "#3a4150",
    fillerColor: "rgba(142, 180, 212, 0.25)",
    handleStyle: { color: SERIES_ENERGY },
  }
  if (yIndex !== undefined) {
    inside.yAxisIndex = yIndex
    slider.yAxisIndex = yIndex
  }
  return [inside, slider]
}

function zoomIndexes(
  playheads: PlayheadAxis[],
  chart: ChartDocument,
  categoryTimes?: number[],
): echarts.DataZoomComponentOption[] | undefined {
  if (chart.chart_kind === "T03") {
    return zoom(0, undefined, "frequency")
  }
  const xIndexes = [...new Set(playheads.filter((axis) => axis.x !== "off").map((axis) => axis.xAxisIndex))]
  const yIndexes = [...new Set(playheads.filter((axis) => axis.y !== "off").map((axis) => axis.yAxisIndex))]
  if (xIndexes.length === 0) {
    return undefined
  }
  const x = xIndexes.length === 1 ? xIndexes[0] : xIndexes
  const y = yIndexes.length === 0 ? undefined : yIndexes.length === 1 ? yIndexes[0] : yIndexes
  const category = playheads.some((axis) => axis.x === "category")
  return zoom(x, y, category ? "time-category" : "time", categoryTimes)
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
      lineStyle: { color: SERIES_PLAYHEAD },
    }
    if (playhead !== null) {
      item.markLine = playheadMark(axis, playhead)
    }
    series.push(item)
  }
  option.series = series
  return { option, playheads, switchResolution }
}

function legendFor(show: boolean, switchResolution: boolean): echarts.LegendComponentOption | undefined {
  if (!show) {
    return undefined
  }
  const legend: echarts.LegendComponentOption = {
    type: "scroll",
    top: 4,
    textStyle: { color: SERIES_INK, fontSize: 12 },
    pageIconColor: SERIES_INK,
    pageTextStyle: { color: SERIES_INK },
  }
  if (switchResolution) {
    legend.selected = resolutionSelected(false)
  }
  return legend
}

function tooltipFor(chart: ChartDocument): echarts.TooltipComponentOption {
  return {
    trigger: "axis",
    confine: true,
    backgroundColor: PLOT_GROUND,
    borderColor: "#3a4150",
    textStyle: { color: SERIES_INK, fontSize: 12 },
    formatter: (params: unknown) => tooltipText(chart, params),
  }
}

function tooltipText(chart: ChartDocument, params: unknown): string {
  const rows = (Array.isArray(params) ? params : [params]) as {
    seriesName?: string
    seriesId?: string
    value?: unknown
    axisValue?: unknown
    axisValueLabel?: string
  }[]
  const lines = rows
    .filter((row) => row.seriesName && !String(row.seriesId ?? "").startsWith("playback-playhead"))
    .map((row) => formatTipRow(chart, row))
    .filter((row) => row.length > 0)
  return lines.join("<br/>")
}

function formatTipRow(
  chart: ChartDocument,
  row: { seriesName?: string; value?: unknown; axisValue?: unknown; axisValueLabel?: string },
): string {
  const heat = chart.series.heatmap
  if (Array.isArray(row.value) && row.value.length >= 3 && heat) {
    const x = heat.x[Number(row.value[0])]
    const y = heat.y[Number(row.value[1])]
    const z = Number(row.value[2])
    const xText = fileTime(chart.axis_definitions.x) ? formatFileTime(x ?? 0) : formatFrequency(x ?? 0)
    const yText = fileTime(chart.axis_definitions.y) ? formatFileTime(y ?? 0) : formatFrequency(y ?? 0)
    const zText = chart.chart_kind === "T09" ? formatTooltipValue(z, "cosine similarity") : formatTooltipValue(z, "dB")
    return escapeHtml(`Cell ${xText}, ${yText}: ${zText}`)
  }
  const named = (chart.series.lines ?? []).find((line) => line.name === row.seriesName)
  if (named && Array.isArray(row.value)) {
    const x = Number(row.value[0])
    const y = row.value[1] === null || row.value[1] === undefined ? null : Number(row.value[1])
    const xText = fileTime(chart.axis_definitions.x)
      ? formatFileTime(x)
      : chart.chart_kind === "T03"
        ? formatFrequency(x)
        : formatStored(x)
    const yText = y === null ? "—" : formatTooltipValue(y, named.unit)
    return escapeHtml(`${named.name}: ${yText} ${named.unit} at ${xText}`)
  }
  if (typeof row.value === "number") {
    const label = formatCategoryLabel(String(row.axisValueLabel ?? row.axisValue ?? ""))
    const unit = chart.chart_kind === "T07" ? "share" : chart.chart_kind === "T03" ? "%" : "dB"
    return escapeHtml(`${label}: ${formatTooltipValue(row.value, unit)}`)
  }
  return ""
}

function escapeHtml(value: string): string {
  return value.replace(/[&<>]/g, (char) => (char === "&" ? "&amp;" : char === "<" ? "&lt;" : "&gt;"))
}

function spanOf(lines: ChartLine[]): number {
  const values = lines.flatMap((line) => line.y).filter((value): value is number => value !== null && Number.isFinite(value))
  if (values.length === 0) {
    return 0
  }
  return Math.max(...values) - Math.min(...values)
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
    lineStyle: { color: SERIES_PLAYHEAD, width: 1.5, type: "solid" },
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

function evidenceCaption(chart: ChartDocument): string {
  const note = combinedEvidenceNote(chart.status, chart.evidence_class, chart.caveats)
  const mixed = note ? ` ${note}` : ""
  return `${evidenceLabel(chart.evidence_class)}.${mixed} ${chart.axis_definitions.x}. ${chart.axis_definitions.y}.`
}

function fileTime(label: string | undefined): boolean {
  return (label ?? "").toLowerCase().startsWith("time")
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

function lineAxisName(chart: ChartDocument, lines: ChartLine[]): string {
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
  if (chart.chart_kind === "T07") {
    return "Share"
  }
  return chart.axis_definitions.y || ""
}
