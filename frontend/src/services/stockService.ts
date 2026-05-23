import { fetchApi } from './api'

export interface Stock {
  code: string
  name: string
  industry: string | null
  market: string | null
  createdAt: string
}

interface RawStock {
  code: string
  name: string
  industry: string | null
  market: string | null
  created_at: string
}

interface StockListResponse {
  items: RawStock[]
  count: number
}

export interface StockCreateInput {
  code: string
  name: string
  industry?: string | null
  market?: string | null
}

function transformStock(raw: RawStock): Stock {
  return {
    code: raw.code,
    name: raw.name,
    industry: raw.industry,
    market: raw.market,
    createdAt: raw.created_at,
  }
}

export async function listStocks(): Promise<Stock[]> {
  const data = await fetchApi<StockListResponse>('/api/v1/stocks')
  return data.items.map(transformStock)
}

export async function createStock(input: StockCreateInput): Promise<Stock> {
  const data = await fetchApi<RawStock>('/api/v1/stocks', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(input),
  })
  return transformStock(data)
}

export async function deleteStock(code: string): Promise<void> {
  await fetchApi<void>(`/api/v1/stocks/${code}`, { method: 'DELETE' })
}
