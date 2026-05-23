import { fetchApi } from './api'

interface ListResponse<T> {
  items: T[]
  count: number
}

export interface EvidenceCard {
  sourceLevel: string
  sourceType: string
  sourceProvider: string
  sourceUrl: string | null
  title: string
  summary: string
  publishedAt: string | null
  fetchedAt: string | null
  confidence: number
  evidenceBoundary: string
}

interface RawEvidenceCard {
  source_level: string
  source_type: string
  source_provider: string
  source_url: string | null
  title: string
  summary: string
  published_at: string | null
  fetched_at: string | null
  confidence: number
  evidence_boundary: string
}

export interface MarketEvent {
  id: number
  stockCode: string
  title: string
  summary: string | null
  sourceProvider: string | null
  sourceUrl: string | null
  sourceType: string
  eventType: string | null
  confidence: number | null
  publishedAt: string
  fetchedAt: string
}

interface RawMarketEvent {
  id: number
  stock_code: string
  title: string
  summary: string | null
  source_provider: string | null
  source_url: string | null
  source_type: string
  event_type: string | null
  confidence: number | null
  published_at: string
  fetched_at: string
}

export interface FundamentalMetric {
  id: number
  stockCode: string
  metricCode: string
  metricName: string
  metricCategory: string | null
  value: number | null
  unit: string | null
  period: string | null
  reportDate: string | null
  sourceProvider: string | null
  createdAt: string
}

interface RawFundamentalMetric {
  id: number
  stock_code: string
  metric_code: string
  metric_name: string
  metric_category: string | null
  value: number | null
  unit: string | null
  period: string | null
  report_date: string | null
  source_provider: string | null
  created_at: string
}

export interface QuoteSnapshot {
  id: number
  stockCode: string
  date: string
  close: number | null
  pe: number | null
  pb: number | null
  marketCap: number | null
  createdAt: string
}

interface RawQuoteSnapshot {
  id: number
  stock_code: string
  date: string
  close: number | null
  pe: number | null
  pb: number | null
  market_cap: number | null
  created_at: string
}

export interface DataRefreshResponse {
  stockCode: string
  created: Record<string, number>
  skipped: Record<string, number>
  errors: Array<{ provider: string; type: string; message: string }>
  refreshedAt: string
}

interface RawDataRefreshResponse {
  stock_code: string
  created: Record<string, number>
  skipped: Record<string, number>
  errors: Array<{ provider: string; type: string; message: string }>
  refreshed_at: string
}

export async function refreshStockData(stockCode: string): Promise<DataRefreshResponse> {
  const data = await fetchApi<RawDataRefreshResponse>(`/api/v1/stocks/${stockCode}/data/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      types: ['announcement', 'news', 'quote', 'metric'],
      lookback_days: 30,
    }),
  })
  return {
    stockCode: data.stock_code,
    created: data.created,
    skipped: data.skipped,
    errors: data.errors,
    refreshedAt: data.refreshed_at,
  }
}

export async function listEvidence(stockCode: string): Promise<EvidenceCard[]> {
  const data = await fetchApi<ListResponse<RawEvidenceCard>>(`/api/v1/stocks/${stockCode}/evidence`)
  return data.items.map(transformEvidenceCard)
}

export async function listEvents(stockCode: string): Promise<MarketEvent[]> {
  const data = await fetchApi<ListResponse<RawMarketEvent>>(`/api/v1/stocks/${stockCode}/events`)
  return data.items.map(transformEvent)
}

export async function listMetrics(stockCode: string): Promise<FundamentalMetric[]> {
  const data = await fetchApi<ListResponse<RawFundamentalMetric>>(`/api/v1/stocks/${stockCode}/metrics`)
  return data.items.map(transformMetric)
}

export async function listQuotes(stockCode: string): Promise<QuoteSnapshot[]> {
  const data = await fetchApi<ListResponse<RawQuoteSnapshot>>(`/api/v1/stocks/${stockCode}/quotes`)
  return data.items.map(transformQuote)
}

function transformEvidenceCard(raw: RawEvidenceCard): EvidenceCard {
  return {
    sourceLevel: raw.source_level,
    sourceType: raw.source_type,
    sourceProvider: raw.source_provider,
    sourceUrl: raw.source_url,
    title: raw.title,
    summary: raw.summary,
    publishedAt: raw.published_at,
    fetchedAt: raw.fetched_at,
    confidence: raw.confidence,
    evidenceBoundary: raw.evidence_boundary,
  }
}

function transformEvent(raw: RawMarketEvent): MarketEvent {
  return {
    id: raw.id,
    stockCode: raw.stock_code,
    title: raw.title,
    summary: raw.summary,
    sourceProvider: raw.source_provider,
    sourceUrl: raw.source_url,
    sourceType: raw.source_type,
    eventType: raw.event_type,
    confidence: raw.confidence,
    publishedAt: raw.published_at,
    fetchedAt: raw.fetched_at,
  }
}

function transformMetric(raw: RawFundamentalMetric): FundamentalMetric {
  return {
    id: raw.id,
    stockCode: raw.stock_code,
    metricCode: raw.metric_code,
    metricName: raw.metric_name,
    metricCategory: raw.metric_category,
    value: raw.value,
    unit: raw.unit,
    period: raw.period,
    reportDate: raw.report_date,
    sourceProvider: raw.source_provider,
    createdAt: raw.created_at,
  }
}

function transformQuote(raw: RawQuoteSnapshot): QuoteSnapshot {
  return {
    id: raw.id,
    stockCode: raw.stock_code,
    date: raw.date,
    close: raw.close,
    pe: raw.pe,
    pb: raw.pb,
    marketCap: raw.market_cap,
    createdAt: raw.created_at,
  }
}
