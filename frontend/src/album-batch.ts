import type { Asset } from "./api/types"

export type BatchPlan = "add" | "add-and-queue" | "missing" | "retry-failed"

export type BatchFailure = { id: string; name: string; message: string }

export type BatchResult = {
  added: string[]
  submitted: string[]
  reused: number
  left: string[]
  failed: BatchFailure[]
}

export type AnalysisCounts = {
  total: number
  completed: number
  queued: number
  running: number
  failed: number
  not_run: number
}

type AnalysisStatus = Asset["analysis_status"]

export function analysisCounts(assets: { analysis_status: AnalysisStatus }[]): AnalysisCounts {
  const counts: AnalysisCounts = { total: assets.length, completed: 0, queued: 0, running: 0, failed: 0, not_run: 0 }
  for (const asset of assets) {
    switch (asset.analysis_status) {
      case "completed":
        counts.completed += 1
        break
      case "queued":
        counts.queued += 1
        break
      case "running":
        counts.running += 1
        break
      case "failed":
        counts.failed += 1
        break
      case "not_run":
        counts.not_run += 1
        break
      default: {
        const unexpected: never = asset.analysis_status
        return unexpected
      }
    }
  }
  return counts
}

export function analysisSummary(counts: AnalysisCounts): string {
  return `Album recordings ${counts.total}. Completed analysis ${counts.completed}. Queued ${counts.queued}. Running ${counts.running}. Failed ${counts.failed}. Not yet analyzed ${counts.not_run}.`
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Request failed."
}

function alreadyMember(error: unknown): boolean {
  return typeof error === "object" && error !== null && "code" in error && error.code === "already_member"
}

function queueAction(
  status: AnalysisStatus,
  plan: Exclude<BatchPlan, "add">,
): "reuse" | "leave" | "submit" | "skip" {
  switch (status) {
    case "completed":
      return "reuse"
    case "queued":
    case "running":
      return "leave"
    case "not_run":
      switch (plan) {
        case "add-and-queue":
        case "missing":
          return "submit"
        case "retry-failed":
          return "skip"
        default: {
          const unexpected: never = plan
          return unexpected
        }
      }
    case "failed":
      switch (plan) {
        case "add-and-queue":
        case "retry-failed":
          return "submit"
        case "missing":
          return "skip"
        default: {
          const unexpected: never = plan
          return unexpected
        }
      }
    default: {
      const unexpected: never = status
      return unexpected
    }
  }
}

export async function runAlbumBatch(input: {
  projectId: string
  targets: Asset[]
  memberIds: ReadonlySet<string>
  plan: BatchPlan
  addMember: (projectId: string, assetId: string) => Promise<unknown>
  analyze: (assetId: string) => Promise<unknown>
  onStep?: (index: number, total: number, name: string) => void
}): Promise<BatchResult> {
  const result: BatchResult = { added: [], submitted: [], reused: 0, left: [], failed: [] }
  const total = input.targets.length
  for (let index = 0; index < total; index += 1) {
    const asset = input.targets[index]
    if (!asset) {
      continue
    }
    input.onStep?.(index + 1, total, asset.original_name)
    if ((input.plan === "add" || input.plan === "add-and-queue") && !input.memberIds.has(asset.id)) {
      try {
        await input.addMember(input.projectId, asset.id)
        result.added.push(asset.original_name)
      } catch (error) {
        if (!alreadyMember(error)) {
          result.failed.push({ id: asset.id, name: asset.original_name, message: errorMessage(error) })
          continue
        }
      }
    }
    if (input.plan === "add") {
      continue
    }
    const action = queueAction(asset.analysis_status, input.plan)
    if (action === "reuse") {
      result.reused += 1
      continue
    }
    if (action === "leave") {
      result.left.push(asset.original_name)
      continue
    }
    if (action === "skip") {
      continue
    }
    try {
      await input.analyze(asset.id)
      result.submitted.push(asset.original_name)
    } catch (error) {
      result.failed.push({ id: asset.id, name: asset.original_name, message: errorMessage(error) })
    }
  }
  return result
}

export function batchMessage(result: BatchResult): { role: "status" | "alert"; text: string } {
  const parts: string[] = []
  if (result.added.length > 0) {
    parts.push(`Added ${result.added.length} to the album.`)
  }
  if (result.submitted.length > 0) {
    parts.push(`Submitted ${result.submitted.length} analysis jobs. Submission is not completed analysis.`)
  }
  if (result.reused > 0) {
    parts.push(`Reused completed analysis for ${result.reused}.`)
  }
  if (result.left.length > 0) {
    parts.push(`Left queued or running: ${result.left.join(", ")}.`)
  }
  if (result.failed.length > 0) {
    parts.push(`Failed: ${result.failed.map((item) => item.name).join(", ")}.`)
  }
  return {
    role: result.failed.length > 0 ? "alert" : "status",
    text: parts.join(" ") || "No recordings needed a change.",
  }
}
