---
title: 项目当前状态快照
date: 2026-05-21
phase: 0 完成，1 待开始
---

# 项目当前状态（State of the Union）

**本文件作用**: 对话中断后，新对话打开时先读此文件，秒级恢复上下文。

---

## 一句话状态

**Phase 0 基础设施全部完成。后端股票池 CRUD + 前端列表页已上线 staging。Phase 1 业务功能（投资假设管理）待开发。**

---

## 已完成 ✅

### 基础设施（Phase 0）

| 模块 | 状态 | URL/产物 |
|---|---|---|
| GitHub 仓库 | ✅ | https://github.com/zhaoxinren0924-bot/stock-review-alpha-assistant |
| CI/CD | ✅ | GitHub Actions: ruff/mypy/pytest + tsc/build + secret scan |
| 分支保护 | ✅ | master 必须通过 PR + 3 status checks |
| Staging 部署 | ✅ | https://stock-review-api.onrender.com |
| 错误监控 | ✅ | Rollbar（已验证收到错误） |
| 可用性监控 | ✅ | UptimeRobot（每 5 分钟轮询） |
| 数据库备份 | ✅ | `scripts/backup.py` |
| 单命令启动 | ✅ | `python main.py` |

### 业务功能（已实现）

| 功能 | 状态 | 说明 |
|---|---|---|
| 股票池 CRUD | ✅ | 添加/列表/详情/删除股票 |
| 股票列表页 | ✅ | 前端卡片展示 + 添加弹窗 + 删除 |

---

## 待开发 📋（Phase 1）

按优先级排序：

| 优先级 | 功能 | 说明 | 预估工作量 |
|---|---|---|---|
| **P0** | 投资假设管理 | 六框架录入（生意/财务/成长/估值/风险/催化） | 2-3 天 |
| **P0** | 单股票详情页 | 点击股票进入假设管理页面 | 1 天 |
| **P1** | 持仓记录 | 成本/数量/买入日期，计算浮盈亏 | 1-2 天 |
| **P1** | AI 对话窗口 | 右侧聊天面板，自然语言→结构化成果 | 2-3 天 |
| **P2** | 接入 a-stock-data | 自动回填股票名称/行业/行情 | 1 天 |
| **P2** | 前端静态站点部署 | Render Static Site（Blueprint 不支持，需手动） | 0.5 天 |
| **P3** | 个人规则系统 | 投资规则录入与检查 | 2 天 |

---

## 技术债务（已知）

| 问题 | 影响 | 解决时机 |
|---|---|---|
| Render 免费版数据库会重置 | 重新部署后数据丢失 | 接入持久化磁盘 或 定期外部备份 |
| 前端 proxy 硬编码 localhost:8000 | 生产环境 API 调用失败 | 前端静态站点部署时统一处理 |
| 没有前端路由 | 单页面，无法 URL 直达股票详情 | 添加 React Router 时解决 |
| 没有用户认证 | 单用户，数据无隔离 | 多用户支持时再考虑 |

---

## 环境信息

| 项目 | 值 |
|---|---|
| 后端 URL (staging) | https://stock-review-api.onrender.com |
| 后端 URL (本地) | http://localhost:8000 |
| 前端 URL (本地) | http://localhost:5173 |
| 数据库 | SQLite (`data/portfolio.db`) |
| 默认分支 | `master` |
| 部署方式 | Render Blueprint (auto-sync from GitHub) |

---

## 快速启动命令

```bash
# 本地开发
python main.py

# 数据库备份
python scripts/backup.py

# 从备份恢复
python scripts/backup.py --restore data/backups/portfolio_YYYYMMDD_HHMMSS.db
```

---

## 最近一次变更

- 2026-05-21: Phase 0 完成，股票池 CRUD 上线 staging
- 2026-05-21: 复盘文档 `decisions/0002-phase0-retrospective.md` 完成

---

## 下一步建议（默认从这里开始）

**推荐先做：投资假设管理（六框架）**

原因：
1. 这是产品的核心价值（第一次打开就要能用）
2. 不依赖外部数据源（纯本地数据即可闭环）
3. 有了假设之后，AI 复盘、新闻影响判断才有上下文

**技术路线**：
1. 后端：Hypothesis 模型的 CRUD API（已存在模型，只需加路由）
2. 前端：单股票详情页 + 假设卡片（分类展示/添加/编辑/删除）
3. 数据库：已就绪（`hypotheses` 表已定义）
