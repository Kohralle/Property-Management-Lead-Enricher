import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import EnrichmentDetail from './components/EnrichmentDetail'
import LeadsTable from './components/LeadsTable'

const qc = new QueryClient()

type Route =
  | { name: 'leads' }
  | { name: 'enrichment'; enrichmentId: number }

function routeFromLocation(pathname: string): Route {
  const match = pathname.match(/^\/enrichments\/(\d+)\/?$/)
  if (match) {
    return { name: 'enrichment', enrichmentId: Number(match[1]) }
  }
  return { name: 'leads' }
}

export default function App() {
  const [route, setRoute] = useState<Route>(() => routeFromLocation(window.location.pathname))

  useEffect(() => {
    const handlePopState = () => setRoute(routeFromLocation(window.location.pathname))
    window.addEventListener('popstate', handlePopState)
    return () => window.removeEventListener('popstate', handlePopState)
  }, [])

  const navigate = (nextRoute: Route) => {
    const nextPath = nextRoute.name === 'leads'
      ? '/'
      : `/enrichments/${nextRoute.enrichmentId}`
    window.history.pushState({}, '', nextPath)
    setRoute(nextRoute)
  }

  const title = route.name === 'leads' ? 'All Leads' : 'Lead Enrichment'

  return (
    <QueryClientProvider client={qc}>
      <div className="flex h-screen bg-luxe-shell font-sans text-luxe-ink">
        {/* Sidebar */}
        <aside className="flex w-60 shrink-0 flex-col border-r border-luxe-line bg-[#f4e7d1]/80 backdrop-blur">
          <div className="px-6 pb-7 pt-9">
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-luxe-muted">Lead Enricher</p>
            <h1 className="mt-3 font-display text-[28px] font-semibold tracking-tight text-luxe-ink">Leads</h1>
            <p className="mt-1 text-[12px] text-luxe-muted">Property management lead workflow</p>
          </div>
          <nav className="flex-1 px-4">
            <button
              onClick={() => navigate({ name: 'leads' })}
              className={`flex w-full items-center gap-3 rounded-2xl px-4 py-3 text-[14px] font-medium transition-colors ${
                route.name === 'leads'
                  ? 'bg-luxe-panel text-luxe-accent shadow-sm ring-1 ring-luxe-line'
                  : 'text-luxe-muted hover:bg-luxe-panel/70 hover:text-luxe-ink'
              }`}
            >
              <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
                <path d="M2 4h12M2 8h12M2 12h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              {route.name === 'leads' ? 'All Leads' : 'Back to Leads'}
            </button>
          </nav>
          <div className="px-6 pb-7">
            <p className="text-[11px] uppercase tracking-[0.2em] text-luxe-muted/80">Private workspace</p>
          </div>
        </aside>

        {/* Main */}
        <main className="flex-1 flex flex-col min-w-0">
          <header className="shrink-0 border-b border-luxe-line bg-luxe-panel/90 px-8 py-5 backdrop-blur">
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-luxe-muted">Private lead workspace</p>
            <h2 className="mt-2 font-display text-[24px] font-semibold tracking-tight text-luxe-ink">{title}</h2>
          </header>
          {route.name === 'leads' ? (
            <LeadsTable onOpenEnrichment={(enrichmentId) => navigate({ name: 'enrichment', enrichmentId })} />
          ) : (
            <EnrichmentDetail
              enrichmentId={route.enrichmentId}
              onBack={() => navigate({ name: 'leads' })}
            />
          )}
        </main>
      </div>
    </QueryClientProvider>
  )
}
