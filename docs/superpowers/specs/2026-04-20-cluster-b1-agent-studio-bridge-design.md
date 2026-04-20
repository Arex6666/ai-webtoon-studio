# Cluster B1: Agent ↔ Studio 数据桥设计

**Date:** 2026-04-20
**Status:** Draft, pending user review
**Scope:** B1 Chat projectId · B7 Commit-to-Studio 端点 · B8 "在 Studio 打开"按钮 · B9 Studio 返回 Agent 链接 · B10 资产来源徽章

---

## 1. 背景

项目有两种创作模式：**Agent 对话创作**（`/chat`, `/agent/[projectId]/...`）和 **Studio 工作台创作**（`/projects/[pid]/chapters/[cid]/studio`）。两者当前是孤岛：

| 能力 | Agent | Studio |
|---|---|---|
| 数据落库 | ❌（存在对话 `entities_json`） | ✅（Chapter/Panel/Asset） |
| 渲染流水线 | 直调 Doubao，临时 URL | ✅（Celery/ComfyUI/LayerPack/QA） |
| 资产系统 | 对话 entity，非 Asset | ✅ |
| 互通 | ❌ | ❌ |

Cluster A 已经让 Studio 模式闭环（脚本→分镜→资产绑定）。本 Cluster 让 Agent 能把对话产物落到 Studio 同一份数据，**让两模式共享同一个后端真相**。

## 2. 目标

- 用户在 Agent 里对话创作后，**一键把该集（或所有集）的产物落到 DB**，变成 Studio 可继续编辑的 `Chapter + Panel + Asset`
- 落库后在 Agent 和 Studio 两端都能**显示来源关联**（Agent → Studio 跳转按钮、Studio → Agent 返回链接、资产溯源徽章）
- Chat 页面不再硬编码 project，而是**路由级 project 感知**
- 多次点击"提交"是**幂等**的（同一 episode 不会建两份 chapter）

## 3. 当前真实状态（核实结论）

1. `apps/web/src/app/chat/page.tsx:18` 硬编码 `projectId = 'demo-project'`
2. `apps/web/src/app/agent/[projectId]/episodes/page.tsx` 从对话历史文本解析集数 —— 数据只在对话 `entities_json` 中
3. Agent 后端 (`/agent/episode/{N}/generate-panels`) 直调 Doubao，产物是临时 URL，不落 DB
4. `Chapter.layout_json` 是 JSON 字段，**现有 auto-apply 已经在这里放 `pending_draft_id / storyboard_job_id`** —— 我们可以复用这个机制存 Agent 来源
5. 后端现成能力：
   - `MediaPersister` / `object_store._http_download` —— 从 URL 下载并存 MinIO
   - `portrait_generator` —— 角色参考图生成（可用于后续完善）
   - `parse_script`, `chapters/{id}/storyboard` —— 已经是 Studio 主路径（Cluster A）
6. `AssetEditDrawer` / `AssetsTab` / `CreateAssetModal` 已存在（Cluster A）

## 4. 设计决策记录

| # | 决策 | 理由 |
|---|---|---|
| D1 | **路由化 Chat**：`/chat` → 必选项目的 landing；`/chat/[projectId]` → 实际对话页 | 符合 Slack/Linear 等工具的惯例；projectId 进 URL 可分享 |
| D2 | **项目切换器放顶栏**（下拉），主要入口是 `/chat` landing | 一屏内切项目，不打断对话；landing 处理空态和项目创建 |
| D3 | **Commit-to-Studio 粒度 = 单 episode**（决策 2b） | 按集独立 chapter，灵活；也支持"commit 全部"按顺序调 N 次 |
| D4 | **Agent 资产落地时同步上传参考图到 MinIO**（决策 1a） | `asset.thumbnail_url` 存的是 MinIO key，Studio 端无需特殊处理 |
| D5 | **幂等性 = chapter.layout_json.source 做去重主键** | `source = { type: 'agent', conversation_id, episode_number }` 组合键唯一；第二次 commit 检测到存在就返回已有 chapter_id |
| D6 | **Asset 去重 = 同 project + 同 type + 同 name** | Agent 里"李明"和手动创建的"李明"是同一人；复用现有 asset |
| D7 | **"在 Studio 打开"按钮的行为 = commit + redirect 单步** | 一键进 Studio；幂等保证反复点不建脏数据 |
| D8 | **一键 commit 全集 = 顺序调 N 次单集 commit**（前端循环） | 后端逻辑简单；前端 progress UI 清晰 |
| D9 | **Asset 来源标记**：`asset.data_json.created_via = "agent"`、`asset.data_json.source_conversation_id = <id>` | 用现有 JSON 字段；不加 DDL |

## 5. 范围

### 5.1 B1 — Chat projectId 上下文

**目标**：`/chat` 不再硬编码 demo-project，支持路由化 + 项目切换器。

#### 前端

**新路由**：`/chat/[projectId]/page.tsx` —— 实际对话页
**改造**：`/chat/page.tsx` —— 变成项目选择 landing

**组件**：
- `<ChatProjectPicker>` - 顶栏下拉（带搜索），显示当前项目头像 + 名 + ▾
- `<ChatEmptyState>` - landing 空态 "选择或创建项目"

**交互**：
1. 未登录 → 跳 `/login`
2. `/chat`（无 projectId）：
   - 若用户有项目 → 显示"最近项目"卡片网格 + 搜索 + 【新建项目】
   - 若无项目 → 空态 CTA "创建你的第一个项目"
3. `/chat/[projectId]`：
   - 验证用户有权限 → 渲染 ChatPanel
   - 无权限 → 显示 403 消息 + 回到 `/chat`
   - 项目不存在 → 404 消息 + 回到 `/chat`
4. 顶栏 `<ChatProjectPicker>` 点击 → 下拉显示所有项目 + 搜索框 + "新建" → 选中 → URL 跳转

**可访问性**：下拉用 Radix `DropdownMenu`（已在项目）；键盘支持 Tab/Enter/Escape；搜索框 `aria-label`。

#### 后端

**不需要改动** —— `/projects/{id}` GET 已有权限检查。

### 5.2 B7 — `POST /api/v1/agent/projects/{project_id}/commit-to-studio` 端点

**目标**：把 Agent 产物落成 `Chapter + Panel + Asset`。

#### 请求

```json
{
  "conversation_id": "conv_xxx",
  "episode_number": 1,
  "episode_title": "初遇",
  "outline_summary": "少年与少女在...",
  "art_style": {
    "base_style": "Korean webtoon",
    "color_tone": "warm",
    "atmosphere": "romantic"
  },
  "characters": [
    {
      "name": "李明",
      "visual_prompt": "...",
      "temp_image_url": "https://doubao-temp.../xxx.png",
      "appearance_traits": ["短发", "黑色眼睛"],
      "personality_traits": ["内向"]
    }
  ],
  "scenes": [
    {
      "name": "校园天台",
      "visual_prompt": "...",
      "temp_image_url": "https://doubao-temp.../yyy.png",
      "time_of_day": "sunset",
      "weather": "clear"
    }
  ],
  "panels": [
    {
      "id": "agent-panel-1",
      "order": 0,
      "scene_name": "校园天台",
      "characters": ["李明"],
      "scene_description": "...",
      "dialogue": "...",
      "shot_type": "MS",
      "camera_angle": "eye-level",
      "emotion": "tender",
      "composition": "...",
      "temp_image_url": "https://doubao-temp.../zzz.png"
    }
  ]
}
```

#### 响应

```json
{
  "chapter_id": "ch_xxx",
  "chapter_title": "第1集 初遇",
  "status": "created" | "already_exists",
  "created_assets": {
    "characters": 2,
    "scenes": 1
  },
  "created_panels": 7,
  "studio_url": "/projects/{project_id}/chapters/{chapter_id}/studio"
}
```

#### 事务逻辑

```
1. 检查 (conversation_id, episode_number) 是否已有 chapter（扫 layout_json.source）
   → 存在：返回 status='already_exists' + chapter_id，不做任何修改
2. 开事务：
   a. 创建 Chapter：
      - title = 第{N}集 {episode_title}
      - script_raw = outline_summary（用户可在 Studio 里编辑）
      - order_index = 下一个可用 index
      - layout_json.source = {
          type: "agent",
          conversation_id,
          episode_number,
          committed_at: <ISO>,
          art_style_snapshot: art_style
        }
      - status = "draft"
   b. 为每个 character：
      - 查 Asset 是否存在（project + type=character + name） → 存在则更新 data_json 的 traits
      - 不存在：创建 Asset（type=character, data_json 含 traits/personality/source），若有 temp_image_url 则下载+MinIO上传，写到 asset.thumbnail_url
      - data_json.created_via = "agent"
      - data_json.source_conversation_id = conversation_id
   c. 为每个 scene：同上（type=scene）
   d. 为每个 panel：
      - 创建 Panel（chapter_id, order_index=panel.order, spec_json=<映射 agent panel → PanelSpec 格式>）
      - 若有 temp_image_url：下载+MinIO上传，写到 panel.preview_url
      - spec_json 中已自动填充角色/场景 asset_id（复用刚创建/查到的 Asset id）
   e. 调用 refresh_chapter_bindings（Cluster A 的逻辑）刷新 ChapterBindings 聚合
3. 返回响应
```

#### 错误处理

- 下载 temp_image 失败 → 事务不回滚，asset/panel 创建成功但 thumbnail/preview_url 为空；在响应里加 `warnings: ["character 李明 参考图下载失败"]`
- MinIO 不可用 → 400，事务整体回滚（半完成的 asset 会造成后续混乱）
- 同名 asset 冲突 → 按 D6 去重逻辑复用，不报错

#### 权限

`current_user: User = Depends(get_current_user)` + 验证用户对该 project 有访问权限（查 `project.owner_id` 或 ACL）。

### 5.3 B8 — Episode 卡片"在 Studio 打开"按钮

**位置**：`apps/web/src/app/agent/[projectId]/episodes/page.tsx`（每张 episode Card 底部）和 `apps/web/src/app/agent/[projectId]/episodes/[episodeNum]/page.tsx`（顶部操作栏）。

**交互**：
- 每个 episode Card 右下角新增 Button：`[🎬 在 Studio 打开]`
- 点击 → loading 状态（文案变"提交中…"）→ 调 B7 端点 → 成功 → 跳转到 `studio_url`
- 若 status='already_exists' → toast "已打开已有章节" → 跳转
- 若后端返回 warnings → toast "章节已创建，但 N 张参考图未能保存（可在 Studio 手动上传）"

**专业体验**：
- Loading 时整个卡片半透明 + spinner 覆盖
- 错误时 toast 红色 + 按钮恢复可点
- 按钮有 disabled 状态：如果该 episode 对应对话还没到"生成分镜"阶段（panels 数 = 0），按钮 disabled + tooltip "请先在聊天中生成分镜"

**顶栏批量操作**：episodes 页顶部加 `[一键提交全部到 Studio]` 按钮，点击 → 顺序调 B7 N 次，显示 "1/3 · 2/3 · 3/3" 进度；结束后 toast "已提交 3 集"。

### 5.4 B9 — Studio 顶栏"返回 Agent 聊天"链接

**位置**：Studio 页顶栏 `StudioTopbar.tsx`。

**逻辑**：
- 读取 `chapter.layout_json.source`，若 `source.type === 'agent'` 且 `source.conversation_id` 存在：
  - 在顶栏右侧添加链接：`[← 返回 Agent 聊天]`
  - 点击跳转到 `/chat/[projectId]?conversation=<id>`（或 `/agent/[projectId]/episodes/[episodeNum]`，根据上下文）

**视觉**：小尺寸 ghost variant Button + Bot icon。仅在 source 是 agent 时显示（不占位）。

### 5.5 B10 — 资产来源徽章

**位置**：`AssetEditDrawer > BasicTab`（Cluster A 已实现）和 `AssetsTab` / `/assets` 页面的资产卡片。

**交互**：
- 若 `asset.data_json.created_via === 'agent'`：
  - 在资产卡片角落显示 Badge："来自 Agent 对话"
  - Hover 显示 tooltip："由 {user} 在 {date} 通过 Agent 对话创建"
  - AssetEditDrawer Basic tab 显示一条 meta："来源：Agent 对话 · {conversation_date}"

**视觉**：Badge variant="secondary"，小字，带 Bot icon。不可编辑（只读 meta）。

## 6. 数据模型

**无 DDL 变更**。全部复用现有：

- `Chapter.layout_json.source = { type, conversation_id, episode_number, committed_at, art_style_snapshot }` —— 幂等主键
- `Asset.data_json.created_via = "agent" | "studio"`
- `Asset.data_json.source_conversation_id = "..."` （可选）
- `Asset.thumbnail_url` = MinIO key（现有字段）
- `Panel.preview_url` = MinIO key（现有字段）
- `Panel.spec_json` = 标准 PanelSpec 格式（与 Cluster A 的 Multi-Agent 输出格式一致）

## 7. API 清单

| # | 方法 | 路径 | 说明 | 状态 |
|---|---|---|---|---|
| 1 | POST | `/api/v1/agent/projects/{project_id}/commit-to-studio` | B7 核心 | **新增** |
| 2 | GET | `/api/v1/chapters/{chapter_id}` | B9 读 source | 已存在 |
| 3 | GET | `/api/v1/projects` | Chat picker 列项目 | 已存在 |

## 8. 前端组件清单

| 组件 | 路径 | 状态 |
|---|---|---|
| `ChatProjectPicker` | `components/chat/ChatProjectPicker.tsx` | **新建** |
| `ChatEmptyState` | `components/chat/ChatEmptyState.tsx` | **新建** |
| `/chat/page.tsx` | `app/chat/page.tsx` | **改造**（landing） |
| `/chat/[projectId]/page.tsx` | `app/chat/[projectId]/page.tsx` | **新建** |
| `EpisodeCard` "开 Studio"按钮 | `app/agent/[projectId]/episodes/page.tsx` | **改造** |
| 批量 commit 按钮 | 同上 | **改造** |
| `StudioTopbar` Agent 返回链接 | `components/studio/StudioTopbar.tsx` | **改造** |
| `AssetSourceBadge` | `components/assets/AssetSourceBadge.tsx` | **新建** |
| `AssetsTab` / `AssetEditDrawer` 集成 badge | Cluster A 文件 | **改造** |
| `agentApi.commitToStudio` | `lib/api/services.ts` | **新建方法** |

## 9. 交互流程

### Journey 1：首次使用 Agent 创作并提交到 Studio

1. 用户进 `/chat` → 空态 → 点【创建项目】→ 填名称 → 跳 `/chat/[newPid]`
2. 在 Chat 对话：生成大纲（3 集）→ 继续生成第 1 集剧本和分镜 → 生成参考图
3. 跳 `/agent/[pid]/episodes` → 第 1 集卡片底部按钮【🎬 在 Studio 打开】
4. 点击 → 按钮变 loading → 后端创建 Chapter + 7 个 Panel + 3 个角色 + 2 个场景（带参考图）
5. 跳转到 `/projects/[pid]/chapters/[cid]/studio` → 画布显示 7 个 panel 卡片（带 Agent 生成的参考图作为 preview）
6. 顶栏右侧显示【← 返回 Agent 聊天】链接
7. 右侧 AssetsTab 列出 3 个角色 + 2 个场景，每个带【来自 Agent 对话】badge

### Journey 2：重复点击"在 Studio 打开"（幂等）

1. 已经 commit 过第 1 集
2. 用户改对话里的分镜描述（但没点重新 commit）
3. 再次点【🎬 在 Studio 打开】→ 后端检测 source 已存在 → 返回 `status='already_exists'`
4. Toast "已打开已有章节" → 跳转到同一 chapter
5. **Studio 里的数据是第一次 commit 时的快照**（不会被对话修改覆盖）—— 这是符合直觉的语义

### Journey 3：项目切换 + 批量 commit

1. 用户在 `/chat/[proj-A]` 对话中
2. 顶栏 `ChatProjectPicker` → 选 [proj-B] → URL 跳 `/chat/[proj-B]`
3. 在 proj-B 里对话生成了 5 集
4. 跳 `/agent/[proj-B]/episodes` → 顶栏【一键提交全部到 Studio】
5. 按钮变 "1/5 提交中… · 2/5… · 3/5…"
6. 完成 → toast "已提交 5 集到 Studio" + 每张卡片显示【在 Studio 查看】按钮
7. 点某一集的【在 Studio 查看】→ 跳 Studio

### Journey 4：Studio 返回 Agent

1. 用户在 Studio 编辑 Agent 提交来的 chapter
2. 顶栏【← 返回 Agent 聊天】
3. 跳 `/chat/[projectId]?conversation=<source.conversation_id>`
4. 回到对话，继续和 Agent 讨论

### Journey 5：错误处理

1. Agent 生成了参考图，但 Doubao 临时 URL 已过期
2. 用户点【在 Studio 打开】→ commit 开始
3. 下载某张图失败（404）
4. 后端继续创建 Asset/Panel（无 thumbnail），响应里加 `warnings: ["场景 '校园天台' 的参考图下载失败，已创建无图资产"]`
5. 前端 toast 警告 + 跳转到 Studio
6. 用户在 Studio 里看到空头像的角色 → 点编辑 → 手动上传或调 Doubao 重新生成

## 10. 测试策略

### 后端（pytest）

**新测试文件**：`apps/api/tests/unit/routes/test_agent_commit.py`

核心用例：
- `test_commit_creates_chapter_and_panels` —— 首次 commit，验证 Chapter/Panel 数量和 spec_json 结构
- `test_commit_creates_assets_with_source_marker` —— 验证 asset.data_json.created_via='agent'
- `test_commit_reuses_existing_asset` —— 同名 asset 不重复创建（复用）
- `test_commit_idempotent` —— 第二次 commit 同 conversation+episode 返回 `already_exists`，Chapter 数量不变
- `test_commit_chapter_binding_refreshed` —— ChapterBindings 被刷新
- `test_commit_handles_image_download_failure` —— Doubao URL 返回 404，asset 创建成功但无 thumbnail，warnings 非空
- `test_commit_rejects_unauthorized_project` —— 用户对 project 无权限时返回 403
- `test_commit_rejects_missing_conversation` —— conversation_id 不存在返回 404
- `test_commit_atomic_on_minio_failure` —— MinIO 完全不可用时不留脏数据

**Mock 策略**：
- HTTP 下载：mock `httpx`/`requests` 返回固定字节流
- MinIO：mock `object_store` 或使用 conftest 里可能已有的 fake

### 前端

**手动 smoke**：
- Journey 1/2/3/4/5 逐个跑
- 幂等性：反复点【在 Studio 打开】，DB 里 chapter 数量不增

**Playwright（可选）**：
- 项目切换器打开/选择/跳转
- 空态 CTA

### 集成

- 从 Agent 对话产出 panel → 点击 commit → 在 Studio 画布看到 panel 卡片（有 preview_url 图）→ 点 AssetsTab 绑定某角色 → 刷新验证

## 11. 验收标准

- [ ] `/chat` 在无项目时显示友好空态 + 创建 CTA
- [ ] `/chat/[projectId]` 正确加载项目对话，权限错误返回友好提示
- [ ] 顶栏项目切换器可搜索/切换
- [ ] Agent episodes 页每张卡片有【在 Studio 打开】按钮，加载/成功/错误三态清晰
- [ ] 顶栏【一键提交全部】按钮能跑完整个 loop，进度可见
- [ ] Commit 成功后 Studio 画布能显示 Agent 生成的 panel 预览图
- [ ] Commit 创建的 Asset 带【来自 Agent 对话】badge
- [ ] Studio 顶栏在 Agent-sourced chapter 上显示【← 返回 Agent】链接
- [ ] 重复 commit 同 episode 幂等，不产生重复数据
- [ ] Doubao URL 失败时 asset/panel 仍创建成功（仅无图），warnings 在 UI 显示
- [ ] 所有后端新端点 pytest 通过
- [ ] `npm run lint` / `npx tsc --noEmit` 无新错误
- [ ] 所有新增 UI 组件通过 shadcn/ui 暗色主题测试（对比度 ≥4.5:1）
- [ ] 键盘可导航（Tab/Enter/Escape），Focus ring 可见

## 12. Out of Scope

- **Studio → Agent 反向同步** —— 用户在 Studio 改了 panel，不会回写到对话（用户期望明显与直觉一致的是单向）
- **增量 commit** —— 用户改对话后再点 commit，不会 patch 已有 chapter（见 Journey 2）。这是 B2/B3 的话题
- **Agent 模式的 EpisodeTree 组件接入** —— B2 处理
- **Chat 页面的命令面板 `Cmd+K`** —— UX 增强，后续
- **更精细的权限（chapter 级 ACL）** —— 沿用项目级
- **Agent commit 的 WS 进度事件** —— 同步完成，不需要 WS

## 13. 风险与缓解

| # | 风险 | 缓解 |
|---|---|---|
| R1 | Doubao 临时 URL 有时效，过期后 commit 失败 | Commit 时单张图失败不阻断整体；UI 明确告知；后续可加"立即 commit"按钮在对话里即时下载 |
| R2 | MinIO 挂掉时半落库 | commit 整体事务；任一图上传失败视 URL 质量单独处理；MinIO 完全不可用时 rollback |
| R3 | 用户反复 commit 同 episode 以为能更新，实际是 no-op | Response 的 `status='already_exists'` 明确告知；UI toast 明确；后续 B2 可加"更新已有 chapter"开关 |
| R4 | Agent 同名资产与 Studio 手动创建的同名资产混淆 | D6 去重以 project+type+name 为键，已有 asset 保留现有 thumbnail（不覆盖用户手上传的图） |
| R5 | commit 过程耗时（N 张图下载 + 上传），用户没反馈 | 前端 loading 覆盖 + 每张图下载有超时；后端 Celery 可选但本期同步足够（图 ≤10 张） |

## 14. 关键代码位置参考

| 位置 | 说明 |
|---|---|
| `apps/api/app/services/storage/media_persister.py` | 参考：URL → MinIO 上传模式 |
| `apps/api/app/services/storage/object_store.py:70-106` | 参考：HTTP 下载 |
| `apps/api/app/api/routes/chapters/storyboard.py:297-517` | 参考：事务性的 Chapter+Panel+Asset 创建 |
| `apps/api/app/api/routes/drafts.py:apply_draft_internal` | 参考：auto-apply draft 落库 |
| `apps/api/app/models/chapter.py:25` | `layout_json` 字段 |
| `apps/web/src/app/chat/page.tsx:18` | B1 改造起点 |
| `apps/web/src/app/agent/[projectId]/episodes/page.tsx` | B8 改造起点 |
| `apps/web/src/components/studio/StudioTopbar.tsx` | B9 改造起点 |
| `apps/web/src/components/assets/AssetEditDrawer.tsx`（Cluster A） | B10 badge 集成 |
