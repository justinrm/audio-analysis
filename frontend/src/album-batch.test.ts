import { describe, expect, it, vi } from "vitest"
import type { Asset } from "./api/types"
import { analysisCounts, analysisSummary, batchMessage, runAlbumBatch } from "./album-batch"

function recording(id: string, status: Asset["analysis_status"]): Asset {
  return {
    id,
    sha256: `${id}${"ab".repeat(32)}`.slice(0, 64),
    original_name: `${id}.wav`,
    byte_length: 80,
    duration_s: 1,
    sample_rate: 8000,
    channels: 1,
    subtype: "pcm_16",
    analysis_status: status,
    playback_status: "ready",
    created_at: "2026-11-11T00:00:00Z",
  }
}

describe("album batch", () => {
  it("adds in order, skips members, and continues after one membership failure", async () => {
    const targets = Array.from({ length: 15 }, (_, index) => recording(`t${index}`, "not_run"))
    const added: string[] = []
    const result = await runAlbumBatch({
      projectId: "album-1",
      targets,
      memberIds: new Set(["t0"]),
      plan: "add",
      addMember: async (_projectId, assetId) => {
        if (assetId === "t3") {
          throw new Error("rejected")
        }
        added.push(assetId)
      },
      analyze: async () => {
        throw new Error("analysis was not requested")
      },
    })
    expect(added).toEqual(["t1", "t2", "t4", "t5", "t6", "t7", "t8", "t9", "t10", "t11", "t12", "t13", "t14"])
    expect(result.failed.map((item) => item.name)).toEqual(["t3.wav"])
    expect(result.added).toHaveLength(13)
    expect(batchMessage(result).role).toBe("alert")
  })

  it("treats an existing member response as already added", async () => {
    const result = await runAlbumBatch({
      projectId: "album-1",
      targets: [recording("t1", "not_run")],
      memberIds: new Set(),
      plan: "add",
      addMember: async () => {
        throw Object.assign(new Error("That recording is already in the album."), { code: "already_member" })
      },
      analyze: async () => undefined,
    })
    expect(result.failed).toEqual([])
    expect(result.added).toEqual([])
  })

  it("queues only missing or failed analysis and leaves finished or active jobs alone", async () => {
    const targets = [
      recording("done", "completed"),
      recording("wait", "queued"),
      recording("busy", "running"),
      recording("new", "not_run"),
      recording("bad", "failed"),
    ]
    const analyzed: string[] = []
    const result = await runAlbumBatch({
      projectId: "album-1",
      targets,
      memberIds: new Set(targets.map((item) => item.id)),
      plan: "add-and-queue",
      addMember: async () => {
        throw new Error("member already known")
      },
      analyze: async (assetId) => {
        if (assetId === "bad") {
          throw new Error("queue failed")
        }
        analyzed.push(assetId)
      },
    })
    expect(analyzed).toEqual(["new"])
    expect(result.reused).toBe(1)
    expect(result.left).toEqual(["wait.wav", "busy.wav"])
    expect(result.submitted).toEqual(["new.wav"])
    expect(result.failed.map((item) => item.name)).toEqual(["bad.wav"])
    expect(batchMessage(result).text).toContain("Submission is not completed analysis.")
  })

  it("analyzes missing recordings and retries only failed ones", async () => {
    const targets = [recording("new", "not_run"), recording("bad", "failed"), recording("done", "completed")]
    const analyzed: string[] = []
    const analyze = async (assetId: string) => {
      analyzed.push(assetId)
    }
    await runAlbumBatch({
      projectId: "album-1",
      targets,
      memberIds: new Set(targets.map((item) => item.id)),
      plan: "missing",
      addMember: async () => undefined,
      analyze,
    })
    await runAlbumBatch({
      projectId: "album-1",
      targets,
      memberIds: new Set(targets.map((item) => item.id)),
      plan: "retry-failed",
      addMember: async () => undefined,
      analyze,
    })
    expect(analyzed).toEqual(["new", "bad"])
  })

  it("submits the next analysis request after the previous request returns", async () => {
    const order: string[] = []
    let release: (() => void) | undefined
    const gate = new Promise<void>((resolve) => {
      release = resolve
    })
    const pending = runAlbumBatch({
      projectId: "album-1",
      targets: [recording("a", "not_run"), recording("b", "not_run")],
      memberIds: new Set(["a", "b"]),
      plan: "missing",
      addMember: async () => undefined,
      analyze: async (assetId) => {
        order.push(`start ${assetId}`)
        if (assetId === "a") {
          await gate
        }
        order.push(`end ${assetId}`)
      },
    })
    await vi.waitFor(() => expect(order).toEqual(["start a"]))
    expect(order).not.toContain("start b")
    release?.()
    await pending
    expect(order).toEqual(["start a", "end a", "start b", "end b"])
  })

  it("counts album recordings from stored status", () => {
    const counts = analysisCounts([
      { analysis_status: "completed" },
      { analysis_status: "queued" },
      { analysis_status: "running" },
      { analysis_status: "failed" },
      { analysis_status: "not_run" },
    ])
    expect(analysisSummary(counts)).toBe(
      "Album recordings 5. Completed analysis 1. Queued 1. Running 1. Failed 1. Not yet analyzed 1.",
    )
  })
})
