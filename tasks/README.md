# 任务卡索引（修订版）

## 总览

| 任务 | Round | 内容 | 预估 | 依赖 | 状态 |
|---|---|---|---|---|---|
| [T-001](T-001.md) | Round 1 | 前端基础设施（shadcn/ui + Router + 目录结构） | 3h | — | 待开始 |
| [T-002](T-002.md) | Round 1 | 后端模型重构（user_id + 约束变更 + 4层架构表） | 4h | — | 待开始 |
| [T-003](T-003.md) | Round 2 | 三栏布局系统（可调宽度 + 拖拽 + 折叠 + 持久化） | 6h | T-001 | 待开始 |
| [T-004](T-004.md) | Round 2 | 后端 CRUD API（Hypothesis + Position + Review + CheckItem） | 6h | T-002 | 待开始 |
| [T-005](T-005.md) | Round 3 | 左侧边栏（导航 + 股票列表 + 用户区） | 4h | T-003 | 待开始 |
| [T-006](T-006.md) | Round 3 | 概览区域（标题栏 + 状态概览 + 持仓 + 复盘表格） | 5h | T-003 | 待开始 |
| [T-007](T-007.md) | Round 3 | 六框架卡片（6张完整实现） | 6h | T-003 | 待开始 |
| [T-008](T-008.md) | Round 4 | AI 对话组件（消息列表 + 输入框 + 快捷按钮） | 5h | T-003 | 待开始 |
| [T-009](T-009.md) | Round 4 | AI 成果卡系统（AISuggestedActionCard + 待保存成果） | 5h | T-003, T-008 | 待开始 |
| [T-010](T-010.md) | Round 4 | AI 后端服务（Claude API + actions apply） | 6h | T-004, T-009 | 待开始 |
| [T-011](T-011.md) | Round 5 | 假设管理交互（新增/编辑弹窗 + 表单 + 状态变更） | 5h | T-004, T-007 | 待开始 |
| [T-012](T-012.md) | Round 5 | 复盘与检查项（季度复盘 + 检查项管理） | 4h | T-004, T-006 | 待开始 |

**总计预估：约 59 小时（7-8 个工作日）**

---

## Round 定义

| Round | 目标 | 任务 | 可并行？ |
|---|---|---|---|
| **Round 1** | 基础设施 | T-001, T-002 | ✅ 前后端完全并行 |
| **Round 2** | 核心骨架 | T-003, T-004 | ✅ 前后端并行 |
| **Round 3** | 页面内容 | T-005, T-006, T-007 | ⚠️ 前端串行（组件复用）|
| **Round 4** | AI 面板 | T-008, T-009, T-010 | ⚠️ T-008→T-009→T-010 串行 |
| **Round 5** | 交互闭环 | T-011, T-012 | ✅ 可并行 |

---

## 关键里程碑

1. **Round 1 完成** → shadcn/ui 就绪，数据库模型更新完成
2. **Round 2 完成** → 浏览器能看到可调三栏，API 可调用
3. **Round 3 完成** → 设计图视觉还原 80%，六框架完整展示
4. **Round 4 完成** → AI 对话可用，成果可保存
5. **Round 5 完成** → 完整操作闭环：添加股票 → 录入假设 → AI 对话 → 保存成果 → 季度复盘

---

## 共享上下文文档

每个 Agent 启动时必须传入对应文档：

| Agent 类型 | 必须文档 |
|---|---|
| 前端 Agent | `docs/design-system.md` + `docs/api-contract.md`（§1, §7）|
| 后端 Agent | `docs/api-contract.md` + `docs/data-architecture.md` |
| AI 功能 Agent | `docs/api-contract.md`（§5 AI API）+ `docs/design-system.md`（§6.1 AI成果卡）|
