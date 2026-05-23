import { FormEvent, ReactNode, useEffect, useMemo, useState } from 'react'
import { BookOpen, Building2, CalendarDays, CheckCircle2, ChevronLeft, ChevronRight, Database, MessageSquare, Plus, RefreshCw, RotateCcw, Save, Sparkles, Trash2, X } from 'lucide-react'
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
  applyDailyReviewAction,
  coachDailyReview,
  deleteDailyReviewSectionItem,
  initializeDailyReview,
  prefillDailyReview,
  updateDailyReview,
  type DailyReview,
} from './services/dailyReviewService'
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

const DAILY_SECTIONS = [
  { key: 'index_review', label: '指数复盘', hint: '判断市场大风格' },
  { key: 'hotspot_review', label: '热点复盘', hint: '锁定主线板块' },
  { key: 'capital_review', label: '资金复盘', hint: '跟踪主力动向' },
  { key: 'limit_review', label: '涨跌停复盘', hint: '识别机会与风险' },
  { key: 'watchlist_review', label: '自选股复盘', hint: '精细化找观察点' },
  { key: 'fundamental_review', label: '基本面复盘', hint: '验证持仓质地' },
  { key: 'tomorrow_plan', label: '今日判断与明日计划', hint: '沉淀触发条件' },
  { key: 'weekly_review', label: '周末系统复盘', hint: '每周归因与计划' },
]

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

function todayString(): string {
  return new Date().toISOString().slice(0, 10)
}

function readField(value: unknown): string {
  if (typeof value === 'string' || typeof value === 'number') return String(value)
  if (value && typeof value === 'object' && 'value' in value) {
    const inner = (value as Record<string, unknown>).value
    return typeof inner === 'string' || typeof inner === 'number' ? String(inner) : ''
  }
  return ''
}

function readSource(value: unknown): string {
  if (value && typeof value === 'object' && 'source' in value) {
    const source = (value as Record<string, unknown>).source
    return typeof source === 'string' ? source : 'manual'
  }
  return 'manual'
}

function sourceLabel(source: string): string {
  if (source === 'data_prefilled') return '已由数据预填'
  if (source === 'ai_generated') return 'AI 整理'
  if (source === 'insufficient_evidence') return '当前证据不足'
  return '需要手动填写'
}

function App() {
  const [viewMode, setViewMode] = useState<'company' | 'daily'>('company')
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
  const [dailyDate, setDailyDate] = useState(todayString())
  const [dailyReview, setDailyReview] = useState<DailyReview | null>(null)
  const [dailyLoading, setDailyLoading] = useState(false)
  const [dailyPrefillLoading, setDailyPrefillLoading] = useState(false)
  const [dailyMessage, setDailyMessage] = useState('')
  const [dailySectionKey, setDailySectionKey] = useState('index_review')
  const [dailyReply, setDailyReply] = useState('')
  const [dailyActions, setDailyActions] = useState<AiAction[]>([])
  const [dailyEvidenceCards, setDailyEvidenceCards] = useState<EvidenceCard[]>([])
  const [dailyError, setDailyError] = useState('')
  const [dailyAiLoading, setDailyAiLoading] = useState(false)
  const [prefillSummary, setPrefillSummary] = useState('')
  const [aiOpen, setAiOpen] = useState(false)

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
    console.log('[AI Chat] submit clicked', { stock: selectedStock?.code, message: aiInput.trim() })
    if (!selectedStock || !aiInput.trim()) return

    setAiLoading(true)
    setAiError('')
    try {
      const response = await chatWithAi(selectedStock.code, aiInput.trim())
      console.log('[AI Chat] response ok', { replyLen: response.reply.length, actions: response.actions.length })
      setAiReply(response.reply)
      setEvidenceCards(response.evidenceCards)
      setAiActions(response.actions.map((action) => ({
        ...action,
        payload: { ...action.payload, stock_code: selectedStock.code },
      })))
      setAiInput('')
    } catch (err) {
      console.error('[AI Chat] error', err)
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

  const handleInitializeDailyReview = async () => {
    setDailyLoading(true)
    setDailyError('')
    try {
      const review = await initializeDailyReview(dailyDate)
      setDailyReview(review)
      setDailyReply('')
      setDailyActions([])
      setPrefillSummary('')
    } catch (err) {
      setDailyError(err instanceof Error ? err.message : '创建每日复盘失败')
    } finally {
      setDailyLoading(false)
    }
  }

  const handleUpdateDailyMeta = async (patch: {
    status?: string
    market_style?: string | null
    main_sector?: string | null
    sentiment?: string | null
  }) => {
    if (!dailyReview) return
    setDailyError('')
    try {
      const next = await updateDailyReview(dailyReview.id, patch)
      setDailyReview(next)
    } catch (err) {
      setDailyError(err instanceof Error ? err.message : '保存每日复盘失败')
    }
  }

  const handlePrefillDailyReview = async () => {
    if (!dailyReview) return
    setDailyPrefillLoading(true)
    setDailyError('')
    try {
      const result = await prefillDailyReview(dailyReview.id)
      setDailyReview(result.review)
      setDailyEvidenceCards(result.evidenceCards)
      setPrefillSummary(`已预填自选股 ${result.filled.watchlist_targets ?? 0} 条、公司基本面 ${result.filled.company_rows ?? 0} 条；仍需手动补充：${result.missing.join('、')}`)
    } catch (err) {
      setDailyError(err instanceof Error ? err.message : '数据预填失败')
    } finally {
      setDailyPrefillLoading(false)
    }
  }

  const handleDailyAiSubmit = async (event: FormEvent) => {
    event.preventDefault()
    console.log('[AI Coach] submit clicked', { reviewId: dailyReview?.id, section: dailySectionKey, message: dailyMessage.trim() })
    if (!dailyReview || !dailyMessage.trim()) return
    setDailyAiLoading(true)
    setDailyError('')
    try {
      const response = await coachDailyReview(dailyReview.id, dailySectionKey, dailyMessage.trim())
      console.log('[AI Coach] response ok', { replyLen: response.reply.length, actions: response.actions.length })
      setDailyReply(response.reply)
      setDailyActions(response.actions)
      setDailyEvidenceCards(response.evidenceCards)
      setDailyMessage('')
    } catch (err) {
      console.error('[AI Coach] error', err)
      setDailyError(err instanceof Error ? err.message : 'AI 复盘教练生成失败')
    } finally {
      setDailyAiLoading(false)
    }
  }

  const handleDeleteDailySectionItem = async (
    sectionKey: string,
    field: 'ai_notes' | 'ai_actions' | 'linked_evidence',
    index: number,
  ) => {
    if (!dailyReview) return
    setDailyError('')
    try {
      const next = await deleteDailyReviewSectionItem(dailyReview.id, sectionKey, field, index)
      setDailyReview(next)
    } catch (err) {
      setDailyError(err instanceof Error ? err.message : '删除待验证条目失败')
    }
  }

  const handleApplyDailyAction = async (action: AiAction, index: number) => {
    if (!dailyReview) return
    setDailyError('')
    try {
      const next = await applyDailyReviewAction(dailyReview.id, action)
      setDailyReview(next)
      setDailyActions((current) => current.filter((_, itemIndex) => itemIndex !== index))
    } catch (err) {
      setDailyError(err instanceof Error ? err.message : '保存每日复盘成果失败')
    }
  }

  return (
    <div className="flex h-screen min-w-[1366px] bg-slate-50">
      <aside className="h-screen w-[280px] shrink-0 border-r border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-4 py-4">
          <h1 className="text-lg font-bold text-slate-900">A股基本面复盘助手</h1>
          <p className="mt-1 text-xs text-slate-500">股票 → 假设 → 检查项 → 复盘</p>
        </div>
        <nav className="border-b border-slate-100 p-3">
          <button
            onClick={() => setViewMode('company')}
            className={`mb-1 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
              viewMode === 'company' ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            <Building2 className="h-4 w-4" />
            公司研究
          </button>
          <button
            onClick={() => setViewMode('daily')}
            className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium ${
              viewMode === 'daily' ? 'bg-blue-50 text-blue-700' : 'text-slate-600 hover:bg-slate-100'
            }`}
          >
            <CalendarDays className="h-4 w-4" />
            每日复盘
          </button>
        </nav>
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
        {viewMode === 'daily' ? (
          <DailyReviewWorkspace
            reviewDate={dailyDate}
            onDateChange={setDailyDate}
            review={dailyReview}
            loading={dailyLoading}
            prefillLoading={dailyPrefillLoading}
            error={dailyError}
            prefillSummary={prefillSummary}
            sectionKey={dailySectionKey}
            onSectionChange={setDailySectionKey}
            onInitialize={() => void handleInitializeDailyReview()}
            onPrefill={() => void handlePrefillDailyReview()}
            onMetaChange={(patch) => void handleUpdateDailyMeta(patch)}
            onDeleteSectionItem={(sectionKey, field, index) =>
              void handleDeleteDailySectionItem(sectionKey, field, index)
            }
          />
        ) : !selectedStock ? (
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

      {!aiOpen && (
        <button
          onClick={() => setAiOpen(true)}
          className="fixed right-5 bottom-5 z-30 flex h-12 items-center gap-2 rounded-full bg-blue-600 px-5 text-sm font-medium text-white shadow-lg shadow-blue-600/30 hover:bg-blue-700"
        >
          <Sparkles className="h-4 w-4" />
          AI 教练
        </button>
      )}

      <aside
        className={`flex h-screen shrink-0 flex-col border-l border-slate-200 bg-white transition-[width] duration-200 ${
          aiOpen ? 'w-[400px]' : 'w-0 overflow-hidden border-l-0'
        }`}
      >
        <div className="flex items-center justify-between border-b border-slate-200 px-3 py-2">
          <div className="flex items-center gap-2 text-sm font-medium text-slate-700">
            <MessageSquare className="h-4 w-4 text-blue-600" />
            AI 复盘教练
          </div>
          <button
            onClick={() => setAiOpen(false)}
            className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
            aria-label="收起 AI 面板"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        {viewMode === 'daily' ? (
          <DailyReviewAiPanel
            review={dailyReview}
            sectionKey={dailySectionKey}
            message={dailyMessage}
            reply={dailyReply}
            actions={dailyActions}
            evidenceCards={dailyEvidenceCards}
            error={dailyError}
            loading={dailyAiLoading}
            onMessageChange={setDailyMessage}
            onSubmit={(event) => void handleDailyAiSubmit(event)}
            onApply={(action, index) => void handleApplyDailyAction(action, index)}
            onDismiss={(index) => setDailyActions((current) => current.filter((_, itemIndex) => itemIndex !== index))}
          />
        ) : (
          <>
        <div className="border-b border-slate-100 px-4 py-2 text-xs text-slate-500">
          先看证据边界，再把想法变成可保存成果
        </div>
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
                {Array.isArray(aiActions) && aiActions.map((action, index) => (
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
          </>
        )}
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

function DailyReviewWorkspace({
  reviewDate,
  onDateChange,
  review,
  loading,
  prefillLoading,
  error,
  prefillSummary,
  sectionKey,
  onSectionChange,
  onInitialize,
  onPrefill,
  onMetaChange,
  onDeleteSectionItem,
}: {
  reviewDate: string
  onDateChange: (value: string) => void
  review: DailyReview | null
  loading: boolean
  prefillLoading: boolean
  error: string
  prefillSummary: string
  sectionKey: string
  onSectionChange: (value: string) => void
  onInitialize: () => void
  onPrefill: () => void
  onMetaChange: (patch: { status?: string; market_style?: string | null; main_sector?: string | null; sentiment?: string | null }) => void
  onDeleteSectionItem: (
    sectionKey: string,
    field: 'ai_notes' | 'ai_actions' | 'linked_evidence',
    index: number,
  ) => void
}) {
  const [errorDismissed, setErrorDismissed] = useState(false)
  useEffect(() => {
    setErrorDismissed(false)
  }, [error])

  const shiftDate = (days: number) => {
    if (!reviewDate) return
    const d = new Date(reviewDate)
    d.setDate(d.getDate() + days)
    onDateChange(d.toISOString().slice(0, 10))
  }

  const handleSectionJump = (key: string) => {
    onSectionChange(key)
    const el = document.getElementById(`section-${key}`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  // Track scroll position to highlight current section in the ToC.
  useEffect(() => {
    if (!review) return
    const handler = () => {
      for (const section of DAILY_SECTIONS) {
        const el = document.getElementById(`section-${section.key}`)
        if (!el) continue
        const rect = el.getBoundingClientRect()
        if (rect.top >= 64 && rect.top < 240) {
          if (section.key !== sectionKey) onSectionChange(section.key)
          break
        }
      }
    }
    const container = document.getElementById('daily-scroll')
    container?.addEventListener('scroll', handler, { passive: true })
    return () => container?.removeEventListener('scroll', handler)
  }, [review, sectionKey, onSectionChange])

  return (
    <div id="daily-scroll" className="relative h-full overflow-y-auto">
      {/* Sticky compact top bar */}
      <div className="sticky top-0 z-20 -mx-6 -mt-6 mb-4 border-b border-slate-200 bg-slate-50/95 px-6 py-2.5 backdrop-blur">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <h2 className="text-base font-semibold text-slate-900">每日复盘</h2>
            <div className="flex items-center gap-0.5 rounded-lg border border-slate-200 bg-white">
              <button
                onClick={() => shiftDate(-1)}
                className="flex h-8 w-8 items-center justify-center text-slate-500 hover:text-slate-900"
                aria-label="前一天"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <input
                type="date"
                value={reviewDate}
                onChange={(event) => onDateChange(event.target.value)}
                className="h-8 border-x border-slate-200 bg-white px-2 text-sm focus:outline-none"
              />
              <button
                onClick={() => shiftDate(1)}
                className="flex h-8 w-8 items-center justify-center text-slate-500 hover:text-slate-900"
                aria-label="后一天"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
            {review && (
              <select
                value={review.status}
                onChange={(event) => onMetaChange({ status: event.target.value })}
                className="h-8 rounded-lg border border-slate-200 bg-white px-2 text-sm"
              >
                <option value="draft">草稿</option>
                <option value="completed">已完成</option>
              </select>
            )}
            {prefillSummary && (
              <span className="hidden text-xs text-slate-500 lg:inline">{prefillSummary}</span>
            )}
          </div>
          <div className="flex items-center gap-2">
            {review ? (
              <button
                onClick={onPrefill}
                disabled={prefillLoading}
                className="flex h-8 items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-50"
              >
                <RefreshCw className={`h-3.5 w-3.5 ${prefillLoading ? 'animate-spin' : ''}`} />
                数据预填
              </button>
            ) : (
              <button
                onClick={onInitialize}
                disabled={loading}
                className="flex h-8 items-center gap-1.5 rounded-lg bg-blue-600 px-3 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
              >
                <CalendarDays className="h-3.5 w-3.5" />
                {loading ? '创建中' : '初始化当日'}
              </button>
            )}
          </div>
        </div>
        {error && !errorDismissed && (
          <div className="mt-2 flex items-start justify-between gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-1.5 text-xs text-amber-800">
            <span>{error}</span>
            <button
              onClick={() => setErrorDismissed(true)}
              className="shrink-0 text-amber-600 hover:text-amber-900"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
      </div>

      {!review ? (
        <div className="flex min-h-[520px] items-center justify-center rounded-lg border border-slate-200 bg-white text-center">
          <div>
            <CalendarDays className="mx-auto mb-4 h-12 w-12 text-slate-300" />
            <p className="text-sm text-slate-500">选择日期后初始化当日复盘模板</p>
          </div>
        </div>
      ) : (
        <div className="flex gap-6">
          {/* Main: 8 sections stacked vertically */}
          <div className="flex-1 space-y-4 pb-24">
            {DAILY_SECTIONS.map((section, index) => (
              <SectionCard
                key={section.key}
                id={`section-${section.key}`}
                index={index + 1}
                title={section.label}
                hint={section.hint}
              >
                <DailyReviewSection review={review} sectionKey={section.key} />
                <DailyAiProposals
                  review={review}
                  sectionKey={section.key}
                  onDelete={(field, idx) => onDeleteSectionItem(section.key, field, idx)}
                />
                {section.key === 'index_review' && (
                  <SectionMetaInput
                    label="市场风格(你的判断)"
                    value={review.marketStyle ?? ''}
                    placeholder="如 小盘 / 科技 / 均衡"
                    onChange={(v) => onMetaChange({ market_style: v || null })}
                  />
                )}
                {section.key === 'hotspot_review' && (
                  <div className="grid grid-cols-2 gap-3">
                    <SectionMetaInput
                      label="主线板块(你的结论)"
                      value={review.mainSector ?? ''}
                      placeholder="如 AI 算力"
                      onChange={(v) => onMetaChange({ main_sector: v || null })}
                    />
                    <SectionMetaInput
                      label="情绪(强 / 弱 / 分歧)"
                      value={review.sentiment ?? ''}
                      placeholder="如 强"
                      onChange={(v) => onMetaChange({ sentiment: v || null })}
                    />
                  </div>
                )}
              </SectionCard>
            ))}
          </div>

          {/* Right-side floating ToC */}
          <nav className="sticky top-20 hidden h-fit w-44 shrink-0 self-start space-y-0.5 xl:block">
            <div className="mb-2 px-2 text-xs font-medium uppercase tracking-wider text-slate-400">导航</div>
            {DAILY_SECTIONS.map((section, index) => (
              <button
                key={section.key}
                onClick={() => handleSectionJump(section.key)}
                className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors ${
                  sectionKey === section.key
                    ? 'bg-blue-50 font-medium text-blue-700'
                    : 'text-slate-600 hover:bg-slate-100'
                }`}
              >
                <span className="text-xs text-slate-400">{index + 1}</span>
                <span className="truncate">{section.label}</span>
              </button>
            ))}
          </nav>
        </div>
      )}
    </div>
  )
}

function SectionCard({
  id,
  index,
  title,
  hint,
  children,
}: {
  id: string
  index: number
  title: string
  hint: string
  children: ReactNode
}) {
  return (
    <section
      id={id}
      className="scroll-mt-20 rounded-xl border border-slate-200 bg-white shadow-sm"
    >
      <div className="flex items-baseline gap-3 border-b border-slate-100 px-5 py-3">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-blue-50 text-xs font-semibold text-blue-700">
          {index}
        </span>
        <h3 className="text-base font-semibold text-slate-900">{title}</h3>
        <span className="text-xs text-slate-400">{hint}</span>
      </div>
      <div className="space-y-3 p-5">{children}</div>
    </section>
  )
}

function SectionMetaInput({
  label,
  value,
  placeholder,
  onChange,
}: {
  label: string
  value: string
  placeholder?: string
  onChange: (value: string) => void
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-500">{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 px-3 text-sm focus:border-blue-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-blue-500/20"
      />
    </label>
  )
}

function DailyReviewSection({ review, sectionKey }: { review: DailyReview; sectionKey: string }) {
  if (sectionKey === 'tomorrow_plan') {
    return (
      <div className="space-y-4">
        <TomorrowPlanEditor review={review} />
      </div>
    )
  }
  const section = review.content[sectionKey]
  const records = section && typeof section === 'object' ? (section as Record<string, unknown>) : {}
  return <div className="space-y-4">{renderDailySectionContent(sectionKey, records)}</div>
}

function DailyAiProposals({
  review,
  sectionKey,
  onDelete,
}: {
  review: DailyReview
  sectionKey: string
  onDelete: (field: 'ai_notes' | 'ai_actions' | 'linked_evidence', index: number) => void
}) {
  const section = review.content[sectionKey] as Record<string, unknown> | undefined
  const notes = Array.isArray(section?.ai_notes) ? (section!.ai_notes as Record<string, unknown>[]) : []
  const actions = Array.isArray(section?.ai_actions) ? (section!.ai_actions as Record<string, unknown>[]) : []

  if (notes.length === 0 && actions.length === 0) return null

  return (
    <div className="mt-2 space-y-3 rounded-lg border border-blue-100 bg-blue-50/40 p-3">
      <div className="flex items-center gap-2 text-xs font-medium text-blue-700">
        <Sparkles className="h-3.5 w-3.5" />
        AI 提议(待验证,可删除)
      </div>

      {notes.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs font-medium text-slate-500">笔记</div>
          {notes.map((note, idx) => (
            <div
              key={`note-${idx}`}
              className="flex items-start justify-between gap-2 rounded-md bg-white px-3 py-2 text-sm text-slate-700 shadow-sm"
            >
              <div className="min-w-0 flex-1">
                <div className="break-words">{String(note.value ?? '')}</div>
                {typeof note.created_at === 'string' && note.created_at && (
                  <div className="mt-0.5 text-xs text-slate-400">
                    {String(note.created_at).slice(0, 19).replace('T', ' ')}
                  </div>
                )}
              </div>
              <button
                onClick={() => onDelete('ai_notes', idx)}
                className="shrink-0 rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"
                aria-label="删除这条笔记"
                title="删除"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}

      {actions.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-xs font-medium text-slate-500">待验证动作</div>
          {actions.map((action, idx) => (
            <div
              key={`action-${idx}`}
              className="flex items-start justify-between gap-2 rounded-md bg-white px-3 py-2 text-sm text-slate-700 shadow-sm"
            >
              <div className="min-w-0 flex-1">
                <div className="break-words">{String(action.content ?? '')}</div>
                {typeof action.created_at === 'string' && action.created_at && (
                  <div className="mt-0.5 text-xs text-slate-400">
                    {String(action.created_at).slice(0, 19).replace('T', ' ')}
                  </div>
                )}
              </div>
              <button
                onClick={() => onDelete('ai_actions', idx)}
                className="shrink-0 rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"
                aria-label="删除这条待验证动作"
                title="删除"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function renderDailySectionContent(sectionKey: string, records: Record<string, unknown>) {
  if (sectionKey === 'watchlist_review') {
    const pool = records.pool_status as Record<string, unknown> | undefined
    const targets = Array.isArray(records.targets) ? records.targets as Record<string, unknown>[] : []
    return (
      <>
        <div className="grid grid-cols-3 gap-3">
          <TraceField label="关注股票数" value={pool?.holding_count} />
          <TraceField label="本月调入" value={pool?.monthly_added} />
          <TraceField label="本月调出" value={pool?.monthly_removed} />
        </div>
        <DailyTable
          empty="暂无自选股数据，点击数据预填后会从关注股票生成。"
          headers={['标的', '技术形态', '日线趋势', '基本面变化']}
          rows={targets.map((item) => [
            `${item.stock_name ?? ''} ${item.stock_code ?? ''}`,
            readField(item.technical_shape),
            readField(item.daily_trend),
            readField(item.fundamental_change),
          ])}
        />
      </>
    )
  }

  if (sectionKey === 'fundamental_review') {
    const rows = Array.isArray(records.company_rows) ? records.company_rows as Record<string, unknown>[] : []
    const risks = Array.isArray(records.risk_checklist) ? records.risk_checklist as Record<string, unknown>[] : []
    return (
      <>
        <DailyTable
          empty="暂无公司基本面数据，点击数据预填后会从公告、新闻、指标和行情快照生成。"
          headers={['标的', '公告/新闻', '财务风险', '估值位置']}
          rows={rows.map((item) => [
            `${item.stock_name ?? ''} ${item.stock_code ?? ''}`,
            readField(item.announcement_news),
            readField(item.financial_risk),
            readField(item.valuation_position),
          ])}
        />
        <div className="grid grid-cols-2 gap-3">
          {risks.map((risk) => (
            <div key={String(risk.label)} className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700">
              {String(risk.label)}
            </div>
          ))}
        </div>
      </>
    )
  }

  if (sectionKey === 'index_review') {
    const indices = Array.isArray(records.indices) ? records.indices as Record<string, unknown>[] : []

    const aShareNames = new Set(['上证指数', '深证成指', '创业板指', '科创50', '中证2000'])
    const overseasNames = new Set(['纳斯达克', '标普500', '恒生指数', '道琼斯'])

    const aShares = indices.filter((i) => aShareNames.has(String(i.name ?? '')))
    const overseas = indices.filter((i) => overseasNames.has(String(i.name ?? '')))

    function fmtChange(val: unknown): { text: string; cls: string } {
      const t = readField(val)
      if (!t || t === '接口失败') return { text: '—', cls: 'text-slate-300' }
      if (t.startsWith('+')) return { text: t, cls: 'text-red-600' }
      if (t.startsWith('-')) return { text: t, cls: 'text-emerald-600' }
      return { text: t, cls: 'text-slate-700' }
    }

    function fmtVol(turnover: unknown, note: unknown): string {
      const n = readField(note)
      if (n === '接口失败') return '数据暂缺'
      const t = readField(turnover)
      return t || '—'
    }

    function IndexCards({ items }: { items: Record<string, unknown>[] }) {
      return (
        <div className="grid grid-cols-5 gap-2">
          {items.map((item) => {
            const change = fmtChange(item.change_pct)
            const missing = readField(item.note) === '接口失败'
            return (
              <div
                key={String(item.name)}
                className={`rounded-lg border p-3 ${missing ? 'border-dashed border-slate-200 bg-slate-50' : 'border-slate-200 bg-white'}`}
              >
                <div className="text-xs text-slate-500">{String(item.name ?? '')}</div>
                <div className={`mt-1 text-xl font-bold ${change.cls}`}>{change.text}</div>
                <div className="mt-0.5 text-[11px] text-slate-400">{fmtVol(item.turnover, item.note)}</div>
              </div>
            )
          })}
        </div>
      )
    }

    return (
      <div className="space-y-4">
        {aShares.length > 0 && (
          <div>
            <div className="mb-2 text-xs font-semibold text-slate-500 uppercase tracking-wide">A股指数</div>
            <IndexCards items={aShares} />
          </div>
        )}

        {overseas.length > 0 && (
          <div>
            <div className="mb-2 text-xs font-semibold text-slate-500 uppercase tracking-wide">海外市场</div>
            <IndexCards items={overseas} />
          </div>
        )}

        {indices.length === 0 && <EmptyText text="暂无指数数据，点击数据预填后从 AKShare 生成。" />}

        <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
          <div className="text-xs font-medium text-amber-700">领涨指数</div>
          <div className="mt-1 text-sm font-semibold text-amber-900">{readField(records.leading_index) || '待补充'}</div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <TraceField label="市场风格" value={records.market_style} />
          <TraceField label="外部影响" value={records.external_impact} />
        </div>
      </div>
    )
  }

  if (sectionKey === 'hotspot_review') {
    const metrics = records.sentiment_metrics as Record<string, unknown> | undefined
    const sectors = Array.isArray(records.main_sectors) ? records.main_sectors as Record<string, unknown>[] : []
    return (
      <>
        <div className="grid grid-cols-4 gap-3">
          <TraceField label="涨停家数" value={metrics?.limit_up_count} />
          <TraceField label="跌停家数" value={metrics?.limit_down_count} />
          <TraceField label="连板高度" value={metrics?.streak_height} />
          <TraceField label="炸板率" value={metrics?.failed_board_rate} />
        </div>
        <DailyTable
          empty="暂无主线板块记录，可让 AI 根据你的观察整理。"
          headers={['板块', '龙头股', '驱动逻辑', '持续性']}
          rows={sectors.map((item) => [
            readField(item.sector),
            readField(item.leader),
            readField(item.driver),
            readField(item.sustainability),
          ])}
        />
      </>
    )
  }

  if (sectionKey === 'capital_review') {
    const leaders = Array.isArray(records.turnover_leaders) ? records.turnover_leaders as Record<string, unknown>[] : []
    return (
      <>
        <DailyTable
          empty="暂无资金流数据，可点击数据预填从板块资金流榜单生成。"
          headers={['标的/板块', '净额', '类型', '主力意图']}
          rows={leaders.map((item) => [
            readField(item.target),
            readField(item.amount),
            readField(item.sector),
            readField(item.intent),
          ])}
        />
        <div className="grid grid-cols-1 gap-3">
          <TraceField label="资金扎堆方向" value={records.capital_direction} />
        </div>
      </>
    )
  }

  if (sectionKey === 'limit_review') {
    const risks = Array.isArray(records.risk_rows) ? records.risk_rows as Record<string, unknown>[] : []
    const opportunities = Array.isArray(records.opportunity_rows) ? records.opportunity_rows as Record<string, unknown>[] : []
    return (
      <>
        <div className="text-sm font-medium text-slate-700">跌幅榜 — 排雷优先</div>
        <DailyTable
          empty="暂无跌停股池数据。"
          headers={['标的', '跌幅', '所属板块', '原因']}
          rows={risks.map((item) => [
            readField(item.stock),
            readField(item.change_pct),
            readField(item.sector),
            readField(item.reason),
          ])}
        />
        <div className="text-sm font-medium text-slate-700">涨停榜 — 找共性</div>
        <DailyTable
          empty="暂无涨停股池数据。"
          headers={['标的', '连板', '所属板块', '驱动原因']}
          rows={opportunities.map((item) => [
            readField(item.stock),
            readField(item.streak),
            readField(item.sector),
            readField(item.driver),
          ])}
        />
        <div className="grid grid-cols-1 gap-3">
          <TraceField label="共性总结" value={records.common_summary} />
        </div>
      </>
    )
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      {Object.entries(records).map(([key, value]) => (
        <TraceField key={key} label={key} value={value} />
      ))}
    </div>
  )
}

const MARKET_EXPECTATION_OPTIONS = [
  { value: 'bullish', label: '看涨' },
  { value: 'neutral', label: '震荡' },
  { value: 'bearish', label: '看跌' },
]

const POSITION_PLAN_OPTIONS = [
  { value: 'add', label: '加仓' },
  { value: 'reduce', label: '减仓' },
  { value: 'hold', label: '维持' },
]

const OPERATION_DIRECTION_OPTIONS = [
  { value: 'buy', label: '买入' },
  { value: 'sell', label: '卖出' },
  { value: 'add', label: '加仓' },
  { value: 'reduce', label: '减仓' },
  { value: 'hold', label: '持有' },
  { value: 'watch', label: '观望' },
]

const LESSON_TYPE_OPTIONS = [
  '追高', '割肉', '没拿住', '错过', '误判风格', '误判主线', '仓位', '心态',
]

function TomorrowPlanEditor({ review }: { review: DailyReview }) {
  const plan = (review.content.tomorrow_plan as Record<string, unknown>) || {}

  const marketExpectation = readField(plan.market_expectation)
  const positionPlan = readField(plan.position_plan)
  const focusSectors = Array.isArray(plan.focus_sectors) ? (plan.focus_sectors as string[]) : []
  const operationPlan = Array.isArray(plan.operation_plan) ? (plan.operation_plan as Record<string, unknown>[]) : []
  const lessons = Array.isArray(plan.lessons) ? (plan.lessons as Record<string, unknown>[]) : []

  // Candidates from today's hotspot review main sectors
  const hotspot = (review.content.hotspot_review as Record<string, unknown>) || {}
  const mainSectors = Array.isArray(hotspot.main_sectors) ? (hotspot.main_sectors as Record<string, unknown>[]) : []
  const sectorCandidates = mainSectors.map((s) => String(s.sector || '')).filter(Boolean).slice(0, 3)

  const [sectorInput, setSectorInput] = useState('')

  const savePlan = async (patch: Record<string, unknown>) => {
    const nextPlan = { ...plan, ...patch }
    try {
      await updateDailyReview(review.id, { content: { tomorrow_plan: nextPlan } })
    } catch {
      // Silently fail for MVP
    }
  }

  return (
    <div className="space-y-5">
      {/* 明日预期 */}
      <div>
        <div className="mb-2 text-xs font-medium text-slate-500">明日预期</div>
        <div className="flex flex-wrap gap-2">
          {MARKET_EXPECTATION_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() =>
                savePlan({
                  market_expectation: { value: opt.value, source: 'manual', note: '' },
                })
              }
              className={`rounded-lg border px-3 py-1.5 text-sm ${
                marketExpectation === opt.value
                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                  : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* 仓位计划 */}
      <div>
        <div className="mb-2 text-xs font-medium text-slate-500">仓位计划</div>
        <div className="flex flex-wrap gap-2">
          {POSITION_PLAN_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() =>
                savePlan({
                  position_plan: { value: opt.value, source: 'manual', note: '' },
                })
              }
              className={`rounded-lg border px-3 py-1.5 text-sm ${
                positionPlan === opt.value
                  ? 'border-blue-500 bg-blue-50 text-blue-700'
                  : 'border-slate-200 bg-white text-slate-600 hover:bg-slate-50'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* 重点关注板块 */}
      <div>
        <div className="mb-2 text-xs font-medium text-slate-500">重点关注板块</div>
        {sectorCandidates.length > 0 && (
          <div className="mb-2 flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-slate-400">今日主线候选:</span>
            {sectorCandidates.map((s) => (
              <button
                key={s}
                onClick={() => {
                  if (!focusSectors.includes(s)) {
                    savePlan({ focus_sectors: [...focusSectors, s] })
                  }
                }}
                className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600 hover:bg-blue-50 hover:text-blue-600"
              >
                + {s}
              </button>
            ))}
          </div>
        )}
        <div className="flex flex-wrap gap-2">
          {focusSectors.map((s, idx) => (
            <span
              key={`${s}-${idx}`}
              className="flex items-center gap-1 rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs text-blue-700"
            >
              {s}
              <button
                onClick={() => savePlan({ focus_sectors: focusSectors.filter((_, i) => i !== idx) })}
                className="text-blue-400 hover:text-blue-700"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
          <div className="flex items-center gap-1">
            <input
              value={sectorInput}
              onChange={(e) => setSectorInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && sectorInput.trim()) {
                  e.preventDefault()
                  savePlan({ focus_sectors: [...focusSectors, sectorInput.trim()] })
                  setSectorInput('')
                }
              }}
              placeholder="输入板块按回车"
              className="h-8 w-40 rounded-lg border border-slate-200 bg-white px-2 text-sm focus:border-blue-500 focus:outline-none"
            />
          </div>
        </div>
      </div>

      {/* 操作计划表 */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-medium text-slate-500">操作计划表</span>
          <button
            onClick={() =>
              savePlan({
                operation_plan: [
                  ...operationPlan,
                  {
                    stock_code: '',
                    stock_name: '',
                    direction: 'buy',
                    trigger_condition: '',
                    target_price: '',
                    stop_loss: '',
                  },
                ],
              })
            }
            className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
          >
            <Plus className="h-3 w-3" /> 添加
          </button>
        </div>
        {operationPlan.length > 0 ? (
          <table className="w-full text-sm">
            <thead className="border-b border-slate-200">
              <tr className="text-xs text-slate-500">
                <th className="px-2 py-1.5 text-left font-medium">标的</th>
                <th className="px-2 py-1.5 text-left font-medium">方向</th>
                <th className="px-2 py-1.5 text-left font-medium">触发条件</th>
                <th className="px-2 py-1.5 text-left font-medium">目标价</th>
                <th className="px-2 py-1.5 text-left font-medium">止损价</th>
                <th className="px-2 py-1.5 text-left font-medium"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {operationPlan.map((row, idx) => (
                <tr key={idx}>
                  <td className="px-2 py-1">
                    <input
                      value={String(row.stock_name || '')}
                      onChange={(e) => {
                        const next = [...operationPlan]
                        next[idx] = { ...next[idx], stock_name: e.target.value }
                        savePlan({ operation_plan: next })
                      }}
                      placeholder="名称/代码"
                      className="h-7 w-24 rounded border border-slate-200 px-1.5 text-sm focus:border-blue-500 focus:outline-none"
                    />
                  </td>
                  <td className="px-2 py-1">
                    <select
                      value={String(row.direction || 'buy')}
                      onChange={(e) => {
                        const next = [...operationPlan]
                        next[idx] = { ...next[idx], direction: e.target.value }
                        savePlan({ operation_plan: next })
                      }}
                      className="h-7 rounded border border-slate-200 bg-white px-1 text-sm"
                    >
                      {OPERATION_DIRECTION_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="px-2 py-1">
                    <input
                      value={String(row.trigger_condition || '')}
                      onChange={(e) => {
                        const next = [...operationPlan]
                        next[idx] = { ...next[idx], trigger_condition: e.target.value }
                        savePlan({ operation_plan: next })
                      }}
                      placeholder="如 突破20日线"
                      className="h-7 w-32 rounded border border-slate-200 px-1.5 text-sm focus:border-blue-500 focus:outline-none"
                    />
                  </td>
                  <td className="px-2 py-1">
                    <input
                      value={String(row.target_price || '')}
                      onChange={(e) => {
                        const next = [...operationPlan]
                        next[idx] = { ...next[idx], target_price: e.target.value }
                        savePlan({ operation_plan: next })
                      }}
                      placeholder="目标价"
                      className="h-7 w-20 rounded border border-slate-200 px-1.5 text-sm focus:border-blue-500 focus:outline-none"
                    />
                  </td>
                  <td className="px-2 py-1">
                    <input
                      value={String(row.stop_loss || '')}
                      onChange={(e) => {
                        const next = [...operationPlan]
                        next[idx] = { ...next[idx], stop_loss: e.target.value }
                        savePlan({ operation_plan: next })
                      }}
                      placeholder="止损价"
                      className="h-7 w-20 rounded border border-slate-200 px-1.5 text-sm focus:border-blue-500 focus:outline-none"
                    />
                  </td>
                  <td className="px-2 py-1">
                    <button
                      onClick={() => savePlan({ operation_plan: operationPlan.filter((_, i) => i !== idx) })}
                      className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <EmptyText text="点击右上角添加按钮录入操作计划" />
        )}
      </div>

      {/* 今日教训 */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-xs font-medium text-slate-500">今日教训</span>
          <button
            onClick={() => savePlan({ lessons: [...lessons, { lesson_type: '', description: '' }] })}
            className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600 hover:bg-slate-50"
          >
            <Plus className="h-3 w-3" /> 添加
          </button>
        </div>
        {lessons.length > 0 ? (
          <div className="space-y-2">
            {lessons.map((lesson, idx) => (
              <div
                key={idx}
                className="flex items-start gap-2 rounded-lg border border-slate-200 bg-white p-2"
              >
                <select
                  value={String(lesson.lesson_type || '')}
                  onChange={(e) => {
                    const next = [...lessons]
                    next[idx] = { ...next[idx], lesson_type: e.target.value }
                    savePlan({ lessons: next })
                  }}
                  className="h-8 shrink-0 rounded border border-slate-200 bg-white px-2 text-sm"
                >
                  <option value="">选择类型</option>
                  {LESSON_TYPE_OPTIONS.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
                <input
                  value={String(lesson.description || '')}
                  onChange={(e) => {
                    const next = [...lessons]
                    next[idx] = { ...next[idx], description: e.target.value }
                    savePlan({ lessons: next })
                  }}
                  placeholder="描述具体发生了什么..."
                  className="h-8 flex-1 rounded border border-slate-200 px-2 text-sm focus:border-blue-500 focus:outline-none"
                />
                <button
                  onClick={() => savePlan({ lessons: lessons.filter((_, i) => i !== idx) })}
                  className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <EmptyText text="点击右上角添加按钮录入今日教训（建议至少1条）" />
        )}
      </div>
    </div>
  )
}

function TraceField({ label, value }: { label: string; value: unknown }) {
  const source = readSource(value)
  return (
    <div className="rounded-lg border border-slate-200 p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-slate-500">{label}</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">{sourceLabel(source)}</span>
      </div>
      <div className="min-h-[20px] text-sm leading-relaxed text-slate-800">{readField(value) || '待补充'}</div>
    </div>
  )
}

function DailyTable({ empty, headers, rows }: { empty: string; headers: string[]; rows: string[][] }) {
  if (rows.length === 0) return <EmptyText text={empty} />
  return (
    <table className="w-full text-sm">
      <thead className="border-b border-slate-200">
        <tr className="text-xs text-slate-500">
          {headers.map((header) => (
            <th key={header} className="px-3 py-2 text-left font-medium">{header}</th>
          ))}
        </tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {rows.map((row, rowIndex) => (
          <tr key={rowIndex} className="hover:bg-slate-50">
            {row.map((cell, cellIndex) => (
              <td key={`${rowIndex}-${cellIndex}`} className="px-3 py-2 text-slate-700">{cell || '待补充'}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function DailyReviewAiPanel({
  review,
  sectionKey,
  message,
  reply,
  actions,
  evidenceCards,
  error,
  loading,
  onMessageChange,
  onSubmit,
  onApply,
  onDismiss,
}: {
  review: DailyReview | null
  sectionKey: string
  message: string
  reply: string
  actions: AiAction[]
  evidenceCards: EvidenceCard[]
  error: string
  loading: boolean
  onMessageChange: (value: string) => void
  onSubmit: (event: FormEvent) => void
  onApply: (action: AiAction, index: number) => void
  onDismiss: (index: number) => void
}) {
  const section = DAILY_SECTIONS.find((item) => item.key === sectionKey)
  return (
    <>
      <div className="border-b border-slate-100 px-4 py-2 text-xs text-slate-500">
        围绕当前 section 追问，并生成待保存成果
      </div>
      <div className="flex-1 overflow-y-auto p-4">
        {!review ? (
          <EmptyText text="先打开当天复盘模板" />
        ) : (
          <div className="space-y-4">
            <div className="rounded-lg bg-slate-50 p-3 text-sm leading-relaxed text-slate-600">
              当前复盘：<span className="font-medium text-slate-900">{review.reviewDate}</span>
              <br />
              当前模块：<span className="font-medium text-slate-900">{section?.label}</span>
            </div>
            {reply && <div className="rounded-lg border border-blue-100 bg-blue-50 p-3 text-sm leading-relaxed text-blue-800">{reply}</div>}
            {error && <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm leading-relaxed text-red-700">{error}</div>}
            {evidenceCards.length > 0 && (
              <div className="space-y-2">
                <div className="flex items-center gap-2 text-xs font-medium text-slate-500">
                  <Database className="h-4 w-4" />
                  本次使用证据
                </div>
                {evidenceCards.slice(0, 5).map((card, index) => (
                  <EvidenceCardView key={`${card.sourceProvider}-${index}`} card={card} compact />
                ))}
              </div>
            )}
            <div className="space-y-3">
              {Array.isArray(actions) && actions.map((action, index) => (
                <AiActionCard
                  key={`${action.type}-${index}`}
                  action={action}
                  onApply={() => onApply(action, index)}
                  onDismiss={() => onDismiss(index)}
                />
              ))}
            </div>
          </div>
        )}
      </div>
      <form onSubmit={onSubmit} className="shrink-0 border-t border-slate-200 p-4">
        <textarea
          value={message}
          onChange={(event) => onMessageChange(event.target.value)}
          placeholder="例如：今天 AI 算力继续扩散，但成交额集中度不够，我不确定是不是主线"
          className="min-h-[88px] w-full resize-none rounded-lg border border-slate-200 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-500/20"
          disabled={!review || loading}
        />
        <button
          className="mt-3 flex h-9 w-full items-center justify-center gap-1.5 rounded-lg bg-blue-600 text-sm font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={!review || loading || !message.trim()}
        >
          <Save className="h-4 w-4" />
          {loading ? '整理中...' : '生成复盘成果'}
        </button>
      </form>
    </>
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
            : action.type === 'update_daily_review_section'
              ? '更新每日复盘模块'
              : action.type === 'create_daily_review_action'
                ? '新增复盘观察项'
                : action.type === 'link_evidence_to_daily_review'
                  ? '关联证据到复盘'
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
  if (action.type === 'update_daily_review_section') {
    return typeof action.payload.section_key === 'string' ? `更新 ${action.payload.section_key} 模块` : '更新每日复盘模块'
  }
  if (action.type === 'create_daily_review_action') {
    return typeof action.payload.content === 'string' ? action.payload.content : '新增一条复盘观察项'
  }
  if (action.type === 'link_evidence_to_daily_review') {
    return '把这条证据关联到当前每日复盘模块'
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
