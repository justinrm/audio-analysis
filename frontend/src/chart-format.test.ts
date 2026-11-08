import { describe, expect, it } from "vitest"
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
  SERIES_LUFS,
  SERIES_REVIEW,
  SERIES_SLATE,
  SERIES_WARM,
  keptLabelIndexes,
  seriesPaint,
  sparseTimeLabels,
} from "./chart-format"

function linear(channel: number): number {
  const value = channel / 255
  return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4
}

function contrast(hex: string, ground: string): number {
  const lum = (color: string) => {
    const r = linear(Number.parseInt(color.slice(1, 3), 16))
    const g = linear(Number.parseInt(color.slice(3, 5), 16))
    const b = linear(Number.parseInt(color.slice(5, 7), 16))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
  }
  const left = lum(hex)
  const right = lum(ground)
  const lighter = Math.max(left, right)
  const darker = Math.min(left, right)
  return (lighter + 0.05) / (darker + 0.05)
}

describe("chart display format", () => {
  it("formats file time, frequency, levels, and stored labels", () => {
    expect(formatFileTime(0)).toBe("0:00")
    expect(formatFileTime(90)).toBe("1:30")
    expect(formatFileTime(1.25)).toBe("0:01.2")
    expect(formatFrequency(100)).toBe("100 Hz")
    expect(formatFrequency(1500)).toBe("1.5 kHz")
    expect(formatFrequency(4000)).toBe("4 kHz")
    expect(formatLevelTick(-14.24, 12)).toBe("-14.2")
    expect(formatLevelTick(-40, 30)).toBe("-40")
    expect(formatLevelTick(0.012, 0.05)).toBe("0.012")
    expect(formatLevelTick(7.4e-5, 7.4e-5)).toBe("7.4e-5")
    expect(formatLevelTick(-18.32, 0)).toBe("-18.3")
    expect(formatLevelTick(0, 0)).toBe("0")
    expect(formatTooltipValue(0.25, "ratio")).toBe("0.250")
    expect(formatTooltipValue(0.082, "share")).toBe("0.082")
    expect(formatTooltipValue(12.26, "%")).toBe("12.3")
    expect(formatTooltipValue(-14.2, "LUFS")).toBe("-14.2")
    expect(formatTooltipValue(-3.04, "dBFS")).toBe("-3.0")
    expect(formatTooltipValue(0.256, "cosine similarity")).toBe("0.26")
    expect(formatCategoryLabel("122.3 BPM (double-time)")).toBe("122.3 BPM (double-time)")
    expect(formatStored(-80)).toBe("-80")
  })

  it("keeps a category slot for every frequency and blanks the rest", () => {
    const labels = frequencyTickLabels([70, 100, 480, 1000, 19000])
    expect(labels).toHaveLength(5)
    expect(labels.filter(Boolean).length).toBeGreaterThan(1)
    expect(labels.every((label, index) => label === "" || label.includes(index === 3 ? "kHz" : ""))).toBe(true)
    expect(sparseTimeLabels([1, 3, 5], 10)).toEqual(["0:01", "0:03", "0:05"])
    expect(keptLabelIndexes(48, 6)).toHaveLength(6)
  })

  it("uses contrast-safe series colors and a heatmap low stop above 1.35:1", () => {
    for (const color of [SERIES_INK, SERIES_ENERGY, SERIES_LUFS, SERIES_WARM, SERIES_SLATE, SERIES_ESTIMATED, SERIES_REVIEW, AXIS_TITLE]) {
      expect(contrast(color, PLOT_GROUND)).toBeGreaterThanOrEqual(4.5)
    }
    expect(HEATMAP_COLORS[0]).not.toBe("#243044")
    expect(HEATMAP_COLORS[0]).not.toBe("#1c2430")
    expect(contrast(HEATMAP_COLORS[0], PLOT_GROUND)).toBeGreaterThan(2.5)
    expect(seriesPaint("LUFS", 0, "measured", "T02").dash).toBe("dashed")
    expect(seriesPaint("dB", 0, "measured", "T05").dash).toBe("dashed")
    expect(seriesPaint("amplitude", 0, "measured", "T01").color).toBe(SERIES_INK)
    expect(seriesPaint("amplitude", 2, "measured", "T01").color).toBe(SERIES_SLATE)
    expect(seriesPaint("amplitude", 2, "measured", "T01").dash).toBe("dashed")
    expect(seriesPaint("dBFS", 0, "measured", "T01").color).not.toBe(SERIES_REVIEW)
  })
})
