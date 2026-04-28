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
  A: 'bg-green-100 text-green-700 border-green-200',
  B: 'bg-blue-100 text-blue-700 border-blue-200',
  C: 'bg-amber-100 text-amber-700 border-amber-200',
  D: 'bg-gray-200 text-gray-700 border-gray-300',
} as const

const SEGMENT_COLORS = {
  hard: 'bg-indigo-500',
  activity: 'bg-pink-500',
  contact: 'bg-sky-500',
  market: 'bg-amber-400',
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
      <div className="flex-1 flex items-center justify-center text-[14px] text-apple-gray">
        Loading enrichment…
      </div>
    )
  }

  const mailtoHref = buildMailto(data.lead_detail.email, data.email_subject, effectiveEmailBody)

  return (
    <div className="flex-1 overflow-auto px-6 py-6">
      <div className="mx-auto flex w-full max-w-6xl flex-col gap-5">
        <div className="flex items-start justify-between gap-4 rounded-3xl bg-white p-6 shadow-sm border border-apple-separator">
          <div className="space-y-3">
            <button
              onClick={onBack}
              className="inline-flex items-center gap-2 text-[13px] font-medium text-apple-blue hover:text-blue-700"
            >
              <span aria-hidden="true">←</span>
              Back to leads
            </button>
            <div className="flex flex-wrap items-center gap-3">
              <h1 className="text-[28px] font-bold tracking-tight text-gray-900">{data.lead_detail.name}</h1>
              <span className={`rounded-full border px-3 py-1 text-[12px] font-semibold ${TIER_CLASSES[data.score_tier]}`}>
                Tier {data.score_tier}
              </span>
            </div>
            <div className="space-y-1">
              <p className="text-[16px] text-gray-700">{data.lead_detail.company || 'Unknown company'}</p>
              <p className="text-[13px] text-apple-gray">
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
              className="rounded-xl bg-apple-lightgray px-4 py-2 text-[14px] font-medium text-gray-700 transition-colors hover:bg-gray-200"
            >
              Draft email
            </button>
            <div className="rounded-3xl bg-apple-lightgray px-6 py-4 text-center">
              <p className="text-[11px] uppercase tracking-[0.18em] text-apple-gray">Score</p>
              <p className="text-[40px] font-bold leading-none text-gray-900">{data.score_total}<span className="text-[18px] text-apple-gray"> / 100</span></p>
              <p className="mt-1 text-[12px] text-apple-gray">{isFetching ? 'Refreshing…' : 'Deterministic score'}</p>
            </div>
          </div>
        </div>

        <div className="space-y-5">
            <section className="rounded-3xl border border-apple-separator bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-[19px] font-semibold text-gray-900">Insights</h2>
                  <p className="text-[13px] text-apple-gray">Quick operator-facing facts and fit signals.</p>
                </div>
              </div>
              <ul className="mt-5 space-y-3">
                {data.insights.map((insight) => (
                  <li key={insight} className="flex gap-3 text-[14px] text-gray-700">
                    <span className="mt-1 h-2 w-2 shrink-0 rounded-full bg-apple-blue" />
                    <span>{insight}</span>
                  </li>
                ))}
              </ul>
            </section>

            <section className="rounded-3xl border border-apple-separator bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-[19px] font-semibold text-gray-900">Score breakdown</h2>
                  <p className="text-[13px] text-apple-gray">Actual bucket points in the 100-point score.</p>
                </div>
                <button
                  onClick={() => setShowRules((value) => !value)}
                  className="text-[13px] font-medium text-apple-blue hover:text-blue-700"
                >
                  {showRules ? 'Hide breakdown' : 'See breakdown'}
                </button>
              </div>

              {showRules && (
                <div className="mt-4 rounded-2xl bg-amber-50 border border-amber-200 px-4 py-3">
                  <div className="space-y-2 text-[13px] text-gray-700">
                    <p><span className="font-semibold">Company Fit</span> — Grounded research classification: company type, property management relevance, multifamily relevance, scale signal, email domain signal, and confidence adjustment. Max 52.</p>
                    <p><span className="font-semibold">News Activity</span> — Recent company news marked as relevant and growth signals. Max 18.</p>
                    <p><span className="font-semibold">Contact Quality</span> — Whether the contact uses a corporate email domain instead of a free inbox. Max 12.</p>
                    <p><span className="font-semibold">Market</span> — Local operating context: renter-occupied percentage &gt; 40%, local population &gt; 4k, median rent &gt; $1,500. Max 18.</p>
                  </div>
                </div>
              )}

              <div className="mt-5 overflow-hidden rounded-2xl bg-apple-lightgray">
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
                  <div key={segment.label} className="rounded-2xl bg-apple-lightgray px-4 py-3">
                    <p className="text-[12px] uppercase tracking-wide text-apple-gray">{segment.label}</p>
                    <p className="mt-1 text-[22px] font-semibold text-gray-900">{segment.points}<span className="text-[14px] font-medium text-apple-gray"> pts</span></p>
                    <p className="mt-1 text-[12px] text-apple-gray">out of {segment.maxPoints}</p>
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

            <section className="rounded-3xl border border-apple-separator bg-white p-6 shadow-sm">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-[19px] font-semibold text-gray-900">Enrichment details</h2>
                  <p className="text-[13px] text-apple-gray">Review resolved evidence, insights, and raw payloads.</p>
                </div>
                <div className="flex items-center gap-2">
                  {showConfidence(details.companyResearch?.confidence) && (
                    <ConfidencePill label="Low confidence company research" />
                  )}
                </div>
              </div>

              <div className="mt-5 max-w-full overflow-x-auto">
                <div className="inline-flex min-w-0 rounded-2xl bg-apple-lightgray p-1">
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
                    <div className="rounded-2xl bg-apple-lightgray p-4">
                      <p className="text-[14px] text-apple-gray">Company research unavailable. Check raw enrichment for details.</p>
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
    <div className="rounded-2xl bg-apple-lightgray p-4">
      <div className="flex items-center justify-between">
        <h3 className="text-[15px] font-semibold text-gray-900">{title}</h3>
        <span className="text-[13px] font-medium text-apple-gray">
          {bucket.points} / {maxPoints} pts
        </span>
      </div>
      <div className="mt-3 space-y-2">
        {bucket.breakdown.map((item) => (
          <div key={item.rule} className="flex items-center justify-between rounded-xl bg-white px-3 py-2">
            <div>
              <p className="text-[13px] font-medium text-gray-900">{formatRuleName(item.rule)}</p>
              <p className={`text-[12px] ${item.fired ? 'text-green-600' : 'text-apple-gray'}`}>
                {item.fired ? '✓' : '✕'}
              </p>
            </div>
            <span className="text-[13px] font-semibold text-gray-700">{formatRuleScore(item.rule, item.points)}</span>
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
    <div className="rounded-2xl bg-apple-lightgray p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[12px] uppercase tracking-wide text-apple-gray">{title}</p>
          {subtitle ? <p className="mt-1 text-[15px] font-semibold text-gray-900">{subtitle}</p> : null}
        </div>
        {link ? (
          <a href={link} target="_blank" rel="noreferrer" className="text-[13px] font-medium text-apple-blue hover:text-blue-700">
            Open
          </a>
        ) : null}
      </div>
      <p className="mt-3 text-[14px] leading-6 text-gray-700">{body}</p>
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
      className={`rounded-xl px-3 py-2 text-[13px] font-medium transition-colors ${
        active ? 'bg-white text-gray-900 shadow-sm' : 'text-apple-gray hover:text-gray-900'
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
      <div className="rounded-2xl bg-apple-lightgray p-4">
        <p className="text-[14px] text-apple-gray">No resolved company-fit evidence available.</p>
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
    <div className="rounded-2xl bg-apple-lightgray p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[12px] uppercase tracking-wide text-apple-gray">Company fit</p>
          <p className="mt-1 text-[15px] font-semibold text-gray-900">
            {companyResearch.company_score}/52 • {formatRuleName(companyResearch.tier)}
          </p>
        </div>
        <div className="rounded-full bg-white px-3 py-1 text-[12px] font-semibold text-gray-700">
          {formatRuleName(companyResearch.company_type)}
        </div>
      </div>

      {metadata.length > 0 && (
        <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {metadata.map((m) => (
            <div key={m.label} className="rounded-xl bg-white px-3 py-2">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-apple-gray">{m.label}</p>
              <p className="mt-1 text-[13px] font-medium text-gray-900">{formatRuleName(m.value)}</p>
            </div>
          ))}
        </div>
      )}

      <div className="mt-4 space-y-3">
        {companyResearch.reasons.map((reason, index) => (
          <div key={`${reason}-${index}`} className="rounded-xl bg-white px-4 py-3">
            <p className="text-[13px] font-medium text-gray-900">{reason}</p>
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
            className="flex items-center gap-2 text-[12px] font-semibold uppercase tracking-wide text-apple-blue hover:text-blue-700"
          >
            <span>{showEvidenceClaims ? '▼' : '▶'}</span>
            Evidence claims ({companyResearch.evidence.length})
          </button>
          {showEvidenceClaims && (
            <div className="space-y-3">
              {companyResearch.evidence.map((item, index) => (
                <div key={`${item.claim}-${index}`} className="rounded-xl bg-white px-4 py-3">
                  <p className="text-[13px] text-gray-800">{item.claim}</p>
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
      <p className="text-[12px] text-apple-gray">Source: {formatSourceType(evidence.source_type)}</p>
      {evidence.url ? (
        <a href={evidence.url} target="_blank" rel="noreferrer" className="text-[12px] font-medium text-apple-blue hover:text-blue-700">
          View source
        </a>
      ) : null}
    </div>
  )
}

function JsonPanel({ title, value }: { title: string; value: unknown }) {
  return (
    <div className="rounded-2xl border border-apple-separator bg-apple-lightgray/60">
      <div className="border-b border-apple-separator px-4 py-3">
        <h3 className="text-[14px] font-semibold text-gray-900">{title}</h3>
      </div>
      <pre className="overflow-auto px-4 py-3 text-[12px] leading-5 text-gray-700">
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
    <div className="rounded-2xl border border-apple-separator bg-apple-lightgray/60">
      <div className="border-b border-apple-separator px-4 py-3">
        <h3 className="text-[14px] font-semibold text-gray-900">{title}</h3>
      </div>
      <div className="space-y-3 px-4 py-3">
        {!articles.length ? (
          <p className="text-[13px] text-apple-gray">{emptyMessage}</p>
        ) : (
          articles.map((article, index) => (
            <div key={`${article.url || article.title || 'article'}-${index}`} className="rounded-2xl bg-white px-4 py-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-[14px] font-semibold text-gray-900">{article.title || 'Untitled article'}</p>
                  <p className="mt-1 text-[12px] text-apple-gray">
                    {article.source || 'Unknown source'}
                    {article.publishedAt ? ` • ${formatDate(article.publishedAt)}` : ''}
                    {relevance[index] ? ' • Relevant' : ''}
                  </p>
                </div>
                {article.url ? (
                  <a href={article.url} target="_blank" rel="noreferrer" className="text-[13px] font-medium text-apple-blue hover:text-blue-700">
                    Read
                  </a>
                ) : null}
              </div>
              {article.snippet ? <p className="mt-2 text-[13px] leading-6 text-gray-700">{article.snippet}</p> : null}
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
        <div className="rounded-2xl bg-apple-lightgray p-4">
          <p className="text-[12px] uppercase tracking-wide text-apple-gray">Coverage area</p>
          <p className="mt-1 text-[15px] font-semibold text-gray-900">
            {location?.geo_name || location?.matched_address || 'Tract context'}
          </p>
          {location?.matched_address ? (
            <p className="mt-2 text-[13px] leading-6 text-gray-700">{location.matched_address}</p>
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
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
            <p className="text-[12px] font-semibold uppercase tracking-wide text-amber-700">Warnings</p>
            <div className="mt-2 space-y-1">
              {warnings.map((warning) => (
                <p key={warning} className="text-[13px] text-amber-700">{warning}</p>
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
      <div className="rounded-2xl bg-apple-lightgray p-4">
        <p className="text-[12px] uppercase tracking-wide text-apple-gray">Local property context</p>
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
    <div className="rounded-xl bg-white px-3 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-apple-gray">{label}</p>
      <p className="mt-1 text-[15px] font-semibold text-gray-900">{value}</p>
    </div>
  )
}

function MetricGroup({ title, items }: { title: string; items: Array<[string, string]> }) {
  return (
    <div className="rounded-2xl bg-apple-lightgray p-4">
      <p className="text-[12px] uppercase tracking-wide text-apple-gray">{title}</p>
      <div className="mt-3 space-y-2">
        {items.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between rounded-xl bg-white px-3 py-2">
            <span className="text-[13px] text-gray-700">{label}</span>
            <span className="text-[13px] font-semibold text-gray-900">{value}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function MessageCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-2xl bg-apple-lightgray p-4">
      <p className="text-[12px] uppercase tracking-wide text-apple-gray">{title}</p>
      <p className="mt-2 text-[14px] leading-6 text-gray-700">{body}</p>
    </div>
  )
}

function ConfidencePill({ label }: { label: string }) {
  return (
    <span className="rounded-full bg-amber-100 px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide text-amber-700">
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 backdrop-blur-sm">
      <div className="mx-4 w-full max-w-2xl rounded-3xl bg-white shadow-lg">
        <div className="border-b border-apple-separator px-6 py-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h2 className="text-[19px] font-semibold text-gray-900">Draft email</h2>
              <p className="text-[13px] text-apple-gray">Generated outreach tailored to this lead.</p>
            </div>
            <button
              onClick={onClose}
              className="text-[24px] leading-none text-apple-gray hover:text-gray-900"
            >
              ✕
            </button>
          </div>
        </div>

        <div className="space-y-4 px-6 py-5">
          <div className="rounded-2xl bg-apple-lightgray px-4 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-apple-gray">Subject</p>
            <p className="mt-1 text-[15px] font-medium text-gray-900">{emailSubject}</p>
          </div>
          <div>
            <label className="mb-2 block text-[11px] font-semibold uppercase tracking-wide text-apple-gray">
              Body
            </label>
            <textarea
              value={emailBody}
              onChange={(event) => onEmailBodyChange(event.target.value)}
              rows={10}
              className="w-full rounded-2xl border border-apple-separator bg-apple-lightgray px-4 py-3 text-[14px] text-gray-900 outline-none focus:ring-2 focus:ring-apple-blue"
            />
          </div>
        </div>

        <div className="border-t border-apple-separator px-6 py-4 flex gap-2 justify-end">
          <button
            onClick={onClose}
            className="rounded-xl bg-apple-lightgray px-4 py-2 text-[14px] font-medium text-gray-700 hover:bg-gray-200"
          >
            Close
          </button>
          <button
            onClick={onCopy}
            className="rounded-xl bg-apple-lightgray px-4 py-2 text-[14px] font-medium text-gray-700 hover:bg-gray-200"
          >
            Copy to clipboard
          </button>
          <a
            href={mailtoHref}
            className="rounded-xl bg-apple-blue px-4 py-2 text-[14px] font-medium text-white hover:bg-blue-600"
          >
            Open in Gmail
          </a>
        </div>
      </div>
    </div>
  )
}
