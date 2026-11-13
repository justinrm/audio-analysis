import { useEffect, useState } from "react"
import { AlbumHome, AlbumWorkspace } from "./album"
import { Analyzer } from "./analyzer"
import { AnalyzerEntry } from "./analyzer-entry"
import { Library } from "./library"

type Route =
  | { name: "library" }
  | { name: "analyzer"; assetId: string | null; projectId: string | null }
  | { name: "album"; projectId: string | null }
  | { name: "settings" }

function readRoute(): Route {
  const url = new URL(window.location.href)
  if (url.pathname === "/analyzer") {
    return {
      name: "analyzer",
      assetId: url.searchParams.get("asset"),
      projectId: url.searchParams.get("project"),
    }
  }
  if (url.pathname === "/album") {
    return { name: "album", projectId: url.searchParams.get("project") }
  }
  if (url.pathname === "/settings") {
    return { name: "settings" }
  }
  return { name: "library" }
}

function page(route: Route, go: (next: string) => void) {
  switch (route.name) {
    case "library":
      return (
        <Library
          onOpen={(assetId, openedProjectId) => go(`/analyzer?asset=${assetId}&project=${openedProjectId}`)}
        />
      )
    case "analyzer":
      return route.assetId ? (
        <Analyzer assetId={route.assetId} projectId={route.projectId} />
      ) : (
        <AnalyzerEntry
          onOpen={(assetId, openedProjectId) => go(`/analyzer?asset=${assetId}&project=${openedProjectId}`)}
          onLibrary={() => go("/")}
        />
      )
    case "album":
      return route.projectId ? (
        <AlbumWorkspace projectId={route.projectId} onInspect={(assetId) => go(`/analyzer?asset=${assetId}`)} />
      ) : (
        <AlbumHome onOpen={(projectId) => go(`/album?project=${projectId}`)} />
      )
    case "settings":
      return (
        <>
          <h1 className="page-title">Settings</h1>
          <p>This studio stays on this computer. There is no account, telemetry, or payment.</p>
          <p>AI interpretation is off.</p>
          <p className="quiet">Audio and the database stay in the local data folder.</p>
        </>
      )
    default: {
      const unreachable: never = route
      return unreachable
    }
  }
}

function useNarrowNav(): boolean {
  const [narrow, setNarrow] = useState(false)
  useEffect(() => {
    if (typeof window.matchMedia !== "function") {
      return
    }
    const query = window.matchMedia("(max-width: 600px)")
    const apply = () => setNarrow(query.matches)
    apply()
    query.addEventListener("change", apply)
    return () => query.removeEventListener("change", apply)
  }, [])
  return narrow
}

export function App() {
  const [route, setRoute] = useState<Route>(readRoute)
  const narrowNav = useNarrowNav()

  function go(next: string) {
    window.history.pushState(null, "", next)
    setRoute(readRoute())
  }

  function openAnalyzer() {
    if (route.name !== "analyzer" || !route.assetId) {
      go("/analyzer")
      return
    }
    const project = route.projectId ? `&project=${route.projectId}` : ""
    go(`/analyzer?asset=${route.assetId}${project}`)
  }

  function chooseDestination(name: string) {
    if (name === "library") {
      go("/")
      return
    }
    if (name === "analyzer") {
      openAnalyzer()
      return
    }
    if (name === "album") {
      go("/album")
      return
    }
    go("/settings")
  }

  useEffect(() => {
    const onPop = () => setRoute(readRoute())
    window.addEventListener("popstate", onPop)
    return () => window.removeEventListener("popstate", onPop)
  }, [])

  return (
    <div className="shell">
      <aside className="rail">
        <p className="mark">Reference</p>
        <p className="quiet mt-2 mb-0">A room for one recording, and for comparing a set.</p>
        {narrowNav ? (
          <label className="nav-picker">
            Destination
            <select aria-label="Destination" value={route.name} onChange={(event) => chooseDestination(event.target.value)}>
              <option value="library">Library</option>
              <option value="analyzer">Analyzer</option>
              <option value="album">Album QC</option>
              <option value="settings">Settings</option>
            </select>
          </label>
        ) : (
          <nav className="nav" aria-label="Primary">
            <button type="button" aria-current={route.name === "library" ? "page" : undefined} onClick={() => go("/")}>
              Library
            </button>
            <button
              type="button"
              aria-current={route.name === "analyzer" ? "page" : undefined}
              onClick={openAnalyzer}
            >
              Analyzer
            </button>
            <button type="button" aria-current={route.name === "album" ? "page" : undefined} onClick={() => go("/album")}>
              Album QC
            </button>
            <button
              type="button"
              aria-current={route.name === "settings" ? "page" : undefined}
              onClick={() => go("/settings")}
            >
              Settings
            </button>
          </nav>
        )}
      </aside>
      <main className="stage">{page(route, go)}</main>
    </div>
  )
}
