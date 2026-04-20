# Cluster A: Studio 主闭环设计

**Date:** 2026-04-20
**Status:** Draft, pending user review
**Scope:** A1 分镜级资产绑定 + A2 剧本→分镜路径统一 + A3 资产编辑 Drawer

---

## 1. 背景

Studio 工作台目前存在三个断点，导致"剧本 → 分镜 → 资产 → 渲染"的主闭环无法闭合：

- **A1**：`AssetsTab` 里点击"选择"和"创建新资产"都只 `console.log`，LLM 自动软匹配后用户无法手动覆写绑定
- **A2**：`ScriptInput.tsx:83` 的 `handleConfirm` 是 TODO，用户写完剧本后点确认没反应。同时后端已有更完整的 `POST /chapters/{id}/storyboard` Multi-Agent 流程，与 `ScriptInput → /parse-script` 形成两条平行路径
- **A3**：资产列表的"编辑"按钮是空函数 (`assets/page.tsx:534`)，资产无法二次修改

本 spec 把这三个断点作为一个内聚单元处理，目标是让 **Studio 和 Agent 两种模式下"从一段剧本到可渲染的分镜"的路径完整、可逆、可调整**。

## 2. 当前真实状态（调研结论）

关键事实，决定了设计方向：

1. `Panel` 模型**没有** `cast_refs / scene_ref` 列。角色/场景信息直接嵌在 `panel.spec_json` 的 `characters[]` 和 `scene` 里。绑定的本质是修改 `spec_json` 中的 `asset_id` 字段
2. `ChapterBindings` 表是章节级聚合，存 `identity_asset_ids / scene_asset_ids / anchor_ids`；每次 panel 级绑定变化需刷新这个聚合
3. `AssetRelation` 表记录 wears/holds/appears_in 等关系图谱，非绑定路径
4. `POST /chapters/{id}/storyboard` 已包办：Multi-Agent 生成 + WS 推送 + auto-apply 落库 + 自动创建 assets + 自动入队生成参考图
5. `PUT /panels/{id}/spec` 已存在（`panels.py:241`），可作为绑定 API 的底层或并列
6. 前端 `assetsApi.update` 已存在，`assetsApi.regenerateReference` 已存在；A3 无需新 API，只需新组件

## 3. 设计决策记录

| # | 决策 | 理由 |
|---|---|---|
| D1 | A2 采用**选项 Y**（`ScriptInput` 保留入口，confirm 时收敛到 `/chapters/{id}/storyboard`） | 用户已有 X/Y/Z 三选，选定 Y：保留熟悉入口 + 底层统一 |
| D2 | A1 新增 **`PATCH /panels/{id}/bindings`** 专用端点，不复用 `PUT /panels/{id}/spec` | 绑定是语义明确的子操作；专用端点可做"更新 spec_json + 刷新 ChapterBindings + 失效缓存"的事务 |
| D3 | A3 采用 **Drawer（从右侧滑入）**，不用 Modal | 列表浏览不被完全打断，符合 UX 原则 `modal-vs-navigation` |
| D4 | A3 版本管理**本期仅展示和回滚**，不做编辑历史 diff | 控制 scope；编辑历史单独列计划 |
| D5 | A1 绑定 UI 使用**已有的 `AssetsTab` Dialog**，不改成 Popover | 已存在可用的 UI，接线优先；Popover 是后续优化 |

## 4. 范围

### 4.1 A1 — 分镜级资产绑定

**作用**：让用户在 Studio Inspector 右侧 `AssetsTab` 把某个分镜里的角色/场景手动绑定到资产库中的具体 asset（覆写 LLM 自动绑定）。

#### 后端

**新端点**：`PATCH /api/v1/panels/{panel_id}/bindings`

请求体：
```json
{
  "slot": "character" | "scene" | "prop",
  "slot_index": 0,                    // character/prop 时用；scene 忽略
  "asset_id": "asset_xxx",            // null 表示清除绑定
  "asset_version_id": "ver_xxx"       // 可选；不传则用 asset 当前版本
}
```

响应：
```json
{
  "panel_id": "...",
  "spec_json": { ... updated ... },
  "chapter_bindings_updated": true
}
```

事务逻辑：
1. 校验 panel 存在 + 用户对所属 project 有权限
2. 校验 asset_id 存在 + asset 类型匹配 slot（character slot 必须接 character asset）
3. 更新 `panel.spec_json`：
   - `slot=character`：`spec_json['characters'][slot_index]` 从字符串名改为 `{ "name": ..., "asset_id": asset_id, "asset_version_id": ... }`
   - `slot=scene`：`spec_json['scene']['anchor_id'] = asset_id`（取该 asset 的当前 scene_anchor）
   - `slot=prop`：类似 character
4. 刷新 `ChapterBindings`（该 panel 所属 chapter 的聚合列表）
5. 触发 WS 事件 `panel_binding_updated`（chapter_id 频道）

**不改动**：
- `PUT /panels/{id}/spec` 保留（用于其他字段的整体更新）
- `ChapterBindings` 表结构不变

#### 前端

接线点：
- `AssetsTab.tsx:634` — 选择 asset 后调 `panelsApi.updateBindings()`
- `AssetsTab.tsx:705` — "创建新资产"：打开 `CreateAssetModal`（已存在），创建成功回调后自动绑定到当前 `bindingTarget`
- 在绑定 Dialog 底部新增【清除绑定】按钮（仅当该槽当前已绑定时显示），点击调 `panelsApi.updateBindings(panelId, { slot, slot_index, asset_id: null })`

新增服务层：
- `apps/web/src/lib/api/services.ts` 里的 `panelsApi` 加 `updateBindings(panelId, payload)`

状态同步：
- 调成功后，`studioStore.updatePanelSpec(panelId, newSpec)` 更新本地状态
- WS 收到 `panel_binding_updated` 时对其他打开的客户端同步

### 4.2 A2 — 剧本 → 分镜路径统一（选项 Y）

**作用**：`ScriptInput` 保留为可视化入口（有剧本编辑 + parse 预览 + 确认），底层统一走 `/chapters/{id}/storyboard`。

#### 前端改动

`ScriptInput.tsx`：
- `handleParse`（已存在）：继续调 `/brain/parse-script`，用于 **预览**（展示 LLM 大致会识别出多少 panel、哪些角色，帮用户决策是否进入正式生成）
- `handleConfirm`（TODO:83）：改为：
  1. 调 `POST /chapters/{chapterId}/storyboard`（带 `provider`、`style_hint`、`target_panels` 取自当前预览结果）
  2. 立即切换到"生成中"状态，订阅 WS `job_progress / job_status / job_result`
  3. 收到 `job_result` → 跳转到 Studio 画布或在当前页展示生成结果

**UI 状态机**：
```
empty → edited → parsing → preview → generating → done | error
                  ↑                      |
                  └──────── retry ───────┘
```

按钮文案随状态：
- `empty/edited`：**【预览分镜】**（调 parse-script）
- `preview`：**【生成正式分镜】**（调 storyboard，主按钮）+【重新预览】（次按钮）
- `generating`：按钮变为进度条 `正在生成... 第 7/23 个分镜`
- `done`：**【查看分镜】** 跳 Studio 画布
- `error`：**【重试】** + 显示错误详情

**WS 消费**：复用 `studioStore` 现有的 job 订阅通道（`studioStore.ts` 已有 `jobs` 状态），新增对 `job_type='storyboard'` 的特殊 UI 状态映射。

#### 后端改动

**不需要改后端**。`/chapters/{id}/storyboard` 已完整。

仅需：
- 补一条文档说明，标注 `/brain/parse-script` 为"预览-only"用途
- `_chapters_legacy.py` 里的老 storyboard 端点**本期不删**（避免破坏其他调用方），但加 `Deprecated` 注释

### 4.3 A3 — 资产编辑 Drawer

**作用**：`/assets` 页面的资产能二次编辑（改名/描述/tag/封面/切换版本）。

#### 前端（纯新组件）

新组件：`apps/web/src/components/assets/AssetEditDrawer.tsx`

结构（从右侧滑入，宽度 560px）：
```
┌─ Header ────────────────────────────┐
│ [封面] Name  [Type Badge]           │
│                       [Save] [X]    │
├─ Tabs ──────────────────────────────┤
│ [Basic] [Traits] [Versions] [Usage] │
├─ Tab Content ───────────────────────┤
│ (see below)                         │
└─────────────────────────────────────┘
```

**Basic tab**（通用）：
- 名称（input）
- 描述（textarea）
- Tags（multi-input）
- 封面图：点击替换 → 上传 or 调 `regenerateReference`
- Style Profile（select；仅 character/scene）

**Traits tab**（类型感知）：
- `character`：appearance_traits、wardrobe_notes、personality_traits（已在 Asset JSON 里）
- `scene`：time_of_day、weather、mood、location
- `prop`：size、category、material
- 其他类型：隐藏该 tab

**Versions tab**（时间线）：
- 纵向时间线，每个节点 = 一个 `AssetVersion`
- 节点内容：缩略图 + version_no + created_at + created_by + commit_message（若有）
- 操作：【设为当前版本】（调 `assetsApi.setActiveVersion`，本期若后端无此 API 则先打 TODO + 只展示）
- 高亮标记当前 active version

**Usage tab**：
- 列出引用该 asset 的 panels / chapters
- 每条显示：Chapter 名 · Panel 序号 · 缩略图 · 跳转到 Studio
- 来源数据：`ChapterBindings.identity_asset_ids / scene_asset_ids`

**交互细节**：
- 底部 sticky 浮条：未保存时显示 "N 项改动，未保存" + 【保存】【丢弃】
- 点 X / 点外关闭：有未保存改动时弹二级确认（UX 原则 `sheet-dismiss-confirm`）
- 保存成功：inline toast，Drawer 保留

#### 后端（最小化改动）

- `PATCH /api/v1/assets/{id}`：已存在 (`assetsApi.update`)，只要把需要的字段加入 whitelist
- `GET /api/v1/assets/{id}/versions`：**本期不新增**，若无则 Versions tab 显示空态 "版本历史功能即将上线"
- `GET /api/v1/assets/{id}/usage`：**需新增**，查 `ChapterBindings` + `panels.spec_json` 里含该 asset_id 的所有引用

新端点：`GET /api/v1/assets/{id}/usage`

响应：
```json
{
  "asset_id": "...",
  "references": [
    {
      "chapter_id": "...",
      "chapter_title": "第一话",
      "panel_id": "...",
      "panel_order": 3,
      "panel_preview_url": "..."
    }
  ],
  "total_count": 7
}
```

## 5. 数据模型变更

**无 DDL 变更**。全部复用现有：
- `Panel.spec_json` 扩展 `characters[i].asset_id` 字段（JSON 里加字段，不动 schema）
- `Panel.spec_json.scene.anchor_id` 新增（JSON 里加字段）
- `ChapterBindings` 表现有字段足够
- `Asset` 表现有字段足够

## 6. API 新增/改动清单

| # | 方法 | 路径 | 说明 | 状态 |
|---|---|---|---|---|
| 1 | PATCH | `/api/v1/panels/{id}/bindings` | A1 核心端点 | **新增** |
| 2 | GET | `/api/v1/assets/{id}/usage` | A3 Usage tab 数据源 | **新增** |
| 3 | POST | `/api/v1/chapters/{id}/storyboard` | A2 复用 | 已存在 |
| 4 | POST | `/api/v1/brain/parse-script` | A2 预览 | 已存在 |
| 5 | PATCH | `/api/v1/assets/{id}` | A3 编辑 | 已存在 |
| 6 | POST | `/api/v1/assets/{id}/regenerate-reference` | A3 换封面 | 已存在 |

## 7. 前端组件清单

| 组件 | 路径 | 状态 |
|---|---|---|
| `AssetEditDrawer` | `components/assets/AssetEditDrawer.tsx` | **新建** |
| `AssetEditDrawer/BasicTab` | `components/assets/drawer/BasicTab.tsx` | **新建** |
| `AssetEditDrawer/TraitsTab` | `components/assets/drawer/TraitsTab.tsx` | **新建** |
| `AssetEditDrawer/VersionsTab` | `components/assets/drawer/VersionsTab.tsx` | **新建**（含空态） |
| `AssetEditDrawer/UsageTab` | `components/assets/drawer/UsageTab.tsx` | **新建** |
| `ScriptInput` | `components/script-editor/ScriptInput.tsx` | **改动**（`handleConfirm` 重写 + 状态机） |
| `AssetsTab` | `components/studio/right/AssetsTab.tsx` | **改动**（:634, :705 接线） |
| `panelsApi.updateBindings` | `lib/api/services.ts` | **新建方法** |
| `assetsApi.getUsage` | `lib/api/services.ts` | **新建方法** |
| `assetsApi.update` whitelist | `lib/api/services.ts` | 已存在（可能需微调字段） |
| `studioStore.updatePanelSpec` | `lib/store/studioStore.ts` | 已存在（复用） |
| `studioStore.setStoryboardJobStatus` | `lib/store/studioStore.ts` | **新增 selector/action** |

## 8. 交互流程（user journeys）

### Journey 1：从零开始一个章节（A2 主路径）

1. 用户进 `/projects/[id]/chapters/[cid]/studio`，左侧 `ScriptEditor` 打开 `ScriptInput`
2. 写剧本 → 点**【预览分镜】** → `/brain/parse-script` 返回 panel 预览（数量、角色列表）
3. 预览 OK → 点**【生成正式分镜】** → 调 `POST /chapters/{cid}/storyboard`
4. 按钮切为进度条，顶部 `JobsConsole` 显示 Multi-Agent 思考过程（复用现有 WS）
5. 生成完成 → 按钮切为**【查看分镜】**，中央画布加载新分镜
6. 画布上的分镜卡片通过已有的 `AssetsTab` 展示 LLM 自动绑定的 asset（置信度 badge 本期不做，见 Out of Scope）

### Journey 2：手动覆写绑定（A1 主路径）

1. 用户在 Studio 选中某个 panel → 右侧 `AssetsTab` 展示当前 panel 的绑定槽
2. 点某个未满的角色槽 → 弹已有的绑定 Dialog
3. 列出 project 下同类型 asset → 点"选择" → `PATCH /panels/{id}/bindings`
4. 成功 → Dialog 关闭 + 画布 panel 卡片上的角色 slot 更新显示选中的 asset 缩略图
5. 若用户点"创建新资产"→ 打开 `CreateAssetModal`（已存在）→ 创建成功回调里自动再调一次 `PATCH /panels/{id}/bindings` 把新 asset 绑上去

### Journey 3：编辑资产（A3 主路径）

1. 用户在 `/assets` 列表点某张卡的"编辑" icon
2. 右侧 `AssetEditDrawer` 滑入，默认 `Basic` tab
3. 改名字、加 tag → 底部浮条出现"2 项改动，未保存"
4. 切到 `Usage` tab → 看到这个角色被 3 个 panel 用 → 心里有数，决定是否改
5. 切回 `Basic` → 点【保存】→ 调 `PATCH /api/v1/assets/{id}` → inline 成功 toast
6. 关 Drawer → 列表卡片上的数据自动刷新（TanStack Query 失效 `['assets']`）

### Journey 4：回滚错误的绑定

1. 用户在 Journey 2 绑错了 asset
2. 在 `AssetsTab` 的绑定 Dialog 里已选中项旁新增一个【清除绑定】按钮（本期在 Dialog 内提供，不在槽位上做 inline ×）
3. 点【清除绑定】→ `PATCH /panels/{id}/bindings` with `asset_id: null`
4. Dialog 关闭，槽位变为空 → 画布 panel 卡片上显示占位

## 9. 测试策略

### 后端（pytest）

**A1**：
- `tests/api/test_panel_bindings.py`
  - `test_patch_bindings_character_happy_path`：成功绑定后 `spec_json` + `ChapterBindings` 都更新
  - `test_patch_bindings_type_mismatch`：character slot 接 scene asset 返回 400
  - `test_patch_bindings_nonexistent_asset`：404
  - `test_patch_bindings_clear`：`asset_id: null` 清除绑定
  - `test_patch_bindings_chapter_bindings_sync`：刷新聚合不产生重复

**A3**：
- `tests/api/test_assets_usage.py`
  - `test_get_usage_returns_all_references`：asset 被 N 个 panel 引用时返回 N 条
  - `test_get_usage_empty`：无引用返回空列表
  - `test_get_usage_across_chapters`：跨章节引用都能查到

**A2**：复用现有 storyboard 测试，不新增（因后端不变）

### 前端（手动 + Playwright 可选）

- **A1**：打开 Studio，选 panel，点角色槽，选 asset，刷新页面验证持久化
- **A2**：进 Studio，写剧本，预览 → 生成，观察按钮状态变化，检查 WS 进度是否驱动 UI
- **A3**：进 `/assets`，编辑一个 character，改名 → 保存 → 刷新验证；切到 Usage tab 验证引用列表

### 集成验证

- 手工跑一次完整 Journey 1 → Journey 2：从空剧本到绑定完成，确认 `ChapterBindings.identity_asset_ids` 与 panel 实际绑定一致

## 10. 验收标准

- [ ] 在 Studio 里粘贴一段剧本 → 预览 → 生成 → 画布出现分镜（全程 WS 驱动，无白屏）
- [ ] 在 Inspector `AssetsTab` 手动更换一个角色 asset → 刷新后绑定保持
- [ ] 删除（清空）一个绑定 → 画布 panel 显示占位
- [ ] 在 `/assets` 编辑资产的名称、描述、tag → 保存后在 Studio 看到更新
- [ ] `AssetEditDrawer` 的 Usage tab 显示该资产被引用的所有 panel，点击能跳转到 Studio
- [ ] A1 绑定错类型返回 400，前端显示可恢复错误提示
- [ ] 所有后端新端点 pytest 通过
- [ ] `npm run lint` 无新错误

## 11. Out of Scope（本期不做）

- 资产绑定的**拖拽交互**（从左侧资产库直接拖到分镜槽）— 放到 Cluster A v2
- `AssetsTab` 改 Popover — 保留现有 Dialog
- `AssetVersion` 的编辑/diff/commit message — 仅展示回滚
- LLM 自动绑定的**置信度 badge** 和**虚线边框** — 作为 A1 延伸，下一期
- `AssetEditDrawer` 的 Versions tab 的"设为主版本"后端 API — 本期若无则 tab 显示空态
- `/brain/parse-script` 路径的删除 — 仍保留
- 老 `_chapters_legacy.py` 的清理

## 12. 风险与待定

| # | 风险 | 缓解 |
|---|---|---|
| R1 | `PATCH /panels/{id}/bindings` 与正在进行的 RenderJob 的并发问题 | 绑定更新写 `panel.spec_json` 时加 UPDATE 行锁；若有 `render_status=running` 则返回 409 "渲染中，无法修改绑定" |
| R2 | `ChapterBindings` 聚合刷新可能遗漏某些场景 | 刷新逻辑独立函数 `refresh_chapter_bindings(chapter_id)`，单测覆盖 |
| R3 | A2 的"预览"和"生成"两次调用 LLM 浪费 token | 预览仍用 parse-script（轻量），正式生成用 storyboard Multi-Agent；两路径本来就分开 |
| R4 | `AssetEditDrawer` 的 Usage tab 在资产被大量引用时加载慢 | Usage 端点支持 `limit` 参数，默认返回前 50 条 + 总数 |
| R5 | `ScriptInput` 改造期间同页面的其他模式（如 Agent 聊天式创作）兼容性 | A2 只改 Studio 入口；Agent 路径独立，不受影响 |

## 13. 后续 Cluster 关联

- **Cluster B**（Chat projectId + Agent 集数渲染）：依赖 A1 的绑定 API，因为 Agent 模式下也需要能写绑定
- **Cluster C**（Canvas 图层 + FaceID UI）：依赖 A3 的 Drawer 框架（FaceID tab 会 plug-in 到 Drawer）
- **Cluster D**（后端 Agent TODO）：D1 AssetAgent 的参考图生成在主流程已跑通，仅 Chat 独立入口待补

## 14. 附：关键代码位置参考

| 位置 | 说明 |
|---|---|
| `apps/api/app/models/panel.py:29` | `spec_json` 字段定义 |
| `apps/api/app/models/bindings.py:10` | `ChapterBindings` 表 |
| `apps/api/app/api/routes/panels.py:241` | 现有 `PUT /panels/{id}/spec` 作为参考 |
| `apps/api/app/api/routes/chapters/storyboard.py` | A2 收敛目标端点 |
| `apps/web/src/components/studio/right/AssetsTab.tsx:617-714` | A1 前端改动区域 |
| `apps/web/src/components/script-editor/ScriptInput.tsx:80-85` | A2 前端改动区域 |
| `apps/web/src/app/assets/page.tsx:534` | A3 入口 |
| `apps/web/src/lib/api/services.ts:290-346` | `assetsApi` 扩展位置 |
