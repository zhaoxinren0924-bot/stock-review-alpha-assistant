# AI 右栏改动前检查清单

任何影响右侧 AI 复盘引导器、`/api/v1/ai/chat`、`/api/v1/ai/actions/apply`、证据卡、前端 service 层的改动，写代码前先过这张表。

## 写代码前

1. 明确用户动作链路：选择股票 → 输入想法或点击证据卡 → 生成 `reply/actions/evidence_cards` → 点击保存 → 刷新假设/检查项/复盘。
2. 确认 API 契约：`ai/chat` 必须返回 `reply`、`actions`、`evidence_cards`，旧字段不能突然删除。
3. 确认降级行为：没有外部证据时必须显示“当前证据不足”，但仍允许整理用户观点。
4. 确认保存边界：AI 只能返回待确认 actions，不能自动改用户假设。
5. 确认前端容错：字段缺失、请求失败、保存失败都要在右栏显示错误。
6. 如果涉及数据源，确认免费源失败不会阻断整个页面。

## 写代码后

1. 后端测试：`backend\venv\Scripts\python.exe -m pytest`
2. 后端静态检查：`backend\venv\Scripts\python.exe -m ruff check backend\app backend\tests`
3. 类型检查：`backend\venv\Scripts\python.exe -m mypy backend\app backend\tests`
4. 前端构建：`npm run build`
5. 右栏 smoke check：`powershell -ExecutionPolicy Bypass -File scripts\check_ai_right_panel.ps1`

## 手动验收

1. 打开 `http://127.0.0.1:5173`。
2. 选择任意股票。
3. 点击“刷新数据”，页面应展示公告/新闻、指标、行情快照或结构化错误。
4. 在右栏输入：“我看好 AI 算力链，帮我整理成可验证假设”。
5. 页面应展示 AI 回复和至少一个“待保存成果”。
6. 点击证据卡后，右栏输入框应带入证据上下文。
7. 点击“保存成果”后，主内容区的假设、检查项或复盘应刷新。
