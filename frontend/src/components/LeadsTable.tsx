import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { enrichmentsApi, personsApi } from '../api/leads'
import type { Person } from '../api/types'
import Modal from './Modal'
import LeadForm from './LeadForm'

interface LeadsTableProps {
  onOpenEnrichment: (enrichmentId: number) => void
}

const ENRICH_STAGES = [
  { until: 18, label: 'Parsing lead details' },
  { until: 38, label: 'Researching company fit' },
  { until: 58, label: 'Scanning relevant news' },
  { until: 78, label: 'Mapping market context' },
  { until: 96, label: 'Drafting outreach' },
  { until: 100, label: 'Finalizing enrichment' },
] as const

function getEnrichStage(progress: number) {
  return ENRICH_STAGES.find((stage) => progress <= stage.until) ?? ENRICH_STAGES[ENRICH_STAGES.length - 1]
}

export default function LeadsTable({ onOpenEnrichment }: LeadsTableProps) {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [addOpen, setAddOpen] = useState(false)
  const [editing, setEditing] = useState<Person | null>(null)
  const [deleting, setDeleting] = useState<Person | null>(null)
  const [enrichingLeadId, setEnrichingLeadId] = useState<number | null>(null)
  const [enrichProgress, setEnrichProgress] = useState(0)
  const [enrichError, setEnrichError] = useState('')

  useEffect(() => {
    if (enrichingLeadId == null) {
      setEnrichProgress(0)
      return
    }

    setEnrichProgress(8)
    const interval = window.setInterval(() => {
      setEnrichProgress((current) => {
        if (current >= 96) return current
        if (current < 28) return current + 6
        if (current < 52) return current + 4
        if (current < 74) return current + 3
        if (current < 88) return current + 2
        return current + 1
      })
    }, 700)

    return () => window.clearInterval(interval)
  }, [enrichingLeadId])

  const { data, isLoading } = useQuery({
    queryKey: ['persons', search],
    queryFn: () => personsApi.list(search || undefined).then((r) => r.data.results),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => personsApi.delete(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['persons'] })
      setDeleting(null)
    },
  })

  const enrichMutation = useMutation({
    mutationFn: (leadId: number) => enrichmentsApi.run(leadId),
    onMutate: (leadId: number) => {
      setEnrichError('')
      setEnrichingLeadId(leadId)
    },
    onSuccess: async (response) => {
      setEnrichProgress(100)
      await new Promise((resolve) => window.setTimeout(resolve, 350))
      qc.invalidateQueries({ queryKey: ['persons'] })
      qc.invalidateQueries({ queryKey: ['enrichment', response.data.id] })
      onOpenEnrichment(response.data.id)
    },
    onError: (error: any) => {
      setEnrichError(error.response?.data?.detail ?? 'Enrichment failed. Please try again.')
    },
    onSettled: () => {
      setEnrichingLeadId(null)
    },
  })

  const enrichStage = getEnrichStage(enrichProgress)

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-6 py-4">
        <div className="flex-1 relative">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-apple-gray" viewBox="0 0 16 16" fill="none">
            <circle cx="6.5" cy="6.5" r="5" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M10.5 10.5l3.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <input
            type="search"
            placeholder="Search leads…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-white rounded-xl pl-9 pr-4 py-2 text-[14px] text-gray-900 border border-apple-separator outline-none focus:ring-2 focus:ring-apple-blue placeholder:text-apple-gray"
          />
        </div>
        <button
          onClick={() => setAddOpen(true)}
          className="flex items-center gap-2 bg-apple-blue text-white px-4 py-2 rounded-xl text-[14px] font-medium hover:bg-blue-600 transition-colors whitespace-nowrap"
        >
          <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
            <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          Add Lead
        </button>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto px-6 pb-6">
        {enrichError ? (
          <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-700">
            {enrichError}
          </div>
        ) : null}
        {enrichingLeadId != null ? (
          <div className="mb-4 rounded-2xl border border-blue-200 bg-blue-50 px-4 py-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[13px] font-semibold uppercase tracking-wide text-blue-700">Enrichment running</p>
                <p className="mt-1 text-[14px] text-blue-700">{enrichStage.label}</p>
              </div>
              <span className="text-[14px] font-semibold text-blue-700">{enrichProgress}%</span>
            </div>
            <div className="mt-3 h-2 overflow-hidden rounded-full bg-blue-100">
              <div
                className="h-full rounded-full bg-apple-blue transition-[width] duration-700 ease-out"
                style={{ width: `${enrichProgress}%` }}
              />
            </div>
            <p className="mt-2 text-[12px] text-blue-700/80">
              This usually takes 5-15 seconds depending on external sources.
            </p>
          </div>
        ) : null}
        <div className="bg-white rounded-2xl overflow-hidden border border-apple-separator shadow-sm">
          {isLoading ? (
            <div className="flex items-center justify-center py-16 text-apple-gray text-[14px]">Loading…</div>
          ) : !data?.length ? (
            <div className="flex flex-col items-center justify-center py-16 gap-2">
              <p className="text-[17px] font-medium text-gray-700">No leads yet</p>
              <p className="text-[14px] text-apple-gray">
                {search ? 'No results for this search.' : 'Click "Add Lead" to get started.'}
              </p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-apple-separator">
                  <th className="text-left text-[12px] font-semibold uppercase tracking-wider text-apple-gray px-5 py-3">Name</th>
                  <th className="text-left text-[12px] font-semibold uppercase tracking-wider text-apple-gray px-5 py-3">Email</th>
                  <th className="text-left text-[12px] font-semibold uppercase tracking-wider text-apple-gray px-5 py-3">Company</th>
                  <th className="text-left text-[12px] font-semibold uppercase tracking-wider text-apple-gray px-5 py-3">Building</th>
                  <th className="text-left text-[12px] font-semibold uppercase tracking-wider text-apple-gray px-5 py-3">Status</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-apple-separator">
                {data.map((p) => (
                  <tr key={p.id} className="hover:bg-apple-lightgray/50 transition-colors group">
                    <td className="px-5 py-3.5">
                      <p className="text-[14px] font-medium text-gray-900">{p.name}</p>
                    </td>
                    <td className="px-5 py-3.5">
                      <a href={`mailto:${p.email}`} className="text-[14px] text-apple-blue hover:underline">{p.email}</a>
                    </td>
                    <td className="px-5 py-3.5">
                      <p className="text-[14px] text-gray-600">{p.company || '—'}</p>
                    </td>
                    <td className="px-5 py-3.5">
                      {p.building_detail ? (
                        <div>
                          <p className="text-[14px] text-gray-900">{p.building_detail.property_address}</p>
                          <p className="text-[12px] text-apple-gray">{p.building_detail.city}, {p.building_detail.state}</p>
                        </div>
                      ) : (
                        <span className="text-[14px] text-apple-gray">—</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      {p.has_enrichment && p.latest_enrichment_id ? (
                        <button
                          onClick={() => onOpenEnrichment(p.latest_enrichment_id!)}
                          className="inline-flex items-center gap-2 rounded-full bg-green-100 px-2.5 py-1 text-[12px] font-medium text-green-700 hover:bg-green-200"
                        >
                          <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                          Enriched
                          {p.latest_enrichment_tier ? ` ${p.latest_enrichment_tier}` : ''}
                        </button>
                      ) : (
                        <span className="text-[13px] text-apple-gray">Not enriched</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity justify-end">
                        <button
                          onClick={() => {
                            if (p.has_enrichment && p.latest_enrichment_id) {
                              onOpenEnrichment(p.latest_enrichment_id)
                              return
                            }
                            enrichMutation.mutate(p.id)
                          }}
                          disabled={enrichingLeadId !== null}
                          className="text-[13px] text-apple-blue hover:text-blue-700 font-medium disabled:opacity-50"
                        >
                          {enrichingLeadId === p.id ? 'Enriching…' : p.has_enrichment ? 'View' : 'Enrich'}
                        </button>
                        <span className="text-apple-separator">|</span>
                        <button
                          onClick={() => setEditing(p)}
                          className="text-[13px] text-apple-blue hover:text-blue-700 font-medium"
                        >
                          Edit
                        </button>
                        <span className="text-apple-separator">|</span>
                        <button
                          onClick={() => setDeleting(p)}
                          className="text-[13px] text-red-500 hover:text-red-700 font-medium"
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        {data?.length ? (
          <p className="text-[12px] text-apple-gray mt-3 px-1">{data.length} lead{data.length !== 1 ? 's' : ''}</p>
        ) : null}
      </div>

      {addOpen && (
        <Modal title="Add Lead" onClose={() => setAddOpen(false)}>
          <LeadForm onClose={() => setAddOpen(false)} />
        </Modal>
      )}

      {editing && (
        <Modal title="Edit Lead" onClose={() => setEditing(null)}>
          <LeadForm person={editing} onClose={() => setEditing(null)} />
        </Modal>
      )}

      {deleting && (
        <Modal title="Delete Lead" onClose={() => setDeleting(null)}>
          <p className="text-[15px] text-gray-600 mb-5">
            Are you sure you want to delete <strong className="text-gray-900">{deleting.name}</strong>? This cannot be undone.
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => setDeleting(null)}
              className="flex-1 py-2.5 rounded-xl text-[15px] font-medium bg-apple-lightgray text-gray-700 hover:bg-gray-200 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => deleteMutation.mutate(deleting.id)}
              disabled={deleteMutation.isPending}
              className="flex-1 py-2.5 rounded-xl text-[15px] font-medium bg-red-500 text-white hover:bg-red-600 transition-colors disabled:opacity-50"
            >
              {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
