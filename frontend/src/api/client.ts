import type {
  AnnotationIn,
  AnnotationOut,
  Asset,
  ChartDocument,
  ChartList,
  Health,
  Job,
  LyricDocumentOut,
  LyricSegmentUpdate,
  LyricVerify,
  Peaks,
  Project,
  ProjectDetail,
  UploadResult,
} from "./types"

type ErrorBody = {
  error?: string
  message?: string
}

export class ApiError extends Error {
  status: number
  code: string
  extra: Record<string, unknown>

  constructor(message: string, status: number, code: string, extra: Record<string, unknown> = {}) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.code = code
    this.extra = extra
  }
}

function extraOf(body: ErrorBody | null): Record<string, unknown> {
  if (!body) {
    return {}
  }
  const extra: Record<string, unknown> = { ...body }
  delete extra.error
  delete extra.message
  return extra
}

async function parse<T>(response: Response): Promise<T> {
  const text = await response.text()
  const body = text ? (JSON.parse(text) as T & ErrorBody) : null
  if (!response.ok) {
    const error = body as ErrorBody | null
    throw new ApiError(
      error?.message || response.statusText,
      response.status,
      error?.error || "error",
      extraOf(error),
    )
  }
  return body as T
}

async function empty(response: Response): Promise<void> {
  if (response.status === 204) {
    return
  }
  await parse(response)
}

export function streamUrl(assetId: string): string {
  return `/api/assets/${assetId}/stream`
}

export function lyricSourceUrl(projectId: string, assetId: string): string {
  return `/api/projects/${projectId}/assets/${assetId}/lyrics/source`
}

function lyricPath(projectId: string, assetId: string): string {
  return `/api/projects/${projectId}/assets/${assetId}`
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
  analyze: (id: string) => fetch(`/api/assets/${id}/analyze`, { method: "POST" }).then(parse<Job>),
  charts: (id: string) => fetch(`/api/assets/${id}/charts`).then(parse<ChartList>),
  chart: (id: string, kind: string) =>
    fetch(`/api/assets/${id}/charts/${kind}/data`).then(parse<ChartDocument>),
  job: (id: string) => fetch(`/api/jobs/${id}`).then(parse<Job>),
  lyrics: (projectId: string, assetId: string) =>
    fetch(`${lyricPath(projectId, assetId)}/lyrics`).then(parse<LyricDocumentOut>),
  uploadLyrics: (projectId: string, assetId: string, file: File) => {
    const body = new FormData()
    body.append("file", file)
    return fetch(`${lyricPath(projectId, assetId)}/lyrics`, { method: "POST", body }).then(parse<LyricDocumentOut>)
  },
  updateSegment: (projectId: string, assetId: string, segmentId: string, body: LyricSegmentUpdate) =>
    fetch(`${lyricPath(projectId, assetId)}/lyric-segments/${segmentId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(parse<LyricDocumentOut>),
  verifySegment: (projectId: string, assetId: string, segmentId: string, body: LyricVerify) =>
    fetch(`${lyricPath(projectId, assetId)}/lyric-segments/${segmentId}/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(parse<LyricDocumentOut>),
  annotations: (projectId: string, assetId: string) =>
    fetch(`${lyricPath(projectId, assetId)}/annotations`).then(parse<AnnotationOut[]>),
  createAnnotation: (projectId: string, assetId: string, body: AnnotationIn) =>
    fetch(`${lyricPath(projectId, assetId)}/annotations`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(parse<AnnotationOut>),
  deleteAnnotation: (projectId: string, assetId: string, annotationId: string) =>
    fetch(`${lyricPath(projectId, assetId)}/annotations/${annotationId}`, { method: "DELETE" }).then(empty),
}
