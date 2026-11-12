// @ts-expect-error Frontend typecheck does not include Node's fs types.
import { readFileSync } from "node:fs"
import { fireEvent, render, screen, waitFor } from "@testing-library/react"
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

function wavFile(name: string): File {
  return new File(["x"], name, { type: "audio/wav" })
}

function pendingUpload() {
  let resolve!: (value: { cache: "hit" | "miss"; asset: Asset }) => void
  const promise = new Promise<{ cache: "hit" | "miss"; asset: Asset }>((res) => {
    resolve = res
  })
  return { promise, resolve }
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
  it("lists a study and skips an album project", async () => {
    api.projects.mockResolvedValue([
      { id: "album-1", name: "Night album", mode: "album", created_at: older.created_at, updated_at: older.updated_at },
      newer,
    ])
    render(<Library onOpen={() => undefined} />)
    expect(await screen.findByRole("button", { name: `Open ${longName}` })).toBeTruthy()
    expect(screen.queryByText("Night album")).toBeNull()
    expect(screen.getByText("QA study")).toBeTruthy()
  })

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
    expect((await screen.findByRole("status")).textContent).toBe("Imported.")
    expect(await screen.findByRole("button", { name: "Open browser-tone.wav" })).toBeTruthy()
    expect(screen.queryByRole("alert")).toBeNull()
  })

  it("keeps an album out of the study list after import", async () => {
    api.projects.mockResolvedValue([older])
    api.project.mockResolvedValue(detail(older, []))
    render(<Library onOpen={() => undefined} />)
    expect(await screen.findByText("No recordings in this study yet.")).toBeTruthy()
    api.projects.mockResolvedValue([
      { id: "album-1", name: "Night album", mode: "album", created_at: older.created_at, updated_at: older.updated_at },
      older,
    ])
    api.upload.mockResolvedValueOnce({ cache: "miss", asset: tone })
    api.project.mockResolvedValue(detail(older, [tone]))
    fireEvent.change(document.getElementById("import-wav") as HTMLInputElement, {
      target: { files: [new File(["x"], "browser-tone.wav", { type: "audio/wav" })] },
    })
    expect(await screen.findByRole("button", { name: "Open browser-tone.wav" })).toBeTruthy()
    expect(screen.queryByText("Night album")).toBeNull()
    expect(screen.getByText("Reference study")).toBeTruthy()
  })

  it("imports each selected wav before refreshing the study", async () => {
    api.projects.mockResolvedValue([older, newer])
    api.project.mockImplementation(async (id: string) =>
      id === older.id ? detail(older, []) : detail(newer, [chase]),
    )
    render(<Library onOpen={() => undefined} />)
    expect(await screen.findByText("No recordings in this study yet.")).toBeTruthy()

    const calls: string[] = []
    const gates = [pendingUpload(), pendingUpload()]
    api.upload.mockImplementation((_projectId: string, file: File) => {
      calls.push(file.name)
      return gates[calls.length - 1].promise
    })

    const input = document.getElementById("import-wav") as HTMLInputElement
    expect(input.multiple).toBe(true)
    expect(input.accept).toBe(".wav,audio/wav")
    fireEvent.change(input, { target: { files: [wavFile("one.wav"), wavFile("two.wav")] } })

    expect(await screen.findByText("Importing 1 of 2: one.wav")).toBeTruthy()
    expect(calls).toEqual(["one.wav"])
    expect((screen.getByRole("button", { name: "Import WAV" }) as HTMLButtonElement).disabled).toBe(true)
    expect(input.disabled).toBe(true)
    expect((screen.getByRole("combobox", { name: "Study" }) as HTMLSelectElement).disabled).toBe(true)
    expect(screen.queryByRole("button", { name: "Open one.wav" })).toBeNull()

    const one = recording({
      id: "a-one",
      original_name: "one.wav",
      analysis_status: "not_run",
      playback_status: "ready",
    })
    const two = recording({
      id: "a-two",
      original_name: "two.wav",
      analysis_status: "not_run",
      playback_status: "ready",
    })
    gates[0].resolve({ cache: "miss", asset: one })
    expect(await screen.findByText("Importing 2 of 2: two.wav")).toBeTruthy()
    expect(calls).toEqual(["one.wav", "two.wav"])
    expect(screen.queryByRole("button", { name: "Open one.wav" })).toBeNull()

    api.projects.mockResolvedValue([
      { id: "album-1", name: "Night album", mode: "album", created_at: older.created_at, updated_at: older.updated_at },
      older,
      newer,
    ])
    api.project.mockImplementation(async (id: string) =>
      id === older.id ? detail(older, [one, two]) : detail(newer, [chase]),
    )
    gates[1].resolve({ cache: "miss", asset: two })

    expect(await screen.findByText("Imported 2. Reused 0.")).toBeTruthy()
    expect(await screen.findByRole("button", { name: "Open one.wav" })).toBeTruthy()
    expect(screen.getByRole("button", { name: "Open two.wav" })).toBeTruthy()
    expect(screen.queryByText("Night album")).toBeNull()
    expect(screen.getByRole("combobox", { name: "Study" }).textContent).toContain("QA study")
    await waitFor(() => {
      expect((screen.getByRole("button", { name: "Import WAV" }) as HTMLButtonElement).disabled).toBe(false)
    })
    expect(api.upload.mock.calls.map((call) => call[0])).toEqual([older.id, older.id])
  })

  it("names a failed file and still imports the files after it", async () => {
    api.projects.mockResolvedValue([older])
    api.project.mockResolvedValue(detail(older, []))
    render(<Library onOpen={() => undefined} />)
    expect(await screen.findByText("No recordings in this study yet.")).toBeTruthy()

    const calls: string[] = []
    const gates = [pendingUpload(), pendingUpload()]
    api.upload.mockImplementation((_projectId: string, file: File) => {
      calls.push(file.name)
      if (file.name === "bad.wav") {
        return Promise.reject(new Error("Not a WAV."))
      }
      return (file.name === "one.wav" ? gates[0] : gates[1]).promise
    })
    fireEvent.change(document.getElementById("import-wav") as HTMLInputElement, {
      target: { files: [wavFile("one.wav"), wavFile("bad.wav"), wavFile("old.wav")] },
    })

    expect(await screen.findByText("Importing 1 of 3: one.wav")).toBeTruthy()
    expect(calls).toEqual(["one.wav"])
    const one = recording({
      id: "a-one",
      original_name: "one.wav",
      analysis_status: "not_run",
      playback_status: "ready",
    })
    const old = recording({
      id: "a-old",
      original_name: "old.wav",
      analysis_status: "completed",
      playback_status: "ready",
    })
    gates[0].resolve({ cache: "miss", asset: one })
    expect(await screen.findByText("Importing 3 of 3: old.wav")).toBeTruthy()
    expect(calls).toEqual(["one.wav", "bad.wav", "old.wav"])

    api.project.mockResolvedValue(detail(older, [one, old]))
    gates[1].resolve({ cache: "hit", asset: old })
    expect((await screen.findByRole("alert")).textContent).toBe(
      "Imported 1. Reused 1: old.wav. Failed: bad.wav.",
    )
    expect(await screen.findByRole("button", { name: "Open one.wav" })).toBeTruthy()
    expect(screen.getByRole("button", { name: "Open old.wav" })).toBeTruthy()
    expect(screen.queryByRole("button", { name: "Open bad.wav" })).toBeNull()
  })

  it("imports the same files again after the batch finishes", async () => {
    api.projects.mockResolvedValue([older])
    api.project.mockResolvedValue(detail(older, []))
    render(<Library onOpen={() => undefined} />)
    expect(await screen.findByText("No recordings in this study yet.")).toBeTruthy()
    const one = recording({
      id: "a-one",
      original_name: "one.wav",
      analysis_status: "not_run",
      playback_status: "ready",
    })
    api.upload.mockResolvedValue({ cache: "miss", asset: one })
    api.project.mockResolvedValue(detail(older, [one]))
    const input = document.getElementById("import-wav") as HTMLInputElement
    const files = [wavFile("one.wav"), wavFile("two.wav")]
    fireEvent.change(input, { target: { files } })
    expect(await screen.findByText("Imported 2. Reused 0.")).toBeTruthy()
    expect(input.value).toBe("")
    expect(api.upload).toHaveBeenCalledTimes(2)
    expect((screen.getByRole("button", { name: "Import WAV" }) as HTMLButtonElement).disabled).toBe(false)

    fireEvent.change(input, { target: { files } })
    await waitFor(() => expect(api.upload).toHaveBeenCalledTimes(4))
  })

  it("reports one reused file without a batch summary", async () => {
    api.projects.mockResolvedValue([older])
    api.project.mockResolvedValue(detail(older, []))
    render(<Library onOpen={() => undefined} />)
    expect(await screen.findByText("No recordings in this study yet.")).toBeTruthy()
    const gate = pendingUpload()
    api.upload.mockImplementation(() => gate.promise)
    fireEvent.change(document.getElementById("import-wav") as HTMLInputElement, {
      target: { files: [wavFile("browser-tone.wav")] },
    })
    expect(await screen.findByText("Importing.")).toBeTruthy()
    api.project.mockResolvedValue(detail(older, [tone]))
    gate.resolve({ cache: "hit", asset: tone })
    expect(await screen.findByText("Already in the library. Reused the stored file.")).toBeTruthy()
    expect(await screen.findByRole("button", { name: "Open browser-tone.wav" })).toBeTruthy()
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

  it("lets the narrow chart table wrap its headers", () => {
    const css = styles()
    const narrow = css.slice(css.indexOf("@media (max-width: 927px)"))
    const table = narrow.slice(narrow.lastIndexOf(".chart-data th"))
    expect(table).toContain("white-space: normal")
    expect(table).toContain("overflow-wrap: anywhere")
  })
})
