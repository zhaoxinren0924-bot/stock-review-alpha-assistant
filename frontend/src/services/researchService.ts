import { fetchApi } from './api'

type JsonRecord = Record<string, unknown>

interface ListResponse<T> {
  items: T[]
  count: number
}

export interface Hypothesis {
  id: number
  category: string
  status: string
  content: JsonRecord
  confidence: number
  evidence: string | null
  nextReviewDate: string | null
  createdAt: string
  updatedAt: string
}

interface RawHypothesis {
  id: number
  category: string
  status: string
  content: JsonRecord
  confidence: number
  evidence: string | null
  next_review_date: string | null
  created_at: string
  updated_at: string
}

export interface HypothesisCreateInput {
  category: string
  status: string
  content: JsonRecord
  confidence?: number
  evidence?: string | null
  next_review_date?: string | null
}

export interface CheckItem {
  id: number
  stockCode: string
  content: string
  dueDate: string | null
  status: string
  linkedHypothesisId: number | null
  sourceType: string | null
  completedAt: string | null
  createdAt: string
}

interface RawCheckItem {
  id: number
  stock_code: string
  content: string
  due_date: string | null
  status: string
  linked_hypothesis_id: number | null
  source_type: string | null
  completed_at: string | null
  created_at: string
}

export interface CheckItemCreateInput {
  content: string
  due_date?: string | null
  status?: string
  linked_hypothesis_id?: number | null
  source_type?: string | null
}

export interface Review {
  id: number
  stockCode: string
  reviewType: string
  title: string | null
  content: string
  conclusions: string | null
  actionItems: string[]
  triggerEventId: number | null
  createdAt: string
}

interface RawReview {
  id: number
  stock_code: string
  review_type: string
  title: string | null
  content: string
  conclusions: string | null
  action_items: string[]
  trigger_event_id: number | null
  created_at: string
}

export interface ReviewCreateInput {
  review_type: string
  title?: string | null
  content: string
  conclusions?: string | null
  action_items?: string[]
  trigger_event_id?: number | null
}

function transformHypothesis(raw: RawHypothesis): Hypothesis {
  return {
    id: raw.id,
    category: raw.category,
    status: raw.status,
    content: raw.content,
    confidence: raw.confidence,
    evidence: raw.evidence,
    nextReviewDate: raw.next_review_date,
    createdAt: raw.created_at,
    updatedAt: raw.updated_at,
  }
}

function transformCheckItem(raw: RawCheckItem): CheckItem {
  return {
    id: raw.id,
    stockCode: raw.stock_code,
    content: raw.content,
    dueDate: raw.due_date,
    status: raw.status,
    linkedHypothesisId: raw.linked_hypothesis_id,
    sourceType: raw.source_type,
    completedAt: raw.completed_at,
    createdAt: raw.created_at,
  }
}

function transformReview(raw: RawReview): Review {
  return {
    id: raw.id,
    stockCode: raw.stock_code,
    reviewType: raw.review_type,
    title: raw.title,
    content: raw.content,
    conclusions: raw.conclusions,
    actionItems: raw.action_items,
    triggerEventId: raw.trigger_event_id,
    createdAt: raw.created_at,
  }
}

export async function listHypotheses(stockCode: string): Promise<Hypothesis[]> {
  const data = await fetchApi<ListResponse<RawHypothesis>>(`/api/v1/stocks/${stockCode}/hypotheses`)
  return data.items.map(transformHypothesis)
}

export async function createHypothesis(
  stockCode: string,
  input: HypothesisCreateInput,
): Promise<Hypothesis> {
  const data = await fetchApi<RawHypothesis>(`/api/v1/stocks/${stockCode}/hypotheses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  return transformHypothesis(data)
}

export async function listCheckItems(stockCode: string): Promise<CheckItem[]> {
  const data = await fetchApi<ListResponse<RawCheckItem>>(`/api/v1/stocks/${stockCode}/check-items`)
  return data.items.map(transformCheckItem)
}

export async function createCheckItem(
  stockCode: string,
  input: CheckItemCreateInput,
): Promise<CheckItem> {
  const data = await fetchApi<RawCheckItem>(`/api/v1/stocks/${stockCode}/check-items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  return transformCheckItem(data)
}

export async function listReviews(stockCode: string): Promise<Review[]> {
  const data = await fetchApi<ListResponse<RawReview>>(`/api/v1/stocks/${stockCode}/reviews`)
  return data.items.map(transformReview)
}

export async function createReview(stockCode: string, input: ReviewCreateInput): Promise<Review> {
  const data = await fetchApi<RawReview>(`/api/v1/stocks/${stockCode}/reviews`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  return transformReview(data)
}
