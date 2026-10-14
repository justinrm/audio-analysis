import { useEffect, useRef, useState } from "react"
import { api, ApiError, lyricSourceUrl } from "./api/client"
import type { AnnotationIn, AnnotationOut, LyricDocumentOut, LyricSegmentOut, LyricSegmentUpdate } from "./api/types"
import { clock } from "./catalog"

/** A single word longer than this is offered for review. A phrase is not. */
export const LONG_SINGLE_TOKEN_S = 2
/** Gap between still-supplied subtitle cues. Not evidence of silence. */
export const SUBTITLE_GAP_S = 2

export type LyricCue = {
  id: string
  start: number
  end: number
  label: string
  origin: "subtitle_supplied" | "manual_edit" | "manual_verified"
}

export type ReviewHint = {
  id: string
  kind: "long-token" | "subtitle-gap" | "overlap" | "out-of-range"
  time_s: number | null
  text: string
}

export type LyricBridge = {
  commit: (id: string, start: number, end: number) => void
  pick: (id: string) => void
}

type Draft = { text: string; start: string; end: string; clear: boolean }

type RegionShape = { id: string; start: number; end: number }

export type LyricRegionPlugin = {
  clearRegions: () => void
  getRegions: () => Array<{ id: string; setOptions: (options: { color?: string }) => void }>
  addRegion: (options: {
    id: string
    start: number
    end: number
    drag: boolean
    resize: boolean
    color: string
    content: string
  }) => RegionShape
  on: (
    event: "region-updated" | "region-clicked",
    handler: (region: RegionShape, event?: MouseEvent) => void,
  ) => () => void
}

const INTERVAL = "The interval needs a start before its end, inside the recording."
const RELOAD_FIRST =
  "Another revision exists, and the latest lines could not be loaded. Your unsaved edit is still in the row. Load the latest lines before saving."

type Hold = {
  id: string
  text: string
  start_s: number | null
  end_s: number | null
  textEdited: boolean
  timesEdited: boolean
}

function near(left: number, right: number): boolean {
  return Math.abs(left - right) < 0.0005
}

function timingChanged(segment: Pick<LyricSegmentOut, "start_s" | "end_s">, draft: Draft): boolean {
  if (draft.clear) {
    return segment.start_s != null || segment.end_s != null
  }
  if (draft.start === "" && draft.end === "") {
    return false
  }
  if (segment.start_s == null || segment.end_s == null) {
    return true
  }
  return !near(segment.start_s, Number(draft.start)) || !near(segment.end_s, Number(draft.end))
}

function wordTokens(text: string): string[] {
  return text.split(/\s+/).filter((token) => /[\p{L}\p{N}]/u.test(token))
}

export function cueLabel(segment: Pick<LyricSegmentOut, "source_cue" | "ordinal">): string {
  return segment.source_cue ? `Cue ${segment.source_cue}` : `Line ${segment.ordinal + 1}`
}

export function cueColor(origin: LyricCue["origin"], active: boolean): string {
  switch (origin) {
    case "subtitle_supplied":
      return active ? "rgba(176, 141, 87, 0.72)" : "rgba(176, 141, 87, 0.32)"
    case "manual_edit":
      return active ? "rgba(183, 192, 200, 0.7)" : "rgba(183, 192, 200, 0.28)"
    case "manual_verified":
      return active ? "rgba(226, 196, 122, 0.8)" : "rgba(226, 196, 122, 0.5)"
    default: {
      const unreachable: never = origin
      return unreachable
    }
  }
}

export function regionCues(segments: LyricSegmentOut[]): LyricCue[] {
  const cues: LyricCue[] = []
  for (const segment of segments) {
    if (!segment.usable || segment.start_s == null || segment.end_s == null) {
      continue
    }
    switch (segment.timing_origin) {
      case "unplaced":
        continue
      case "subtitle_supplied":
      case "manual_edit":
      case "manual_verified":
        cues.push({
          id: segment.id,
          start: segment.start_s,
          end: segment.end_s,
          label: cueLabel(segment),
          origin: segment.timing_origin,
        })
        break
      default: {
        const unreachable: never = segment.timing_origin
        throw new Error(unreachable)
      }
    }
  }
  return cues
}

export function cueKey(cues: LyricCue[]): string {
  return cues.map((cue) => `${cue.id}:${cue.start}:${cue.end}:${cue.origin}`).join("|")
}

/** Earliest usable cue that contains time. A shared boundary belongs to the later cue. */
export function activeSegmentId(segments: LyricSegmentOut[], time: number): string | null {
  if (!Number.isFinite(time)) {
    return null
  }
  const hits = segments.filter((segment) => {
    if (!segment.usable || segment.start_s == null || segment.end_s == null) {
      return false
    }
    return segment.start_s <= time && time < segment.end_s
  })
  hits.sort((a, b) => (a.start_s ?? 0) - (b.start_s ?? 0) || a.ordinal - b.ordinal)
  return hits[0]?.id ?? null
}

/**
 * Advisory only. Nothing here is stored or applied to a cue.
 * One token longer than LONG_SINGLE_TOKEN_S seconds is a review candidate.
 * A multiword line is never flagged for length.
 * A gap of at least SUBTITLE_GAP_S seconds between subtitle-supplied cues is a
 * review candidate and is not musical silence.
 * Overlap and out-of-range hints repeat stored validation so they can be opened.
 */
export function reviewHints(document: LyricDocumentOut): ReviewHint[] {
  const hints: ReviewHint[] = []
  for (const segment of document.segments) {
    if (segment.start_s == null || segment.end_s == null || !(segment.end_s > segment.start_s)) {
      continue
    }
    const length = segment.end_s - segment.start_s
    if (wordTokens(segment.text).length === 1 && length > LONG_SINGLE_TOKEN_S) {
      hints.push({
        id: `long:${segment.id}`,
        kind: "long-token",
        time_s: segment.start_s,
        text: `Single word "${segment.text}" is ${length.toFixed(1)} s. Review only. This is not an error.`,
      })
    }
  }
  const supplied = document.segments
    .filter(
      (segment) =>
        segment.timing_origin === "subtitle_supplied" &&
        segment.start_s != null &&
        segment.end_s != null &&
        segment.end_s > segment.start_s,
    )
    .slice()
    .sort((a, b) => (a.start_s ?? 0) - (b.start_s ?? 0) || a.ordinal - b.ordinal)
  for (let index = 1; index < supplied.length; index += 1) {
    const previous = supplied[index - 1]
    const next = supplied[index]
    if (previous.end_s == null || next.start_s == null) {
      continue
    }
    const gap = next.start_s - previous.end_s
    if (gap >= SUBTITLE_GAP_S) {
      hints.push({
        id: `gap:${previous.id}:${next.id}`,
        kind: "subtitle-gap",
        time_s: previous.end_s,
        text: `${gap.toFixed(1)} s between subtitle cues. A gap is not silence.`,
      })
    }
  }
  for (const item of document.validation) {
    if (item.code !== "overlap" && item.code !== "out_of_range") {
      continue
    }
    const segment = document.segments.find((row) => row.id === item.segment_id)
    hints.push({
      id: `val:${item.code}:${item.segment_id ?? "document"}:${item.detail}`,
      kind: item.code === "overlap" ? "overlap" : "out-of-range",
      time_s: segment?.start_s ?? null,
      text: `${item.detail} This repeats stored validation and does not change the cue.`,
    })
  }
  return hints
}

export function syncLyricRegions(
  plugin: LyricRegionPlugin,
  cues: LyricCue[],
  onCommit: (id: string, start: number, end: number) => void,
  onPick: (id: string) => void,
): () => void {
  let applying = true
  const unsubscribeUpdate = plugin.on("region-updated", (region) => {
    if (applying) {
      return
    }
    const cue = cues.find((item) => item.id === region.id)
    if (cue && near(cue.start, region.start) && near(cue.end, region.end)) {
      return
    }
    onCommit(region.id, region.start, region.end)
  })
  const unsubscribeClick = plugin.on("region-clicked", (region, event) => {
    event?.stopPropagation()
    onPick(region.id)
  })
  plugin.clearRegions()
  for (const cue of cues) {
    plugin.addRegion({
      id: cue.id,
      start: cue.start,
      end: cue.end,
      drag: true,
      resize: true,
      color: cueColor(cue.origin, false),
      content: cue.label,
    })
  }
  applying = false
  return () => {
    applying = true
    unsubscribeUpdate()
    unsubscribeClick()
    plugin.clearRegions()
  }
}

function originCopy(origin: LyricSegmentOut["timing_origin"]): string {
  switch (origin) {
    case "unplaced":
      return "Unplaced. No time is assigned."
    case "subtitle_supplied":
      return "Subtitle-supplied timing. Not artist-confirmed."
    case "manual_edit":
      return "Manually edited timing. Not artist-confirmed."
    case "manual_verified":
      return "Artist-confirmed alignment. Not an acoustic measurement."
    default: {
      const unreachable: never = origin
      return unreachable
    }
  }
}

function fieldText(value: number | null): string {
  return value == null ? "" : String(value)
}

function blankDraft(segment: LyricSegmentOut): Draft {
  return { text: segment.text, start: fieldText(segment.start_s), end: fieldText(segment.end_s), clear: false }
}

async function findProject(assetId: string): Promise<{ id: string } | { id: null; reason: "none" | "several" }> {
  const projects = await api.projects()
  const matches: string[] = []
  for (const project of projects) {
    const detail = await api.project(project.id)
    if (detail.assets.some((asset) => asset.id === assetId)) {
      matches.push(project.id)
    }
  }
  if (matches.length === 1) {
    return { id: matches[0] }
  }
  return { id: null, reason: matches.length === 0 ? "none" : "several" }
}

export function LyricsWorkspace({
  projectId,
  assetId,
  durationS,
  playhead,
  onSeek,
  onCues,
  onActive,
  bridge,
  onRegionReset,
}: {
  projectId: string | null
  assetId: string
  durationS: number
  playhead: number | null
  onSeek: (seconds: number) => void
  onCues: (cues: LyricCue[]) => void
  onActive: (id: string | null) => void
  bridge: { current: LyricBridge }
  onRegionReset: () => void
}) {
  const [project, setProject] = useState<string | null>(projectId)
  const [document, setDocument] = useState<LyricDocumentOut | null>(null)
  const [drafts, setDrafts] = useState<Record<string, Draft>>({})
  const [notes, setNotes] = useState<AnnotationOut[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [conflict, setConflict] = useState<{ segmentId: string; server: LyricDocumentOut } | null>(null)
  const [status, setStatus] = useState("Loading lyrics.")
  const [alert, setAlert] = useState("")
  const [busy, setBusy] = useState(false)
  const [hold, setHold] = useState<Hold | null>(null)
  const [noteStart, setNoteStart] = useState("")
  const [noteEnd, setNoteEnd] = useState("")
  const [noteText, setNoteText] = useState("")
  const [attachNote, setAttachNote] = useState(true)
  const docRef = useRef(document)
  const projectRef = useRef(project)
  const draftsRef = useRef(drafts)
  const regionQueue = useRef<Promise<void>>(Promise.resolve())
  const writeEpoch = useRef(0)
  const holdRef = useRef<Hold | null>(null)
  docRef.current = document
  projectRef.current = project
  draftsRef.current = drafts
  holdRef.current = hold

  function rememberHold(next: Hold | null) {
    holdRef.current = next
    setHold(next)
  }

  function adopt(pending: Hold, latest: LyricDocumentOut) {
    const draft = draftsRef.current[pending.id]
    const saved = latest.segments.find((item) => item.id === pending.id)
    docRef.current = latest
    setDocument(latest)
    setConflict({ segmentId: pending.id, server: latest })
    const textEdited = draft != null && (pending.textEdited || draft.text !== pending.text)
    const timesEdited = draft != null && (pending.timesEdited || timingChanged(pending, draft))
    if (draft && saved && (textEdited || timesEdited)) {
      const next = {
        ...draftsRef.current,
        [pending.id]: {
          text: textEdited ? draft.text : saved.text,
          start: timesEdited ? draft.start : fieldText(saved.start_s),
          end: timesEdited ? draft.end : fieldText(saved.end_s),
          clear: timesEdited && draft.clear,
        },
      }
      draftsRef.current = next
      setDrafts(next)
    } else if (draft && !saved) {
      // The line is gone on the server. Keep the local row for comparison.
    } else if (draft) {
      const copy = { ...draftsRef.current }
      delete copy[pending.id]
      draftsRef.current = copy
      setDrafts(copy)
    }
    rememberHold(null)
    setStatus("")
    setAlert(
      textEdited || timesEdited
        ? `Another revision exists (revision ${latest.revision}). The saved lines were reloaded. Your unsaved edit is still in the row. Save again to write it onto this revision.`
        : `Another revision exists (revision ${latest.revision}). The saved lines were reloaded. Confirmation was not saved.`,
    )
  }

  useEffect(() => {
    let cancel = false
    async function load() {
      setStatus("Loading lyrics.")
      setAlert("")
      docRef.current = null
      setDocument(null)
      setDrafts({})
      setConflict(null)
      try {
        const resolved = projectId != null ? { id: projectId } : await findProject(assetId)
        if (cancel) {
          return
        }
        if (resolved.id == null) {
          setProject(null)
          setStatus("")
          setAlert(
            resolved.reason === "several"
              ? "This recording is in more than one study. Open it from the study list."
              : "This recording is not in a study, so lyrics cannot be attached.",
          )
          return
        }
        setProject(resolved.id)
        projectRef.current = resolved.id
        const [lyricDocument, annotations] = await Promise.all([
          api.lyrics(resolved.id, assetId).catch((error: unknown) => {
            if (error instanceof ApiError && error.code === "no_lyrics") {
              return null
            }
            throw error
          }),
          api.annotations(resolved.id, assetId),
        ])
        if (cancel) {
          return
        }
        docRef.current = lyricDocument
        setDocument(lyricDocument)
        setNotes(annotations)
        setStatus("")
      } catch (error) {
        if (cancel) {
          return
        }
        setStatus("")
        setAlert(error instanceof Error ? error.message : "Lyrics could not be loaded.")
      }
    }
    void load()
    return () => {
      cancel = true
    }
  }, [projectId, assetId])

  useEffect(() => {
    onCues(regionCues(document?.segments ?? []))
  }, [document, onCues])

  useEffect(() => {
    onActive(document ? activeSegmentId(document.segments, playhead ?? Number.NaN) : null)
  }, [document, playhead, onActive])

  useEffect(() => {
    return () => {
      onCues([])
      onActive(null)
    }
  }, [onCues, onActive])

  function draftFor(segment: LyricSegmentOut): Draft {
    return drafts[segment.id] ?? blankDraft(segment)
  }

  function editDraft(segment: LyricSegmentOut, patch: Partial<Draft>) {
    setDrafts((prev) => {
      const current = prev[segment.id] ?? blankDraft(segment)
      return { ...prev, [segment.id]: { ...current, ...patch, clear: patch.clear ?? false } }
    })
  }

  function select(id: string) {
    setSelected(id)
    const segment = docRef.current?.segments.find((item) => item.id === id)
    if (segment?.usable && segment.start_s != null && segment.end_s != null) {
      setNoteStart((current) => (current === "" ? String(segment.start_s) : current))
      setNoteEnd((current) => (current === "" ? String(segment.end_s) : current))
    }
    if (!segment?.usable || segment.start_s == null) {
      return
    }
    onSeek(segment.start_s)
  }

  async function recover(id: string, draft: Draft, epoch: number) {
    const currentProject = projectRef.current
    if (!currentProject) {
      return
    }
    const stale = docRef.current?.segments.find((item) => item.id === id)
    const pending: Hold = {
      id,
      text: stale?.text ?? draft.text,
      start_s: stale?.start_s ?? null,
      end_s: stale?.end_s ?? null,
      textEdited: stale == null || draft.text !== stale.text,
      timesEdited: stale == null || timingChanged(stale, draft),
    }
    if (pending.textEdited || pending.timesEdited) {
      const next = { ...draftsRef.current, [id]: draft }
      draftsRef.current = next
      setDrafts(next)
    }
    try {
      const latest = await api.lyrics(currentProject, assetId)
      if (epoch !== writeEpoch.current) {
        return
      }
      adopt(pending, latest)
    } catch {
      if (epoch !== writeEpoch.current) {
        return
      }
      rememberHold(pending)
      setStatus("")
      setAlert(RELOAD_FIRST)
    }
    onRegionReset()
  }

  async function reloadLatest() {
    const pending = holdRef.current
    const currentProject = projectRef.current
    if (!pending || !currentProject) {
      return
    }
    setBusy(true)
    setStatus("Loading the latest lines.")
    try {
      const latest = await api.lyrics(currentProject, assetId)
      if (holdRef.current?.id !== pending.id) {
        return
      }
      adopt(pending, latest)
    } catch {
      setStatus("")
      setAlert(RELOAD_FIRST)
    } finally {
      setBusy(false)
    }
  }

  async function putSegment(id: string, payload: LyricSegmentUpdate, draft: Draft) {
    const currentProject = projectRef.current
    if (!currentProject) {
      return
    }
    if (holdRef.current) {
      setAlert(RELOAD_FIRST)
      return
    }
    const epoch = (writeEpoch.current += 1)
    setBusy(true)
    setAlert("")
    setStatus("Saving the line.")
    try {
      const next = await api.updateSegment(currentProject, assetId, id, payload)
      if (epoch !== writeEpoch.current) {
        return
      }
      docRef.current = next
      setDocument(next)
      setDrafts((prev) => {
        const existing = prev[id]
        const saved = next.segments.find((item) => item.id === id)
        if (!existing || existing.text === saved?.text) {
          const copy = { ...prev }
          delete copy[id]
          return copy
        }
        return {
          ...prev,
          [id]: {
            text: existing.text,
            start: saved?.start_s == null ? "" : String(saved.start_s),
            end: saved?.end_s == null ? "" : String(saved.end_s),
            clear: false,
          },
        }
      })
      setConflict(null)
      setStatus("Saved.")
    } catch (error) {
      if (error instanceof ApiError && error.status === 409 && error.code === "stale_revision") {
        await recover(id, draft, epoch)
        return
      }
      setStatus("")
      setAlert(error instanceof Error ? error.message : "The line was not saved.")
      onRegionReset()
    } finally {
      setBusy(false)
    }
  }

  async function sendRegion(id: string, start: number, end: number) {
    const doc = docRef.current
    if (holdRef.current) {
      setAlert(RELOAD_FIRST)
      onRegionReset()
      return
    }
    if (!doc || !projectRef.current) {
      return
    }
    const segment = doc.segments.find((item) => item.id === id)
    if (!segment) {
      return
    }
    if (segment.start_s != null && segment.end_s != null && near(segment.start_s, start) && near(segment.end_s, end)) {
      return
    }
    if (!(start < end) || start < -0.001 || end > durationS + 0.001) {
      setAlert(INTERVAL)
      onRegionReset()
      return
    }
    const existing = draftsRef.current[id]
    const draft: Draft = {
      text: existing?.text ?? segment.text,
      start: String(start),
      end: String(end),
      clear: false,
    }
    await putSegment(id, { expected_revision: doc.revision, start_s: start, end_s: end }, draft)
  }

  function enqueueRegion(id: string, start: number, end: number) {
    regionQueue.current = regionQueue.current
      .then(() => sendRegion(id, start, end))
      .catch(() => undefined)
  }

  bridge.current.commit = enqueueRegion
  bridge.current.pick = select

  async function save(segment: LyricSegmentOut, draft: Draft) {
    if (holdRef.current) {
      setAlert(RELOAD_FIRST)
      return
    }
    const doc = docRef.current
    if (!doc) {
      return
    }
    const payload: LyricSegmentUpdate = { expected_revision: doc.revision }
    let changing = false
    if (draft.text !== segment.text) {
      payload.text = draft.text
      changing = true
    }
    if (draft.clear) {
      if (segment.start_s != null || segment.end_s != null) {
        payload.clear_timing = true
        changing = true
      }
    } else if (draft.start !== "" || draft.end !== "") {
      const start = Number(draft.start)
      const end = Number(draft.end)
      const same =
        segment.start_s != null &&
        segment.end_s != null &&
        draft.start !== "" &&
        draft.end !== "" &&
        near(segment.start_s, start) &&
        near(segment.end_s, end)
      if (!same) {
        if (draft.start === "" || draft.end === "" || !Number.isFinite(start) || !Number.isFinite(end)) {
          setAlert(INTERVAL)
          return
        }
        if (!(start < end) || start < -0.001 || end > durationS + 0.001) {
          setAlert(INTERVAL)
          return
        }
        payload.start_s = start
        payload.end_s = end
        changing = true
      }
    }
    if (!changing) {
      setStatus("Nothing to save.")
      return
    }
    await putSegment(segment.id, payload, draft)
  }

  async function confirmAlignment(segment: LyricSegmentOut) {
    const doc = docRef.current
    const currentProject = projectRef.current
    const draft = draftsRef.current[segment.id] ?? blankDraft(segment)
    if (holdRef.current) {
      setAlert(RELOAD_FIRST)
      return
    }
    if (!doc || !currentProject || !segment.usable) {
      return
    }
    if (draft.text !== segment.text || timingChanged(segment, draft)) {
      setAlert("Save the line before confirming alignment.")
      return
    }
    const epoch = (writeEpoch.current += 1)
    setBusy(true)
    setAlert("")
    setStatus("Saving artist confirmation.")
    try {
      const next = await api.verifySegment(currentProject, assetId, segment.id, {
        expected_revision: doc.revision,
        verified: true,
      })
      if (epoch !== writeEpoch.current) {
        return
      }
      docRef.current = next
      setDocument(next)
      setConflict(null)
      setStatus("Artist confirmation saved.")
    } catch (error) {
      if (error instanceof ApiError && error.status === 409 && error.code === "stale_revision") {
        await recover(segment.id, draft, epoch)
        return
      }
      setStatus("")
      setAlert(error instanceof Error ? error.message : "The line was not confirmed.")
    } finally {
      setBusy(false)
    }
  }

  async function onFile(file: File | undefined) {
    if (holdRef.current) {
      setAlert(RELOAD_FIRST)
      return
    }
    if (!file || !projectRef.current) {
      return
    }
    if (
      docRef.current &&
      !window.confirm(
        "Replace the lyric file for this recording? The current lines will be replaced. The new file is stored as uploaded.",
      )
    ) {
      return
    }
    const epoch = (writeEpoch.current += 1)
    setStatus("Uploading lyrics.")
    setAlert("")
    try {
      const next = await api.uploadLyrics(projectRef.current, assetId, file)
      if (epoch !== writeEpoch.current) {
        return
      }
      docRef.current = next
      setDocument(next)
      setDrafts({})
      setConflict(null)
      setSelected(null)
      setStatus("Lyric file stored.")
    } catch (error) {
      setStatus("")
      setAlert(error instanceof Error ? error.message : "The lyric file was not stored.")
    }
  }

  async function saveNote() {
    const currentProject = projectRef.current
    if (!currentProject) {
      return
    }
    const text = noteText.trim()
    if (!text) {
      setAlert("Write a note before saving.")
      return
    }
    const start = Number(noteStart)
    const end = Number(noteEnd)
    if (noteStart === "" || noteEnd === "" || !Number.isFinite(start) || !Number.isFinite(end)) {
      setAlert(INTERVAL)
      return
    }
    if (!(end > start) || start < -0.001 || end > durationS + 0.001) {
      setAlert(INTERVAL)
      return
    }
    const body: AnnotationIn = { start_s: start, end_s: end, text }
    if (attachNote && selected) {
      body.segment_id = selected
    }
    setAlert("")
    setStatus("Saving the note.")
    try {
      const created = await api.createAnnotation(currentProject, assetId, body)
      setNotes((prev) => [...prev, created])
      setNoteText("")
      setStatus("Note stored.")
    } catch (error) {
      setStatus("")
      setAlert(error instanceof Error ? error.message : "The note was not stored.")
    }
  }

  async function removeNote(id: string) {
    const currentProject = projectRef.current
    if (!currentProject) {
      return
    }
    setAlert("")
    try {
      await api.deleteAnnotation(currentProject, assetId, id)
      setNotes((prev) => prev.filter((note) => note.id !== id))
      setStatus("Note deleted.")
    } catch (error) {
      setAlert(error instanceof Error ? error.message : "The note was not deleted.")
    }
  }

  const hints = document ? reviewHints(document) : []
  const activeId = document ? activeSegmentId(document.segments, playhead ?? Number.NaN) : null
  const selectedSegment = document?.segments.find((segment) => segment.id === selected) ?? null

  return (
    <>
      <div role="tabpanel">
        <p>{document ? `Source ${document.source_kind.toUpperCase()}` : "Text"}</p>
        <p className="quiet">
          {document
            ? `${document.original_name} · original file kept`
            : "No lyric file is attached."}
        </p>
        {document ? (
          <p className="quiet">
            {document.segments.length} lines · revision {document.revision}
          </p>
        ) : null}
        {document ? (
          <p>
            <a href={lyricSourceUrl(document.project_id, document.asset_id)}>View original file</a>
          </p>
        ) : null}
      </div>
      <div>
        <h2 className="m-0 font-serif text-3xl font-medium">Lyrics & Inspiration</h2>
        <p>Sung timing is not guessed. Plain text stays unplaced until you assign times.</p>
        {project ? (
          <div className="import-row">
            <label htmlFor="lyric-file">Lyric file</label>
            <input
              id="lyric-file"
              type="file"
              accept=".txt,.md,.srt,text/plain,text/markdown"
              disabled={busy || hold != null}
              onChange={(event) => {
                const file = event.target.files?.[0]
                event.target.value = ""
                void onFile(file)
              }}
            />
          </div>
        ) : null}
        <p role="status">{status}</p>
        {alert ? <p role="alert">{alert}</p> : null}
        {hold ? (
          <button type="button" className="action" disabled={busy} onClick={() => void reloadLatest()}>
            Load the latest lines
          </button>
        ) : null}
        {document && document.segments.length === 0 ? <p>This file has no lyric lines.</p> : null}
        {document
          ? document.validation
              .filter((item) => item.segment_id == null)
              .map((item) => (
                <p key={`${item.code}:${item.detail}`} className="warn">
                  {item.detail}
                </p>
              ))
          : null}
        <div>
          {document?.segments.map((segment) => {
            const label = cueLabel(segment)
            const draft = draftFor(segment)
            const warnings = document.validation.filter((item) => item.segment_id === segment.id)
            const saved = conflict?.segmentId === segment.id
              ? conflict.server.segments.find((item) => item.id === segment.id)
              : null
            return (
              <form
                key={segment.id}
                className="lyric-row"
                aria-current={selected === segment.id ? "true" : undefined}
                data-playing={activeId === segment.id ? "true" : undefined}
                onSubmit={(event) => {
                  event.preventDefault()
                  void save(segment, draft)
                }}
              >
                <p>
                  {label}
                  {activeId === segment.id ? " · Playing" : ""}
                </p>
                {selected === segment.id ? <p>Selected</p> : null}
                <p>{originCopy(segment.timing_origin)}</p>
                {segment.timing_origin === "unplaced" ? <p>No seek time.</p> : null}
                {!segment.usable && segment.timing_origin !== "unplaced" ? <p>Not drawn on the waveform.</p> : null}
                {segment.usable && segment.start_s != null ? (
                  <button type="button" className="ghost" onClick={() => select(segment.id)}>
                    Go to {clock(segment.start_s, true)}
                  </button>
                ) : (
                  <button type="button" className="ghost" onClick={() => setSelected(segment.id)}>
                    Select {label}
                  </button>
                )}
                <label>
                  Text for {label}
                  <textarea
                    value={draft.text}
                    onChange={(event) => editDraft(segment, { text: event.target.value })}
                  />
                </label>
                <div className="lyric-times">
                  <label>
                    Start seconds for {label}
                    <input
                      type="number"
                      step="0.01"
                      inputMode="decimal"
                      value={draft.start}
                      onChange={(event) => editDraft(segment, { start: event.target.value })}
                    />
                  </label>
                  <label>
                    End seconds for {label}
                    <input
                      type="number"
                      step="0.01"
                      inputMode="decimal"
                      value={draft.end}
                      onChange={(event) => editDraft(segment, { end: event.target.value })}
                    />
                  </label>
                  <p className="quiet">
                    {draft.start === "" || draft.end === ""
                      ? "No interval in the draft."
                      : `${clock(Number(draft.start), true)} – ${clock(Number(draft.end), true)}`}
                  </p>
                </div>
                {warnings.map((item) => (
                  <p key={`${item.code}:${item.detail}`} className="warn">
                    {item.detail}
                  </p>
                ))}
                {segment.note ? <p>Stored line note: {segment.note}</p> : null}
                {saved ? (
                  <p>
                    Saved revision {conflict?.server.revision}: {saved.text}
                  </p>
                ) : null}
                {conflict?.segmentId === segment.id && !saved ? (
                  <p>Saved revision {conflict.server.revision}: that line is not on the latest revision.</p>
                ) : null}
                <div className="import-row">
                  <button type="submit" className="action" disabled={busy || hold != null}>
                    Save {label}
                  </button>
                  <button
                    type="button"
                    className="ghost"
                    disabled={busy || hold != null}
                    onClick={() => {
                      const next = { ...draft, start: "", end: "", clear: true }
                      setDrafts((prev) => ({ ...prev, [segment.id]: next }))
                      void save(segment, next)
                    }}
                  >
                    Clear timing for {label}
                  </button>
                  {segment.usable && segment.timing_origin !== "manual_verified" ? (
                    <button
                      type="button"
                      className="ghost"
                      disabled={busy || hold != null || draft.text !== segment.text || timingChanged(segment, draft)}
                      onClick={() => void confirmAlignment(segment)}
                    >
                      Confirm alignment for {label}
                    </button>
                  ) : null}
                  {segment.usable && segment.timing_origin !== "manual_verified" && (draft.text !== segment.text || timingChanged(segment, draft)) ? (
                    <p>Save this line before confirming alignment.</p>
                  ) : null}
                  {!segment.usable ? <p>Confirm alignment is unavailable until the interval is usable.</p> : null}
                </div>
              </form>
            )
          })}
        </div>
      </div>
      <aside>
        <h2 className="m-0 font-serif text-2xl font-medium">Notes</h2>
        <p className="quiet">Artist observations. Not measured evidence and not an Album QC verdict.</p>
        {notes.length === 0 ? <p>No notes yet.</p> : null}
        {notes.map((note) => {
          const line = document?.segments.find((segment) => segment.id === note.segment_id)
          return (
          <p key={note.id}>
            {clock(note.start_s, true)} – {clock(note.end_s, true)}
            {line ? ` · ${cueLabel(line)}` : ""}: {note.text}{" "}
            <button type="button" className="ghost" onClick={() => void removeNote(note.id)}>
              Delete note {note.id}
            </button>
          </p>
          )
        })}
        <form
          className="note-form"
          onSubmit={(event) => {
            event.preventDefault()
            void saveNote()
          }}
        >
          <label>
            Note start seconds
            <input
              type="number"
              step="0.01"
              inputMode="decimal"
              value={noteStart}
              onChange={(event) => setNoteStart(event.target.value)}
            />
          </label>
          <label>
            Note end seconds
            <input
              type="number"
              step="0.01"
              inputMode="decimal"
              value={noteEnd}
              onChange={(event) => setNoteEnd(event.target.value)}
            />
          </label>
          <label>
            Note text
            <textarea value={noteText} onChange={(event) => setNoteText(event.target.value)} />
          </label>
          <label>
            <input
              type="checkbox"
              checked={attachNote && selected != null}
              disabled={selected == null}
              onChange={(event) => setAttachNote(event.target.checked)}
            />
            Attach this note to {selectedSegment ? cueLabel(selectedSegment) : "the selected line"}
          </label>
          <button type="submit" className="action">
            Save note
          </button>
        </form>
        <h2 className="m-0 font-serif text-2xl font-medium">Timing review</h2>
        <p className="quiet">Suggestions only. Nothing here changes a cue.</p>
        {hints.length === 0 ? <p>No timing review suggestions.</p> : null}
        {hints.map((hint) => (
          <p key={hint.id} className="advisory">
            {hint.text}{" "}
            {hint.time_s == null ? (
              <button type="button" className="ghost" disabled>
                No time to jump to
              </button>
            ) : (
              <button type="button" className="ghost" onClick={() => onSeek(hint.time_s ?? 0)}>
                Jump to {clock(hint.time_s, true)}
              </button>
            )}
          </p>
        ))}
        <h2 className="m-0 font-serif text-2xl font-medium">Evidence</h2>
        {document ? <p>textual</p> : <p>No lyric document yet.</p>}
        <p>Timing is not measured from the audio. Inspiration charts are not in this slice.</p>
      </aside>
    </>
  )
}
