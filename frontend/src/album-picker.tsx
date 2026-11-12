import { useEffect, useRef, useState } from "react"
import { createPortal } from "react-dom"
import type { Asset, Project } from "./api/types"
import { clock, statusLabel } from "./catalog"

type Feedback = { role: "status" | "alert"; text: string }

const FOCUSABLE = "button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href]"

function choiceLabel(item: Asset, member: boolean): string {
  return [item.original_name, member ? "Already in this album" : "Not in this album", statusLabel(item.analysis_status)].join(". ")
}

function selectionSummary(selected: number, hidden: number): string {
  const count = `${selected} selected.`
  if (hidden === 0) {
    return count
  }
  const hiddenText = hidden === 1 ? "1 selected recording is" : `${hidden} selected recordings are`
  return `${count} ${hiddenText} hidden by this filter.`
}

export function AddRecordingsDialog({
  library,
  memberIds,
  studies,
  studyMembers,
  picked,
  onPickedChange,
  busy,
  feedback,
  onAdd,
  onQueue,
  onClose,
}: {
  library: Asset[]
  memberIds: Set<string>
  studies: Project[]
  studyMembers: Record<string, string[]>
  picked: Set<string>
  onPickedChange: (next: Set<string>) => void
  busy: boolean
  feedback: Feedback | null
  onAdd: () => void
  onQueue: () => void
  onClose: () => void
}) {
  const dialogRef = useRef<HTMLDivElement>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const onCloseRef = useRef(onClose)
  const [query, setQuery] = useState("")
  const [studyId, setStudyId] = useState("")
  onCloseRef.current = onClose

  useEffect(() => {
    const node = dialogRef.current
    const returnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
    const root = document.getElementById("root")
    const previousOverflow = document.body.style.overflow
    document.body.style.overflow = "hidden"
    root?.setAttribute("inert", "")
    searchRef.current?.focus()
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") {
        event.preventDefault()
        onCloseRef.current()
        return
      }
      if (event.key !== "Tab" || !node) {
        return
      }
      const items = [...node.querySelectorAll<HTMLElement>(FOCUSABLE)]
      if (items.length === 0) {
        return
      }
      event.preventDefault()
      const index = items.indexOf(document.activeElement as HTMLElement)
      const next = event.shiftKey
        ? items[(index <= 0 ? items.length : index) - 1]
        : items[index === -1 || index === items.length - 1 ? 0 : index + 1]
      next?.focus()
    }
    document.addEventListener("keydown", onKey)
    return () => {
      document.removeEventListener("keydown", onKey)
      document.body.style.overflow = previousOverflow
      root?.removeAttribute("inert")
      returnFocus?.focus()
    }
  }, [])

  const needle = query.trim().toLowerCase()
  const studyIds = studyId ? new Set(studyMembers[studyId] ?? []) : null
  const visible = library.filter((item) => {
    const inStudy = studyIds ? studyIds.has(item.id) : true
    const named = needle.length === 0 || item.original_name.toLowerCase().includes(needle)
    return inStudy && named
  })
  const visibleIds = new Set(visible.map((item) => item.id))
  const selected = library.filter((item) => picked.has(item.id) && !memberIds.has(item.id))
  const hidden = selected.filter((item) => !visibleIds.has(item.id)).length
  const selectable = visible.filter((item) => !memberIds.has(item.id))

  return createPortal(
    <div
      className="album-dialog-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      <div
        ref={dialogRef}
        className="album-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="add-recordings-title"
        aria-describedby="add-recordings-note"
      >
        <div className="album-dialog-head">
          <h2 id="add-recordings-title">Add recordings</h2>
          <button type="button" className="ghost" onClick={onClose}>
            Close
          </button>
        </div>
        <p id="add-recordings-note" className="album-dialog-note">
          Choose recordings already in the library. Adding one does not copy its WAV.
        </p>
        <div className="album-dialog-filters">
          <label className="album-dialog-field" htmlFor="recording-filename">
            Filename
            <input
              id="recording-filename"
              ref={searchRef}
              type="search"
              value={query}
              autoComplete="off"
              onChange={(event) => setQuery(event.target.value)}
            />
          </label>
          <label className="album-dialog-field" htmlFor="recording-study">
            Study
            <select id="recording-study" value={studyId} onChange={(event) => setStudyId(event.target.value)}>
              <option value="">All recordings</option>
              {studies.map((study) => (
                <option key={study.id} value={study.id}>
                  {study.name}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div className="album-dialog-tools">
          <button
            type="button"
            className="ghost"
            disabled={busy || selectable.length === 0}
            onClick={() => {
              const next = new Set(picked)
              for (const item of selectable) {
                next.add(item.id)
              }
              onPickedChange(next)
            }}
          >
            Select all visible
          </button>
          <button
            type="button"
            className="ghost"
            disabled={busy || selected.length === 0}
            onClick={() => onPickedChange(new Set<string>())}
          >
            Clear selection
          </button>
        </div>
        <div className="album-dialog-scroll">
          {library.length === 0 ? <p>No recordings in the library.</p> : null}
          {library.length > 0 && visible.length === 0 ? <p>No recordings match this filter.</p> : null}
          {visible.length > 0 ? (
            <table className="log">
              <thead>
                <tr>
                  <th scope="col">Select</th>
                  <th scope="col">Name</th>
                  <th scope="col">Duration</th>
                  <th scope="col">Analysis</th>
                  <th scope="col">Album</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((item) => {
                  const member = memberIds.has(item.id)
                  return (
                    <tr key={item.id} data-member={member ? "true" : "false"}>
                      <td className="picker-check">
                        <input
                          id={`pick-${item.id}`}
                          type="checkbox"
                          aria-label={choiceLabel(item, member)}
                          checked={!member && picked.has(item.id)}
                          disabled={member || busy}
                          onChange={(event) => {
                            const next = new Set(picked)
                            if (event.target.checked) {
                              next.add(item.id)
                            } else {
                              next.delete(item.id)
                            }
                            onPickedChange(next)
                          }}
                        />
                      </td>
                      <td className="name" data-label="Name">
                        <label htmlFor={`pick-${item.id}`}>{item.original_name}</label>
                      </td>
                      <td className="num" data-label="Duration">
                        {clock(item.duration_s)}
                      </td>
                      <td data-label="Analysis">
                        <span className="analysis-state" data-status={item.analysis_status}>
                          {statusLabel(item.analysis_status)}
                        </span>
                      </td>
                      <td data-label="Album">{member ? "In album" : "Available"}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          ) : null}
        </div>
        <div className="album-dialog-foot">
          <p id="recording-selection-summary" aria-live="polite">
            {selectionSummary(selected.length, hidden)}
          </p>
          {feedback ? (
            <p className={feedback.role === "alert" ? "feedback is-alert" : "feedback"} role={feedback.role}>
              {feedback.text}
            </p>
          ) : null}
          <div className="album-dialog-actions">
            <button type="button" className="action" onClick={onAdd} disabled={busy || selected.length === 0}>
              Add
            </button>
            <button type="button" className="action" onClick={onQueue} disabled={busy || selected.length === 0}>
              Add & Queue Analysis
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  )
}
