import type {
  AnnotationIn,
  AnnotationOut,
  Asset,
  ChartDocument,
  ChartList,
  Health,
  Job,
  LyricChartDocument,
  LyricDocumentOut,
  LyricSegmentUpdate,
  AlbumExportManifest,
  ComparisonDocument,
  ExportCreate,
  ExportManifest,
  LyricVerify,
  Peaks,
  Project,
  ProjectDetail,
  ReviewRecord,
  ReviewUpdate,
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
  createProject: (name: string, mode: "study" | "album" = "study") =>
    fetch("/api/projects", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name, mode }),
    }).then(parse<Project>),
  assets: () => fetch("/api/assets").then(parse<Asset[]>),
  addMember: (projectId: string, assetId: string) =>
    fetch(`/api/projects/${projectId}/members`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ asset_id: assetId }),
    }).then(parse<{ asset_id: string; ordering: number }>),
  removeMember: (projectId: string, assetId: string) =>
    fetch(`/api/projects/${projectId}/members/${assetId}`, { method: "DELETE" }).then(empty),
  orderAlbum: (projectId: string, assetIds: string[]) =>
    fetch(`/api/projects/${projectId}/order`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ asset_ids: assetIds }),
    }).then(parse<{ asset_ids: string[] }>),
  comparison: (projectId: string, x: "seconds" | "progress" = "seconds") =>
    fetch(`/api/projects/${projectId}/comparison?x=${x}`).then(parse<ComparisonDocument>),
  reviews: (projectId: string) => fetch(`/api/projects/${projectId}/reviews`).then(parse<ReviewRecord[]>),
  saveReview: (projectId: string, body: ReviewUpdate) =>
    fetch(`/api/projects/${projectId}/reviews`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(parse<ReviewRecord>),
  createAlbumExport: (projectId: string) =>
    fetch(`/api/projects/${projectId}/album-export`, { method: "POST" }).then(parse<AlbumExportManifest>),
  downloadAlbumExport: async (projectId: string, exportId: string, filename: string) => {
    const response = await fetch(`/api/projects/${projectId}/album-exports/${exportId}`)
    if (!response.ok) {
      await parse(response)
      return
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  },
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
  lyricCharts: (projectId: string, assetId: string) =>
    fetch(`${lyricPath(projectId, assetId)}/lyric-charts`).then(parse<ChartList>),
  lyricChart: (projectId: string, assetId: string, kind: string) =>
    fetch(`${lyricPath(projectId, assetId)}/lyric-charts/${kind}/data`).then(parse<LyricChartDocument>),
  createExport: (projectId: string, assetId: string, body: ExportCreate) =>
    fetch(`${lyricPath(projectId, assetId)}/exports`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(parse<ExportManifest>),
  downloadExport: async (projectId: string, assetId: string, exportId: string, filename: string) => {
    const response = await fetch(`${lyricPath(projectId, assetId)}/exports/${exportId}`)
    if (!response.ok) {
      await parse(response)
      return
    }
    const blob = await response.blob()
    const url = URL.createObjectURL(blob)
    const link = document.createElement("a")
    link.href = url
    link.download = filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  },
}
