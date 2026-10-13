import { useEffect, useRef } from "react"
import * as echarts from "echarts"
import type { ChartDocument } from "./api/types"

export function ChartView({ chart, onSeek }: { chart: ChartDocument; onSeek: (seconds: number) => void }) {
  const node = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const element = node.current
    if (!element || chart.status !== "ready") {
      return
    }
    const plot = echarts.init(element)
    const ink = getComputedStyle(element).color
    plot.setOption(optionFor(chart, ink))
    plot.getZr().on("click", (event) => {
      if (!(chart.axis_definitions.x ?? "").toLowerCase().startsWith("time")) {
        return
      }
      const point = plot.convertFromPixel({ seriesIndex: 0 }, [event.offsetX, event.offsetY])
      const raw = Array.isArray(point) ? point[0] : point
      const seconds = chart.series.heatmap ? timeOf(chart, Math.round(Number(raw))) : Number(raw)
      if (seconds !== null && Number.isFinite(seconds)) {
        onSeek(seconds)
      }
    })
    const observer = new ResizeObserver(() => plot.resize())
    observer.observe(element)
    return () => {
      observer.disconnect()
      plot.dispose()
    }
  }, [chart, onSeek])

  if (chart.status !== "ready") {
    return null
  }
  const lines = chart.series.lines?.length ?? 0
  const bars = chart.series.bars?.length ?? 0
  const stacked = lines > 0 && (bars > 0 || chart.series.heatmap != null)
  return <div ref={node} className={stacked ? "chart stacked" : "chart"} role="img" aria-label={chart.title} />
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

function optionFor(chart: ChartDocument, ink: string): echarts.EChartsOption {
  const lines = chart.series.lines ?? []
  const bars = chart.series.bars ?? []
  const heat = chart.series.heatmap
  const text = ink || "#1c1917"
  const grids: echarts.GridComponentOption[] = []
  const xAxis: echarts.XAXisComponentOption[] = []
  const yAxis: echarts.YAXisComponentOption[] = []
  const series: echarts.SeriesOption[] = []
  const panels = [heat && heat.z.length > 0, lines.length > 0, bars.length > 0].filter(Boolean).length
  const band = panels > 1 ? `${Math.floor(70 / panels)}%` : undefined

  if (heat && heat.z.length > 0) {
    const index = grids.length
    const flat = heat.z.flat()
    grids.push({ left: 56, right: 16, top: 28, height: band, bottom: band ? undefined : 36 })
    xAxis.push({ type: "category", gridIndex: index, data: heat.x.map((time) => time.toFixed(1)) })
    yAxis.push({ type: "category", gridIndex: index, data: heat.y.map((hz) => String(Math.round(hz))) })
    series.push({
      type: "heatmap",
      xAxisIndex: index,
      yAxisIndex: index,
      data: heat.z.flatMap((row, y) => row.map((value, x) => [x, y, value])),
    })
    if (lines.length > 0) {
      const lineIndex = grids.length
      grids.push({ left: 56, right: 16, top: "58%", bottom: 36 })
      xAxis.push({ type: "value", gridIndex: lineIndex, name: chart.axis_definitions.x })
      yAxis.push({ type: "value", gridIndex: lineIndex, name: lines[0]?.unit })
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
    return withMap(text, grids, xAxis, yAxis, series, flat)
  }

  if (lines.length > 0) {
    const index = grids.length
    grids.push({ left: 56, right: 16, top: 28, height: band, bottom: band ? undefined : 36 })
    xAxis.push({ type: "value", gridIndex: index, name: chart.axis_definitions.x })
    yAxis.push({ type: "value", gridIndex: index, name: lines[0]?.unit || chart.axis_definitions.y })
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
    yAxis.push({ type: "value", gridIndex: index, name: chart.axis_definitions.y })
    series.push({
      type: "bar",
      xAxisIndex: index,
      yAxisIndex: index,
      data: bars.map((bar) => bar.value),
      itemStyle: { color: "#9a3412" },
    })
  }
  return {
    animation: false,
    textStyle: { color: text },
    color: [text, "#9a3412", "#1f4b99"],
    legend: lines.length > 1 ? { top: 0, textStyle: { color: text } } : undefined,
    grid: grids,
    xAxis,
    yAxis,
    series,
  }
}

function withMap(
  text: string,
  grid: echarts.GridComponentOption[],
  xAxis: echarts.XAXisComponentOption[],
  yAxis: echarts.YAXisComponentOption[],
  series: echarts.SeriesOption[],
  flat: number[],
): echarts.EChartsOption {
  return {
    animation: false,
    textStyle: { color: text },
    color: [text, "#9a3412", "#1f4b99"],
    legend: series.filter((item) => item.type === "line").length > 1 ? { top: 0, textStyle: { color: text } } : undefined,
    grid,
    xAxis,
    yAxis,
    series,
    visualMap: {
      show: false,
      min: Math.min(...flat),
      max: Math.max(...flat),
      seriesIndex: 0,
      inRange: { color: ["#1c2430", "#9a3412", "#e6e0d4"] },
    },
  }
}
