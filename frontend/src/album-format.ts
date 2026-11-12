const MEASUREMENTS: Record<string, string> = {
  integrated_loudness: "Integrated loudness",
  loudness_range: "Loudness range",
  sample_peak: "Sample peak",
  rms: "Whole-file RMS",
  crest_factor: "Crest factor",
  ffmpeg_true_peak: "FFmpeg true peak",
  reconstructed_peak: "4× reconstructed peak",
  correlation: "Whole-file correlation",
  side_mid: "Side/mid",
  mono_fold_down: "Mono fold-down change",
  sub_bass_correlation: "Correlation below 120 Hz",
}

const CHECKPOINTS: Record<string, string> = {
  sample_peak: "Sample peak",
  ffmpeg_true_peak: "FFmpeg true peak",
  reconstructed_peak: "4× reconstructed peak",
  full_scale_rail: "Full-scale samples",
  endpoint: "Endpoint",
  tail_level: "Ending level",
  subthreshold: "Sub-threshold intervals",
  level_spread: "Loudness spread",
}

const OMIT: Record<string, string> = {
  analysis_incomplete: "Analysis incomplete",
  unsupported_analysis_version: "Unsupported analysis version",
  chart_missing: "Required charts missing",
}

const REASONS: Record<string, string> = {
  missing_value: "Missing value",
  method_mismatch: "Method mismatch",
  band_edges_differ: "Band edges differ",
  no_bands: "No bands stored",
}

export function measurementLabel(name: string): string {
  return MEASUREMENTS[name] ?? name
}

export function checkpointLabel(id: string): string {
  return CHECKPOINTS[id] ?? measurementLabel(id)
}

export function omitLabel(reason: string | null | undefined): string {
  if (!reason) {
    return "Not included"
  }
  return OMIT[reason] ?? reason
}

export function evidenceReason(reason: string | null | undefined): string {
  if (!reason) {
    return "Not stored"
  }
  return REASONS[reason] ?? reason
}

/** Absolute dBFS, LUFS, and dBTP stay on levels. Their differences are dB, LU, and dB. */
export function differenceUnit(unit: string): string {
  if (unit === "dBFS" || unit === "dBTP") {
    return "dB"
  }
  if (unit === "LUFS") {
    return "LU"
  }
  return unit
}

function digitsFor(unit: string): number {
  if (unit === "LUFS" || unit === "LU") {
    return 1
  }
  if (unit === "ratio" || unit === "score" || unit === "s") {
    return 3
  }
  return 2
}

export function formatNumber(value: number, unit: string): string {
  return value.toFixed(digitsFor(unit))
}

export function formatMeasure(value: number, unit: string): string {
  return `${formatNumber(value, unit)} ${unit}`
}

export function formatCount(value: number | null): string {
  if (value === null || !Number.isFinite(value)) {
    return "Not stored"
  }
  return String(value)
}

export function formatScore(value: number): string {
  return value.toFixed(3)
}

export function storedNumber(value: number): string {
  return String(value)
}

export function pairKey(pair: { left_asset_id: string; right_asset_id: string }): string {
  return `${pair.left_asset_id}:${pair.right_asset_id}`
}

export function filterPairs<T extends { left_asset_id: string; right_asset_id: string }>(
  tracks: readonly { asset_id: string; ordering: number }[],
  pairs: readonly T[],
  choice: string,
): T[] {
  if (choice === "all") {
    return [...pairs]
  }
  if (choice !== "adjacent") {
    return pairs.filter((pair) => pairKey(pair) === choice)
  }
  const order = new Map(tracks.map((track) => [track.asset_id, track.ordering]))
  return pairs.filter((pair) => {
    const earlier = order.get(pair.left_asset_id)
    const later = order.get(pair.right_asset_id)
    return earlier !== undefined && later !== undefined && later - earlier === 1
  })
}
