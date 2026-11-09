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

/** Viewport modes from docs/design/studio-precision.md. Widths are CSS pixels. */
export function workspaceMode(viewportWidth: number): "wide" | "list-side" | "stacked" | "phone" {
  if (viewportWidth >= 1332) {
    return "wide"
  }
  if (viewportWidth >= 1100) {
    return "list-side"
  }
  if (viewportWidth >= 928) {
    return "stacked"
  }
  return "phone"
}

/**
 * Usable plot width after the rail, 16px stage padding on each side, the chart
 * list, and one 12px gap. Evidence sits under the plot, so it is not subtracted.
 * Assumes a 16px root, matching styles.css.
 */
export function plotBudget(viewportWidth: number): number {
  const mode = workspaceMode(viewportWidth)
  const rail = mode === "phone" ? 0 : 176
  const inner = viewportWidth - rail - 32
  if (mode === "wide" || mode === "list-side") {
    return inner - 160 - 12
  }
  return inner
}
