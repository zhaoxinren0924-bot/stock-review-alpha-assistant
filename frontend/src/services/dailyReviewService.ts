import { fetchApi } from './api'
import type { AiAction } from './aiService'
import type { EvidenceCard } from './dataService'

type JsonRecord = Record<string, unknown>

interface ListResponse<T> {
  items: T[]
  count: number
}

export interface DailyReview {
  id: number
  reviewDate: string
  status: string
  marketStyle: string | null
  mainSector: string | null
  sentiment: string | null
  content: JsonRecord
  createdAt: string
  updatedAt: string
}

interface RawDailyReview {
  id: number
  review_date: string
  status: string
  market_style: string | null
  main_sector: string | null
  sentiment: string | null
  content: JsonRecord
  created_at: string
  updated_at: string
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

interface DailyReviewPrefillRaw {
  review: RawDailyReview
  filled: Record<string, number>
  missing: string[]
  evidence_cards: RawEvidenceCard[]
}

export interface DailyReviewPrefillResponse {
  review: DailyReview
  filled: Record<string, number>
  missing: string[]
  evidenceCards: EvidenceCard[]
}

interface DailyReviewCoachRaw {
  reply: string
  actions: AiAction[]
  evidence_cards: RawEvidenceCard[]
}

export interface DailyReviewCoachResponse {
  reply: string
  actions: AiAction[]
  evidenceCards: EvidenceCard[]
}

export interface DailyReviewUpdateInput {
  status?: string
  market_style?: string | null
  main_sector?: string | null
  sentiment?: string | null
  content?: JsonRecord
}

function transformDailyReview(raw: RawDailyReview): DailyReview {
  return {
    id: raw.id,
    reviewDate: raw.review_date,
    status: raw.status,
    marketStyle: raw.market_style,
    mainSector: raw.main_sector,
    sentiment: raw.sentiment,
    content: raw.content,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  }
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

export async function listDailyReviews(): Promise<DailyReview[]> {
  const data = await fetchApi<ListResponse<RawDailyReview>>('/api/v1/daily-reviews')
  return data.items.map(transformDailyReview)
}

export async function initializeDailyReview(reviewDate: string): Promise<DailyReview> {
  const data = await fetchApi<RawDailyReview>(`/api/v1/daily-reviews/${reviewDate}/initialize`, {
    method: 'POST',
  })
  return transformDailyReview(data)
}

export async function getDailyReview(reviewDate: string): Promise<DailyReview> {
  const data = await fetchApi<RawDailyReview>(`/api/v1/daily-reviews/${reviewDate}`)
  return transformDailyReview(data)
}

export async function updateDailyReview(id: number, input: DailyReviewUpdateInput): Promise<DailyReview> {
  const data = await fetchApi<RawDailyReview>(`/api/v1/daily-reviews/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  return transformDailyReview(data)
}

export async function prefillDailyReview(id: number): Promise<DailyReviewPrefillResponse> {
  const data = await fetchApi<DailyReviewPrefillRaw>(`/api/v1/daily-reviews/${id}/prefill`, {
    method: 'POST',
  })
  return {
    review: transformDailyReview(data.review),
    filled: data.filled,
    missing: data.missing,
    evidenceCards: data.evidence_cards.map(transformEvidenceCard),
  }
}

export async function coachDailyReview(
  id: number,
  sectionKey: string,
  message: string,
): Promise<DailyReviewCoachResponse> {
  const data = await fetchApi<DailyReviewCoachRaw>(`/api/v1/daily-reviews/${id}/ai/coach`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      section_key: sectionKey,
      message,
      history: [],
    }),
  })
  return {
    reply: data.reply,
    actions: data.actions,
    evidenceCards: data.evidence_cards.map(transformEvidenceCard),
  }
}

export async function applyDailyReviewAction(id: number, action: AiAction): Promise<DailyReview> {
  const data = await fetchApi<{ result: RawDailyReview }>(`/api/v1/daily-reviews/${id}/actions/apply`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(action),
  })
  return transformDailyReview(data.result)
}
