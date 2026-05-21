import { useEffect, useState } from 'react'

function App() {
  const [health, setHealth] = useState<string>('checking...')

  useEffect(() => {
    fetch('/api/health')
      .then((res) => res.json())
      .then((data) => setHealth(data.status))
      .catch(() => setHealth('offline'))
  }, [])

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-lg p-8 max-w-md w-full">
        <h1 className="text-2xl font-bold text-slate-900 mb-2">
          Stock Review Alpha
        </h1>
        <p className="text-slate-500 mb-6">
          A股基本面复盘智能助手
        </p>

        <div className="space-y-3">
          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
            <span className="text-sm font-medium text-slate-700">前端状态</span>
            <span className="text-sm font-semibold text-green-600">运行中</span>
          </div>

          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
            <span className="text-sm font-medium text-slate-700">后端状态</span>
            <span className={`text-sm font-semibold ${
              health === 'healthy' ? 'text-green-600' : 'text-amber-600'
            }`}>
              {health === 'healthy' ? '健康' : health}
            </span>
          </div>

          <div className="flex items-center justify-between p-3 bg-slate-50 rounded-lg">
            <span className="text-sm font-medium text-slate-700">版本</span>
            <span className="text-sm text-slate-500">v0.1.0</span>
          </div>
        </div>

        <p className="text-xs text-slate-400 mt-6 text-center">
          基础设施建设完成，等待业务功能接入
        </p>
      </div>
    </div>
  )
}

export default App
