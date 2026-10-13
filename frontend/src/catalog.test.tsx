import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import { TechnicalBoard } from "./analyzer"
import { playbackCaption, TECHNICAL } from "./catalog"

describe("milestone 0 analysis state", () => {
  it("lists T01 through T10 as not run", () => {
    expect(TECHNICAL.map((item) => item.id)).toEqual([
      "T01",
      "T02",
      "T03",
      "T04",
      "T05",
      "T06",
      "T07",
      "T08",
      "T09",
      "T10",
    ])
    expect(TECHNICAL.every((item) => item.status === "not_run")).toBe(true)
  })

  it("shows not-run analysis and does not offer a progress control", () => {
    render(<TechnicalBoard notice="" onAnalyze={() => undefined} />)
    expect(screen.getByRole("tab", { name: "Technical Analysis" }).getAttribute("aria-selected")).toBe("true")
    expect(screen.getAllByText(/not run/i).length).toBeGreaterThan(0)
    expect(screen.queryByRole("progressbar")).toBeNull()
    fireEvent.click(screen.getByRole("tab", { name: "Lyrics & Inspiration" }))
    expect(screen.getByText(/text upload is not in this milestone/i)).toBeTruthy()
    expect(screen.getByText(/no evidence yet/i)).toBeTruthy()
  })

  it("distinguishes a 24-bit master from the playback copy", () => {
    const caption = playbackCaption({ subtype: "pcm_24", playback_status: "ready" })
    expect(caption).toContain("16-bit copy")
    expect(caption).toContain("was not changed")
  })
})
