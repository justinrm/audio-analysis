// @ts-expect-error Frontend typecheck does not include Node's fs types.
import { readFileSync } from "node:fs"
import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { Asset, Project, ProjectDetail } from "./api/types"
import { Library } from "./library"

const api = vi.hoisted(() => ({
  projects: vi.fn(),
  project: vi.fn(),
  createProject: vi.fn(),
  upload: vi.fn(),
}))

vi.mock("./api/client", () => ({ api }))

function study(id: string, name: string): Project {
  return { id, name, mode: "study", created_at: "2026-10-12T00:00:00Z", updated_at: "2026-10-12T00:00:00Z" }
}

function recording(partial: Pick<Asset, "id" | "original_name" | "analysis_status" | "playback_status">): Asset {
  return {
    sha256: "abc",
    byte_length: 44,
    duration_s: 12,
    sample_rate: 44100,
    channels: 2,
    subtype: "pcm_16",
    created_at: "2026-10-12T06:11:17Z",
    ...partial,
  }
}

const older = study("p-old", "Reference study")
const newer = study("p-new", "QA study")
const tone = recording({
  id: "a-tone",
  original_name: "browser-tone.wav",
  analysis_status: "not_run",
  playback_status: "ready",
})
const longName = "Evening-session-reference-with-a-very-long-file-name.wav"
const chase = recording({
  id: "a-chase",
  original_name: longName,
  analysis_status: "completed",
  playback_status: "unavailable",
})

function detail(project: Project, assets: Asset[]): ProjectDetail {
  return { ...project, assets }
}

beforeEach(() => {
  api.projects.mockReset()
  api.project.mockReset()
  api.upload.mockReset()
  api.projects.mockResolvedValue([older, newer])
  api.project.mockImplementation(async (id: string) =>
    id === older.id ? detail(older, [tone]) : detail(newer, [chase]),
  )
})

describe("library studies", () => {
  it("shows the first saved study and can switch to another", async () => {
    const opened: string[] = []
    render(<Library onOpen={(assetId) => opened.push(assetId)} />)

    const openTone = await screen.findByRole("button", { name: "Open browser-tone.wav" })
    expect(screen.getByText("Not run")).toBeTruthy()
    expect(screen.getByText("Ready")).toBeTruthy()
    expect(screen.queryByText("not_run")).toBeNull()
    expect(screen.queryByText(longName)).toBeNull()

    fireEvent.change(screen.getByRole("combobox", { name: "Study" }), { target: { value: newer.id } })
    const openLong = await screen.findByRole("button", { name: `Open ${longName}` })
    expect(openLong.closest("tr")?.textContent).toContain(longName)
    expect(screen.getByText("Completed")).toBeTruthy()
    expect(screen.getByText("Unavailable")).toBeTruthy()
    expect(screen.queryByText("unavailable")).toBeNull()
    expect(screen.queryByText("browser-tone.wav")).toBeNull()

    fireEvent.click(openLong)
    expect(opened).toEqual(["a-chase"])
    expect(openTone).toBeTruthy()
  })

  it("reports import success and failure without dropping the study", async () => {
    api.projects.mockResolvedValue([older])
    api.project.mockResolvedValue(detail(older, []))
    render(<Library onOpen={() => undefined} />)
    expect(await screen.findByText("No recordings in this study yet.")).toBeTruthy()

    api.upload.mockRejectedValueOnce(new Error("Not a WAV."))
    const input = document.getElementById("import-wav") as HTMLInputElement
    fireEvent.change(input, { target: { files: [new File(["x"], "notes.txt", { type: "text/plain" })] } })
    expect((await screen.findByRole("alert")).textContent).toMatch(/Not a WAV/)
    expect(screen.getByText("No recordings in this study yet.")).toBeTruthy()

    api.upload.mockResolvedValueOnce({ cache: "miss", asset: tone })
    api.project.mockResolvedValue(detail(older, [tone]))
    fireEvent.change(document.getElementById("import-wav") as HTMLInputElement, {
      target: { files: [new File(["x"], "browser-tone.wav", { type: "audio/wav" })] },
    })
    expect((await screen.findByRole("status")).textContent).toMatch(/Imported/)
    expect(await screen.findByRole("button", { name: "Open browser-tone.wav" })).toBeTruthy()
    expect(screen.queryByRole("alert")).toBeNull()
  })

  function styles(): string {
    const cssPath = decodeURIComponent(import.meta.url.slice("file://".length)).replace(/[^/]+$/, "styles.css")
    return readFileSync(cssPath, "utf8")
  }

  it("wraps long filenames only in the narrow library", () => {
    const css = styles()
    const desktop = css.slice(0, css.indexOf("@media (max-width: 927px)"))
    const desktopName = desktop.slice(desktop.indexOf(".log td.name {"))
    expect(desktopName).toContain("white-space: nowrap")
    expect(desktopName).toContain("text-overflow: ellipsis")
    const narrow = css.slice(css.indexOf("@media (max-width: 927px)"))
    const narrowName = narrow.slice(narrow.indexOf(".log td.name {"), narrow.indexOf("}", narrow.indexOf(".log td.name {")))
    expect(narrowName).toContain("white-space: normal")
    expect(narrowName).toContain("overflow-wrap: anywhere")
  })

  it("packs the mobile shell under the navigation", () => {
    const css = styles()
    const narrow = css.slice(css.indexOf("@media (max-width: 927px)"))
    const shell = narrow.slice(narrow.indexOf(".shell {"), narrow.indexOf("}", narrow.indexOf(".shell {")))
    expect(shell).toContain("align-content: start")
  })
})
