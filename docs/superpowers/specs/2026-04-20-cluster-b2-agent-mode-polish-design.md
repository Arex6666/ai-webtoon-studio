# Cluster B2: Agent 模式独立完善设计

**Date:** 2026-04-20
**Status:** Draft, pending user review
**Scope:** 补齐 Agent 对话创作模式的可靠性、反馈、导航、工具补全。11 个特性 / ~24 tasks。

---

## 1. 背景

Cluster B1 打通了 Agent → Studio 的数据桥。审计发现 Agent 模式本身仍有阻塞级缺口：

- **B1 的 lean-payload fallback 没有真数据源**：`conversation_reader` 预期从 `entities_json.card` 读取 `panels/characters/scenes/art_style` 四种 card type，但**当前 agent 后端根本不写这些 card**。Bulk commit 只能靠前端发现的"episode_pipeline card"绕弯子（B1-Task 14 的补救）
- **图片和视频都是 Doubao 临时 URL**，会过期；commit 之前用户看到的图随时会 404
- **长 LLM 调用（30+秒）无进度反馈**，UI 看起来冻死
- **生成失败无重试 UI**，用户卡死
- **EpisodeTree 组件是死代码**，没接入任何页面

Cluster B2 解决这些问题，让 Agent 模式独立可靠、专业。

## 2. 目标

- **可靠**：图片/视频在生成完成即落 MinIO，永不过期；card 类型写入 conversation，让 B1 的 lean-payload 真正可用
- **反馈**：长操作（script generation、panel image generation）有实时进度（SSE）
- **可恢复**：生成失败有明确错误 UI + 重试按钮
- **可导航**：EpisodeTree 接入 episode 详情页，phase 状态从 DB 真实映射
- **对话能力完整**：删除、切换对话历史、重新生成、真实进度指示
- **工具链接通**：3 个核心 tool handler 落地（render_panels、analyze_quality、suggest_fixes）

## 3. 当前真实状态（审计结论）

| 模块 | 现状 | 问题 |
|---|---|---|
| `/agent/episode/{N}/generate-panels` | 同步调 Doubao，返回 `image_url: string` | 临时 URL，会过期；不写 card |
| `agent_orchestrator` 写 `entities_json` | 仅写通用 `intent_result.entities` | 不写 B1 期望的 card 格式 |
| `/agent/episode/{N}/script` | 同步 POST，30+秒才返回 | 无 SSE / 无进度 |
| Episode detail `page.tsx` | 有 `generationError` state | 未渲染 UI / 无重试按钮 |
| `EpisodeTree.tsx` | 存在但从未 import | 死代码 |
| 消息删除 | `/agent/[pid]/page.tsx:564` 实现了 | episode 页没实现 |
| 对话切换 | 无 | 用户切对话要 URL 手动改 |
| `tool_handlers.py:131,379,413,463,502` | 5 个 TODO stub | 工具调用静默失败 |
| `panelProgress` state（episode page） | 定义了没用 | UI 只显示 "…" |
| commit warnings | B1-Task 13 toast 了一个"N 条警告"总数 | 没展示具体哪张图失败 |

## 4. 设计决策记录

| # | 决策 | 理由 |
|---|---|---|
| D1 | Card types **沿用** `characters / scenes / panels / art_style`（B1 定的） | 和 B1 conversation_reader 无缝衔接，不返工 |
| D2 | **图片和视频都在生成完成即同步持久化到 MinIO**。返回的 URL 是 MinIO 预签名 URL 或 key | 一劳永逸；commit、重渲染、导出都不再依赖 Doubao 临时 URL |
| D3 | 长 LLM 调用用 **SSE**（`text/event-stream`）；FastAPI `StreamingResponse` + Starlette | Next.js App Router 对 SSE 原生支持好；比 polling 少连接开销 |
| D4 | EpisodeTree **保留**，**phase 状态从 DB 真实映射**：读 chapter+panel 派生 script/storyboard/assets/render/qa/export 每项的 status | 让已有的漂亮 UI 变成真数据驱动 |
| D5 | Tool handler 补全选 3 个：`render_panels`、`analyze_quality`、`suggest_fixes`。其他 2 个（`refine_script`、`get_render_status`）memory 显示已实现，再核验 | 有限资源优先给"Agent 能实际驱动渲染+QA+修复"的核心闭环 |
| D6 | Regenerate 统一入口：每个 agent 生成的消息 card 加【重新生成】按钮；参数编辑改用 inline 编辑弹层 | UX 符合专业工具对话式操作惯例 |
| D7 | 进度展示：`panelProgress` 绑定真数据 + 文字 "3/7 · 等待..." + 条形进度 | 专业进度条而非 spinner |
| D8 | SSE 事件 schema 统一 = `{ event: 'progress', data: '...' }` / `{ event: 'chunk', data: '...' }` / `{ event: 'done', data: '{json}' }` / `{ event: 'error', data: '{msg}' }` | 后续其他 agent route 复用同一 pattern |
| D9 | MinIO key 结构：`agent-media/{project_id}/{conversation_id}/ep{N}/{kind}/{safe_name}-{uuid}{ext}`（kind ∈ character/scene/panel/video） | 可追溯 + 可 project 级批量清理 |

## 5. 范围

### 5.1 B2-1 — Agent 写 card types

**作用**：让 conversation_reader 有真数据源，并作为前端列表页的显示来源。

**后端改动**（`app/services/conversation/agent_orchestrator.py` 或在 `agent.py` 各 endpoint 内）：

- 完成 `generate-panels` 后，往 conversation 追加一条 `assistant` 消息，`entities_json = { card: { type: "panels", episode_number: N, panels: [...] } }`
- 完成 script generation 后，追加 `characters`、`scenes` 两张 card（字段见 spec B1 §5.2）
- 在 `intent`/`outline` 阶段得到风格信息时写 `art_style` card
- Card 的 `temp_image_url` 字段**必须填 MinIO key**（B2-2 合作）

**新增 helper**：`services/agent_commit/card_writer.py` — 纯函数，输入实体数据 + conversation_id，返回 `ConversationMessage` 实例（不直接 commit）。调用方（agent 端点）使用统一 session。

### 5.2 B2-2 — 媒体 MinIO 持久化（图片 + 视频）

**作用**：Agent 生成的每张图、每段视频在生成完成立即下载到 MinIO。返回 URL 始终是 MinIO 预签名或 key。

**后端改动**：

1. **图片路径**（`/agent/episode/{N}/generate-panels` at `agent.py:737-793`）：
   - 生成成功后，对每个 `PanelResult`，调用 `agent_commit.image_fetcher.fetch_and_persist`（Cluster B1 Task 2 已有）
   - 替换 `result.image_url` 为 MinIO key
   - 失败时：保留 temp URL + 加 warning
2. **视频路径**（需先 grep 定位 agent 视频生成入口；若 `components/agent/VideoGenerateDialog.tsx` 调的是 `/api/v1/video/*`，统一走 `video_worker` 落 MinIO 的既有流程，核查输出是否已是 MinIO key）
3. **Asset 图片**（character/scene 首次生成时产生的图）：同路径处理
4. **返回体变更**：`PanelResult.image_url` 改名为 `image_key` 或保留名字但语义变为 "MinIO key"；前端通过 `useMediaUrl` hook 解析成预签名 URL

**兼容性**：如果 `MINIO_ENDPOINT` 未配置（dev 环境），fallback 到 temp URL + log warning。

### 5.3 B2-3 — Episode detail 错误状态 + 重试

**作用**：生成失败不再卡死，有重试入口。

**前端改动**（`app/agent/[projectId]/episodes/[episodeNum]/page.tsx`）：

- `generationError` state 对应的 UI：每个 phase（script/panels/assets/render）单独一个错误 banner，位置在该 phase section 顶部
- Banner 样式：`bg-red-500/10 border-red-500/30`，内含错误描述 + 【重新生成】+【跳过】按钮
- 【重新生成】重置 phase state，重新调对应 endpoint
- 【跳过】标记该 phase 为手动处理（layout_json 里加 `skipped_phases`），继续后面 phase

**无后端改动**。

### 5.4 B2-4 — Script generation SSE 流式进度

**作用**：`POST /agent/episode/{N}/script` 30 秒长调用改成 SSE，实时推进度。

**后端改动**：

1. 新增 route `GET /agent/episode/{episode_number}/script/stream`（SSE）
   - 接收与 `POST /script` 一样的 body（通过 query 或 POST body 两者都行；Starlette 支持）
   - 返回 `text/event-stream`
   - 事件：
     - `progress`: `{phase: "analyzing" | "writing" | "finalizing", pct: 0-100}`
     - `chunk`: `{text: "..."}` —— LLM 流式 token
     - `done`: `{script: "...", characters: [...], scenes: [...], panels: [...]}`
     - `error`: `{message: "..."}`
2. `StandardLLMService` 已有 streaming 支持（`_chat_completion` 带 `stream=True`）；若无，先给 Doubao 加 stream adapter
3. 旧 `POST /script` 保留（向后兼容），但标记 deprecated

**前端改动**：
- `EventSource` 消费 SSE，实时追加 chunk 到 UI 的"正在写剧本..."区
- progress 事件更新进度条
- done 事件触发现有 `setScriptData`

### 5.5 B2-5 — EpisodeTree 接入 + 状态真实化

**作用**：Episode detail 页左侧添加 EpisodeTree 侧栏，显示所有集 + 当前集的 phase 实时状态。

**前端改动**：

- Episode detail page layout 改造：`flex` 左侧固定宽度 EpisodeTree，右侧原页面内容
- 新增 hook/selector `useEpisodeTreeData(projectId)`：
  - 聚合：conversation 列表 + 解析每集的状态
  - 每集 6 phase 状态推导：
    - `script` = `script_data` 是否存在 → locked/draft/pending
    - `storyboard` = `panels` 数量 → same mapping
    - `assets` = characters + scenes 是否都有 thumbnail → done/pending
    - `render` = chapter.status 是否 rendered → locked/rendering/pending
    - `qa` = qa_report 存在 → locked/fixing/pending
    - `export` = export_url 存在 → done/pending
- EpisodeTree 的 `onSelectEpisode` / `onSelectPhase` 触发 URL 跳转 + 滚动到对应 section
- 新建 episode 按钮打开输入框 → 调 `/agent/episode/{N+1}/script` 开启新集

### 5.6 B2-6 — Episode 页消息删除

**作用**：用户能删除错误的 prompt/回复。

**前端改动**：ChatPanel 已接受 `onDeleteMessage` prop（从 `/agent/[pid]/page.tsx:564` 复制 handler 到 episode 页），1 个 handler，几行代码。

### 5.7 B2-7 — Episode 页对话切换器

**作用**：同项目内切换不同 conversation（对比多个 episode 草稿）。

**前端改动**：页面顶部加下拉：列出当前 project 下所有 conversation（通过 `conversationsApi.listByProject`），选中切换 URL `?conversation=<id>`。重载数据。

### 5.8 B2-8 — 3 个核心 tool handler 补全

**作用**：Agent 的 LLM 工具调用能真执行渲染和 QA。

**后端改动**（`services/conversation/tool_handlers.py`）：

1. `render_panels`（原 stub at `:379`）：
   - 参数：`chapter_id`, `panel_ids?`
   - 调用 `app.services.orchestrator.studio_orchestrator.trigger_render` 或直接 enqueue celery task
   - 返回 `{ batch_id, queued_panels }`
2. `analyze_quality`（原 stub at `:463`）：
   - 参数：`panel_id` 或 `chapter_id`
   - 调用 `app.services.qa.image_qa.ImageQAService.run`
   - 返回 QA scores
3. `suggest_fixes`（原 stub at `:502`）：
   - 参数：`qa_report_id` 或 `chapter_id`
   - 调用 `app.services.qa.fix_plan_generator`（已存在）
   - 返回 fix plan JSON

### 5.9 B2-9 — 【重新生成】按钮

**作用**：每个 agent 生成的消息上有一键重试。

**前端改动**：
- ChatPanel 的 message 组件（或 MessageCard）加一个 kebab menu：【重新生成】【编辑参数】【删除】
- 【重新生成】= 复用上次的参数重新调 endpoint，替换当前消息
- 【编辑参数】= 弹 inline 编辑器（shadcn Popover），修改后重调

### 5.10 B2-10 — Panel 生成真进度

**作用**：`panelProgress` 状态接通 UI。

**前端改动**：`episodes/[episodeNum]/page.tsx` — `generatePanelImages` 中用 `AsyncGenerator` 或 WS 回调或 SSE 逐个推，每完成一张 `setPanelProgress({done: k, total: N})`；UI 渲染 "3/7 · 正在生成..." + 进度条。后端已有 `for panel in panels` 循环，在每张完成时通过 WS 或 SSE 推 event。

**如果 SSE 改造工作量大**：退化方案 —— 改成客户端并发 `Promise.all(map(generateOne))` 改成 `for await` 串行，每张完后 setState；或者每张单独 POST（串行）。

### 5.11 B2-12 — Commit warning 详情展示

**作用**：用户能看到具体哪张图失败。

**前端改动**：B1-Task 13 现在 toast 了"N 条警告"总数。改成 toast 的 `description` 列前 3 条具体 warning，加一个【查看全部】按钮打开 Dialog 显示所有。

## 6. 数据模型

**无 DDL 变更**。

- `ConversationMessage.entities_json` 新增 4 种 card type（字符串常量）
- `Chapter.layout_json.skipped_phases`（B2-3）= 字符串列表
- 其他复用现有字段

## 7. API 新增/改动清单

| # | 方法 | 路径 | 说明 | 状态 |
|---|---|---|---|---|
| 1 | GET | `/api/v1/agent/episode/{N}/script/stream` | B2-4 SSE | **新增** |
| 2 | POST | `/api/v1/agent/episode/{N}/generate-panels` | B2-2 返回体改 image_key | **改造** |
| 3 | POST | `/api/v1/agent/episode/{N}/script` | 仍保留（deprecated）；新版内部也写 card | **改造** |
| 4 | Tool | `render_panels` / `analyze_quality` / `suggest_fixes` handlers | B2-8 补全 | **改造** |

## 8. 前端组件清单

| 组件 | 路径 | 状态 |
|---|---|---|
| `useEpisodeTreeData` hook | `apps/web/src/hooks/useEpisodeTreeData.ts` | **新建** |
| Episode detail page layout | 现有 | **改造**（加 sidebar）|
| Error banner 组件 | `components/agent/PhaseErrorBanner.tsx` | **新建** |
| SSE consumer hook | `hooks/useScriptStream.ts` | **新建** |
| Message kebab menu | 扩展 ChatPanel 的 message 组件 | **改造** |
| `CommitWarningsDialog` | `components/commit/CommitWarningsDialog.tsx` | **新建** |
| Conversation selector | `components/agent/ConversationSelector.tsx` | **新建** |

## 9. 交互流程（user journeys）

### Journey 1：新建 episode + 实时看进度
1. 用户 `/agent/[pid]/episodes`，EpisodeTree 侧栏显示现有集 + 【+ 新建集】
2. 点【+】→ 输入"第 4 集：最终对决"→ 自动跳 `/episodes/4` + 调 SSE script 端点
3. 实时看到 LLM 生成文本逐字出现，顶部进度条 "分析剧情... 30%"
4. 完成 → characters/scenes card 出现在对话里 → 继续生成 panels
5. Panel 生成进度 "5/23"，完成后所有图立即可用（MinIO 不过期）

### Journey 2：生成失败 → 重试
1. Panel 生成第 5 张时 Doubao 返回 500
2. 该 phase 顶部出现红色 banner "生成失败: rate limit"
3. 点【重新生成】→ 重试第 5 张
4. 或【跳过】→ 继续生成 6-23

### Journey 3：切对话、删消息、重新生成
1. Episode 4 生成了不好的 panels
2. 右上角【对话切换器】→ 看到 Episode 4 v1、v2 两个对话
3. 切回 v1
4. 找到某条坏回复，点 kebab →【删除】
5. 上一条用户消息下点【重新生成】→ 新回复

### Journey 4：Agent 驱动渲染 + QA + 修复
1. 对话里说"开始渲染第 1 集分镜"
2. LLM 调 `render_panels` tool → 后端 enqueue celery → 返回 batch_id
3. 渲染完成 → LLM 调 `analyze_quality` → 读 QA 分数
4. 有低分 → LLM 调 `suggest_fixes` → 生成修复计划 → 和用户讨论是否应用

## 10. 测试策略

### 后端

- `test_agent_card_writer.py` — card_writer 纯函数单测（6 tests）
- `test_agent_generate_panels_persists_to_minio.py` — generate-panels 后验证返回的 key 确实是 MinIO 格式，且 conversation 有 panels card（mock Doubao + mock MinIO）
- `test_script_sse.py` — SSE endpoint 返回 text/event-stream，yields 至少 2 个 event，带 final done
- `test_tool_handlers_render.py` / `_qa.py` / `_fix.py` — 3 个 handler 实际调用底层服务

### 前端

- 手动 smoke：Journey 1/2/3/4 全走
- Playwright（可选）：SSE 消费、错误 banner 渲染

## 11. 验收标准

- [ ] 生成后的 panel/character/scene 图 URL 是 MinIO key；24h 后仍可访问（不过期）
- [ ] Conversation 里出现 `panels/characters/scenes/art_style` 4 种 card 消息（通过 DB 查 entities_json 验证）
- [ ] B1 的 bulk commit（lean payload）现在能真正 populate 数据（不再依赖 episode_pipeline 绕弯路）
- [ ] Script SSE 端点返回 `text/event-stream`，前端 EventSource 接收到 chunk + progress + done
- [ ] Panel 生成过程中，UI 显示真实 "N/M" 进度
- [ ] 任意 phase 失败 → 红色 banner + 重试按钮 → 点击后成功恢复
- [ ] EpisodeTree 在 episode detail 页可见，phase 状态真实映射（非 demoEpisodes）
- [ ] 删除消息按钮在 episode 页可用
- [ ] 对话切换器能切换同 project 下的不同 conversation
- [ ] 【重新生成】按钮能在 agent 生成的消息上出现，点击真能重跑
- [ ] 3 个 tool handler 真实调底层服务（不返回 stub）
- [ ] Commit 的 warnings 能在 UI 看到具体哪几条（而非只看到总数）
- [ ] 所有新增后端端点 pytest 通过
- [ ] `npx tsc --noEmit` 和 `npm run lint` 无新错误
- [ ] Cluster A + B1 测试无回归

## 12. Out of Scope

- **LLM 超时 / 断路器**（B3 处理）
- **批量多集 script 生成**（B3）
- **对话搜索**（后续）
- **对话分支 / fork**（后续）
- **SSE 用于其他非 script 端点**（本期只改 script）
- **视频生成的 SSE 化**（视频生成本来就是异步任务，用 WS 足够）

## 13. 风险与缓解

| # | 风险 | 缓解 |
|---|---|---|
| R1 | 同步上传 MinIO 增加 generate-panels 响应时间（每张图多 2-5 秒） | 可改为 `asyncio.gather` 并发下载上传；超时 fallback temp URL + warning |
| R2 | SSE 断连后前端不自动重连 | 使用 `EventSource` 自带 reconnect；服务端支持 `Last-Event-ID` 续传（本期先不做续传，仅 reconnect） |
| R3 | EpisodeTree 状态映射复杂，可能有 bug | 状态映射集中在 `useEpisodeTreeData` hook 做，纯派生函数可写单测 |
| R4 | 旧 `/script` POST 还会被调用（向后兼容），造成两条路径要维护 | POST 内部也调新的 SSE 函数，结果汇总返回；不真正维护两份代码 |
| R5 | Tool handler 真实调渲染可能对 DB/Celery 有副作用 | handler 内部加 `dry_run=True` 参数；测试环境用 mock celery |

## 14. 关键代码位置

| 位置 | 说明 |
|---|---|
| `apps/api/app/api/routes/agent.py:737-793` | B2-2 改造起点（generate-panels） |
| `apps/api/app/api/routes/agent.py:501-746` | B2-4 script SSE 改造 |
| `apps/api/app/services/agent_commit/image_fetcher.py` | B2-2 复用的下载/上传工具（Cluster B1 Task 2）|
| `apps/api/app/services/conversation/tool_handlers.py:131,379,413,463,502` | B2-8 要补的 TODO stub |
| `apps/web/src/app/agent/[projectId]/episodes/[episodeNum]/page.tsx` | B2-3/B2-5/B2-9/B2-10 改造起点 |
| `apps/web/src/components/agent/EpisodeTree.tsx` | B2-5 接入目标 |
| `apps/web/src/components/chat/` | B2-6/B2-7/B2-9 改造起点 |

## 15. 后续 Cluster 预告

- **B3**: Studio 模式补全（AI 起草入口、Dashboard 数据、401/403 全局处理、LLM 超时/断路器、视频生成 UX 完善、资产版本管理）
- **后续**: 单独一期 Studio 渲染流水线的真 QA（vision 打分模型）
