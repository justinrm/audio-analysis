import { fireEvent, render, screen, waitFor } from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { ApiError } from "./api/client"
import type { AnnotationOut, LyricDocumentOut, LyricSegmentOut } from "./api/types"
import { Analyzer } from "./analyzer"
import {
  activeSegmentId,
  regionLabel,
  reviewHints,
  syncLyricRegions,
  type LyricCue,
  type LyricRegionPlugin,
  LyricsWorkspace,
  type LyricBridge,
} from "./lyrics"

const api = vi.hoisted(() => ({
  asset: vi.fn(),
  peaks: vi.fn(),
  charts: vi.fn(),
  chart: vi.fn(),
  projects: vi.fn(),
  project: vi.fn(),
  lyrics: vi.fn(),
  annotations: vi.fn(),
  uploadLyrics: vi.fn(),
  updateSegment: vi.fn(),
  verifySegment: vi.fn(),
  createAnnotation: vi.fn(),
  deleteAnnotation: vi.fn(),
  lyricCharts: vi.fn(),
  lyricChart: vi.fn(),
}))

const bus = vi.hoisted(() => {
  const handlers = new Map<string, Set<(...args: never[]) => void>>()
  const added: { id: string; start: number; end: number; content: string }[] = []
  let echo = false
  let onTime: ((value: number) => void) | undefined
  return {
    handlers,
    added,
    created: [] as number[],
    setTime: vi.fn(),
    setEcho(value: boolean) {
      echo = value
    },
    time(value: number) {
      onTime?.(value)
    },
    emit(name: string, ...args: never[]) {
      handlers.get(name)?.forEach((handler) => handler(...args))
    },
    plugin() {
      return {
        on(name: string, handler: (...args: never[]) => void) {
          const set = handlers.get(name) ?? new Set<(...args: never[]) => void>()
          set.add(handler)
          handlers.set(name, set)
          return () => set.delete(handler)
        },
        clearRegions() {
          added.length = 0
        },
        getRegions() {
          return added.map((region) => ({
            ...region,
            setOptions(next: { content?: string }) {
              if (next.content != null) {
                region.content = next.content
              }
            },
          }))
        },
        addRegion(options: { id: string; start: number; end: number; content?: string }) {
          const region = {
            id: options.id,
            start: options.start,
            end: options.end,
            content: options.content ?? "",
            setOptions(next: { content?: string }) {
              if (next.content != null) {
                region.content = next.content
              }
            },
            remove() {},
          }
          added.push(region)
          if (echo) {
            handlers.get("region-updated")?.forEach((handler) => handler(region as never))
          }
          return region
        },
      }
    },
    bindTime(handler: (value: number) => void) {
      onTime = handler
    },
    reset() {
      handlers.clear()
      added.length = 0
      this.created.length = 0
      this.setTime.mockClear()
      echo = false
      onTime = undefined
    },
  }
})

vi.mock("./api/client", () => {
  class ApiError extends Error {
    status: number
    code: string
    extra: Record<string, unknown>
    constructor(message: string, status: number, code: string, extra: Record<string, unknown> = {}) {
      super(message)
      this.status = status
      this.code = code
      this.extra = extra
    }
  }
  return { ApiError, streamUrl: () => "/api/assets/a/stream", lyricSourceUrl: () => "/lyrics/source", api }
})

vi.mock("wavesurfer.js", () => ({
  default: {
    create() {
      bus.created.push(1)
      return {
        on(name: string, handler: (value: number) => void) {
          if (name === "timeupdate") {
            bus.bindTime(handler)
          }
          return () => undefined
        },
        destroy() {},
        playPause() {},
        setTime: bus.setTime,
        setVolume() {},
        registerPlugin() {
          return bus.plugin()
        },
      }
    },
  },
}))

vi.mock("wavesurfer.js/dist/plugins/regions.esm.js", () => ({
  default: { create: () => ({}) },
}))

vi.mock("echarts", () => ({
  init: () => ({
    setOption() {},
    on() {},
    getZr: () => ({ on() {} }),
    resize() {},
    dispose() {},
  }),
}))

vi.stubGlobal(
  "ResizeObserver",
  class {
    observe() {}
    unobserve() {}
    disconnect() {}
  },
)

function segment(overrides: Partial<LyricSegmentOut> & Pick<LyricSegmentOut, "id" | "text">): LyricSegmentOut {
  return {
    ordinal: 0,
    source_cue: null,
    start_s: null,
    end_s: null,
    timing_origin: "unplaced",
    artist_verified: false,
    note: "",
    usable: false,
    ...overrides,
  }
}

function document(overrides: Partial<LyricDocumentOut> = {}): LyricDocumentOut {
  return {
    id: "doc",
    project_id: "p",
    asset_id: "a",
    upload_id: "up",
    source_kind: "txt",
    source_sha256: "abc",
    original_name: "song.txt",
    revision: 1,
    segments: [],
    validation: [],
    ...overrides,
  }
}

async function openEdit() {
  fireEvent.click(await screen.findByRole("button", { name: /^Edit / }))
}

function workspace(
  props: Partial<{
    onSeek: (seconds: number) => void
    onCues: (cues: LyricCue[]) => void
    durationS: number
    projectId: string | null
  }> = {},
) {
  const bridge: { current: LyricBridge } = { current: { commit() {}, pick() {} } }
  return render(
    <LyricsWorkspace
      projectId={props.projectId === undefined ? "p" : props.projectId}
      assetId="a"
      durationS={props.durationS ?? 30}
      playhead={null}
      onSeek={props.onSeek ?? (() => undefined)}
      onCues={props.onCues ?? (() => undefined)}
      onActive={() => undefined}
      bridge={bridge}
      onRegionReset={() => undefined}
    />,
  )
}

describe("lyric workspace", () => {
  beforeEach(() => {
    bus.reset()
    api.lyrics.mockRejectedValue(new ApiError("No lyric document is attached.", 404, "no_lyrics"))
    api.annotations.mockResolvedValue([])
    api.uploadLyrics.mockReset()
    api.updateSegment.mockReset()
    api.verifySegment.mockReset()
    api.createAnnotation.mockReset()
    api.deleteAnnotation.mockReset()
    api.lyricCharts.mockResolvedValue({ charts: [] })
    api.lyricChart.mockResolvedValue({
      chart_kind: "L01",
      status: "not_available",
      title: "Unified music-and-lyrics timeline",
      evidence_class: "unknown",
      method_id: "lyrics-v1",
      method_version: "lyrics-v1",
      analysis_version: null,
      lyric_document_id: null,
      lyric_revision: null,
      caveats: [],
      summary: [],
      series: { lines: [], bars: [], heatmap: null },
      axis_definitions: { x: "", y: "", y_scale: "linear" },
      review_markers: [],
      regions: [],
      rows: [],
      insufficient: [],
      not_available_reason: "Stored T02 energy is not m1-v3.",
    })
    api.asset.mockResolvedValue({
      id: "a",
      sha256: "abc",
      original_name: "tone",
      byte_length: 10,
      duration_s: 30,
      sample_rate: 8000,
      channels: 1,
      subtype: "pcm_16",
      analysis_status: "completed",
      playback_status: "ready",
      created_at: "",
    })
    api.peaks.mockResolvedValue({
      duration_s: 30,
      sample_rate: 8000,
      channels: 1,
      method_id: "playback",
      buckets: [{ min: -0.2, max: 0.2 }],
    })
    api.charts.mockResolvedValue({ charts: [] })
    api.chart.mockResolvedValue({
      chart_kind: "T01",
      status: "not_run",
      title: "T01",
      evidence_class: "measured",
      method_id: "m",
      method_version: "m1-v3",
      caveats: [],
      summary: [],
      series: { lines: [], bars: [], heatmap: null },
      axis_definitions: { x: "Time (s)" },
      review_markers: [],
    })
  })

  it("shows txt lines as unplaced and does not emit a region", async () => {
    const cues: LyricCue[][] = []
    api.lyrics.mockResolvedValue(
      document({
        segments: [segment({ id: "s", text: "hello world", ordinal: 0 })],
      }),
    )
    workspace({ onCues: (next) => cues.push(next) })
    expect(await screen.findByText("Unplaced. No time is assigned.")).toBeTruthy()
    expect(screen.getByText("No seek time.")).toBeTruthy()
    expect(screen.getByText(/Source TXT/)).toBeTruthy()
    expect(screen.getByText(/original file kept/)).toBeTruthy()
    expect(screen.queryByRole("button", { name: /Go to/ })).toBeNull()
    await waitFor(() => expect(cues.at(-1)).toEqual([]))
  })

  it("shows srt cues with supplied timing", async () => {
    const cues: LyricCue[][] = []
    api.lyrics.mockResolvedValue(
      document({
        source_kind: "srt",
        original_name: "song.srt",
        segments: [
          segment({
            id: "s",
            text: "hello",
            source_cue: "1",
            start_s: 1,
            end_s: 2,
            timing_origin: "subtitle_supplied",
            usable: true,
          }),
        ],
      }),
    )
    workspace({ onCues: (next) => cues.push(next) })
    expect(await screen.findByText("Subtitle-supplied timing. Not artist-confirmed.")).toBeTruthy()
    expect(screen.getByRole("button", { name: "Go to 0:01.0" })).toBeTruthy()
    expect(screen.getByText(/Source SRT/)).toBeTruthy()
    await waitFor(() => expect(cues.at(-1)?.map((cue) => cue.id)).toEqual(["s"]))
  })

  it("identifies invalid timing and does not emit a region", async () => {
    const cues: LyricCue[][] = []
    api.lyrics.mockResolvedValue(
      document({
        source_kind: "srt",
        original_name: "song.srt",
        segments: [
          segment({
            id: "bad",
            text: "reversed",
            source_cue: "2",
            start_s: 2,
            end_s: 1,
            timing_origin: "subtitle_supplied",
            usable: false,
          }),
        ],
        validation: [{ segment_id: "bad", code: "reversed_time", detail: "End is before start." }],
      }),
    )
    workspace({ onCues: (next) => cues.push(next) })
    expect(await screen.findByText("End is before start.")).toBeTruthy()
    expect(screen.getByText("Not drawn on the waveform.")).toBeTruthy()
    expect(screen.getByText("Confirm alignment is unavailable until the interval is usable.")).toBeTruthy()
    await waitFor(() => expect(cues.at(-1)).toEqual([]))
  })

  it("a text edit is saved unverified and does not confirm alignment", async () => {
    api.lyrics.mockResolvedValue(
      document({
        segments: [
          segment({
            id: "s",
            text: "Hello",
            start_s: 0,
            end_s: 1,
            timing_origin: "manual_verified",
            artist_verified: true,
            usable: true,
          }),
        ],
      }),
    )
    api.updateSegment.mockResolvedValue(
      document({
        revision: 2,
        segments: [
          segment({
            id: "s",
            text: "Hello there",
            start_s: 0,
            end_s: 1,
            timing_origin: "manual_edit",
            artist_verified: false,
            usable: true,
          }),
        ],
      }),
    )
    workspace()
    expect(await screen.findByText("Artist-confirmed alignment. Not an acoustic measurement.")).toBeTruthy()
    await openEdit()
    fireEvent.change(screen.getByLabelText("Text for Line 1"), { target: { value: "Hello there" } })
    fireEvent.click(screen.getByRole("button", { name: "Save Line 1" }))
    expect(await screen.findByText("Manually edited timing. Not artist-confirmed.")).toBeTruthy()
    expect(screen.queryByText("Artist-confirmed alignment. Not an acoustic measurement.")).toBeNull()
    expect(api.verifySegment).not.toHaveBeenCalled()
    expect(api.updateSegment).toHaveBeenCalledWith(
      "p",
      "a",
      "s",
      expect.objectContaining({ expected_revision: 1, text: "Hello there" }),
    )
  })

  it("a time edit is saved unverified", async () => {
    api.lyrics.mockResolvedValue(
      document({
        segments: [
          segment({
            id: "s",
            text: "Hello",
            start_s: 0,
            end_s: 1,
            timing_origin: "manual_verified",
            artist_verified: true,
            usable: true,
          }),
        ],
      }),
    )
    api.updateSegment.mockResolvedValue(
      document({
        revision: 2,
        segments: [
          segment({
            id: "s",
            text: "Hello",
            start_s: 0,
            end_s: 1.4,
            timing_origin: "manual_edit",
            artist_verified: false,
            usable: true,
          }),
        ],
      }),
    )
    workspace()
    expect(await screen.findByText("Artist-confirmed alignment. Not an acoustic measurement.")).toBeTruthy()
    await openEdit()
    fireEvent.change(screen.getByLabelText("End seconds for Line 1"), { target: { value: "1.4" } })
    fireEvent.click(screen.getByRole("button", { name: "Save Line 1" }))
    expect(await screen.findByText("Manually edited timing. Not artist-confirmed.")).toBeTruthy()
    expect(api.verifySegment).not.toHaveBeenCalled()
    expect(api.updateSegment).toHaveBeenCalledWith(
      "p",
      "a",
      "s",
      expect.objectContaining({ expected_revision: 1, start_s: 0, end_s: 1.4 }),
    )
  })

  it("confirm alignment is a separate request", async () => {
    api.lyrics.mockResolvedValue(
      document({
        source_kind: "srt",
        segments: [
          segment({
            id: "s",
            text: "hello",
            source_cue: "1",
            start_s: 1,
            end_s: 2,
            timing_origin: "subtitle_supplied",
            usable: true,
          }),
        ],
      }),
    )
    api.verifySegment.mockResolvedValue(
      document({
        revision: 2,
        source_kind: "srt",
        segments: [
          segment({
            id: "s",
            text: "hello",
            source_cue: "1",
            start_s: 1,
            end_s: 2,
            timing_origin: "manual_verified",
            artist_verified: true,
            usable: true,
          }),
        ],
      }),
    )
    workspace()
    await openEdit()
    fireEvent.click(await screen.findByRole("button", { name: "Confirm alignment for Cue 1" }))
    expect(await screen.findByText("Artist-confirmed alignment. Not an acoustic measurement.")).toBeTruthy()
    expect(api.updateSegment).not.toHaveBeenCalled()
    expect(api.verifySegment).toHaveBeenCalledWith("p", "a", "s", { expected_revision: 1, verified: true })
  })

  it("keeps a stale edit and saves it against the fetched revision", async () => {
    api.lyrics
      .mockResolvedValueOnce(
        document({
          revision: 1,
          segments: [segment({ id: "s", text: "Hello", ordinal: 0 })],
        }),
      )
      .mockResolvedValueOnce(
        document({
          revision: 4,
          segments: [segment({ id: "s", text: "server line", ordinal: 0 })],
        }),
      )
    api.updateSegment
      .mockRejectedValueOnce(new ApiError("The lyric document changed.", 409, "stale_revision", { current_revision: 4 }))
      .mockResolvedValueOnce(
        document({
          revision: 5,
          segments: [segment({ id: "s", text: "Hello there", ordinal: 0 })],
        }),
      )
    workspace()
    await openEdit()
    fireEvent.change(await screen.findByLabelText("Text for Line 1"), { target: { value: "Hello there" } })
    fireEvent.click(screen.getByRole("button", { name: "Save Line 1" }))
    expect(await screen.findByRole("alert")).toBeTruthy()
    expect(screen.getByRole("alert").textContent).toMatch(/Another revision exists \(revision 4\)/)
    expect((screen.getByLabelText("Text for Line 1") as HTMLTextAreaElement).value).toBe("Hello there")
    expect(screen.getByText("Saved revision 4: server line")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Save Line 1" }))
    await waitFor(() => expect(api.updateSegment).toHaveBeenCalledTimes(2))
    expect(api.updateSegment).toHaveBeenLastCalledWith(
      "p",
      "a",
      "s",
      expect.objectContaining({ expected_revision: 4, text: "Hello there" }),
    )
  })

  it("a timing conflict keeps the new times and the newer line", async () => {
    api.lyrics
      .mockResolvedValueOnce(
        document({
          revision: 1,
          segments: [
            segment({
              id: "s",
              text: "Hello",
              start_s: 0,
              end_s: 1,
              timing_origin: "manual_edit",
              usable: true,
            }),
          ],
        }),
      )
      .mockResolvedValueOnce(
        document({
          revision: 4,
          segments: [
            segment({
              id: "s",
              text: "server line",
              start_s: 0,
              end_s: 1,
              timing_origin: "manual_edit",
              usable: true,
            }),
          ],
        }),
      )
    api.updateSegment
      .mockRejectedValueOnce(new ApiError("The lyric document changed.", 409, "stale_revision", { current_revision: 4 }))
      .mockImplementation(async (_project: string, _asset: string, _id: string, body: { start_s?: number; end_s?: number; text?: string }) =>
        document({
          revision: 5,
          segments: [
            segment({
              id: "s",
              text: body.text ?? "server line",
              start_s: body.start_s ?? 0,
              end_s: body.end_s ?? 1,
              timing_origin: "manual_edit",
              usable: true,
            }),
          ],
        }),
      )
    workspace()
    await openEdit()
    fireEvent.change(await screen.findByLabelText("End seconds for Line 1"), { target: { value: "1.4" } })
    fireEvent.click(screen.getByRole("button", { name: "Save Line 1" }))
    expect(await screen.findByRole("alert")).toBeTruthy()
    expect((screen.getByLabelText("Text for Line 1") as HTMLTextAreaElement).value).toBe("server line")
    fireEvent.click(screen.getByRole("button", { name: "Save Line 1" }))
    await waitFor(() => expect(api.updateSegment).toHaveBeenCalledTimes(2))
    const body = api.updateSegment.mock.calls[1][3] as { text?: string; expected_revision: number; end_s: number }
    expect(body).toMatchObject({ expected_revision: 4, start_s: 0, end_s: 1.4 })
    expect(body.text).toBeUndefined()
  })

  it("blocks saving when the conflict reload fails, then keeps the newer line", async () => {
    api.lyrics
      .mockResolvedValueOnce(
        document({
          revision: 1,
          segments: [
            segment({
              id: "s",
              text: "Hello",
              start_s: 0,
              end_s: 1,
              timing_origin: "manual_edit",
              usable: true,
            }),
          ],
        }),
      )
      .mockRejectedValueOnce(new Error("The latest lines could not be loaded."))
      .mockResolvedValueOnce(
        document({
          revision: 4,
          segments: [
            segment({
              id: "s",
              text: "server line",
              start_s: 0,
              end_s: 1,
              timing_origin: "manual_edit",
              usable: true,
            }),
          ],
        }),
      )
    api.updateSegment
      .mockRejectedValueOnce(new ApiError("The lyric document changed.", 409, "stale_revision", { current_revision: 4 }))
      .mockImplementation(async (_project: string, _asset: string, _id: string, body: { text?: string; start_s?: number; end_s?: number }) =>
        document({
          revision: 5,
          segments: [
            segment({
              id: "s",
              text: body.text ?? "server line",
              start_s: body.start_s ?? 0,
              end_s: body.end_s ?? 1,
              timing_origin: "manual_edit",
              usable: true,
            }),
          ],
        }),
      )
    workspace()
    await openEdit()
    fireEvent.change(await screen.findByLabelText("End seconds for Line 1"), { target: { value: "1.4" } })
    fireEvent.click(screen.getByRole("button", { name: "Save Line 1" }))
    expect(await screen.findByRole("button", { name: "Load the latest lines" })).toBeTruthy()
    expect(screen.getByRole("alert").textContent).toMatch(/Load the latest lines before saving/)
    expect((screen.getByLabelText("Text for Line 1") as HTMLTextAreaElement).value).toBe("Hello")
    expect((screen.getByLabelText("End seconds for Line 1") as HTMLInputElement).value).toBe("1.4")
    expect((screen.getByRole("button", { name: "Save Line 1" }) as HTMLButtonElement).disabled).toBe(true)
    expect(api.updateSegment).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByRole("button", { name: "Load the latest lines" }))
    expect(await screen.findByText("Saved revision 4: server line")).toBeTruthy()
    expect((screen.getByLabelText("Text for Line 1") as HTMLTextAreaElement).value).toBe("server line")
    expect((screen.getByLabelText("End seconds for Line 1") as HTMLInputElement).value).toBe("1.4")
    fireEvent.click(screen.getByRole("button", { name: "Save Line 1" }))
    await waitFor(() => expect(api.updateSegment).toHaveBeenCalledTimes(2))
    const body = api.updateSegment.mock.calls[1][3] as { text?: string }
    expect(body).toMatchObject({ expected_revision: 4, start_s: 0, end_s: 1.4 })
    expect(body.text).toBeUndefined()
  })

  it("does not confirm a line while its time is unsaved", async () => {
    api.lyrics.mockResolvedValue(
      document({
        source_kind: "srt",
        segments: [
          segment({
            id: "s",
            text: "hello",
            source_cue: "1",
            start_s: 1,
            end_s: 2,
            timing_origin: "subtitle_supplied",
            usable: true,
          }),
        ],
      }),
    )
    workspace()
    await openEdit()
    fireEvent.change(await screen.findByLabelText("End seconds for Cue 1"), { target: { value: "2.5" } })
    expect((screen.getByRole("button", { name: "Confirm alignment for Cue 1" }) as HTMLButtonElement).disabled).toBe(true)
    expect(screen.getByText("Save this line before confirming alignment.")).toBeTruthy()
    expect(api.verifySegment).not.toHaveBeenCalled()
  })

  it("does not pick a study when the recording is in two", async () => {
    api.projects.mockResolvedValue([{ id: "old" }, { id: "new" }])
    api.project.mockImplementation(async (id: string) => ({ id, assets: [{ id: "a" }] }))
    workspace({ projectId: null })
    expect(await screen.findByRole("alert")).toBeTruthy()
    expect(screen.getByRole("alert").textContent).toMatch(/more than one study/)
    expect(api.lyrics).not.toHaveBeenCalled()
  })

  it("does not commit or seek when a region is rebuilt", () => {
    const commits: Array<[string, number, number]> = []
    const picks: string[] = []
    const contents: string[] = []
    const handlers = new Map<string, Set<(...args: never[]) => void>>()
    const added: { id: string; start: number; end: number }[] = []
    const plugin = {
      clearRegions() {
        added.length = 0
      },
      getRegions() {
        return added
      },
      addRegion(options: { id: string; start: number; end: number; content?: string }) {
        const region = { id: options.id, start: options.start, end: options.end, setOptions() {}, remove() {} }
        contents.push(options.content ?? "")
        added.push(region)
        handlers.get("region-updated")?.forEach((handler) => handler(region as never))
        return region
      },
      on(name: string, handler: (...args: never[]) => void) {
        const set = handlers.get(name) ?? new Set<(...args: never[]) => void>()
        set.add(handler)
        handlers.set(name, set)
        return () => set.delete(handler)
      },
    }
    const cues: LyricCue[] = [{ id: "s", start: 0, end: 1, label: "Cue 1", origin: "subtitle_supplied" }]
    const stop = syncLyricRegions(plugin as unknown as LyricRegionPlugin, cues, (id, start, end) => {
      commits.push([id, start, end])
    }, (id) => picks.push(id))
    expect(commits).toEqual([])
    expect(added).toHaveLength(1)
    expect(contents).toEqual([""])
    stop()
    const moved: LyricCue[] = [{ ...cues[0], end: 1.5, origin: "manual_edit" }]
    syncLyricRegions(plugin as unknown as LyricRegionPlugin, moved, (id, start, end) => {
      commits.push([id, start, end])
    }, (id) => picks.push(id))
    expect(commits).toEqual([])
    plugin.on("region-clicked", () => undefined)
    handlers.get("region-clicked")?.forEach((handler) =>
      handler({ id: "s", start: 0, end: 1.5 } as never, { stopPropagation() {} } as never),
    )
    expect(picks).toEqual(["s"])
    expect(commits).toEqual([])
    expect(contents).toEqual(["", ""])
  })

  it("asks before replacing a lyric file and reports an empty file", async () => {
    api.lyrics.mockResolvedValue(document({ segments: [segment({ id: "s", text: "keep", ordinal: 0 })] }))
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false)
    workspace()
    const input = await screen.findByLabelText("Lyric file")
    const file = new File(["keep"], "song.txt", { type: "text/plain" })
    fireEvent.change(input, { target: { files: [file] } })
    expect(api.uploadLyrics).not.toHaveBeenCalled()
    confirm.mockReturnValue(true)
    api.uploadLyrics.mockResolvedValue(document({ segments: [], original_name: "empty.txt" }))
    fireEvent.change(input, { target: { files: [file] } })
    expect(await screen.findByText("This file has no lyric lines.")).toBeTruthy()
    expect(api.uploadLyrics).toHaveBeenCalledTimes(1)
    confirm.mockRestore()
  })

  it("loads, attaches, and deletes an annotation", async () => {
    const note: AnnotationOut = {
      id: "note-1",
      project_id: "p",
      asset_id: "a",
      segment_id: null,
      start_s: 1,
      end_s: 2,
      text: "kept from before",
      created_at: "2026-10-13T00:00:00Z",
    }
    api.lyrics.mockResolvedValue(
      document({
        segments: [
          segment({
            id: "s",
            text: "hello",
            start_s: 1,
            end_s: 2,
            timing_origin: "manual_edit",
            usable: true,
          }),
        ],
      }),
    )
    api.annotations.mockResolvedValue([note])
    api.createAnnotation.mockResolvedValue({
      ...note,
      id: "note-2",
      segment_id: "s",
      text: "bridge",
    })
    const seen: number[] = []
    const first = workspace({ onSeek: (seconds) => seen.push(seconds) })
    expect(await screen.findByText(/kept from before/)).toBeTruthy()
    first.unmount()
    workspace({ onSeek: (seconds) => seen.push(seconds) })
    expect(await screen.findByText(/kept from before/)).toBeTruthy()
    expect(api.annotations).toHaveBeenCalledTimes(2)
    fireEvent.click(screen.getByRole("button", { name: "Go to 0:01.0" }))
    fireEvent.change(screen.getByLabelText("Note text"), { target: { value: "bridge" } })
    fireEvent.click(screen.getByRole("button", { name: "Save note" }))
    expect(await screen.findByText(/bridge/)).toBeTruthy()
    expect(api.createAnnotation).toHaveBeenCalledWith(
      "p",
      "a",
      expect.objectContaining({ text: "bridge", segment_id: "s", start_s: 1, end_s: 2 }),
    )
    fireEvent.click(screen.getByRole("button", { name: "Delete note: kept from before" }))
    await waitFor(() => expect(screen.queryByText(/kept from before/)).toBeNull())
    expect(api.deleteAnnotation).toHaveBeenCalledWith("p", "a", "note-1")
    expect(seen).toEqual([1])
  })

  it("offers timing review without changing a cue", async () => {
    const lyric = document({
      source_kind: "srt",
      original_name: "song.srt",
      segments: [
        segment({
          id: "phrase",
          text: "Yeah yeah",
          ordinal: 0,
          source_cue: "1",
          start_s: 0,
          end_s: 5,
          timing_origin: "subtitle_supplied",
          usable: true,
        }),
        segment({
          id: "next",
          text: "three four",
          ordinal: 1,
          source_cue: "2",
          start_s: 8,
          end_s: 9,
          timing_origin: "subtitle_supplied",
          usable: true,
        }),
        segment({
          id: "word",
          text: "Yeah",
          ordinal: 2,
          source_cue: "3",
          start_s: 10,
          end_s: 13,
          timing_origin: "subtitle_supplied",
          usable: true,
        }),
      ],
      validation: [{ segment_id: "phrase", code: "overlap", detail: "Cues overlap." }],
    })
    const hints = reviewHints(lyric)
    expect(hints.filter((hint) => hint.kind === "long-token").map((hint) => hint.text)).toEqual([
      'Single word "Yeah" is 3.0 s. Review only. This is not an error.',
    ])
    expect(hints.some((hint) => hint.kind === "subtitle-gap")).toBe(true)
    expect(hints.some((hint) => hint.kind === "overlap")).toBe(true)
    api.lyrics.mockResolvedValue(lyric)
    const seen: number[] = []
    workspace({ onSeek: (seconds) => seen.push(seconds) })
    expect(await screen.findByText(/Single word "Yeah"/)).toBeTruthy()
    expect(screen.getByText(/A gap is not silence/)).toBeTruthy()
    expect(screen.getByText(/does not change the cue/)).toBeTruthy()
    expect(screen.queryByText(/Single word "Yeah yeah"/)).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: "Jump to 0:10.0" }))
    expect(seen).toEqual([10])
    expect(api.updateSegment).not.toHaveBeenCalled()
    expect(api.verifySegment).not.toHaveBeenCalled()
  })

  it("keeps one editor and an unsaved draft across line changes", async () => {
    api.lyrics.mockResolvedValue(
      document({
        segments: [
          segment({ id: "s1", text: "one", ordinal: 0 }),
          segment({ id: "s2", text: "two", ordinal: 1 }),
        ],
      }),
    )
    workspace()
    expect((await screen.findByRole("button", { name: "Explore" })).getAttribute("aria-pressed")).toBe("true")
    expect(screen.queryByLabelText("Text for Line 1")).toBeNull()
    fireEvent.click(screen.getByRole("button", { name: /^Line 2/ }))
    expect(screen.queryByLabelText(/Text for/)).toBeNull()
    await openEdit()
    expect(screen.getByLabelText("Text for Line 2")).toBeTruthy()
    expect(screen.getAllByRole("textbox", { name: /Text for/ })).toHaveLength(1)
    fireEvent.click(screen.getByRole("button", { name: /^Line 1/ }))
    fireEvent.change(screen.getByLabelText("Text for Line 1"), { target: { value: "one edited" } })
    fireEvent.click(screen.getByRole("button", { name: /^Line 2/ }))
    expect(screen.getByLabelText("Text for Line 2")).toBeTruthy()
    expect(screen.queryByLabelText("Text for Line 1")).toBeNull()
    expect(screen.getByText("Unsaved")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Explore" }))
    expect(screen.queryByLabelText(/Text for/)).toBeNull()
    expect(screen.getByText(/still in the cue list/)).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: /^Line 1/ }))
    await openEdit()
    expect((screen.getByLabelText("Text for Line 1") as HTMLTextAreaElement).value).toBe("one edited")
    expect(api.updateSegment).not.toHaveBeenCalled()
  })

  it("scrolls a long document as a line list with one editor", async () => {
    api.lyrics.mockResolvedValue(
      document({
        segments: Array.from({ length: 100 }, (_, ordinal) =>
          segment({ id: `s${ordinal}`, text: `line ${ordinal}`, ordinal }),
        ),
      }),
    )
    workspace()
    expect(await screen.findByRole("button", { name: /^Line 1line 0/ })).toBeTruthy()
    expect(screen.queryByLabelText("Text for Line 1")).toBeNull()
    expect(screen.getAllByRole("button", { name: /Unplaced/ })).toHaveLength(100)
    await openEdit()
    expect(screen.getAllByRole("textbox", { name: /Text for/ })).toHaveLength(1)
    fireEvent.click(screen.getByRole("button", { name: /^Line 100line 99/ }))
    expect(screen.getByLabelText("Text for Line 100")).toBeTruthy()
    expect(screen.queryByLabelText("Text for Line 1")).toBeNull()
  })

  it("keeps one player when the study tab changes", async () => {
    api.lyrics.mockResolvedValue(document({ segments: [segment({ id: "s", text: "keep", ordinal: 0 })] }))
    render(<Analyzer assetId="a" projectId="p" />)
    await screen.findByRole("button", { name: "Play" })
    await waitFor(() => expect(bus.created).toEqual([1]))
    fireEvent.click(screen.getByRole("tab", { name: "Lyrics & Inspiration" }))
    await openEdit()
    const line = await screen.findByLabelText("Text for Line 1")
    fireEvent.change(line, { target: { value: "unsaved line" } })
    fireEvent.click(screen.getByRole("tab", { name: "Technical Analysis" }))
    await screen.findByRole("button", { name: "Play" })
    expect(line.closest("[hidden]")).toBeTruthy()
    expect(line.closest("[inert]")).toBeTruthy()
    expect(screen.queryByRole("textbox", { name: "Text for Line 1" })).toBeNull()
    line.focus()
    expect(globalThis.document.activeElement).not.toBe(line)
    fireEvent.click(screen.getByRole("tab", { name: "Lyrics & Inspiration" }))
    expect((screen.getByLabelText("Text for Line 1") as HTMLTextAreaElement).value).toBe("unsaved line")
    expect(bus.created).toEqual([1])
  })

  it("keeps the lyric draft and player when the deck collapses", async () => {
    api.lyrics.mockResolvedValue(document({ segments: [segment({ id: "s", text: "keep", ordinal: 0 })] }))
    render(<Analyzer assetId="a" projectId="p" />)
    await screen.findByRole("button", { name: "Play" })
    await waitFor(() => expect(bus.created).toEqual([1]))
    fireEvent.click(screen.getByRole("tab", { name: "Lyrics & Inspiration" }))
    await openEdit()
    const line = await screen.findByLabelText("Text for Line 1")
    fireEvent.change(line, { target: { value: "unsaved line" } })
    fireEvent.click(screen.getByRole("button", { name: "Compact player" }))
    expect(screen.getByRole("button", { name: "Expand recording" }).getAttribute("aria-expanded")).toBe("false")
    expect(screen.queryByRole("button", { name: "Export Technical ZIP" })).toBeNull()
    fireEvent.click(screen.getByRole("tab", { name: "Technical Analysis" }))
    expect(screen.getByRole("button", { name: "Expand recording" })).toBeTruthy()
    fireEvent.click(screen.getByRole("tab", { name: "Lyrics & Inspiration" }))
    expect((screen.getByLabelText("Text for Line 1") as HTMLTextAreaElement).value).toBe("unsaved line")
    expect(api.updateSegment).not.toHaveBeenCalled()
    expect(bus.created).toEqual([1])
    fireEvent.click(screen.getByRole("button", { name: "Expand recording" }))
    expect(screen.getByRole("button", { name: "Export Technical ZIP" })).toBeTruthy()
  })

  it("keeps an unsaved lyric draft when the inspiration chart changes", async () => {
    api.lyrics.mockResolvedValue(document({ segments: [segment({ id: "s", text: "keep", ordinal: 0 })] }))
    workspace()
    await openEdit()
    const line = await screen.findByLabelText("Text for Line 1")
    fireEvent.change(line, { target: { value: "draft stays" } })
    fireEvent.click(screen.getByRole("button", { name: /L02 Density/ }))
    expect((screen.getByLabelText("Text for Line 1") as HTMLTextAreaElement).value).toBe("draft stays")
    expect(bus.created).toEqual([])
  })

  it("saves one region edit and still seeks once", async () => {
    bus.setEcho(true)
    api.lyrics.mockResolvedValue(
      document({
        source_kind: "srt",
        original_name: "song.srt",
        segments: [
          segment({
            id: "s",
            text: "hello",
            source_cue: "1",
            start_s: 0,
            end_s: 1,
            timing_origin: "subtitle_supplied",
            usable: true,
          }),
        ],
      }),
    )
    api.updateSegment.mockImplementation(async (_project: string, _asset: string, _id: string, body: { start_s: number; end_s: number }) =>
      document({
        revision: 2,
        source_kind: "srt",
        original_name: "song.srt",
        segments: [
          segment({
            id: "s",
            text: "hello",
            source_cue: "1",
            start_s: body.start_s,
            end_s: body.end_s,
            timing_origin: "manual_edit",
            usable: true,
          }),
        ],
      }),
    )
    render(<Analyzer assetId="a" projectId="p" />)
    await screen.findByRole("button", { name: "Play" })
    fireEvent.click(screen.getByRole("tab", { name: "Lyrics & Inspiration" }))
    expect(await screen.findByText("Subtitle-supplied timing. Not artist-confirmed.")).toBeTruthy()
    await waitFor(() => expect(bus.added.map((region) => region.id)).toEqual(["s"]))
    expect(api.updateSegment).not.toHaveBeenCalled()
    bus.emit("region-updated", { id: "s", start: 0, end: 1.5 } as never)
    expect(await screen.findByText("Manually edited timing. Not artist-confirmed.")).toBeTruthy()
    expect(api.updateSegment).toHaveBeenCalledTimes(1)
    expect(bus.setTime).not.toHaveBeenCalled()
    bus.emit("region-clicked", { id: "s", start: 0, end: 1.5 } as never, { stopPropagation() {} } as never)
    expect(bus.setTime).toHaveBeenCalledTimes(1)
    expect(bus.setTime).toHaveBeenCalledWith(0)
    expect(api.updateSegment).toHaveBeenCalledTimes(1)
  })

  it("keeps overlapping regions selectable", async () => {
    api.lyrics.mockResolvedValue(
      document({
        source_kind: "srt",
        original_name: "song.srt",
        segments: [
          segment({
            id: "s1",
            text: "first",
            ordinal: 0,
            source_cue: "1",
            start_s: 0,
            end_s: 2,
            timing_origin: "subtitle_supplied",
            usable: true,
          }),
          segment({
            id: "s2",
            text: "second",
            ordinal: 1,
            source_cue: "2",
            start_s: 1,
            end_s: 3,
            timing_origin: "subtitle_supplied",
            usable: true,
          }),
        ],
      }),
    )
    render(<Analyzer assetId="a" projectId="p" />)
    await screen.findByRole("button", { name: "Play" })
    fireEvent.click(screen.getByRole("tab", { name: "Lyrics & Inspiration" }))
    await screen.findByText("Cue 1")
    await waitFor(() => expect(bus.added.map((region) => region.content)).toEqual(["Cue 1", ""]))
    expect(bus.added.map((region) => region.id)).toEqual(["s1", "s2"])
    bus.time(1.5)
    expect(await screen.findByText("Cue 1 · Playing")).toBeTruthy()
    bus.emit("region-clicked", { id: "s2", start: 1, end: 3 } as never, { stopPropagation() {} } as never)
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /second/ }).getAttribute("aria-current")).toBe("true")
    })
    expect(screen.getByRole("button", { name: /first/ }).getAttribute("data-playing")).toBe("true")
    expect(bus.added.map((region) => region.id)).toEqual(["s1", "s2"])
    expect(bus.setTime).toHaveBeenCalledTimes(1)
    expect(bus.setTime).toHaveBeenCalledWith(1)
    expect(activeSegmentId(
      [
        segment({ id: "s1", text: "first", ordinal: 0, start_s: 0, end_s: 2, usable: true, timing_origin: "subtitle_supplied" }),
        segment({ id: "s2", text: "second", ordinal: 1, start_s: 1, end_s: 3, usable: true, timing_origin: "subtitle_supplied" }),
      ],
      1.5,
    )).toBe("s1")
  })

  it("labels only the active or selected waveform cue", () => {
    const cue = { id: "s", start: 0, end: 1, label: "Cue 1", origin: "subtitle_supplied" as const }
    const other = { ...cue, id: "t", label: "Cue 2" }
    expect(regionLabel(cue, null, null)).toBe("")
    expect(regionLabel(cue, null, "s")).toBe("Cue 1")
    expect(regionLabel(other, "s", "s")).toBe("")
    expect(regionLabel(other, "t", "s")).toBe("Cue 2")
  })

  it("filters lyric lines and moves between visible cues from the keyboard", async () => {
    api.lyrics.mockResolvedValue(
      document({
        segments: [
          segment({ id: "s1", text: "alpha street", ordinal: 0 }),
          segment({ id: "s2", text: "beta road", ordinal: 1 }),
          segment({ id: "s3", text: "gamma lane", ordinal: 2 }),
        ],
      }),
    )
    workspace()
    expect(await screen.findByRole("button", { name: /^Line 1/ })).toBeTruthy()
    expect(screen.queryByLabelText(/Text for/)).toBeNull()
    fireEvent.change(screen.getByLabelText("Find a lyric line"), { target: { value: "beta" } })
    expect(screen.getByText("1 of 3 lines · revision 1")).toBeTruthy()
    expect(screen.queryByRole("button", { name: /^Line 1/ })).toBeNull()
    const match = screen.getByRole("button", { name: /^Line 2/ })
    expect(match).toBeTruthy()
    fireEvent.change(screen.getByLabelText("Find a lyric line"), { target: { value: "" } })
    const again = screen.getByRole("button", { name: /^Line 1/ })
    again.focus()
    fireEvent.keyDown(again, { key: "ArrowDown" })
    expect(screen.getByRole("button", { name: /^Line 2/ }).getAttribute("aria-current")).toBe("true")
    expect(screen.queryByLabelText(/Text for/)).toBeNull()
  })

})
