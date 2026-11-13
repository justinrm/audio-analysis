import type { Asset, PeakBucket } from "./api/types"

export type TechnicalChart = {
  id: string
  title: string
  short: string
  status: "not_run"
  note: string
}

const notRun = "Not run. Nothing has been measured for this recording."

export const LYRIC = [
  { id: "L01", title: "Unified music-and-lyrics timeline", short: "Timeline" },
  { id: "L02", title: "Phrasing and written density", short: "Density" },
  { id: "L03", title: "Energy and dynamic contrast", short: "Energy" },
  { id: "L04", title: "Repetition map", short: "Repetition" },
  { id: "L05", title: "Musical DNA and transferable principles", short: "Principles" },
] as const

export const TECHNICAL: TechnicalChart[] = [
  {
    id: "T01",
    title: "Waveform and peak envelope",
    short: "Waveform",
    status: "not_run",
    note: "The transport drawing is a playback preview, not this chart.",
  },
  { id: "T02", title: "Loudness and dynamics", short: "Loudness", status: "not_run", note: notRun },
  { id: "T03", title: "Long-term spectral balance", short: "Spectrum", status: "not_run", note: notRun },
  { id: "T04", title: "Spectrogram", short: "Spectrogram", status: "not_run", note: notRun },
  { id: "T05", title: "Stereo and mono compatibility", short: "Stereo", status: "not_run", note: notRun },
  { id: "T06", title: "Rhythm and pulse evidence", short: "Pulse", status: "not_run", note: notRun },
  { id: "T07", title: "Pitch-class and tonal estimates", short: "Pitch", status: "not_run", note: notRun },
  { id: "T08", title: "Structure novelty", short: "Novelty", status: "not_run", note: notRun },
  { id: "T09", title: "Recurrence and self-similarity", short: "Recurrence", status: "not_run", note: notRun },
  { id: "T10", title: "Ending, gap, and anomaly review", short: "Events", status: "not_run", note: notRun },
]

export function playbackCaption(asset: Pick<Asset, "subtype" | "playback_status">): string {
  if (asset.playback_status === "unavailable") {
    return "Playback is unavailable. The stored master was not changed."
  }
  if (asset.subtype === "pcm_24") {
    return "Playing a 16-bit copy. The stored master is 24-bit and was not changed."
  }
  return "Playing the stored 16-bit master."
}

/** WaveSurfer draws the first array upward and the second downward. */
export function toWavePeaks(buckets: PeakBucket[]): [number[], number[]] {
  return [
    buckets.map((bucket) => Math.max(0, bucket.max)),
    buckets.map((bucket) => Math.max(0, -bucket.min)),
  ]
}

export function clock(seconds: number, precise = false): string {
  const safe = Number.isFinite(seconds) && seconds > 0 ? seconds : 0
  const rounded = Math.round(safe)
  const minutes = Math.floor((precise ? safe : rounded) / 60)
  const remain = precise ? safe - minutes * 60 : rounded % 60
  const whole = Math.floor(remain)
  const body = `${minutes}:${whole.toString().padStart(2, "0")}`
  if (!precise) {
    return body
  }
  const tenth = Math.min(9, Math.floor((remain - whole) * 10))
  return `${body}.${tenth}`
}

const STATUS_LABEL: Record<string, string> = {
  not_run: "Not run",
  not_available: "Not available",
  ready: "Ready",
  failed: "Failed",
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  canceled: "Canceled",
  unavailable: "Unavailable",
}

/** Display word for a job, chart, or playback status. Evidence class is not a status. */
export function statusLabel(value: string): string {
  return STATUS_LABEL[value] ?? value
}

export function formatLabel(asset: Pick<Asset, "subtype" | "sample_rate" | "channels">): string {
  const bits = asset.subtype === "pcm_16" ? "16-bit PCM" : "24-bit PCM"
  const khz = asset.sample_rate / 1000
  const rate = Number.isInteger(khz) ? `${khz} kHz` : `${khz.toFixed(1)} kHz`
  const channels = asset.channels === 1 ? "mono" : asset.channels === 2 ? "stereo" : `${asset.channels} ch`
  return `${bits}, ${rate}, ${channels}`
}

const EVIDENCE_LABEL: Record<string, string> = {
  measured: "Measured",
  estimated: "Estimated",
  textual: "Textual",
  interpretive: "Interpretive",
  unknown: "Unknown",
  not_applicable: "Not applicable",
}

/** Display word for an evidence class. This is not a status. */
export function evidenceLabel(value: string): string {
  return EVIDENCE_LABEL[value] ?? value
}

export function combinedEvidenceNote(status: string, evidenceClass: string, caveats: readonly string[]): string {
  if (status === "ready" && evidenceClass === "unknown" && caveats.some((item) => item.includes("combines"))) {
    return "Combined classes, not missing data."
  }
  return ""
}

/** Side-inspector width. This is a presentation budget, not a measured audio threshold. */
export const INSPECTOR_WIDTH = 288

/** Gap between the chart container and a side inspector. */
export const INSPECTOR_GAP = 16

/**
 * Chart-container width that must remain before evidence may sit beside the plot.
 * A layout constraint, not a scientific measurement threshold.
 */
export const INSPECTOR_PLOT_MIN = 800

const RAIL_WIDTH = 176
const PHONE_MAX = 927

/** Horizontal stage padding on each side. Desktop is 24px. Narrow recording screens are 16px. */
export function stageGutter(viewportWidth: number): number {
  return viewportWidth <= PHONE_MAX ? 16 : 24
}

/** Width inside the recording stage after the rail and gutters. */
export function recordingStageWidth(viewportWidth: number): number {
  const rail = viewportWidth <= PHONE_MAX ? 0 : RAIL_WIDTH
  return viewportWidth - rail - stageGutter(viewportWidth) * 2
}

/** True when docking a 288px inspector would still leave an 800px chart container. */
export function inspectorFitsBeside(stageWidth: number): boolean {
  return stageWidth - INSPECTOR_WIDTH - INSPECTOR_GAP >= INSPECTOR_PLOT_MIN
}

/**
 * Technical chart-container width for a viewport.
 * Open evidence is subtracted only when it fits beside the plot.
 * Assumes a 16px root and the recording-stage gutters in styles.css.
 */
export function plotBudget(viewportWidth: number, evidenceOpen = false): number {
  const stage = recordingStageWidth(viewportWidth)
  if (evidenceOpen && inspectorFitsBeside(stage)) {
    return stage - INSPECTOR_WIDTH - INSPECTOR_GAP
  }
  return stage
}
