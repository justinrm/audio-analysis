import { useEffect, useState } from "react"
import { api } from "./api/client"
import type { Asset, Project } from "./api/types"

type StudyRecord = {
  id: string
  name: string
  assets: Asset[]
}

export function AnalyzerEntry({
  onOpen,
  onLibrary,
}: {
  onOpen: (assetId: string, projectId: string) => void
  onLibrary: () => void
}) {
  const [studies, setStudies] = useState<StudyRecord[]>([])
  const [studyId, setStudyId] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")

  useEffect(() => {
    let cancelled = false
    api
      .projects()
      .then(async (list) => {
        const studies = list.filter((item) => item.mode === "study")
        const records = await Promise.all(studies.map((item) => loadStudy(item)))
        if (cancelled) {
          return
        }
        setStudies(records)
        setStudyId(records[0]?.id ?? "")
        setLoading(false)
      })
      .catch((reason: unknown) => {
        if (!cancelled) {
          setError(reason instanceof Error ? reason.message : "Could not load recordings.")
          setLoading(false)
        }
      })
    return () => {
      cancelled = true
    }
  }, [])

  const study = studies.find((item) => item.id === studyId) ?? null
  const recordings = study?.assets ?? []

  return (
    <section className="analyzer-entry">
      <h1 className="page-title">Analyzer</h1>
      <p>Choose a recording from a study, or open the library.</p>
      <button type="button" className="action" onClick={onLibrary}>
        Open Library
      </button>
      {loading ? <p role="status">Loading recordings.</p> : null}
      {error ? (
        <p className="feedback is-alert" role="alert">
          {error}
        </p>
      ) : null}
      {!loading && !error && studies.length === 0 ? <p>No study recordings yet.</p> : null}
      {!loading && !error && studies.length > 0 ? (
        <>
          <div className="field">
            <label htmlFor="analyzer-study">Study</label>
            <select
              id="analyzer-study"
              value={studyId}
              onChange={(event) => setStudyId(event.target.value)}
            >
              {studies.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>
          {recordings.length === 0 ? <p>This study has no recordings.</p> : null}
          {recordings.length > 0 ? (
            <ul className="analyzer-recordings">
              {recordings.map((asset) => (
                <li key={asset.id}>
                  <button type="button" onClick={() => onOpen(asset.id, studyId)}>
                    {asset.original_name}
                  </button>
                </li>
              ))}
            </ul>
          ) : null}
        </>
      ) : null}
    </section>
  )
}

async function loadStudy(project: Project): Promise<StudyRecord> {
  const detail = await api.project(project.id)
  return { id: detail.id, name: detail.name, assets: detail.assets }
}
