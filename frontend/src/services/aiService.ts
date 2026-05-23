import { fetchApi } from './api'

export interface AiAction {
  type: string
  payload: Record<string, unknown>
}

export interface AiChatResponse {
  reply: string
  actions: AiAction[]
  evidenceCards: EvidenceCard[]
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

interface RawAiChatResponse {
  reply: string
  actions: AiAction[]
  evidence_cards?: RawEvidenceCard[]
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

export async function chatWithAi(stockCode: string, message: string): Promise<AiChatResponse> {
  const data = await fetchApi<RawAiChatResponse>('/api/v1/ai/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      stock_code: stockCode,
      message,
      history: [],
    }),
  }, 90000)
  return {
    reply: data.reply,
    actions: data.actions,
    evidenceCards: (data.evidence_cards ?? []).map(transformEvidenceCard),
  }
}

export async function applyAiAction(action: AiAction): Promise<void> {
  await fetchApi('/api/v1/ai/actions/apply', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(action),
  })
}
