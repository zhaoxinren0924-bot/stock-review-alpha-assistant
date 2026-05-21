import { useEffect, useState } from 'react'
import { Plus, Trash2, Building2, TrendingUp, X } from 'lucide-react'

interface Stock {
  code: string
  name: string
  industry: string | null
  market: string | null
  created_at: string
}

function App() {
  const [stocks, setStocks] = useState<Stock[]>([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState({ code: '', name: '', industry: '', market: 'SH' })
  const [error, setError] = useState('')

  const fetchStocks = async () => {
    try {
      const res = await fetch('/api/v1/stocks')
      const data = await res.json()
      setStocks(data.stocks)
    } catch {
      setStocks([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStocks()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError('')
    try {
      const res = await fetch('/api/v1/stocks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      })
      if (!res.ok) {
        const data = await res.json()
        setError(data.detail || '添加失败')
        return
      }
      setForm({ code: '', name: '', industry: '', market: 'SH' })
      setShowAdd(false)
      fetchStocks()
    } catch {
      setError('网络错误')
    }
  }

  const handleDelete = async (code: string) => {
    if (!confirm(`确定删除 ${code}？`)) return
    try {
      await fetch(`/api/v1/stocks/${code}`, { method: 'DELETE' })
      fetchStocks()
    } catch {
      alert('删除失败')
    }
  }

  const marketLabel = (m: string | null) => {
    const map: Record<string, string> = { SH: '沪', SZ: '深', BJ: '北交' }
    return map[m || ''] || m || '-'
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-slate-900">股票池</h1>
            <p className="text-sm text-slate-500">管理你关注的公司</p>
          </div>
          <button
            onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800 transition-colors"
          >
            <Plus className="w-4 h-4" />
            添加股票
          </button>
        </div>
      </header>

      {/* Main */}
      <main className="max-w-4xl mx-auto px-4 py-6">
        {loading ? (
          <div className="text-center py-20 text-slate-400">加载中...</div>
        ) : stocks.length === 0 ? (
          <div className="text-center py-20">
            <Building2 className="w-12 h-12 text-slate-300 mx-auto mb-4" />
            <p className="text-slate-500 mb-2">还没有关注任何股票</p>
            <p className="text-sm text-slate-400">点击右上角添加你的第一只股票</p>
          </div>
        ) : (
          <div className="grid gap-3">
            {stocks.map((stock) => (
              <div
                key={stock.code}
                className="bg-white rounded-xl border border-slate-200 p-4 flex items-center justify-between hover:shadow-sm transition-shadow"
              >
                <div className="flex items-center gap-4">
                  <div className="w-10 h-10 bg-slate-100 rounded-lg flex items-center justify-center">
                    <TrendingUp className="w-5 h-5 text-slate-600" />
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-900">{stock.name}</span>
                      <span className="text-xs px-2 py-0.5 bg-slate-100 text-slate-600 rounded-full">
                        {stock.code}
                      </span>
                      <span className="text-xs px-2 py-0.5 bg-blue-50 text-blue-600 rounded-full">
                        {marketLabel(stock.market)}
                      </span>
                    </div>
                    {stock.industry && (
                      <p className="text-sm text-slate-500 mt-0.5">{stock.industry}</p>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => handleDelete(stock.code)}
                  className="p-2 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors"
                  title="删除"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* Add Modal */}
      {showAdd && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl w-full max-w-md shadow-xl">
            <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100">
              <h2 className="font-semibold text-slate-900">添加股票</h2>
              <button
                onClick={() => { setShowAdd(false); setError('') }}
                className="p-1 text-slate-400 hover:text-slate-600 rounded"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="p-5 space-y-4">
              {error && (
                <div className="text-sm text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</div>
              )}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">股票代码</label>
                <input
                  type="text"
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  placeholder="如: 600519"
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-transparent"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">股票名称</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="如: 贵州茅台"
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-transparent"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">所属行业</label>
                <input
                  type="text"
                  value={form.industry}
                  onChange={(e) => setForm({ ...form, industry: e.target.value })}
                  placeholder="如: 白酒"
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-transparent"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">市场</label>
                <select
                  value={form.market}
                  onChange={(e) => setForm({ ...form, market: e.target.value })}
                  className="w-full px-3 py-2 border border-slate-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 focus:border-transparent"
                >
                  <option value="SH">上海 (SH)</option>
                  <option value="SZ">深圳 (SZ)</option>
                  <option value="BJ">北京 (BJ)</option>
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => { setShowAdd(false); setError('') }}
                  className="flex-1 px-4 py-2 border border-slate-200 text-slate-700 text-sm font-medium rounded-lg hover:bg-slate-50 transition-colors"
                >
                  取消
                </button>
                <button
                  type="submit"
                  className="flex-1 px-4 py-2 bg-slate-900 text-white text-sm font-medium rounded-lg hover:bg-slate-800 transition-colors"
                >
                  确认添加
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}

export default App