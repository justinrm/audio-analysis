import { useEffect, useState } from "react"
import { Analyzer } from "./analyzer"
import { Library } from "./library"

type Route =
  | { name: "library" }
  | { name: "analyzer"; assetId: string | null; projectId: string | null }
  | { name: "album" }
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
    return { name: "album" }
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
        <>
          <h1 className="page-title">Analyzer</h1>
          <p>Choose a recording from the library.</p>
        </>
      )
    case "album":
      return (
        <>
          <h1 className="page-title">Album QC</h1>
          <p>Comparison is not in this milestone. Study one recording in the analyzer until then.</p>
        </>
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

export function App() {
  const [route, setRoute] = useState<Route>(readRoute)

  function go(next: string) {
    window.history.pushState(null, "", next)
    setRoute(readRoute())
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
        <p className="quiet mt-2 mb-0">A room for one recording at a time.</p>
        <nav className="nav" aria-label="Primary">
          <button type="button" aria-current={route.name === "library" ? "page" : undefined} onClick={() => go("/")}>
            Library
          </button>
          <button
            type="button"
            aria-current={route.name === "analyzer" ? "page" : undefined}
            onClick={() => {
              if (route.name !== "analyzer" || !route.assetId) {
                go("/analyzer")
                return
              }
              const project = route.projectId ? `&project=${route.projectId}` : ""
              go(`/analyzer?asset=${route.assetId}${project}`)
            }}
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
      </aside>
      <main className="stage">{page(route, go)}</main>
    </div>
  )
}
