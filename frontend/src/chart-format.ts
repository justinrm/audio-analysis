import { clock, evidenceLabel } from "./catalog"

/** Page ground. Series colors are checked against this in chart-format tests. */
export const PLOT_GROUND = "#14171c"
export const SERIES_INK = "#e8e6e1"
export const SERIES_ENERGY = "#8ec8f0"
export const SERIES_LUFS = "#8fce8a"
export const SERIES_WARM = "#e2b07a"
export const SERIES_SLATE = "#c5ced8"
export const SERIES_ESTIMATED = "#d4b6ea"
export const SERIES_PLAYHEAD = "#f3efe6"
export const SERIES_REVIEW = "#c4a36a"
export const AXIS_TITLE = "#b7c2ce"

/**
 * Sequential heatmap. The low stop is darker slate than the page, at about 3:1.
 * `#243044` was rejected: it measures about 1.35:1 on `PLOT_GROUND`.
 */
export const HEATMAP_COLORS = ["#4c6680", SERIES_ENERGY, SERIES_PLAYHEAD] as const

const LINE_PALETTE = [SERIES_INK, SERIES_ENERGY, SERIES_WARM, SERIES_SLATE] as const

export type LineDash = "solid" | "dashed"

export function evidenceWord(evidenceClass: string): string {
  return evidenceLabel(evidenceClass)
}

/** Display time. Whole seconds use `m:ss`. Off-second values use one decimal, floored like the transport clock. */
export function formatFileTime(seconds: number, fractional?: boolean): string {
  const abs = Number.isFinite(seconds) ? Math.abs(seconds) : 0
  const useFraction = fractional ?? Math.abs(abs - Math.round(abs)) > 0.049
  return clock(abs, useFraction)
}

export function formatFrequency(hz: number): string {
  if (!Number.isFinite(hz)) {
    return ""
  }
  const abs = Math.abs(hz)
  const sign = hz < 0 ? "-" : ""
  if (abs >= 1000) {
    const khz = abs / 1000
    const text = Number.isInteger(khz) ? String(khz) : khz.toFixed(1).replace(/\.0$/, "")
    return `${sign}${text} kHz`
  }
  return `${sign}${Math.round(abs)} Hz`
}

export function formatStored(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "—"
  }
  const rounded = Math.round(value * 1e9) / 1e9
  return Object.is(rounded, -0) ? "0" : String(rounded)
}

export function formatLevelTick(value: number, span: number): string {
  if (!Number.isFinite(value)) {
    return ""
  }
  if (value === 0) {
    return "0"
  }
  const magnitude = Math.max(Math.abs(value), span)
  if (magnitude < 0.001) {
    return value.toExponential(1)
  }
  const digits = magnitude < 0.2 ? 3 : magnitude < 2 ? 2 : magnitude < 20 ? 1 : 0
  return value.toFixed(digits)
}

export function formatTooltipValue(value: number, unit: string): string {
  if (!Number.isFinite(value)) {
    return "—"
  }
  const normalized = unit.toLowerCase()
  if (normalized === "ratio") {
    return value.toFixed(3)
  }
  if (normalized === "share") {
    return value.toFixed(3)
  }
  if (normalized === "cosine" || normalized === "cosine similarity") {
    return value.toFixed(2)
  }
  if (normalized.includes("%") || normalized === "percent") {
    return value.toFixed(1)
  }
  if (normalized === "amplitude") {
    return value.toFixed(3)
  }
  if (normalized.includes("db") || normalized === "lufs" || normalized === "lu") {
    return value.toFixed(1)
  }
  if (normalized === "score") {
    return value.toFixed(2)
  }
  return formatStored(value)
}

/** BPM and other category labels stay the stored string. */
export function formatCategoryLabel(label: string): string {
  return label
}

export function seriesPaint(
  unit: string,
  index: number,
  evidenceClass: string,
  chartKind: string,
): { color: string; dash: LineDash } {
  if (unit === "LUFS") {
    return { color: SERIES_LUFS, dash: "dashed" }
  }
  if (unit === "ratio") {
    return { color: SERIES_INK, dash: "solid" }
  }
  if (chartKind === "T05" && unit === "dB") {
    return { color: SERIES_ENERGY, dash: "dashed" }
  }
  if (unit === "amplitude") {
    if (index < 2) {
      return { color: SERIES_INK, dash: "solid" }
    }
    return { color: SERIES_SLATE, dash: "dashed" }
  }
  if (unit === "dBFS") {
    return { color: SERIES_ENERGY, dash: "solid" }
  }
  if (unit === "score" || evidenceClass === "estimated") {
    return { color: SERIES_ESTIMATED, dash: "dashed" }
  }
  return {
    color: LINE_PALETTE[index % LINE_PALETTE.length] ?? SERIES_INK,
    dash: index === 0 ? "solid" : "dashed",
  }
}

export function tickBudget(width: number): number {
  const px = width > 0 ? width : 900
  if (px < 480) {
    return 6
  }
  if (px < 800) {
    return 8
  }
  return 10
}

export function keptLabelIndexes(count: number, budget: number): number[] {
  if (count <= 0) {
    return []
  }
  if (count <= budget) {
    return Array.from({ length: count }, (_, index) => index)
  }
  const last = count - 1
  const slots = Math.max(2, budget)
  const indexes = new Set<number>([0, last])
  for (let step = 1; step < slots - 1; step += 1) {
    indexes.add(Math.round((last * step) / (slots - 1)))
  }
  return [...indexes].sort((left, right) => left - right)
}

function closerThanTwoSeconds(times: number[]): boolean {
  let previous = times[0] ?? 0
  for (const time of times.slice(1)) {
    if (Math.abs(time - previous) < 2) {
      return true
    }
    previous = time
  }
  return false
}

export function sparseTimeLabels(times: number[], budget: number): string[] {
  const keep = new Set(keptLabelIndexes(times.length, budget))
  const fractional = closerThanTwoSeconds(times)
  return times.map((time, index) => (keep.has(index) ? formatFileTime(time, fractional) : ""))
}

const FREQUENCY_TARGETS = [50, 100, 200, 500, 1000, 2000, 5000, 10000, 20000]

/** One label per stored row. Hidden rows stay in the category list as blank strings. */
export function frequencyTickLabels(hz: number[]): string[] {
  const positive = hz.filter((value) => value > 0)
  const max = positive.length > 0 ? Math.max(...positive) : 0
  const chosen = new Set<number>()
  for (const target of FREQUENCY_TARGETS) {
    if (target > max * 1.05) {
      continue
    }
    let best = -1
    let bestDist = Number.POSITIVE_INFINITY
    hz.forEach((value, index) => {
      if (!(value > 0)) {
        return
      }
      const dist = Math.abs(Math.log(value) - Math.log(target))
      if (dist < bestDist) {
        best = index
        bestDist = dist
      }
    })
    if (best >= 0) {
      chosen.add(best)
    }
  }
  if (chosen.size === 0 && hz.length > 0) {
    chosen.add(0)
    chosen.add(hz.length - 1)
  }
  return hz.map((value, index) => (chosen.has(index) ? formatFrequency(value) : ""))
}
