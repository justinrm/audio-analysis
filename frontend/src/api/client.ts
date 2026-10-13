import type {
  Asset,
  ErrorBody,
  Health,
  Peaks,
  Project,
  ProjectDetail,
  UploadResult,
} from "./types"

export class ApiError extends Error {
  status: number
  code: string

  constructor(message: string, status: number, code: string) {
    super(message)
    this.status = status
    this.code = code
  }
}

async function parse<T>(response: Response): Promise<T> {
  const text = await response.text()
  const body = text ? (JSON.parse(text) as T & Partial<ErrorBody>) : null
  if (!response.ok) {
    const error = body as Partial<ErrorBody> | null
    throw new ApiError(error?.message || response.statusText, response.status, error?.error || "error")
  }
  return body as T
}

export function streamUrl(assetId: string): string {
  return `/api/assets/${assetId}/stream`
}

export const api = {
  health: () => fetch("/api/health").then(parse<Health>),
  projects: () => fetch("/api/projects").then(parse<Project[]>),
  createProject: (name: string) =>
    fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    }).then(parse<Project>),
  project: (id: string) => fetch(`/api/projects/${id}`).then(parse<ProjectDetail>),
  upload: (projectId: string, file: File) => {
    const body = new FormData()
    body.append("file", file)
    return fetch(`/api/projects/${projectId}/assets`, { method: "POST", body }).then(parse<UploadResult>)
  },
  asset: (id: string) => fetch(`/api/assets/${id}`).then(parse<Asset>),
  peaks: (id: string) => fetch(`/api/assets/${id}/peaks`).then(parse<Peaks>),
  analyze: (id: string) =>
    fetch(`/api/assets/${id}/analyze`, { method: "POST" }).then(parse<ErrorBody>),
}
