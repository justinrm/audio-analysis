import type { Asset, PeakBucket } from "./api/types"

export type TechnicalChart = {
  id: string
  title: string
  status: "not_run"
  note: string
}

const notRun = "Not run. Nothing has been measured for this recording."

export const TECHNICAL: TechnicalChart[] = [
  {
    id: "T01",
    title: "Waveform and peak envelope",
    status: "not_run",
    note: "The transport drawing is a playback preview, not this chart.",
  },
  { id: "T02", title: "Loudness and dynamics", status: "not_run", note: notRun },
  { id: "T03", title: "Long-term spectral balance", status: "not_run", note: notRun },
  { id: "T04", title: "Spectrogram", status: "not_run", note: notRun },
  { id: "T05", title: "Stereo and mono compatibility", status: "not_run", note: notRun },
  { id: "T06", title: "Rhythm and pulse evidence", status: "not_run", note: notRun },
  { id: "T07", title: "Pitch-class and tonal estimates", status: "not_run", note: notRun },
  { id: "T08", title: "Structure novelty", status: "not_run", note: notRun },
  { id: "T09", title: "Recurrence and self-similarity", status: "not_run", note: notRun },
  { id: "T10", title: "Ending, gap, and anomaly review", status: "not_run", note: notRun },
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
