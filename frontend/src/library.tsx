import { useEffect, useRef, useState } from "react"
import { api } from "./api/client"
import type { Asset, Project, ProjectDetail } from "./api/types"
import { clock, formatLabel, statusLabel } from "./catalog"

function when(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })
}

type Feedback = { role: "status" | "alert"; text: string }

export function Library({
  onOpen,
}: {
  onOpen: (assetId: string, projectId: string) => void
}) {
  const [studies, setStudies] = useState<Project[]>([])
  const [project, setProject] = useState<ProjectDetail | null>(null)
  const [assets, setAssets] = useState<Asset[]>([])
  const [name, setName] = useState("Reference study")
  const [feedback, setFeedback] = useState<Feedback | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  async function openStudy(projectId: string) {
    const detail = await api.project(projectId)
    setProject(detail)
    setAssets(detail.assets)
  }

  useEffect(() => {
    let cancelled = false
    api
      .projects()
      .then(async (list) => {
        if (cancelled) {
          return
        }
        setStudies(list)
        const existing = list[0]
        if (!existing) {
          setLoading(false)
          return
        }
        await openStudy(existing.id)
        if (!cancelled) {
          setLoading(false)
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setFeedback({
            role: "alert",
            text: error instanceof Error ? error.message : "Could not load the library.",
          })
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function createStudy() {
    setFeedback(null)
    setBusy(true)
    try {
      const created = await api.createProject(name.trim())
      const list = await api.projects()
      setStudies(list)
      await openStudy(created.id)
      setFeedback({ role: "status", text: "Study created." })
    } catch (error) {
      setFeedback({
        role: "alert",
        text: error instanceof Error ? error.message : "Could not create the study.",
      })
    } finally {
      setBusy(false)
    }
  }

  async function selectStudy(projectId: string) {
    if (projectId === project?.id) {
      return
    }
    setFeedback(null)
    setBusy(true)
    try {
      await openStudy(projectId)
    } catch (error) {
      setFeedback({
        role: "alert",
        text: error instanceof Error ? error.message : "Could not open that study.",
      })
    } finally {
      setBusy(false)
    }
  }

  async function importFile(file: File | undefined) {
    if (!file || !project) {
      return
    }
    setFeedback({ role: "status", text: "Importing." })
    setBusy(true)
    try {
      const result = await api.upload(project.id, file)
      setFeedback({
        role: "status",
        text: result.cache === "hit" ? "Already in the library. Reused the stored file." : "Imported.",
      })
      const list = await api.projects()
      setStudies(list)
      await openStudy(project.id)
    } catch (error) {
      setFeedback({
        role: "alert",
        text: error instanceof Error ? error.message : "Import failed.",
      })
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <h1 className="page-title">Library</h1>
      {loading ? <p role="status">Loading the library.</p> : null}
      {!loading && !project ? (
        <form
          className="field"
          onSubmit={(event) => {
            event.preventDefault()
            void createStudy()
          }}
        >
          <label htmlFor="study-name">Name this study</label>
          <input
            id="study-name"
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
          <button type="submit" className="action" disabled={busy}>
            Create study
          </button>
        </form>
      ) : null}
      {project && studies.length > 1 ? (
        <div className="field">
          <label htmlFor="study">Study</label>
          <select
            id="study"
            value={project.id}
            disabled={busy}
            onChange={(event) => {
              void selectStudy(event.target.value)
            }}
          >
            {studies.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </div>
      ) : null}
      {project && studies.length === 1 ? <p>{project.name}</p> : null}
      {project ? (
        <div className="import-row">
          <button
            type="button"
            className="action"
            disabled={busy}
            onClick={() => fileRef.current?.click()}
          >
            Import WAV
          </button>
          <input
            ref={fileRef}
            id="import-wav"
            className="file-input"
            type="file"
            accept=".wav,audio/wav"
            aria-hidden="true"
            tabIndex={-1}
            disabled={busy}
            onChange={(event) => {
              void importFile(event.target.files?.[0])
              event.target.value = ""
            }}
          />
        </div>
      ) : null}
      {feedback ? (
        <p className={feedback.role === "alert" ? "feedback is-alert" : "feedback"} role={feedback.role}>
          {feedback.text}
        </p>
      ) : null}
      {project && assets.length === 0 ? <p>No recordings in this study yet.</p> : null}
      {assets.length > 0 ? (
        <div className="log-scroll">
          <table className="log">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Format</th>
                <th scope="col">Duration</th>
                <th scope="col">Analysis</th>
                <th scope="col">Playback</th>
                <th scope="col">Added</th>
                <th scope="col">
                  <span className="sr-only">Open</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {assets.map((asset) => (
                <tr key={asset.id}>
                  <td className="name" data-label="Name" title={asset.original_name}>
                    {asset.original_name}
                  </td>
                  <td data-label="Format">{formatLabel(asset)}</td>
                  <td className="num" data-label="Duration">
                    {clock(asset.duration_s)}
                  </td>
                  <td data-label="Analysis">{statusLabel(asset.analysis_status)}</td>
                  <td data-label="Playback">{statusLabel(asset.playback_status)}</td>
                  <td className="num" data-label="Added">
                    {when(asset.created_at)}
                  </td>
                  <td data-label="Open">
                    <button
                      type="button"
                      className="ghost"
                      aria-label={`Open ${asset.original_name}`}
                      onClick={() => {
                        if (project) {
                          onOpen(asset.id, project.id)
                        }
                      }}
                    >
                      Open
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </>
  )
}
