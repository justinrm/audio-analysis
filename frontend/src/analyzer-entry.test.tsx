import { fireEvent, render, screen } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { Asset, Project, ProjectDetail } from "./api/types"
import { AnalyzerEntry } from "./analyzer-entry"

const api = vi.hoisted(() => ({
  projects: vi.fn(),
  project: vi.fn(),
  createProject: vi.fn(),
  upload: vi.fn(),
  analyze: vi.fn(),
}))

vi.mock("./api/client", () => ({ api }))

function study(id: string, name: string): Project {
  return { id, name, mode: "study", created_at: "", updated_at: "" }
}

function recording(id: string, name: string): Asset {
  return {
    id,
    sha256: "abc",
    original_name: name,
    byte_length: 44,
    duration_s: 1,
    sample_rate: 44100,
    channels: 2,
    subtype: "pcm_16",
    analysis_status: "not_run",
    playback_status: "ready",
    created_at: "",
  }
}

describe("assetless analyzer entry", () => {
  beforeEach(() => {
    api.projects.mockReset()
    api.project.mockReset()
    api.createProject.mockReset()
    api.upload.mockReset()
    api.analyze.mockReset()
  })

  it("lists study recordings with reads and opens the selected one", async () => {
    const opened: string[] = []
    api.projects.mockResolvedValue([study("p", "Night study"), { ...study("album", "Album"), mode: "album" }])
    api.project.mockResolvedValue({
      ...study("p", "Night study"),
      assets: [recording("a", "night.wav")],
    } satisfies ProjectDetail)
    render(
      <AnalyzerEntry
        onOpen={(assetId, projectId) => opened.push(`${projectId}:${assetId}`)}
        onLibrary={() => opened.push("library")}
      />,
    )
    expect(screen.getByRole("status").textContent).toMatch(/Loading recordings/)
    fireEvent.click(await screen.findByRole("button", { name: "night.wav" }))
    expect(opened).toEqual(["p:a"])
    fireEvent.click(screen.getByRole("button", { name: "Open Library" }))
    expect(opened).toEqual(["p:a", "library"])
    expect(api.projects).toHaveBeenCalledTimes(1)
    expect(api.project).toHaveBeenCalledTimes(1)
    expect(api.project).toHaveBeenCalledWith("p")
    expect(api.createProject).not.toHaveBeenCalled()
    expect(api.upload).not.toHaveBeenCalled()
    expect(api.analyze).not.toHaveBeenCalled()
  })

  it("shows an empty study and a load error without writing", async () => {
    api.projects.mockResolvedValueOnce([study("p", "Empty study")])
    api.project.mockResolvedValueOnce({ ...study("p", "Empty study"), assets: [] } satisfies ProjectDetail)
    const view = render(<AnalyzerEntry onOpen={() => undefined} onLibrary={() => undefined} />)
    expect(await screen.findByText("This study has no recordings.")).toBeTruthy()
    view.unmount()
    api.projects.mockRejectedValueOnce(new Error("Library unavailable."))
    render(<AnalyzerEntry onOpen={() => undefined} onLibrary={() => undefined} />)
    expect((await screen.findByRole("alert")).textContent).toMatch(/Library unavailable/)
    expect(api.createProject).not.toHaveBeenCalled()
    expect(api.upload).not.toHaveBeenCalled()
    expect(api.analyze).not.toHaveBeenCalled()
  })
})
