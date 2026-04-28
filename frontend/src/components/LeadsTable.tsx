import { useEffect, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { enrichmentsApi, personsApi } from '../api/leads'
import type { Person } from '../api/types'
import Modal from './Modal'
import LeadForm from './LeadForm'

interface LeadsTableProps {
  onOpenEnrichment: (enrichmentId: number) => void
}

const ENRICHMENT_STATUS_CLASSES: Record<'A' | 'B' | 'C' | 'D', string> = {
  A: 'border-[#bfcf9d] bg-[#edf3de] text-[#5c7440]',
  B: 'border-[#cdb58d] bg-[#f2eadc] text-[#7a5a2f]',
  C: 'border-[#dfc59f] bg-[#f8efdf] text-[#9a7241]',
  D: 'border-[#d8cec1] bg-[#f1ebe2] text-[#766656]',
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
      <div className="flex items-center gap-3 px-8 py-6">
        <div className="flex-1 relative">
          <svg className="absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-luxe-muted" viewBox="0 0 16 16" fill="none">
            <circle cx="6.5" cy="6.5" r="5" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M10.5 10.5l3.5 3.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <input
            type="search"
            placeholder="Search leads…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full rounded-2xl border border-luxe-line bg-luxe-panel/90 py-3 pl-11 pr-4 text-[14px] text-luxe-ink outline-none shadow-sm focus:ring-2 focus:ring-luxe-accent/25 placeholder:text-luxe-muted"
          />
        </div>
        <button
          onClick={() => setAddOpen(true)}
          className="flex items-center gap-2 whitespace-nowrap rounded-2xl border border-[#7b5a33] bg-gradient-to-br from-[#9a7343] via-[#8e6839] to-[#74512a] px-5 py-3 text-[14px] font-semibold text-[#fff9f0] shadow-[0_12px_24px_rgba(116,81,42,0.22)] transition-all hover:-translate-y-[1px] hover:shadow-[0_16px_28px_rgba(116,81,42,0.28)]"
        >
          <svg className="w-4 h-4" viewBox="0 0 16 16" fill="none">
            <path d="M8 3v10M3 8h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
          </svg>
          Add Lead
        </button>
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto px-8 pb-8">
        <div className="mb-4 flex items-center justify-between gap-4 rounded-[28px] border border-luxe-line bg-luxe-panel/80 px-5 py-4 shadow-[0_14px_30px_rgba(98,73,46,0.06)]">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-luxe-muted">Lead book</p>
            <p className="mt-1 text-[15px] text-[#5f4935]">Track contacts, enrich qualified accounts, and keep outreach drafts in one place.</p>
          </div>
          {data?.length ? (
            <div className="rounded-2xl border border-[#dfcfb7] bg-[#f7efe3] px-4 py-3 text-center">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-luxe-muted">Visible leads</p>
              <p className="mt-1 text-[22px] font-semibold text-luxe-ink">{data.length}</p>
            </div>
          ) : null}
        </div>
        {enrichError ? (
          <div className="mb-4 rounded-3xl border border-red-200 bg-red-50/90 px-4 py-3 text-[13px] text-red-700">
            {enrichError}
          </div>
        ) : null}
        {enrichingLeadId != null ? (
          <div className="mb-4 rounded-3xl border border-[#d8c39d] bg-[#f8eedf] px-5 py-5 shadow-sm">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[12px] font-semibold uppercase tracking-[0.22em] text-luxe-accent">Enrichment running</p>
                <p className="mt-1 text-[15px] text-luxe-ink">{enrichStage.label}</p>
              </div>
              <span className="text-[14px] font-semibold text-luxe-accent">{enrichProgress}%</span>
            </div>
            <div className="mt-4 h-2.5 overflow-hidden rounded-full bg-[#eadcc5]">
              <div
                className="h-full rounded-full bg-luxe-accent transition-[width] duration-700 ease-out"
                style={{ width: `${enrichProgress}%` }}
              />
            </div>
            <p className="mt-3 text-[12px] text-luxe-muted">
              This usually takes 5-15 seconds depending on external sources.
            </p>
          </div>
        ) : null}
        <div className="overflow-hidden rounded-[30px] border border-luxe-line bg-luxe-panel/95 shadow-[0_18px_40px_rgba(98,73,46,0.08)]">
          {isLoading ? (
            <div className="flex items-center justify-center py-16 text-[14px] text-luxe-muted">Loading…</div>
          ) : !data?.length ? (
            <div className="flex flex-col items-center justify-center py-16 gap-2">
              <p className="font-display text-[24px] font-semibold text-luxe-ink">No leads yet</p>
              <p className="text-[14px] text-luxe-muted">
                {search ? 'No results for this search.' : 'Click "Add Lead" to get started.'}
              </p>
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-luxe-line bg-[#f7efe2]">
                  <th className="px-5 py-3 text-left text-[12px] font-semibold uppercase tracking-[0.18em] text-luxe-muted">Name</th>
                  <th className="px-5 py-3 text-left text-[12px] font-semibold uppercase tracking-[0.18em] text-luxe-muted">Email</th>
                  <th className="px-5 py-3 text-left text-[12px] font-semibold uppercase tracking-[0.18em] text-luxe-muted">Company</th>
                  <th className="px-5 py-3 text-left text-[12px] font-semibold uppercase tracking-[0.18em] text-luxe-muted">Building</th>
                  <th className="px-5 py-3 text-left text-[12px] font-semibold uppercase tracking-[0.18em] text-luxe-muted">Status</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-luxe-line/70">
                {data.map((p) => (
                  <tr key={p.id} className="group transition-colors hover:bg-[#fbf4e8]">
                    <td className="px-5 py-3.5">
                      <p className="text-[14px] font-medium text-luxe-ink">{p.name}</p>
                    </td>
                    <td className="px-5 py-3.5">
                      <a href={`mailto:${p.email}`} className="text-[14px] text-luxe-accent hover:underline">{p.email}</a>
                    </td>
                    <td className="px-5 py-3.5">
                      <p className="text-[14px] text-[#5f4935]">{p.company || '—'}</p>
                    </td>
                    <td className="px-5 py-3.5">
                      {p.building_detail ? (
                        <div>
                          <p className="text-[14px] text-luxe-ink">{p.building_detail.property_address}</p>
                          <p className="text-[12px] text-luxe-muted">{p.building_detail.city}, {p.building_detail.state}</p>
                        </div>
                      ) : (
                        <span className="text-[14px] text-luxe-muted">—</span>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      {p.has_enrichment && p.latest_enrichment_id ? (
                        <button
                          onClick={() => onOpenEnrichment(p.latest_enrichment_id!)}
                          className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-[12px] font-medium transition-colors hover:brightness-[0.98] ${
                            p.latest_enrichment_tier
                              ? ENRICHMENT_STATUS_CLASSES[p.latest_enrichment_tier]
                              : 'border-[#dac59f] bg-[#f5ecdd] text-luxe-accent'
                          }`}
                        >
                          <span
                            className={`h-1.5 w-1.5 rounded-full ${
                              p.latest_enrichment_tier === 'A'
                                ? 'bg-[#6f8a4f]'
                                : p.latest_enrichment_tier === 'B'
                                  ? 'bg-[#8e6839]'
                                  : p.latest_enrichment_tier === 'C'
                                    ? 'bg-[#b07a3a]'
                                    : p.latest_enrichment_tier === 'D'
                                      ? 'bg-[#8f8172]'
                                      : 'bg-luxe-accent'
                            }`}
                          />
                          Enriched
                          {p.latest_enrichment_tier ? ` ${p.latest_enrichment_tier}` : ''}
                        </button>
                      ) : (
                        <span className="text-[13px] text-luxe-muted">Not enriched</span>
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
                          className="text-[13px] font-medium text-luxe-accent hover:text-[#6e4f2d] disabled:opacity-50"
                        >
                          {enrichingLeadId === p.id ? 'Enriching…' : p.has_enrichment ? 'View' : 'Enrich'}
                        </button>
                        <span className="text-luxe-line">|</span>
                        <button
                          onClick={() => setEditing(p)}
                          className="text-[13px] font-medium text-luxe-accent hover:text-[#6e4f2d]"
                        >
                          Edit
                        </button>
                        <span className="text-luxe-line">|</span>
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
          <p className="mt-3 px-1 text-[12px] text-luxe-muted">{data.length} lead{data.length !== 1 ? 's' : ''}</p>
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
          <p className="mb-5 text-[15px] text-[#5f4935]">
            Are you sure you want to delete <strong className="text-luxe-ink">{deleting.name}</strong>? This cannot be undone.
          </p>
          <div className="flex gap-3">
            <button
              onClick={() => setDeleting(null)}
              className="flex-1 rounded-2xl border border-luxe-line bg-luxe-soft px-4 py-2.5 text-[15px] font-medium text-luxe-ink transition-colors hover:bg-luxe-accentSoft"
            >
              Cancel
            </button>
            <button
              onClick={() => deleteMutation.mutate(deleting.id)}
              disabled={deleteMutation.isPending}
              className="flex-1 rounded-2xl border border-[#925f53] bg-gradient-to-br from-[#a36a5c] to-[#8f5a4c] px-4 py-2.5 text-[15px] font-medium text-[#fff8f2] transition-colors hover:from-[#9a6255] hover:to-[#835244] disabled:opacity-50"
            >
              {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
            </button>
          </div>
        </Modal>
      )}
    </div>
  )
}
