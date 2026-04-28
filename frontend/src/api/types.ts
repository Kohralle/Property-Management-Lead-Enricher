export interface Building {
  id: number
  property_address: string
  city: string
  state: string
  country: string
  created_at: string
  updated_at: string
}

export interface Person {
  id: number
  name: string
  email: string
  company: string
  building: number | null
  building_detail: Building | null
  has_enrichment: boolean
  latest_enrichment_id: number | null
  latest_enrichment_tier: 'A' | 'B' | 'C' | 'D' | null
  created_at: string
  updated_at: string
}

export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export interface RuleBreakdownItem {
  rule: string
  fired: boolean
  points: number
  confidence?: number
}

export interface ScoreBucket {
  points: number
  breakdown: RuleBreakdownItem[]
}

export interface ScoreBreakdown {
  company_fit_hard: ScoreBucket
  company_fit_activity: ScoreBucket
  contact_quality: ScoreBucket
  market_context: ScoreBucket
}

export interface NewsArticle {
  title?: string | null
  source?: string | null
  publishedAt?: string | null
  snippet?: string | null
  url?: string | null
  [key: string]: unknown
}

export interface MarketData {
  name?: string | null
  city?: string | null
  state_abbr?: string | null
  population?: number | null
  median_rent?: number | null
  renter_occupied_units?: number | null
  total_housing_units?: number | null
  renter_percentage?: number | null
  [key: string]: unknown
}

export interface GeoDemographics {
  status: 'success' | 'skipped' | 'not_found' | 'error'
  source?: string
  acs_year?: number
  location?: {
    input_address?: string | null
    matched_address?: string | null
    latitude?: number | null
    longitude?: number | null
    state_fips?: string | null
    county_fips?: string | null
    tract?: string | null
    block_group?: string | null
    geo_name?: string | null
    county_name?: string | null
    state_name?: string | null
  }
  demographics?: {
    total_population?: number | null
    race_ethnicity?: {
      white_alone_pct?: number | null
      black_alone_pct?: number | null
      asian_alone_pct?: number | null
      hispanic_or_latino_pct?: number | null
    }
    education?: {
      bachelors_or_higher_count?: number | null
      bachelors_or_higher_pct?: number | null
    }
  }
  economics?: {
    median_household_income?: number | null
    poverty_count?: number | null
    poverty_rate_pct?: number | null
    unemployment_rate_pct?: number | null
  }
  housing?: {
    median_home_value?: number | null
    median_gross_rent?: number | null
    owner_occupied_pct?: number | null
    renter_occupied_pct?: number | null
  }
  quality?: {
    geocode_confidence?: string | null
    warnings?: string[]
  }
  reason?: string
  details?: string | null
}

export interface WeatherData {
  description?: string | null
  temp_f?: number | null
  conditions_label?: string | null
  [key: string]: unknown
}

export interface EnrichmentScore {
  rule_total?: number
  total_score?: number
  score_tier?: 'A' | 'B' | 'C' | 'D'
  score_breakdown?: ScoreBreakdown
}

export interface CompanyResearchEvidence {
  claim: string
  url: string | null
  source_type: 'official_website' | 'linkedin' | 'property_listing' | 'news' | 'directory' | 'unknown'
}

export interface GroundingSource {
  url: string
  title: string | null
}

export interface CompanyResearch {
  company_score: number
  tier: 'strong' | 'medium' | 'weak' | 'poor'
  company_name_normalized: string
  website: string | null
  description: string
  industry: string
  company_type: 'large_property_manager' | 'small_property_manager' | 'owner_operator' | 'property_specific_entity' | 'broker' | 'vendor' | 'unrelated' | 'unknown'
  property_management_relevance: 'high' | 'medium' | 'low' | 'unknown'
  multifamily_relevance: 'high' | 'medium' | 'low' | 'unknown'
  scale_signal: 'large' | 'medium' | 'small' | 'unknown'
  email_domain_type: 'corporate' | 'generic' | 'property_specific' | 'unknown'
  confidence: number
  reasons: string[]
  evidence: CompanyResearchEvidence[]
  grounding_sources: GroundingSource[]
  recommended_next_step: 'prioritize' | 'enrich_further' | 'manual_review' | 'discard'
  score_components?: RuleBreakdownItem[]
}

export interface RawEnrichment {
  parsed_lead?: Record<string, unknown>
  company_research?: CompanyResearch
  news_articles?: NewsArticle[]
  weather?: WeatherData | null
  geo_demographics?: GeoDemographics | null
  market_data?: MarketData | null
  news_relevance?: boolean[]
  score?: EnrichmentScore
  generated_output?: {
    email_subject?: string
    email_body?: string
    insights?: string[]
  }
  _errors?: { step: string; error: string; message: string }[]
  [key: string]: unknown
}

export interface EnrichmentResult {
  id: number
  lead: number
  lead_detail: Person
  score_total: number
  score_tier: 'A' | 'B' | 'C' | 'D'
  score_breakdown: ScoreBreakdown
  email_subject: string
  email_body: string
  insights: string[]
  raw_enrichment: RawEnrichment
  created_at: string
  updated_at: string
}
