import { describe, expect, it } from "vitest"
import {
  differenceUnit,
  filterPairs,
  formatCount,
  formatMeasure,
  formatScore,
  measurementLabel,
  pairKey,
  storedNumber,
} from "./album-format"

describe("album presentation", () => {
  it("keeps absolute units and labels a difference without changing the number", () => {
    expect(formatMeasure(-1, "dBFS")).toBe("-1.00 dBFS")
    expect(formatMeasure(-14.24, "LUFS")).toBe("-14.2 LUFS")
    expect(formatMeasure(-0.4, "dBTP")).toBe("-0.40 dBTP")
    expect(differenceUnit("dBFS")).toBe("dB")
    expect(differenceUnit("LUFS")).toBe("LU")
    expect(differenceUnit("dBTP")).toBe("dB")
    expect(differenceUnit("LU")).toBe("LU")
    const peakDelta = -3 - -1
    const truePeakDelta = -0.25 - -1
    expect(formatMeasure(peakDelta, differenceUnit("dBFS"))).toBe("-2.00 dB")
    expect(formatMeasure(3.1, differenceUnit("LUFS"))).toBe("3.1 LU")
    expect(formatMeasure(truePeakDelta, differenceUnit("dBTP"))).toBe("0.75 dB")
    expect(truePeakDelta).toBe(0.75)
    expect(measurementLabel("integrated_loudness")).toBe("Integrated loudness")
    expect(measurementLabel("sample_peak")).not.toContain("_")
    expect(formatCount(12)).toBe("12")
    expect(formatCount(0)).toBe("0")
    expect(formatCount(null)).toBe("Not stored")
    expect(formatScore(0.41237)).toBe("0.412")
    expect(storedNumber(0.41237)).toBe("0.41237")
  })

  it("shows adjacent pairs by default and keeps every stored pair available", () => {
    const tracks = Array.from({ length: 6 }, (_, index) => ({ asset_id: `t${index}`, ordering: index }))
    const pairs = tracks.flatMap((left, index) =>
      tracks.slice(index + 1).map((right) => ({
        left_asset_id: left.asset_id,
        right_asset_id: right.asset_id,
        deltas: [{ name: "sample_peak", delta: Number(right.asset_id.slice(1)) - index }],
      })),
    )
    expect(pairs).toHaveLength(15)
    const adjacent = filterPairs(tracks, pairs, "adjacent")
    expect(adjacent).toHaveLength(5)
    expect(adjacent.map((pair) => pair.deltas[0]?.delta)).toEqual([1, 1, 1, 1, 1])
    expect(filterPairs(tracks, pairs, "all")).toHaveLength(15)
    const far = pairs.find((pair) => pair.left_asset_id === "t0" && pair.right_asset_id === "t5")
    expect(far).toBeTruthy()
    expect(filterPairs(tracks, pairs, pairKey(far!))[0]?.deltas[0]?.delta).toBe(5)
    expect(filterPairs(tracks, pairs, "adjacent").some((pair) => pair.right_asset_id === "t5" && pair.left_asset_id === "t0")).toBe(
      false,
    )
  })
})