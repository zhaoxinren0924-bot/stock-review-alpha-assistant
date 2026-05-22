import { FormEvent, ReactNode, useEffect, useMemo, useState } from 'react'
import { BookOpen, Building2, CheckCircle2, Database, Plus, RefreshCw, RotateCcw, Trash2, X } from 'lucide-react'
import { applyAiAction, chatWithAi, type AiAction } from './services/aiService'
import {
  listEvents,
  listEvidence,
  listMetrics,
  listQuotes,
  refreshStockData,
  type DataRefreshResponse,
  type EvidenceCard,
  type FundamentalMetric,
  type MarketEvent,
  type QuoteSnapshot,
} from './services/dataService'
import {
  createCheckItem,
  createHypothesis,
  createReview,
  listCheckItems,
  listHypotheses,
  listReviews,
  type CheckItem,
  type Hypothesis,
  type Review,
} from './services/researchService'
import { createStock, deleteStock, listStocks, type Stock } from './services/stockService'

const MARKET_LABELS: Record<string, string> = {
  SH: '上海',
  SZ: '深圳',
  BJ: '北京',
}

const CATEGORY_LABELS: Record<string, string> = {
  business_quality: '生意质量',
  financial_quality: '财务质量',
  growth_logic: '成长逻辑',
  valuation: '估值水平',
  risk_changes: '风险变化',
  catalyst_events: '催化事件',
}

const STATUS_LABELS: Record<string, string> = {
  stable: '稳定',
  watching: '待观察',
  unverified: '待验证',
  risk: '风险',
  undervalued: '合理偏低',
  new_impact: '有新影响',
  strengthened: '增强',
  weakened: '削弱',
  at_risk: '风险',
  archived: '归档',
}

const STATUS_CLASSES: Record<string, string> = {
  stable: 'border-blue-200 bg-blue-50 text-blue-700',
  watching: 'border-amber-200 bg-amber-50 text-amber-700',
  unverified: 'border-slate-200 bg-slate-100 text-slate-600',
  risk: 'border-red-200 bg-red-50 text-red-700',
  undervalued: 'border-indigo-200 bg-indigo-50 text-indigo-700',
  new_impact: 'border-violet-200 bg-violet-50 text-violet-700',
  strengthened: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  weakened: 'border-orange-200 bg-orange-50 text-orange-700',
  at_risk: 'border-red-200 bg-red-50 text-red-700',
  archived: 'border-gray-200 bg-gray-100 text-gray-500',
}

const SOURCE_LEVEL_LABELS: Record<string, string> = {
  A: 'A 法定披露',
  B: 'B 指标数据',
  C: 'C 新闻线索',
  D: 'D 用户观点',
}

const SOURCE_LEVEL_CLASSES: Record<string, string> = {
  A: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  B: 'border-blue-200 bg-blue-50 text-blue-700',
  C: 'border-amber-200 bg-amber-50 text-amber-700',
  D: 'border-slate-200 bg-slate-100 text-slate-600',
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`rounded-full border px-2 py-0.5 text-xs ${STATUS_CLASSES[status] ?? STATUS_CLASSES.unverified}`}>
      {STATUS_LABELS[status] ?? status}
    </span>
  )
}

function getText(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function App() {
  const [stocks, setStocks] = useState<Stock[]>([])
  const [selectedCode, setSelectedCode] = useState<string | null>(null)
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([])
  const [checkItems, setCheckItems] = useState<CheckItem[]>([])
  const [reviews, setReviews] = useState<Review[]>([])
  const [marketEvents, setMarketEvents] = useState<MarketEvent[]>([])
  const [metrics, setMetrics] = useState<FundamentalMetric[]>([])
  const [quotes, setQuotes] = useState<QuoteSnapshot[]>([])
  const [refreshResult, setRefreshResult] = useState<DataRefreshResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [detailLoading, setDetailLoading] = useState(false)
  const [dataRefreshing, setDataRefreshing] = useState(false)
  const [dataError, setDataError] = useState('')
  const [showAddStock, setShowAddStock] = useState(false)
  const [error, setError] = useState('')
  const [stockForm, setStockForm] = useState({ code: '', name: '', industry: '', market: 'SH' })
  const [hypothesisForm, setHypothesisForm] = useState({
    category: 'growth_logic',
    status: 'unverified',
    title: '',
    summary: '',
    evidence: '',
    nextReviewDate: '',
  })
  const [checkForm, setCheckForm] = useState({ content: '', dueDate: '' })
  const [reviewForm, setReviewForm] = useState({ reviewType: 'quarterly', title: '', content: '', conclusions: '' })
  const [aiInput, setAiInput] = useState('')
  const [aiReply, setAiReply] = useState('')
  const [aiActions, setAiActions] = useState<AiAction[]>([])
  const [evidenceCards, setEvidenceCards] = useState<EvidenceCard[]>([])
  const [aiError, setAiError] = useState('')
  const [aiLoading, setAiLoading] = useState(false)

  const selectedStock = useMemo(
    () => stocks.find((stock) => stock.code === selectedCode) ?? null,
    [selectedCode, stocks],
  )

  const hasExternalEvidence = evidenceCards.some((card) => ['A', 'B', 'C'].includes(card.sourceLevel))

  const loadStocks = async () => {
    try {
      const items = await listStocks()
      setStocks(items)
      setSelectedCode((current) => current ?? items[0]?.code ?? null)
    } catch {
      setStocks([])
    } finally {
      setLoading(false)
    }
  }

  const loadResearch = async (stockCode: string) => {
    setDetailLoading(true)
    try {
      const [
        nextHypotheses,
        nextCheckItems,
        nextReviews,
        nextEvidenceCards,
        nextEvents,
        nextMetrics,
        nextQuotes,
      ] = await Promise.all([
        listHypotheses(stockCode),
        listCheckItems(stockCode),
        listReviews(stockCode),
        listEvidence(stockCode),
        listEvents(stockCode),
        listMetrics(stockCode),
        listQuotes(stockCode),
      ])
      setHypotheses(nextHypotheses)
      setCheckItems(nextCheckItems)
      setReviews(nextReviews)
      setEvidenceCards(nextEvidenceCards)
      setMarketEvents(nextEvents)
      setMetrics(nextMetrics)
      setQuotes(nextQuotes)
    } finally {
      setDetailLoading(false)
    }
  }

  useEffect(() => {
    void loadStocks()
  }, [])

  useEffect(() => {
    setAiReply('')
    setAiActions([])
    setEvidenceCards([])
    setAiError('')
    setDataError('')
    setRefreshResult(null)
    if (selectedCode) {
      void loadResearch(selectedCode)
    }
  }, [selectedCode])

  const handleCreateStock = async (event: FormEvent) => {
    event.preventDefault()
    setError('')

    try {
      const stock = await createStock({
        code: stockForm.code.trim(),
        name: stockForm.name.trim(),
        industry: stockForm.industry.trim() || null,
        market: stockForm.market,
      })
      setStockForm({ code: '', name: '', industry: '', market: 'SH' })
      setShowAddStock(false)
      await loadStocks()
      setSelectedCode(stock.code)
    } catch (err) {
      setError(err instanceof Error ? err.message : '添加失败')
    }
  }

  const handleDeleteStock = async (code: string) => {
    if (!confirm(`确定删除 ${code}？`)) return
    await deleteStock(code)
    setSelectedCode(null)
    await loadStocks()
  }

  const handleCreateHypothesis = async (event: FormEvent) => {
    event.preventDefault()
    if (!selectedStock) return

    await createHypothesis(selectedStock.code, {
      category: hypothesisForm.category,
      status: hypothesisForm.status,
      content: {
        title: hypothesisForm.title.trim(),
        summary: hypothesisForm.summary.trim(),
      },
      evidence: hypothesisForm.evidence.trim() || null,
      next_review_date: hypothesisForm.nextReviewDate || null,
    })
    setHypothesisForm({
      category: 'growth_logic',
      status: 'unverified',
      title: '',
      summary: '',
      evidence: '',
      nextReviewDate: '',
    })
    await loadResearch(selectedStock.code)
  }

  const handleCreateCheckItem = async (event: FormEvent) => {
    event.preventDefault()
    if (!selectedStock) return

    await createCheckItem(selectedStock.code, {
      content: checkForm.content.trim(),
      due_date: checkForm.dueDate || null,
      source_type: 'manual',
    })
    setCheckForm({ content: '', dueDate: '' })
    await loadResearch(selectedStock.code)
  }

  const handleCreateReview = async (event: FormEvent) => {
    event.preventDefault()
    if (!selectedStock) return

    await createReview(selectedStock.code, {
      review_type: reviewForm.reviewType,
      title: reviewForm.title.trim() || null,
      content: reviewForm.content.trim(),
      conclusions: reviewForm.conclusions.trim() || null,
      action_items: [],
    })
    setReviewForm({ reviewType: 'quarterly', title: '', content: '', conclusions: '' })
    await loadResearch(selectedStock.code)
  }

  const handleAiSubmit = async (event: FormEvent) => {
    event.preventDefault()
    if (!selectedStock || !aiInput.trim()) return

    setAiLoading(true)
    setAiError('')
    try {
      const response = await chatWithAi(selectedStock.code, aiInput.trim())
      setAiReply(response.reply)
      setEvidenceCards(response.evidenceCards)
      setAiActions(response.actions.map((action) => ({
        ...action,
        payload: { ...action.payload, stock_code: selectedStock.code },
      })))
      setAiInput('')
    } catch (err) {
      setAiError(err instanceof Error ? err.message : 'AI 生成失败，请稍后重试')
    } finally {
      setAiLoading(false)
    }
  }

  const handleApplyAiAction = async (action: AiAction, index: number) => {
    if (!selectedStock) return
    setAiError('')
    try {
      await applyAiAction(action)
      setAiActions((current) => current.filter((_, itemIndex) => itemIndex !== index))
      await loadResearch(selectedStock.code)
    } catch (err) {
      setAiError(err instanceof Error ? err.message : '保存成果失败，请稍后重试')
    }
  }

  const handleRefreshData = async () => {
    if (!selectedStock) return
    setDataRefreshing(true)
    setDataError('')
    try {
      const result = await refreshStockData(selectedStock.code)
      setRefreshResult(result)
      await loadResearch(selectedStock.code)
    } catch (err) {
      setDataError(err instanceof Error ? err.message : '刷新数据失败，请稍后重试')
    } finally {
      setDataRefreshing(false)
    }
  }

  const handleUseEvidence = (card: EvidenceCard) => {
    setAiInput(`请基于这条证据分析它影响了我哪条投资假设：${card.title}。证据摘要：${card.summary}`)
    setAiReply('')
    setAiActions([])
    setAiError('')
  }

  return (
    <div className="flex h-screen min-w-[1366px] bg-slate-50">
      <aside className="h-screen w-[280px] shrink-0 border-r border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-4">
          <h1 className="text-lg font-bold text-slate-900">A股基本面复盘助手</h1>
          <p className="mt-1 text-xs text-slate-500">股票 → 假设 → 检查项 → 复盘</p>
        </div>
        <div className="p-4">
          <button
            onClick={() => setShowAddStock(true)}
            className="flex h-9 w-full items-center justify-center gap-1.5 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" />
            添加股票
          </button>
        </div>
        <div className="space-y-1 px-3">
          {loading ? (
            <div className="px-3 py-8 text-center text-sm text-slate-400">加载中...</div>
          ) : stocks.length === 0 ? (
            <div className="px-3 py-8 text-center text-sm text-slate-400">还没有股票</div>
          ) : (
            stocks.map((stock) => (
              <button
                key={stock.code}
                onClick={() => setSelectedCode(stock.code)}
                className={`w-full rounded-lg px-3 py-2.5 text-left transition-colors ${
                  selectedCode === stock.code ? 'bg-blue-50' : 'hover:bg-slate-50'
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium text-slate-900">{stock.name}</span>
                  <span className="text-xs text-slate-400">{stock.market ? MARKET_LABELS[stock.market] : '-'}</span>
                </div>
                <div className="mt-0.5 flex items-center justify-between gap-2">
                  <span className="text-xs text-slate-500">{stock.code}</span>
                  {stock.industry && <span className="truncate text-xs text-slate-500">{stock.industry}</span>}
                </div>
              </button>
            ))
          )}
        </div>
      </aside>

      <main className="h-screen flex-1 overflow-y-auto p-6">
        {!selectedStock ? (
          <div className="flex h-full items-center justify-center text-center">
            <div>
              <Building2 className="mx-auto mb-4 h-12 w-12 text-slate-300" />
              <p className="text-slate-500">先添加或选择一家公司</p>
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-xl font-bold text-slate-900">{selectedStock.name} · 基本面假设台</h2>
                <p className="mt-1 text-sm text-slate-500">
                  {selectedStock.code} · {selectedStock.industry || '未设置主题'} · 数据仅供研究
                </p>
              </div>
              <button
                onClick={() => void handleDeleteStock(selectedStock.code)}
                className="flex h-9 items-center gap-1.5 rounded-lg border border-slate-200 px-3 text-sm text-slate-600 hover:bg-red-50 hover:text-red-600"
              >
                <Trash2 className="h-4 w-4" />
                删除股票
              </button>
            </div>

            <div className="grid grid-cols-3 gap-4">
              <SummaryCard label="投资假设" value={hypotheses.length} icon={<BookOpen className="h-4 w-4" />} />
              <SummaryCard label="检查项" value={checkItems.length} icon={<CheckCircle2 className="h-4 w-4" />} />
              <SummaryCard label="复盘记录" value={reviews.length} icon={<RotateCcw className="h-4 w-4" />} />
            </div>

            {detailLoading && <div className="text-sm text-slate-400">正在刷新研究记录...</div>}

            <Panel title="数据证据">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div className="text-sm text-slate-500">
                  免费数据源仅用于研究复盘，不保证交易级实时性。证据进入 AI 前会先标准化和分级。
                </div>
                <button
                  onClick={() => void handleRefreshData()}
                  disabled={dataRefreshing}
                  className="flex h-9 items-center gap-1.5 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <RefreshCw className={`h-4 w-4 ${dataRefreshing ? 'animate-spin' : ''}`} />
                  {dataRefreshing ? '刷新中' : '刷新数据'}
                </button>
              </div>

              {dataError && (
                <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {dataError}
                </div>
              )}

              {refreshResult && (
                <div className="mb-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-600">
                  最近刷新：新增 {sumCounts(refreshResult.created)} 条，跳过重复 {sumCounts(refreshResult.skipped)} 条
                  {refreshResult.errors.length > 0 && `，${refreshResult.errors.length} 个来源暂时失败`}
                </div>
              )}

              <div className="grid grid-cols-3 gap-4">
                <EvidenceColumn
                  title="最新公告/新闻"
                  empty="暂无公告或新闻证据"
                  items={marketEvents.slice(0, 4).map((event) => ({
                    id: event.id,
                    title: event.title,
                    meta: `${event.sourceProvider || '未知来源'} · ${event.publishedAt.slice(0, 10)}`,
                  }))}
                />
                <EvidenceColumn
                  title="核心指标"
                  empty="暂无指标证据"
                  items={metrics.slice(0, 4).map((metric) => ({
                    id: metric.id,
                    title: `${metric.metricName}: ${metric.value ?? '暂无'}${metric.unit || ''}`,
                    meta: `${metric.sourceProvider || '未知来源'} · ${metric.period || '未知期间'}`,
                  }))}
                />
                <EvidenceColumn
                  title="行情/估值"
                  empty="暂无行情快照"
                  items={quotes.slice(0, 4).map((quote) => ({
                    id: quote.id,
                    title: `${quote.date} 收盘 ${quote.close ?? '暂无'}`,
                    meta: `PE ${quote.pe ?? '暂无'} · PB ${quote.pb ?? '暂无'}`,
                  }))}
                />
              </div>

              {evidenceCards.length > 0 && (
                <div className="mt-4 grid grid-cols-2 gap-3">
                  {evidenceCards.slice(0, 4).map((card, index) => (
                    <button
                      key={`${card.sourceProvider}-${card.title}-${index}`}
                      onClick={() => handleUseEvidence(card)}
                      className="text-left"
                    >
                      <EvidenceCardView card={card} compact />
                    </button>
                  ))}
                </div>
              )}
            </Panel>

            <section className="grid grid-cols-[1fr_360px] gap-4">
              <div className="space-y-4">
                <Panel title="投资假设">
                  <form onSubmit={handleCreateHypothesis} className="mb-4 grid gap-3 rounded-lg bg-slate-50 p-3">
                    <div className="grid grid-cols-2 gap-3">
                      <select
                        value={hypothesisForm.category}
                        onChange={(event) => setHypothesisForm({ ...hypothesisForm, category: event.target.value })}
                        className="h-9 rounded-lg border border-slate-200 px-3 text-sm"
                      >
                        {Object.entries(CATEGORY_LABELS).map(([value, label]) => (
                          <option key={value} value={value}>{label}</option>
                        ))}
                      </select>
                      <select
                        value={hypothesisForm.status}
                        onChange={(event) => setHypothesisForm({ ...hypothesisForm, status: event.target.value })}
                        className="h-9 rounded-lg border border-slate-200 px-3 text-sm"
                      >
                        {Object.entries(STATUS_LABELS).map(([value, label]) => (
                          <option key={value} value={value}>{label}</option>
                        ))}
                      </select>
                    </div>
                    <input
                      value={hypothesisForm.title}
                      onChange={(event) => setHypothesisForm({ ...hypothesisForm, title: event.target.value })}
                      placeholder="假设标题，如 AI 资本开支持续增长"
                      className="h-9 rounded-lg border border-slate-200 px-3 text-sm"
                      required
                    />
                    <textarea
                      value={hypothesisForm.summary}
                      onChange={(event) => setHypothesisForm({ ...hypothesisForm, summary: event.target.value })}
                      placeholder="一句话说明这个假设如何验证"
                      className="min-h-[72px] rounded-lg border border-slate-200 px-3 py-2 text-sm"
                      required
                    />
                    <div className="grid grid-cols-[1fr_150px] gap-3">
                      <input
                        value={hypothesisForm.evidence}
                        onChange={(event) => setHypothesisForm({ ...hypothesisForm, evidence: event.target.value })}
                        placeholder="证据来源，可选"
                        className="h-9 rounded-lg border border-slate-200 px-3 text-sm"
                      />
                      <input
                        type="date"
                        value={hypothesisForm.nextReviewDate}
                        onChange={(event) => setHypothesisForm({ ...hypothesisForm, nextReviewDate: event.target.value })}
                        className="h-9 rounded-lg border border-slate-200 px-3 text-sm"
                      />
                    </div>
                    <button className="h-9 rounded-lg bg-blue-600 px-4 text-sm font-medium text-white hover:bg-blue-700">
                      保存假设
                    </button>
                  </form>

                  <div className="space-y-3">
                    {hypotheses.length === 0 ? (
                      <EmptyText text="还没有投资假设。先写下你为什么关注它。" />
                    ) : (
                      hypotheses.map((item) => (
                        <div key={item.id} className="rounded-lg border border-slate-200 p-4">
                          <div className="mb-2 flex items-center justify-between gap-3">
                            <div className="text-sm font-semibold text-slate-900">{getText(item.content.title)}</div>
                            <StatusBadge status={item.status} />
                          </div>
                          <p className="text-sm leading-relaxed text-slate-600">{getText(item.content.summary)}</p>
                          <div className="mt-3 flex flex-wrap gap-2 text-xs text-slate-500">
                            <span>{CATEGORY_LABELS[item.category] ?? item.category}</span>
                            <span>信心 {item.confidence}</span>
                            {item.nextReviewDate && <span>复盘 {item.nextReviewDate}</span>}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </Panel>
              </div>

              <div className="space-y-4">
                <Panel title="检查项">
                  <form onSubmit={handleCreateCheckItem} className="mb-4 grid gap-3">
                    <input
                      value={checkForm.content}
                      onChange={(event) => setCheckForm({ ...checkForm, content: event.target.value })}
                      placeholder="如下季度检查毛利率是否下行"
                      className="h-9 rounded-lg border border-slate-200 px-3 text-sm"
                      required
                    />
                    <div className="grid grid-cols-[1fr_80px] gap-3">
                      <input
                        type="date"
                        value={checkForm.dueDate}
                        onChange={(event) => setCheckForm({ ...checkForm, dueDate: event.target.value })}
                        className="h-9 rounded-lg border border-slate-200 px-3 text-sm"
                      />
                      <button className="h-9 rounded-lg bg-blue-600 text-sm font-medium text-white hover:bg-blue-700">
                        添加
                      </button>
                    </div>
                  </form>
                  <RecordList
                    empty="暂无检查项"
                    items={checkItems.map((item) => ({
                      id: item.id,
                      title: item.content,
                      meta: item.dueDate ? `到期 ${item.dueDate}` : '未设置日期',
                    }))}
                  />
                </Panel>

                <Panel title="复盘记录">
                  <form onSubmit={handleCreateReview} className="mb-4 grid gap-3">
                    <input
                      value={reviewForm.title}
                      onChange={(event) => setReviewForm({ ...reviewForm, title: event.target.value })}
                      placeholder="复盘标题"
                      className="h-9 rounded-lg border border-slate-200 px-3 text-sm"
                    />
                    <textarea
                      value={reviewForm.content}
                      onChange={(event) => setReviewForm({ ...reviewForm, content: event.target.value })}
                      placeholder="这次复盘发现了什么？"
                      className="min-h-[72px] rounded-lg border border-slate-200 px-3 py-2 text-sm"
                      required
                    />
                    <input
                      value={reviewForm.conclusions}
                      onChange={(event) => setReviewForm({ ...reviewForm, conclusions: event.target.value })}
                      placeholder="结论，可选"
                      className="h-9 rounded-lg border border-slate-200 px-3 text-sm"
                    />
                    <button className="h-9 rounded-lg bg-blue-600 text-sm font-medium text-white hover:bg-blue-700">
                      保存复盘
                    </button>
                  </form>
                  <RecordList
                    empty="暂无复盘记录"
                    items={reviews.map((item) => ({
                      id: item.id,
                      title: item.title || item.content,
                      meta: item.conclusions || item.reviewType,
                    }))}
                  />
                </Panel>
              </div>
            </section>
          </div>
        )}
      </main>

      <aside className="flex h-screen w-[400px] shrink-0 flex-col border-l border-slate-200 bg-white">
        <header className="shrink-0 border-b border-slate-200 px-4 py-4">
          <h2 className="text-base font-semibold text-slate-900">AI 复盘引导器</h2>
          <p className="mt-1 text-xs text-slate-500">先看证据边界，再把想法变成可保存成果</p>
        </header>
        <div className="flex-1 overflow-y-auto p-4">
          {!selectedStock ? (
            <EmptyText text="选择股票后开始整理投资判断" />
          ) : (
            <div className="space-y-4">
              <div className="rounded-lg bg-slate-50 p-3 text-sm leading-relaxed text-slate-600">
                当前股票：<span className="font-medium text-slate-900">{selectedStock.name}</span>。先说你的关注逻辑，AI 会追问并生成待确认的假设、检查项或复盘。
              </div>

              {aiReply && (
                <div className="rounded-lg border border-blue-100 bg-blue-50 p-3 text-sm leading-relaxed text-blue-800">
                  {aiReply}
                </div>
              )}

              {aiError && (
                <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm leading-relaxed text-red-700">
                  {aiError}
                </div>
              )}

              {aiReply && !hasExternalEvidence && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm leading-relaxed text-amber-800">
                  当前证据不足：系统还没有可用于交叉验证的公告、财报、行情或新闻证据。这里生成的是“待验证观点”，不是事实结论。
                </div>
              )}

              {evidenceCards.length > 0 && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
                    <Database className="h-4 w-4" />
                    证据卡
                  </div>
                  {evidenceCards.map((card, index) => (
                    <EvidenceCardView key={`${card.sourceProvider}-${index}`} card={card} />
                  ))}
                </div>
              )}

              <div className="space-y-3">
                {aiActions.map((action, index) => (
                  <AiActionCard
                    key={`${action.type}-${index}`}
                    action={action}
                    onApply={() => void handleApplyAiAction(action, index)}
                    onDismiss={() => setAiActions((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
        <form onSubmit={handleAiSubmit} className="shrink-0 border-t border-slate-200 p-4">
          <textarea
            value={aiInput}
            onChange={(event) => setAiInput(event.target.value)}
            placeholder="输入你的判断，比如：我看好 AI 算力链，海外订单可能继续兑现"
            className="min-h-[88px] w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
            disabled={!selectedStock || aiLoading}
          />
          <button
            className="mt-3 h-9 w-full rounded-lg bg-blue-600 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
            disabled={!selectedStock || aiLoading || !aiInput.trim()}
          >
            {aiLoading ? '整理中...' : '生成可保存成果'}
          </button>
        </form>
      </aside>

      {showAddStock && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-md rounded-lg bg-white shadow-xl">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <h2 className="font-semibold text-slate-900">添加股票</h2>
              <button
                onClick={() => {
                  setShowAddStock(false)
                  setError('')
                }}
                className="rounded p-1 text-slate-400 hover:text-slate-600"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <form onSubmit={handleCreateStock} className="space-y-4 p-5">
              {error && <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</div>}
              <input
                value={stockForm.code}
                onChange={(event) => setStockForm({ ...stockForm, code: event.target.value })}
                placeholder="股票代码，如 300308"
                className="h-9 w-full rounded-lg border border-slate-200 px-3 text-sm"
                required
              />
              <input
                value={stockForm.name}
                onChange={(event) => setStockForm({ ...stockForm, name: event.target.value })}
                placeholder="股票名称，如 中际旭创"
                className="h-9 w-full rounded-lg border border-slate-200 px-3 text-sm"
                required
              />
              <input
                value={stockForm.industry}
                onChange={(event) => setStockForm({ ...stockForm, industry: event.target.value })}
                placeholder="行业/主题，如 AI 算力链"
                className="h-9 w-full rounded-lg border border-slate-200 px-3 text-sm"
              />
              <select
                value={stockForm.market}
                onChange={(event) => setStockForm({ ...stockForm, market: event.target.value })}
                className="h-9 w-full rounded-lg border border-slate-200 px-3 text-sm"
              >
                <option value="SH">上海 (SH)</option>
                <option value="SZ">深圳 (SZ)</option>
                <option value="BJ">北京 (BJ)</option>
              </select>
              <button className="h-9 w-full rounded-lg bg-blue-600 text-sm font-medium text-white hover:bg-blue-700">
                确认添加
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

function SummaryCard({ label, value, icon }: { label: string; value: number; icon: ReactNode }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between text-slate-500">
        <span className="text-sm">{label}</span>
        {icon}
      </div>
      <div className="mt-3 text-2xl font-bold text-slate-900">{value}</div>
    </div>
  )
}

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-5">
      <h3 className="mb-4 text-base font-semibold text-slate-900">{title}</h3>
      {children}
    </section>
  )
}

function EmptyText({ text }: { text: string }) {
  return <div className="rounded-lg bg-slate-50 px-4 py-6 text-center text-sm text-slate-400">{text}</div>
}

function RecordList({ empty, items }: { empty: string; items: Array<{ id: number; title: string; meta: string }> }) {
  if (items.length === 0) {
    return <EmptyText text={empty} />
  }

  return (
    <div className="space-y-2">
      {items.map((item) => (
        <div key={item.id} className="rounded-lg border border-slate-200 px-3 py-2">
          <div className="text-sm text-slate-800">{item.title}</div>
          <div className="mt-1 text-xs text-slate-500">{item.meta}</div>
        </div>
      ))}
    </div>
  )
}

function EvidenceColumn({
  title,
  empty,
  items,
}: {
  title: string
  empty: string
  items: Array<{ id: number; title: string; meta: string }>
}) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className="mb-3 text-sm font-semibold text-slate-900">{title}</div>
      {items.length === 0 ? (
        <div className="text-sm text-slate-400">{empty}</div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <div key={item.id}>
              <div className="line-clamp-2 text-sm text-slate-800">{item.title}</div>
              <div className="mt-0.5 text-xs text-slate-500">{item.meta}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function EvidenceCardView({ card, compact = false }: { card: EvidenceCard; compact?: boolean }) {
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className={`rounded-full border px-2 py-0.5 text-xs ${SOURCE_LEVEL_CLASSES[card.sourceLevel] ?? SOURCE_LEVEL_CLASSES.D}`}>
          {SOURCE_LEVEL_LABELS[card.sourceLevel] ?? card.sourceLevel}
        </span>
        <span className="text-xs text-slate-400">置信 {card.confidence}</span>
      </div>
      <div className="text-sm font-semibold text-slate-900">{card.title}</div>
      <p className={`mt-1 text-sm leading-relaxed text-slate-600 ${compact ? 'line-clamp-2' : ''}`}>{card.summary}</p>
      <div className="mt-2 text-xs leading-relaxed text-slate-500">
        {card.sourceProvider} · {card.fetchedAt ? card.fetchedAt.slice(0, 10) : '未知时间'}
      </div>
      {!compact && <div className="mt-2 text-xs leading-relaxed text-slate-500">{card.evidenceBoundary}</div>}
    </div>
  )
}

function sumCounts(values: Record<string, number>): number {
  return Object.values(values).reduce((sum, value) => sum + value, 0)
}

function AiActionCard({
  action,
  onApply,
  onDismiss,
}: {
  action: AiAction
  onApply: () => void
  onDismiss: () => void
}) {
  const title =
    action.type === 'create_hypothesis'
      ? '创建投资假设'
      : action.type === 'create_check_item'
        ? '创建检查项'
        : action.type === 'create_review'
          ? '创建复盘记录'
          : action.type === 'update_hypothesis_status'
            ? '更新假设状态'
            : action.type

  const description = getActionDescription(action)

  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className="text-sm font-semibold text-slate-900">{title}</div>
      <p className="mt-2 text-sm leading-relaxed text-slate-600">{description}</p>
      <div className="mt-3 flex gap-2">
        <button
          onClick={onApply}
          className="h-8 flex-1 rounded-lg bg-blue-600 px-3 text-xs font-medium text-white hover:bg-blue-700"
        >
          保存成果
        </button>
        <button
          onClick={onDismiss}
          className="h-8 rounded-lg border border-slate-200 px-3 text-xs text-slate-600 hover:bg-slate-50"
        >
          忽略
        </button>
      </div>
    </div>
  )
}

function getActionDescription(action: AiAction): string {
  if (action.type === 'create_hypothesis') {
    const content = action.payload.content
    if (content && typeof content === 'object' && 'summary' in content) {
      return String((content as Record<string, unknown>).summary ?? '')
    }
  }
  if (action.type === 'update_hypothesis_status') {
    return typeof action.payload.reason === 'string' ? action.payload.reason : '更新一条假设的状态'
  }
  if (typeof action.payload.content === 'string') {
    return action.payload.content
  }
  if (typeof action.payload.title === 'string') {
    return action.payload.title
  }
  return '待保存成果'
}

export default App
