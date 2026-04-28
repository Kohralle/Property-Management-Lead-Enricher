import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { enrichmentsApi } from '../api/leads'
import type {
  CompanyResearch,
  EnrichmentResult,
  GeoDemographics,
  MarketData,
  NewsArticle,
  ScoreBucket,
} from '../api/types'

interface EnrichmentDetailProps {
  enrichmentId: number
  onBack: () => void
}

interface Segment {
  label: string
  points: number
  maxPoints: number
  width: number
  color: string
}

const TIER_CLASSES = {
  A: 'border-[#cdb58d] bg-[#f2eadc] text-[#7a5a2f]',
  B: 'border-[#d8c6a9] bg-[#f7f0e4] text-[#8e6839]',
  C: 'border-[#ddcdb5] bg-[#f4ecdf] text-[#9a7241]',
  D: 'border-[#d7cec1] bg-[#f1ebe1] text-[#766656]',
} as const

const SEGMENT_COLORS = {
  hard: 'bg-[#8e6839]',
  activity: 'bg-[#b78758]',
  contact: 'bg-[#7c8f6a]',
  market: 'bg-[#bfa27a]',
} as const

export default function EnrichmentDetail({
  enrichmentId,
  onBack,
}: EnrichmentDetailProps) {
  const [emailBody, setEmailBody] = useState('')
  const [showRules, setShowRules] = useState(false)
  const [showEvidenceClaims, setShowEvidenceClaims] = useState(false)
  const [showEmailModal, setShowEmailModal] = useState(false)
  const [activeTab, setActiveTab] = useState<'company' | 'news' | 'market' | 'raw'>('company')

  const { data, isLoading, isFetching } = useQuery({
    queryKey: ['enrichment', enrichmentId],
    queryFn: () => enrichmentsApi.get(enrichmentId).then((response) => response.data),
  })

  const details = useMemo(() => buildDetailState(data), [data])

  const effectiveEmailBody = emailBody || data?.email_body || ''

  const handleCopy = async () => {
    if (!data) return
    await navigator.clipboard.writeText(`Subject: ${data.email_subject}\n\n${effectiveEmailBody}`)
  }

  if (isLoading || !data || !details) {
    return (
      <div className="flex flex-1 items-center justify-center text-[14px] text-luxe-muted">
        Loading enrichment…
      </div>
    )
  }

  const mailtoHref = buildMailto(data.lead_detail.email, data.email_subject, effectiveEmailBody)

  return (
    <div className="flex-1 overflow-auto px-8 py-8">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
        <div className="flex items-start justify-between gap-4 rounded-[32px] border border-luxe-line bg-luxe-panel/95 p-7 shadow-[0_24px_56px_rgba(90,67,48,0.10)]">
          <div className="space-y-3">
            <button
              onClick={onBack}
              className="inline-flex items-center gap-2 text-[13px] font-medium text-luxe-accent hover:text-[#6e4f2d]"
            >
              <span aria-hidden="true">←</span>
              Back to leads
            </button>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="font-display text-[34px] font-semibold tracking-tight text-luxe-ink">{data.lead_detail.name}</h1>
              <span className={`rounded-full border px-3 py-1 text-[12px] font-semibold ${TIER_CLASSES[data.score_tier]}`}>
                Tier {data.score_tier}
              </span>
            </div>
            <div className="space-y-1">
              <p className="text-[16px] text-[#5f4935]">{data.lead_detail.company || 'Unknown company'}</p>
              <p className="text-[13px] text-luxe-muted">
                {data.lead_detail.email}
                {data.lead_detail.building_detail
                  ? ` • ${data.lead_detail.building_detail.city}, ${data.lead_detail.building_detail.state}`
                  : ''}
              </p>
            </div>
          </div>

          <div className="flex flex-col items-end gap-3">
            <button
              onClick={() => setShowEmailModal(true)}
              className="rounded-2xl border border-luxe-line bg-luxe-soft px-4 py-2.5 text-[14px] font-medium text-luxe-ink transition-colors hover:bg-luxe-accentSoft"
            >
              Draft email
            </button>
            <div className="rounded-[28px] border border-luxe-line bg-[#f4e9d6] px-7 py-5 text-center shadow-inner">
              <p className="text-[11px] uppercase tracking-[0.18em] text-luxe-muted">Score</p>
              <p className="text-[40px] font-bold leading-none text-luxe-ink">{data.score_total}<span className="text-[18px] text-luxe-muted"> / 100</span></p>
              <p className="mt-1 text-[12px] text-luxe-muted">{isFetching ? 'Refreshing…' : 'Deterministic score'}</p>
            </div>
          </div>
        </div>

        <div className="space-y-5">
            <section className="rounded-[30px] border border-luxe-line bg-luxe-panel/95 p-6 shadow-[0_16px_40px_rgba(90,67,48,0.08)]">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-luxe-muted">Snapshot</p>
                  <h2 className="font-display text-[24px] font-semibold text-luxe-ink">Insights</h2>
                  <p className="text-[13px] text-luxe-muted">Quick operator-facing facts and fit signals.</p>
                </div>
              </div>
              <ul className="mt-5 space-y-3">
                {data.insights.map((insight) => (
                  <li key={insight} className="flex gap-3 text-[14px] text-[#5f4935]">
                    <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-luxe-accent" />
                    <span>{insight}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="rounded-[30px] border border-luxe-line bg-luxe-panel/95 p-6 shadow-[0_16px_40px_rgba(90,67,48,0.08)]">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-luxe-muted">Scoring</p>
                  <h2 className="font-display text-[24px] font-semibold text-luxe-ink">Score breakdown</h2>
                  <p className="text-[13px] text-luxe-muted">Actual bucket points in the 100-point score.</p>
                </div>
                <button
                  onClick={() => setShowRules((value) => !value)}
                  className="text-[13px] font-medium text-luxe-accent hover:text-[#6e4f2d]"
                >
                  {showRules ? 'Hide breakdown' : 'See breakdown'}
                </button>
              </div>

              {showRules && (
                <div className="mt-4 rounded-2xl border border-luxe-line bg-[#f5ecde] px-4 py-3">
                  <div className="space-y-2 text-[13px] text-[#5f4935]">
                    <p><span className="font-semibold">Company Fit</span> — Grounded research classification: company type, property management relevance, multifamily relevance, scale signal, email domain signal, and confidence adjustment. Max 52.</p>
                    <p><span className="font-semibold">News Activity</span> — Recent company news marked as relevant and growth signals. Max 18.</p>
                    <p><span className="font-semibold">Contact Quality</span> — Whether the contact uses a corporate email domain instead of a free inbox. Max 12.</p>
                    <p><span className="font-semibold">Market</span> — Local operating context: renter-occupied percentage &gt; 40%, local population &gt; 4k, median rent &gt; $1,500. Max 18.</p>
                  </div>
                </div>
              )}

              <div className="mt-5 overflow-hidden rounded-2xl bg-luxe-soft">
                <div className="flex h-12 w-full">
                  {details.segments.map((segment) => (
                    <div
                      key={segment.label}
                      className={`${segment.color} flex items-center justify-center text-[12px] font-semibold text-white`}
                      style={{ width: `${segment.width}%` }}
                      title={`${segment.label}: ${segment.points} points`}
                    >
                      {segment.points > 0 ? segment.points : ''}
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                {details.segments.map((segment) => (
                  <div key={segment.label} className="rounded-2xl border border-[#dfcfb7] bg-luxe-soft px-4 py-3 shadow-[0_8px_18px_rgba(98,73,46,0.05)]">
                    <p className="text-[12px] uppercase tracking-wide text-luxe-muted">{segment.label}</p>
                    <p className="mt-1 text-[22px] font-semibold text-luxe-ink">{segment.points}<span className="text-[14px] font-medium text-luxe-muted"> pts</span></p>
                    <p className="mt-1 text-[12px] text-luxe-muted">out of {segment.maxPoints}</p>
                  </div>
                ))}
              </div>

              {showRules && (
                <div className="mt-5 grid gap-4 lg:grid-cols-2">
                  <RuleList title="Company Fit Hard" bucket={data.score_breakdown.company_fit_hard} maxPoints={52} />
                  <RuleList title="Activity" bucket={data.score_breakdown.company_fit_activity} maxPoints={18} />
                  <RuleList title="Contact Quality" bucket={data.score_breakdown.contact_quality} maxPoints={12} />
                  <RuleList title="Market" bucket={data.score_breakdown.market_context} maxPoints={18} />
                </div>
              )}
            </section>

            <section className="rounded-[30px] border border-luxe-line bg-luxe-panel/95 p-6 shadow-[0_16px_40px_rgba(90,67,48,0.08)]">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-luxe-muted">Resolved sources</p>
                  <h2 className="font-display text-[24px] font-semibold text-luxe-ink">Enrichment details</h2>
                  <p className="text-[13px] text-luxe-muted">Review resolved evidence, insights, and raw payloads.</p>
                </div>
                <div className="flex items-center gap-2">
                  {showConfidence(details.companyResearch?.confidence) && (
                    <ConfidencePill label="Low confidence company research" />
                  )}
                </div>
              </div>

              <div className="mt-5 max-w-full overflow-x-auto">
                <div className="inline-flex min-w-0 rounded-2xl border border-[#dfcfb7] bg-luxe-soft p-1 shadow-[inset_0_1px_0_rgba(255,255,255,0.55)]">
                  <TabButton
                    label="Company fit"
                    active={activeTab === 'company'}
                    onClick={() => setActiveTab('company')}
                  />
                  <TabButton
                    label="Relevant news"
                    active={activeTab === 'news'}
                    onClick={() => setActiveTab('news')}
                  />
                  <TabButton
                    label="Property context"
                    active={activeTab === 'market'}
                    onClick={() => setActiveTab('market')}
                  />
                  <TabButton
                    label="Raw enrichment"
                    active={activeTab === 'raw'}
                    onClick={() => setActiveTab('raw')}
                  />
                </div>
              </div>

              {activeTab === 'company' ? (
                <div className="mt-5 space-y-4 overflow-hidden">
                  {details.companyResearch?.confidence !== undefined && details.companyResearch.confidence >= 0.3 ? (
                    <>
                      <SourceCard
                        title="Company research"
                        subtitle={details.companyTitle}
                        link={details.companyWebsite}
                        body={details.companyBody}
                      />
                      <CompanyFitPanel
                        companyResearch={details.companyResearch}
                        showEvidenceClaims={showEvidenceClaims}
                        onToggleEvidence={() => setShowEvidenceClaims(!showEvidenceClaims)}
                      />
                    </>
                  ) : (
                    <div className="rounded-2xl border border-luxe-line bg-luxe-soft p-4 shadow-[0_8px_20px_rgba(90,67,48,0.06)]">
                      <p className="text-[14px] text-luxe-muted">Company research unavailable. Check raw enrichment for details.</p>
                    </div>
                  )}
                </div>
              ) : null}

              {activeTab === 'news' ? (
                <div className="mt-5 space-y-4 overflow-hidden">
                  <NewsPanel
                    title="Relevant news"
                    articles={details.relevantArticles}
                    relevance={details.relevantArticleFlags}
                    emptyMessage="No LLM-filtered relevant articles yet."
                  />
                </div>
              ) : null}

              {activeTab === 'market' ? (
                <div className="mt-5 space-y-4 overflow-hidden">
                  <MarketContextPanel
                    geoDemographics={details.geoDemographics}
                    marketData={details.marketData}
                  />
                </div>
              ) : null}

              {activeTab === 'raw' ? (
                <div className="mt-5 space-y-4 overflow-hidden">
                  <JsonPanel title="Company research" value={data.raw_enrichment.company_research} />
                  <NewsPanel
                    title="News articles"
                    articles={data.raw_enrichment.news_articles || []}
                    relevance={data.raw_enrichment.news_relevance || []}
                    emptyMessage="No articles returned."
                  />
                  <JsonPanel title="Geo demographics" value={data.raw_enrichment.geo_demographics || data.raw_enrichment.market_data} />
                  {data.raw_enrichment._errors?.length ? (
                    <JsonPanel title="Pipeline errors" value={data.raw_enrichment._errors} />
                  ) : null}
                </div>
              ) : null}
            </section>

            {showEmailModal && (
              <EmailModal
                emailSubject={data.email_subject}
                emailBody={effectiveEmailBody}
                onEmailBodyChange={setEmailBody}
                onCopy={handleCopy}
                mailtoHref={mailtoHref}
                onClose={() => setShowEmailModal(false)}
              />
            )}
        </div>
      </div>
    </div>
  )
}

function RuleList({ title, bucket, maxPoints }: { title: string; bucket: ScoreBucket; maxPoints: number }) {
  return (
    <div className="rounded-2xl border border-luxe-line bg-luxe-soft p-4 shadow-[0_8px_20px_rgba(90,67,48,0.06)]">
      <div className="flex items-center justify-between">
        <h3 className="text-[15px] font-semibold text-luxe-ink">{title}</h3>
        <span className="text-[13px] font-medium text-luxe-muted">
          {bucket.points} / {maxPoints} pts
        </span>
      </div>
      <div className="mt-3 space-y-2">
        {bucket.breakdown.map((item) => (
          <div key={item.rule} className="flex items-center justify-between rounded-xl border border-[#e4d6c1] bg-luxe-panel px-3 py-2">
            <div>
              <p className="text-[13px] font-medium text-luxe-ink">{formatRuleName(item.rule)}</p>
              <p className={`text-[12px] ${item.fired ? 'text-[#7a5a2f]' : 'text-luxe-muted'}`}>
                {item.fired ? '✓' : '✕'}
              </p>
            </div>
            <span className="text-[13px] font-semibold text-[#5f4935]">{formatRuleScore(item.rule, item.points)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function SourceCard({
  title,
  subtitle,
  body,
  link,
}: {
  title: string
  subtitle?: string
  body: string
  link?: string
}) {
  return (
    <div className="rounded-2xl border border-luxe-line bg-luxe-soft p-4 shadow-[0_8px_20px_rgba(90,67,48,0.06)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[12px] uppercase tracking-wide text-luxe-muted">{title}</p>
          {subtitle ? <p className="mt-1 text-[15px] font-semibold text-luxe-ink">{subtitle}</p> : null}
        </div>
        {link ? (
          <a href={link} target="_blank" rel="noreferrer" className="text-[13px] font-medium text-luxe-accent hover:text-[#6e4f2d]">
            Open
          </a>
        ) : null}
      </div>
      <p className="mt-3 text-[14px] leading-6 text-[#5f4935]">{body}</p>
    </div>
  )
}

function TabButton({
  label,
  active,
  onClick,
}: {
  label: string
  active: boolean
  onClick: () => void
}) {
  return (
    <button
      onClick={onClick}
      className={`rounded-xl border px-4 py-2.5 text-[13px] font-semibold tracking-[0.02em] transition-all ${
        active
          ? 'border-luxe-line bg-luxe-panel text-luxe-ink shadow-[0_6px_14px_rgba(90,67,48,0.10)]'
          : 'border-transparent text-luxe-muted hover:border-[#ddccb4] hover:bg-[#f7efe3] hover:text-luxe-ink'
      }`}
    >
      {label}
    </button>
  )
}

function CompanyFitPanel({
  companyResearch,
  showEvidenceClaims,
  onToggleEvidence,
}: {
  companyResearch?: CompanyResearch
  showEvidenceClaims?: boolean
  onToggleEvidence?: () => void
}) {
  if (!companyResearch) {
    return (
      <div className="rounded-2xl border border-luxe-line bg-luxe-soft p-4 shadow-[0_8px_20px_rgba(90,67,48,0.06)]">
        <p className="text-[14px] text-luxe-muted">No resolved company-fit evidence available.</p>
      </div>
    )
  }

  const metadata = [
    { label: 'Industry', value: companyResearch.industry },
    { label: 'Type', value: formatRuleName(companyResearch.company_type) },
    { label: 'Property Management Relevance', value: companyResearch.property_management_relevance },
    { label: 'Multifamily', value: companyResearch.multifamily_relevance },
    { label: 'Scale', value: companyResearch.scale_signal },
    { label: 'Email Domain', value: companyResearch.email_domain_type },
  ].filter((m) => m.value && m.value !== 'unknown')

  return (
    <div className="rounded-2xl border border-luxe-line bg-luxe-soft p-4 shadow-[0_8px_20px_rgba(90,67,48,0.06)]">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[12px] uppercase tracking-wide text-luxe-muted">Company fit</p>
          <p className="mt-1 text-[15px] font-semibold text-luxe-ink">
            {companyResearch.company_score}/52 • {formatRuleName(companyResearch.tier)}
          </p>
        </div>
        <div className="rounded-full bg-luxe-panel px-3 py-1 text-[12px] font-semibold text-[#5f4935]">
          {formatRuleName(companyResearch.company_type)}
        </div>
      </div>

      {metadata.length > 0 && (
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {metadata.map((m) => (
            <div key={m.label} className="rounded-xl border border-[#e4d6c1] bg-luxe-panel px-3 py-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-luxe-muted">{m.label}</p>
              <p className="mt-1 text-[13px] font-medium text-luxe-ink">{formatRuleName(m.value)}</p>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 space-y-3">
        {companyResearch.reasons.map((reason, index) => (
          <div key={`${reason}-${index}`} className="rounded-xl border border-[#e4d6c1] bg-luxe-panel px-4 py-3">
            <p className="text-[13px] font-medium text-luxe-ink">{reason}</p>
            {companyResearch.evidence[index] ? (
              <SourceLinkRow evidence={companyResearch.evidence[index]} />
            ) : null}
          </div>
        ))}
      </div>

      {companyResearch.evidence.length ? (
        <div className="mt-4 space-y-3">
          <button
            onClick={onToggleEvidence}
            className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wide text-luxe-accent hover:text-[#6e4f2d]"
          >
            <span>{showEvidenceClaims ? '▼' : '▶'}</span>
            Evidence claims ({companyResearch.evidence.length})
          </button>
          {showEvidenceClaims && (
            <div className="space-y-3">
              {companyResearch.evidence.map((item, index) => (
                <div key={`${item.claim}-${index}`} className="rounded-xl border border-[#e4d6c1] bg-luxe-panel px-4 py-3">
                  <p className="text-[13px] text-[#4f3b28]">{item.claim}</p>
                  <SourceLinkRow evidence={item} />
                </div>
              ))}
            </div>
          )}
        </div>
      ) : null}
    </div>
  )
}

function SourceLinkRow({ evidence }: { evidence: CompanyResearch['evidence'][number] }) {
  return (
    <div className="mt-2 flex items-center justify-between gap-3">
      <p className="text-[12px] text-luxe-muted">Source: {formatSourceType(evidence.source_type)}</p>
      {evidence.url ? (
        <a href={evidence.url} target="_blank" rel="noreferrer" className="text-[12px] font-medium text-luxe-accent hover:text-[#6e4f2d]">
          View source
        </a>
      ) : null}
    </div>
  )
}

function JsonPanel({ title, value }: { title: string; value: unknown }) {
  return (
    <div className="rounded-2xl border border-luxe-line bg-luxe-soft/70 shadow-[0_8px_20px_rgba(90,67,48,0.06)]">
      <div className="border-b border-luxe-line px-4 py-3">
        <h3 className="text-[14px] font-semibold text-luxe-ink">{title}</h3>
      </div>
      <pre className="overflow-auto px-4 py-3 text-[12px] leading-5 text-[#5f4935]">
        {JSON.stringify(value ?? null, null, 2)}
      </pre>
    </div>
  )
}

function NewsPanel({
  title,
  articles,
  relevance,
  emptyMessage,
}: {
  title: string
  articles: NewsArticle[]
  relevance: boolean[]
  emptyMessage: string
}) {
  return (
    <div className="rounded-2xl border border-luxe-line bg-luxe-soft/70 shadow-[0_8px_20px_rgba(90,67,48,0.06)]">
      <div className="border-b border-luxe-line px-4 py-3">
        <h3 className="text-[14px] font-semibold text-luxe-ink">{title}</h3>
      </div>
      <div className="space-y-3 px-4 py-3">
        {!articles.length ? (
          <p className="text-[13px] text-luxe-muted">{emptyMessage}</p>
        ) : (
          articles.map((article, index) => (
            <div key={`${article.url || article.title || 'article'}-${index}`} className="rounded-2xl border border-[#e4d6c1] bg-luxe-panel px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[14px] font-semibold text-luxe-ink">{article.title || 'Untitled article'}</p>
                  <p className="mt-1 text-[12px] text-luxe-muted">
                    {article.source || 'Unknown source'}
                    {article.publishedAt ? ` • ${formatDate(article.publishedAt)}` : ''}
                    {relevance[index] ? ' • Relevant' : ''}
                  </p>
                </div>
                {article.url ? (
                  <a href={article.url} target="_blank" rel="noreferrer" className="text-[13px] font-medium text-luxe-accent hover:text-[#6e4f2d]">
                    Read
                  </a>
                ) : null}
              </div>
              {article.snippet ? <p className="mt-2 text-[13px] leading-6 text-[#5f4935]">{article.snippet}</p> : null}
            </div>
          ))
        )}
      </div>
    </div>
  )
}

function MarketContextPanel({
  geoDemographics,
  marketData,
}: {
  geoDemographics?: GeoDemographics | null
  marketData?: MarketData | null
}) {
  if (geoDemographics?.status === 'success') {
    const location = geoDemographics.location
    const demographics = geoDemographics.demographics
    const economics = geoDemographics.economics
    const housing = geoDemographics.housing
    const warnings = (geoDemographics.quality?.warnings || []).filter(
      (warning) => warning !== 'ACS API key rejected; retrying without key.',
    )

    return (
      <div className="space-y-4">
        <div className="rounded-2xl border border-luxe-line bg-luxe-soft p-4 shadow-[0_8px_20px_rgba(90,67,48,0.06)]">
          <p className="text-[12px] uppercase tracking-wide text-luxe-muted">Coverage area</p>
          <p className="mt-1 text-[15px] font-semibold text-luxe-ink">
            {location?.geo_name || location?.matched_address || 'Tract context'}
          </p>
          {location?.matched_address ? (
            <p className="mt-2 text-[13px] leading-6 text-[#5f4935]">{location.matched_address}</p>
          ) : null}
          <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Population" value={formatMetricNumber(demographics?.total_population)} />
            <MetricCard label="Median income" value={formatCurrency(economics?.median_household_income)} />
            <MetricCard label="Median rent" value={formatCurrency(housing?.median_gross_rent)} />
            <MetricCard label="Renter occupied" value={formatMetricPercent(housing?.renter_occupied_pct)} />
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-3">
          <MetricGroup
            title="Housing"
            items={[
              ['Median home value', formatCurrency(housing?.median_home_value)],
              ['Owner occupied', formatMetricPercent(housing?.owner_occupied_pct)],
              ['Renter occupied', formatMetricPercent(housing?.renter_occupied_pct)],
            ]}
          />
          <MetricGroup
            title="Economics"
            items={[
              ['Median income', formatCurrency(economics?.median_household_income)],
              ['Poverty rate', formatMetricPercent(economics?.poverty_rate_pct)],
              ['Unemployment', formatMetricPercent(economics?.unemployment_rate_pct)],
            ]}
          />
          <MetricGroup
            title="Demographics"
            items={[
              ['Bachelor’s or higher', formatMetricPercent(demographics?.education?.bachelors_or_higher_pct)],
              ['White alone', formatMetricPercent(demographics?.race_ethnicity?.white_alone_pct)],
              ['Hispanic or Latino', formatMetricPercent(demographics?.race_ethnicity?.hispanic_or_latino_pct)],
            ]}
          />
        </div>

        {warnings.length ? (
          <div className="rounded-2xl border border-[#dac29b] bg-[#f4e8d5] px-4 py-3 shadow-[0_8px_20px_rgba(90,67,48,0.05)]">
            <p className="text-[12px] font-semibold uppercase tracking-wide text-luxe-accent">Warnings</p>
            <div className="mt-2 space-y-1">
              {warnings.map((warning) => (
                <p key={warning} className="text-[13px] text-[#6f5434]">{warning}</p>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    )
  }

  if (geoDemographics?.status === 'skipped') {
    return <MessageCard title="Property context unavailable" body="Geo-demographic enrichment was skipped for a non-U.S. location." />
  }

  if (geoDemographics?.status === 'not_found') {
    return <MessageCard title="Property context unavailable" body="Census could not match the provided address to a tract." />
  }

  if (geoDemographics?.status === 'error') {
    return (
      <MessageCard
        title="Property context unavailable"
        body={geoDemographics.details || geoDemographics.reason || 'Geo-demographic enrichment failed.'}
      />
    )
  }

  if (marketData) {
    return (
      <div className="rounded-2xl border border-luxe-line bg-luxe-soft p-4 shadow-[0_8px_20px_rgba(90,67,48,0.06)]">
        <p className="text-[12px] uppercase tracking-wide text-luxe-muted">Local property context</p>
        <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
          <MetricCard label="Population" value={formatMetricNumber(marketData.population)} />
          <MetricCard label="Median rent" value={formatCurrency(marketData.median_rent)} />
          <MetricCard label="Renter occupied" value={formatMetricPercent(marketData.renter_percentage)} />
        </div>
      </div>
    )
  }

  return <MessageCard title="Property context unavailable" body="No geo-demographic context is available for this lead." />
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[#e4d6c1] bg-luxe-panel px-3 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-luxe-muted">{label}</p>
      <p className="mt-1 text-[15px] font-semibold text-luxe-ink">{value}</p>
    </div>
  )
}

function MetricGroup({ title, items }: { title: string; items: Array<[string, string]> }) {
  return (
    <div className="rounded-2xl border border-luxe-line bg-luxe-soft p-4 shadow-[0_8px_20px_rgba(90,67,48,0.06)]">
      <p className="text-[12px] uppercase tracking-wide text-luxe-muted">{title}</p>
      <div className="mt-3 space-y-2">
        {items.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between rounded-xl border border-[#e4d6c1] bg-luxe-panel px-3 py-2">
            <span className="text-[13px] text-[#5f4935]">{label}</span>
            <span className="text-[13px] font-semibold text-luxe-ink">{value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function MessageCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-2xl border border-luxe-line bg-luxe-soft p-4 shadow-[0_8px_20px_rgba(90,67,48,0.06)]">
      <p className="text-[12px] uppercase tracking-wide text-luxe-muted">{title}</p>
      <p className="mt-2 text-[14px] leading-6 text-[#5f4935]">{body}</p>
    </div>
  )
}

function ConfidencePill({ label }: { label: string }) {
  return (
    <span className="rounded-full border border-[#dbc49f] bg-[#f2e7d3] px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-[#8e6839]">
      {label}
    </span>
  )
}

function buildDetailState(data: EnrichmentResult | undefined) {
  if (!data) return null

  const companyFitPoints = data.score_breakdown.company_fit_hard.points
  const newsActivityPoints = data.score_breakdown.company_fit_activity.points
  const contactPoints = data.score_breakdown.contact_quality.points
  const marketPoints = data.score_breakdown.market_context.points
  const withWidth = (points: number) => {
    if (data.score_total <= 0) return 0
    return Math.max(0, Math.min(100, (points / data.score_total) * 100))
  }
  const segments: Segment[] = [
    { label: 'Company Fit', points: companyFitPoints, maxPoints: 52, width: withWidth(companyFitPoints), color: SEGMENT_COLORS.hard },
    { label: 'News Activity', points: newsActivityPoints, maxPoints: 18, width: withWidth(newsActivityPoints), color: SEGMENT_COLORS.activity },
    { label: 'Contact Quality', points: contactPoints, maxPoints: 12, width: withWidth(contactPoints), color: SEGMENT_COLORS.contact },
    { label: 'Market', points: marketPoints, maxPoints: 18, width: withWidth(marketPoints), color: SEGMENT_COLORS.market },
  ]

  const companyResearch = data.raw_enrichment.company_research
  const geoDemographics = data.raw_enrichment.geo_demographics
  const marketData = data.raw_enrichment.market_data
  const allArticles = data.raw_enrichment.news_articles || []
  const relevanceFlags = data.raw_enrichment.news_relevance || []
  const relevantPairs = allArticles
    .map((article, index) => ({ article, relevant: Boolean(relevanceFlags[index]) }))
    .filter((pair) => pair.relevant)

  return {
    segments,
    companyResearch,
    geoDemographics,
    marketData,
    relevantArticles: relevantPairs.map((pair) => pair.article),
    relevantArticleFlags: relevantPairs.map(() => true),
    companyTitle: data.lead_detail.company || companyResearch?.company_name_normalized || 'No company research',
    companyWebsite: companyResearch?.website || undefined,
    companyBody: buildCompanyBody(companyResearch),
  }
}

function formatRuleName(rule: string) {
  return rule
    .split('_')
    .map((part) => {
      if (part === 'pct') return '%'
      return part.charAt(0).toUpperCase() + part.slice(1)
    })
    .join(' ')
}

function formatRuleScore(rule: string, points: number) {
  if (rule === 'confidence_multiplier') {
    return points === 0 ? '0 adj' : `${points > 0 ? '+' : ''}${points} adj`
  }

  const maxPoints = maxPointsForRule(rule, points)
  if (maxPoints === null) {
    return `${points}`
  }
  return `${points} / ${maxPoints}`
}

function maxPointsForRule(rule: string, points: number): number | null {
  if (rule.startsWith('company_type_')) {
    return Math.abs(points)
  }

  const exactMatches: Record<string, number> = {
    property_management_relevance_high: 5,
    property_management_relevance_medium: 3,
    multifamily_relevance_high: 3,
    multifamily_relevance_medium: 2,
    scale_signal_large: 3,
    scale_signal_medium: 2,
    scale_signal_small: 1,
    email_domain_type_corporate: 12,
    email_domain_type_property_specific: 1,
    email_domain_type_generic: 5,
    recent_relevant_news: 8,
    growth_signal_news: 10,
    renter_pct_over_40: 6,
    local_population_over_4k: 6,
    median_rent_over_1500: 6,
  }

  return exactMatches[rule] ?? (points > 0 ? points : null)
}

function formatDate(value: string) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

function formatNumber(value: number) {
  return Intl.NumberFormat().format(value)
}

function formatPercent(value: number) {
  return `${value.toFixed(1)}%`
}

function formatCurrency(value: number | null | undefined) {
  if (typeof value !== 'number') return '—'
  return `$${Intl.NumberFormat().format(value)}`
}

function formatMetricNumber(value: number | null | undefined) {
  return typeof value === 'number' ? formatNumber(value) : '—'
}

function formatMetricPercent(value: number | null | undefined) {
  return typeof value === 'number' ? formatPercent(value) : '—'
}

function formatSourceType(value: CompanyResearch['evidence'][number]['source_type']) {
  return value
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}


function buildCompanyBody(companyResearch: CompanyResearch | undefined) {
  if (!companyResearch) return 'No grounded company research available.'
  return companyResearch.description || 'No grounded company research available.'
}

function buildMailto(to: string, subject: string, body: string) {
  const params = new URLSearchParams({
    subject,
    body,
  })
  return `mailto:${encodeURIComponent(to)}?${params.toString()}`
}

function showConfidence(confidence: number | undefined) {
  return confidence != null && confidence < 0.6
}

function EmailModal({
  emailSubject,
  emailBody,
  onEmailBodyChange,
  onCopy,
  mailtoHref,
  onClose,
}: {
  emailSubject: string
  emailBody: string
  onEmailBodyChange: (body: string) => void
  onCopy: () => void
  mailtoHref: string
  onClose: () => void
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-[#2d2115]/35 backdrop-blur-md">
      <div className="mx-4 w-full max-w-2xl rounded-[30px] border border-luxe-line bg-luxe-panel shadow-[0_28px_72px_rgba(72,49,26,0.20)]">
        <div className="border-b border-luxe-line px-6 py-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="font-display text-[24px] font-semibold text-luxe-ink">Draft email</h2>
              <p className="text-[13px] text-luxe-muted">Generated outreach tailored to this lead.</p>
            </div>
            <button
              onClick={onClose}
              className="text-[24px] leading-none text-luxe-muted hover:text-luxe-ink"
            >
              ✕
            </button>
          </div>
        </div>

        <div className="space-y-4 px-6 py-5">
          <div className="rounded-2xl bg-luxe-soft px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-luxe-muted">Subject</p>
            <p className="mt-1 text-[15px] font-medium text-luxe-ink">{emailSubject}</p>
          </div>
          <div>
            <label className="mb-2 block text-[11px] font-semibold uppercase tracking-wide text-luxe-muted">
              Body
            </label>
            <textarea
              value={emailBody}
              onChange={(event) => onEmailBodyChange(event.target.value)}
              rows={10}
              className="w-full rounded-2xl border border-luxe-line bg-luxe-soft px-4 py-3 text-[14px] text-luxe-ink outline-none focus:ring-2 focus:ring-luxe-accent/25"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 border-t border-luxe-line px-6 py-4">
          <button
            onClick={onClose}
            className="rounded-xl border border-luxe-line bg-luxe-soft px-4 py-2 text-[14px] font-medium text-luxe-ink hover:bg-luxe-accentSoft"
          >
            Close
          </button>
          <button
            onClick={onCopy}
            className="rounded-xl border border-luxe-line bg-luxe-soft px-4 py-2 text-[14px] font-medium text-luxe-ink hover:bg-luxe-accentSoft"
          >
            Copy to clipboard
          </button>
          <a
            href={mailtoHref}
            className="rounded-xl bg-luxe-accent px-4 py-2 text-[14px] font-medium text-[#fff9f0] hover:bg-[#77562e]"
          >
            Open in Gmail
          </a>
        </div>
      </div>
    </div>
  )
}
