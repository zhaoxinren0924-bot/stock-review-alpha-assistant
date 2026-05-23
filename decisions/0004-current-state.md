---
title: 项目当前状态快照(取代 0003)
date: 2026-05-23
phase: Phase 1 进行中(代码框架已成,等端到端验证)
supersedes: 0003-current-state.md
---

# 项目当前状态(State of the Union)

**本文件作用**: 对话中断后,新对话打开时先读此文件,秒级恢复上下文。
**0003 已过时**(2026-05-21 快照),后续以本文件为准。

---

## 一句话状态

**Phase 1 核心代码已经搭起来了**:后端 29 个 v1 路由(含 AI chat / actions)、LLM provider + 数据源双层适配器、前端三栏布局 + 六框架卡 + AI 右面板 — 但还没经过端到端跑通验证,任务卡状态没维护,测试本地暂跑不起来。

---

## 已完成 ✅

### Phase 0 — 基础设施(无变化)

GitHub / CI / 分支保护 / Render Staging / Rollbar / UptimeRobot / 备份脚本 / 单命令启动 — 见 [0003](0003-current-state.md) 历史快照。

### Phase 1 — 核心业务代码(本轮新增,2026-05-22~23)

5 个 commit 落地(9e4ac30 → a2dd4d5):

| 模块 | 状态 | 关键点 |
|---|---|---|
| 数据模型扩展 | ✅ 代码 | RawSource / Evidence / Event / Metric / Quote / CheckItem / Review / AISuggestedAction / ResearchTrace;positions 加 user_id 唯一约束 |
| 数据源适配器 | ✅ 代码 | akshare / baostock / tushare 三个 Adapter,统一 `DataSourceAdapter` 协议;`data_refresh.py` 串成 Pandas → SQLite ETL |
| LLM provider 抽象 | ✅ 代码 | `ChatProvider` 协议 + factory,支持 anthropic / minimax(anthropic 协议) / openai-compatible 切换;env 变量 `LLM_PROVIDER` 控制 |
| 调度器 | ✅ 代码 | `scheduler.py`(APScheduler)— 周期刷新数据 |
| 后端 API | ✅ 代码 | 29 个 v1 路由:股票池 + Hypothesis CRUD + CheckItem CRUD + Review CRUD + 数据刷新 + evidence/events/metrics/quotes 只读 + `/ai/chat` + `/ai/provider-status` + `/ai/actions/apply` |
| 前端三栏布局 | ✅ 代码 | App.tsx 213→923 行:左侧导航 + 中央六框架卡 + 右侧 AI 面板 + AISuggestedActionCard |
| 前端 service 拆分 | ✅ 代码 | api / stock / data / ai / research 5 个 service 文件 |
| 后端测试 | ✅ 代码 | test_ai_actions / test_llm_provider / test_research_loop / test_data_driven_research,test_main 已更新 |
| 设计文档 | ✅ | docs/ 下 7 篇:design-system / api-contract / data-architecture / investment-themes / LLM_PROVIDER_INTERFACE / DATA_DRIVEN_RESEARCH_ASSISTANT / AI_RIGHT_PANEL_CHECKLIST |
| 任务卡 | ✅ 模板 | tasks/T-001..T-014,5 个 Round 编排 |

---

## 进行中 / 未验证 ⚠️

| 项 | 状态 | 备注 |
|---|---|---|
| **本地 pytest 跑通** | ❌ | `ModuleNotFoundError: No module named 'rollbar'` — 本地 venv 没装齐 requirements.txt,5 个测试文件 collection error |
| **CI 是否绿** | ❓ | 5 个新 commit 推上去后还没看 GitHub Actions 结果 |
| **端到端 demo** | ❌ | 添加股票 → 录入假设 → AI 对话 → 保存成果 → 季度复盘 这个闭环没有人工跑过一遍 |
| **Staging 部署** | ❓ | Render auto-sync 触发后是否成功未确认 |
| **AI provider 实测** | ❌ | MiniMax / Anthropic 真实 API 调用是否能拉通,只看代码无法判断 |
| **任务卡真实状态** | ❌ | tasks/README.md 14 张卡全标"待开始",但代码已经实现了 T-001 / T-002 / T-003 / T-004 / T-007 / T-008 / T-009 / T-010 的大部分 — 卡和实物脱节 |

---

## 已知技术债

| 问题 | 影响 | 建议解决时机 |
|---|---|---|
| Render 免费版数据库会重置 | 重新部署后数据丢失 | 接入持久化磁盘 或 定期外部备份 |
| 前端 proxy 硬编码 localhost:8000 | 生产 API 调用失败 | 静态站点部署时统一处理 |
| 没有前端路由 | 单页面,无法 URL 直达股票详情 | 引入 React Router |
| 没有用户认证 | 单用户,数据无隔离 | positions/hypotheses 已加 user_id 字段,等多用户化 |
| 任务卡状态字段是 `[ 待开始 / 进行中 / ... ]` 模板占位 | 任务追踪无效 | 立刻补一次 |
| CRLF 换行警告 | 本地 Windows 与仓库 LF 不一致 | 加 `.gitattributes` 或忽略 |

---

## 环境信息

| 项目 | 值 |
|---|---|
| 后端 URL (staging) | https://stock-review-api.onrender.com |
| 后端 URL (本地) | http://localhost:8000 |
| 前端 URL (本地) | http://localhost:5173 |
| 数据库 | SQLite (`data/portfolio.db`),支持 `DATABASE_URL` 环境变量 override |
| LLM 默认 provider | `LLM_PROVIDER=minimax`(env 配置) |
| 默认分支 | `master` |
| 部署方式 | Render Blueprint (auto-sync from GitHub) |

---

## 快速启动命令

```bash
# 本地开发(单命令)
python main.py

# 装依赖(本地测试失败时先跑这个)
pip install -r backend/requirements.txt

# 跑测试
python -m pytest backend/tests/ -v

# 数据库备份
python scripts/backup.py
```

---

## 最近一次变更

- 2026-05-23: 拆出 5 个 commit(数据层 / services / API / 前端 / docs),把 2600+ 行未提交工作落库;新建本快照 0004 取代 0003
- 2026-05-21: Phase 0 完成,股票池 CRUD 上线 staging(原 0003)

---

## 下一步建议(默认从这里开始)

按优先级:

1. **跑通本地测试** — 先 `pip install -r backend/requirements.txt`,确认 5 个测试文件能 collect、能过。这是最便宜的健康检查。
2. **手动跑一次端到端 demo** — 启动 `python main.py`,在浏览器里:添加一只股票 → 录入一条六框架假设 → 在右侧 AI 面板问"这家公司毛利率怎么样" → 把 AI 返回的成果卡保存成 hypothesis → 写一条季度 review。能跑通就证明骨架对。
3. **维护任务卡状态** — 把 T-001/T-002/T-003/T-004/T-007/T-008/T-009/T-010 标 ✅,剩下的标真实进度。否则下次再写 5 张新卡时,旧卡会持续误导。
4. **验证 LLM provider 真实调用** — `curl /api/v1/ai/provider-status` + 一次真实 chat 调用,确认 MiniMax key 与 Anthropic key 能拉通。
5. **看 GitHub Actions** — `gh run list -L 5`,确认本轮 5 个 commit 的 CI 都绿。如果红,先修。
6. **Phase 1 收尾** — T-011(假设管理交互)+ T-012(复盘与检查项)还没动,做完才算闭环。

**不建议现在做的**:加新功能、接外部付费数据源、加用户认证。先把已有的跑通。
