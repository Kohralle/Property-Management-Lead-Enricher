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
      <div className="flex h-screen bg-apple-lightgray font-sans">
        {/* Sidebar */}
        <aside className="w-56 bg-white border-r border-apple-separator flex flex-col shrink-0">
          <div className="px-5 pt-8 pb-6">
            <h1 className="text-[20px] font-bold text-gray-900 tracking-tight">Leads</h1>
            <p className="text-[12px] text-apple-gray mt-0.5">Lead Tracker</p>
          </div>
          <nav className="flex-1 px-3">
            <button
              onClick={() => navigate({ name: 'leads' })}
              className={`w-full flex items-center gap-3 px-3 py-2 rounded-xl text-[14px] font-medium ${
                route.name === 'leads'
                  ? 'bg-apple-blue/10 text-apple-blue'
                  : 'text-gray-600 hover:bg-apple-lightgray'
              }`}
            >
              <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
                <path d="M2 4h12M2 8h12M2 12h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              {route.name === 'leads' ? 'All Leads' : 'Back to Leads'}
            </button>
          </nav>
          <div className="px-5 pb-6">
            <p className="text-[11px] text-apple-separator">Lead Enricher</p>
          </div>
        </aside>

        {/* Main */}
        <main className="flex-1 flex flex-col min-w-0">
          <header className="bg-white border-b border-apple-separator px-6 py-4 shrink-0">
            <h2 className="text-[17px] font-semibold text-gray-900">{title}</h2>
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
