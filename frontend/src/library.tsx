import { useEffect, useState } from "react"
import { api } from "./api/client"
import type { Asset, Project } from "./api/types"
import { clock, formatLabel } from "./catalog"

function when(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }
  return date.toLocaleString()
}

export function Library({
  onOpen,
}: {
  onOpen: (assetId: string) => void
}) {
  const [project, setProject] = useState<Project | null>(null)
  const [assets, setAssets] = useState<Asset[]>([])
  const [name, setName] = useState("Reference study")
  const [message, setMessage] = useState("")
  const [loading, setLoading] = useState(true)

  async function refresh(projectId: string) {
    const detail = await api.project(projectId)
    setProject(detail)
    setAssets(detail.assets)
  }

  useEffect(() => {
    let cancelled = false
    api
      .projects()
      .then(async (projects) => {
        if (cancelled) {
          return
        }
        const existing = projects[0]
        if (!existing) {
          setLoading(false)
          return
        }
        await refresh(existing.id)
        if (!cancelled) {
          setLoading(false)
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setMessage(error instanceof Error ? error.message : "Could not load the library.")
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  async function createStudy() {
    setMessage("")
    try {
      const created = await api.createProject(name.trim())
      await refresh(created.id)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not create the study.")
    }
  }

  async function importFile(file: File | undefined) {
    if (!file || !project) {
      return
    }
    setMessage("")
    try {
      const result = await api.upload(project.id, file)
      setMessage(result.cache === "hit" ? "Already in the library. Reused the stored file." : "Imported.")
      await refresh(project.id)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Import failed.")
    }
  }

  return (
    <>
      <h1 className="page-title">Library</h1>
      {loading ? <p>Loading the library.</p> : null}
      {!loading && !project ? (
        <form
          className="field"
          onSubmit={(event) => {
            event.preventDefault()
            void createStudy()
          }}
        >
          <label htmlFor="study-name">Name this study</label>
          <input id="study-name" value={name} onChange={(event) => setName(event.target.value)} />
          <button type="submit" className="action">
            Create study
          </button>
        </form>
      ) : null}
      {project ? (
        <>
          <p>{project.name}</p>
          <div className="import-row">
            <label htmlFor="import-wav">Import WAV</label>
            <input
              id="import-wav"
              type="file"
              accept=".wav,audio/wav"
              onChange={(event) => {
                void importFile(event.target.files?.[0])
                event.target.value = ""
              }}
            />
          </div>
        </>
      ) : null}
      {message ? <p role="status">{message}</p> : null}
      {project && assets.length === 0 ? <p>No recordings in this study yet.</p> : null}
      {assets.length > 0 ? (
        <div className="log-scroll">
        <table className="log">
          <thead>
            <tr>
              <th>Name</th>
              <th>Format</th>
              <th>Duration</th>
              <th>Analysis</th>
              <th>Playback</th>
              <th>Added</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {assets.map((asset) => (
              <tr key={asset.id}>
                <td>{asset.original_name}</td>
                <td>{formatLabel(asset)}</td>
                <td>{clock(asset.duration_s)}</td>
                <td>{asset.analysis_status}</td>
                <td>{asset.playback_status}</td>
                <td>{when(asset.created_at)}</td>
                <td>
                  <button type="button" className="ghost" onClick={() => onOpen(asset.id)}>
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
