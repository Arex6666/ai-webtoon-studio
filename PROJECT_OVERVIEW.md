
# AI Webtoon Studio — 工程规格与开发路线（V1/V2）

## 1. 项目目标与定位

**AI 漫剧开发工作台**：从剧本 → 分镜 → 分层素材（LayerPack）→ 气泡排版 → 导出（条漫 PNG / 微动 MP4 / 后续视频模型）的一站式创作工具。

### 1.1 核心公式（产品核心）

`(人物层 + 背景层 + 前景层) × 视差微动 + SVG 气泡排版 = 漫剧`

### 1.2 关键原则（设计约束）

* **可复用**：角色/场景/风格资产可复用；同一资产更新不污染历史产物（版本化）。
* **可追溯**：任意一张图/一个视频片段都能追溯到：panel_spec + style_profile + asset_versions + seed。
* **可自动化**：整章批量渲染、QA 打分、自动重试、失败可解释。
* **引擎可插拔**：ComfyUI 是默认渲染工厂；外部视频大模型（可灵/通义/豆包等）通过 Provider 接口集成。
* **商业化导向**：输出标准化 LayerPack/VideoPack，便于后期/剪辑/交付与迭代。

---

## 2. 术语表（统一语言，避免接口/代码混乱）

| 术语            | 含义                                     |
| ------------- | -------------------------------------- |
| Project       | 作品工程（全局风格、主角资产、权限等）                    |
| Chapter       | 一章/一集（剧本、分镜布局、导出单元）                    |
| Panel         | 分镜/镜头（静态画面与后续微动/视频都以 panel 为单位）        |
| PanelSpec     | 分镜规格 JSON（人物/场景/运镜/气泡/风格/时长等）          |
| Asset         | 资产（角色/场景/风格/道具等）                       |
| StyleProfile  | 风格配置包（模型栈、LoRA、prompt 模板、参数模板、输出策略）    |
| RenderJob     | 渲染任务（一次渲染请求，可能包含多步骤）                   |
| RenderAttempt | 渲染尝试（重试/返工的每一次执行记录）                    |
| LayerPack     | 分层素材包（Full/Char/BG/FG/Mask + manifest） |
| VideoPack     | 视频素材包（frames 或 mp4 + manifest）         |
| SceneAnchor   | 场景锚点（BG anchor + control maps）         |
| FaceEmbedding | 角色一致性向量（FaceID embedding / refs）       |
| QAReport      | 质量评分报告（可解释维度 + 分数 + 建议）                |
| FixPlan       | 自动返工计划（换 seed / 提权重 / 局部修复等）           |

---

## 3. 系统架构（你在做什么）

### 3.1 总体结构（模块职责）

* **前端 Studio（Next.js + Konva）**

  * 剧本编辑、分镜浏览、单镜头编辑、气泡拖拽、参数面板、资产库、实时任务进度
* **后端 API（FastAPI）**

  * 项目/章节/分镜/资产 CRUD
  * 触发渲染、嵌字、合成导出
  * WebSocket 推送任务进度
* **服务层（可插拔 Provider）**

  * Brain（LLM 分镜/增强/连续性检查）
  * LayerFactory（ComfyUI workflow 构建 + 调用）
  * Identity（FaceID embedding 管理）
  * SceneAnchor（控制图生成/锁定）
  * QA（评分 + 返工建议）
  * Composer（条漫拼接 / 微动视频合成）
* **基础设施**

  * PostgreSQL（主库）
  * MinIO（图片/视频/manifest 存储）
  * Redis（队列/缓存/锁/任务状态）
  * ComfyUI（渲染引擎，可单机或集群）

### 3.2 数据流（最重要的生产线）

1. Script → Brain.analyze_script → 生成 Chapter.layout_json + Panels(spec_json)
2. PanelSpec → LayerFactory.payload_builder → ComfyUI workflow_json
3. RenderJob → ComfyUI 执行 → 产出 LayerPack（Full/Char/BG/FG/Mask）
4. Typesetter → SVG 气泡 → PNG（文本层或合成后图）
5. Composer → 条漫 PNG / 微动 MP4（基于 LayerPack 做视差）
6. QA → QAReport → 低分触发 FixPlan → 自动重试或 NeedsFix

---

## 4. 后端功能实现（FastAPI + Python）

### 4.1 API 路由清单（现状 + 目标）

> 你已有的路由很完整，V1 需要补齐“真实引擎调用 + 任务队列 + 版本化/尝试记录”。

| 模块           | 路径                     | 当前       | V1 目标补充                                       |
| ------------ | ---------------------- | -------- | --------------------------------------------- |
| Projects     | `/api/v1/projects`     | ✅        | 加权限/配额字段（可后置）                                 |
| Chapters     | `/api/v1/chapters`     | ✅        | layout_json 结构固定化 + 批量渲染入口                    |
| Panels       | `/api/v1/panels`       | ✅        | PanelVersion / Spec 校验 / duration_s           |
| Assets       | `/api/v1/assets`       | ✅        | AssetVersion / StyleProfile / 检索              |
| Render       | `/api/v1/render`       | ✅(Mock)  | 真 ComfyUI 调用 + job/attempt + outputs manifest |
| Typeset      | `/api/v1/typeset`      | ✅        | 输出 text_layer + 合成策略（覆盖/不覆盖）                  |
| Compose      | `/api/v1/compose`      | ✅        | 微动 MP4 pipeline（parallax + fx + ffmpeg）       |
| Identity     | `/api/v1/identity`     | ✅(逻辑)    | InsightFace 提取 + ref 图管理 + 权重策略               |
| Scene Anchor | `/api/v1/scene-anchor` | ✅(逻辑)    | control maps 生成/缓存/复用                         |
| Brain        | `/api/v1/brain`        | ✅(真实LLM) | 输出稳定 JSON schema + 可复现 prompt                 |
| QA           | `/api/v1/qa`           | ✅        | 可解释维度 + FixPlan + 自动重试规则                      |
| WS           | `/api/v1/ws`           | ✅        | 推送 job/attempt/artifacts/qa/fix 状态            |
| Health       | `/api/v1/health`       | ✅        | 增加依赖检查：redis/minio/comfyui 连接与延迟              |

---

## 5. 服务层（你已有目录，补齐工程契约）

### 5.1 Brain 服务（LLM）

目录（保持不变）：

```
services/brain/
  base.py
  mock.py
  standard_llm.py
```

#### Brain 输出的关键契约（必须稳定）

* `analyze_script()` 返回：

  * `chapter_layout_json`
  * `panels: PanelSpec[]`
  * `assets_suggestions`（需要的角色/场景/风格）
  * `warnings`（复杂动作/超时长镜头/不适合当前引擎）

> **要求**：PanelSpec 字段要“少而稳”，不要把一切都塞 prompt 字符串里。语义字段结构化，prompt 由 StyleProfile 模板拼装。

### 5.2 Layer Factory（ComfyUI）

目录（保持不变）：

```
services/layer_factory/
  comfyui_client.py
  mock_comfyui.py
  payload_builder.py
```

#### V1 必须新增：Workflow Contract（工作流契约）

LayerFactory 必须提供一个“统一合同”，让前端/后端/引擎不打架：

**输入**

* `PanelSpec`
* `StyleProfile`
* `AssetRefs`（角色 embedding / 场景 anchor / LoRA 列表等）

**输出**

* `workflow_json`
* `expected_outputs[]`（明确类型与命名）
* `outputs_manifest.json`（渲染完成后填充）

> 你之前遇到的 `VAE` vs `CLIP_VISION` 类型错连，本质是“工作流合同缺失”。合同一旦建立，这类错误应在编译阶段就被拦截。

### 5.3 Typesetter（气泡排版）

要求补充两点工程化约束：

* 输出支持两种模式：

  1. `text_layer.png`（透明背景，仅文字/气泡层）
  2. `panel_with_text.png`（直接合成）
* 气泡布局建议由 Brain 提供但必须可编辑；最终以前端 Konva 保存的 `bubble_json` 为准。

### 5.4 QA 服务（评分与返工）

V1 建议 QAReport 至少先做 3 个维度（后续再扩展）：

* `face_similarity`（角色是否像 / 是否漂）
* `artifact_score`（畸形手、脏点、崩脸）
* `composition_readability`（气泡遮挡/对比度/可读性）

并输出 FixPlan（自动返工策略）：

* 换 seed
* 提高 FaceID 权重
* 局部 inpaint（脸/手/书封面）
* 降 denoise / 降 motion（视频时）
* 降档或升档（fast/normal/hero）

---

## 6. 数据模型（建议补齐 V1 必需字段）

你现在列的模型很好，V1 建议补齐“版本化与尝试”：

**必须新增/强化（V1）**

* `PanelVersion`：每次 spec 更改都形成版本
* `AssetVersion`：角色/场景/风格资产的版本快照
* `RenderAttempt`：RenderJob 的每一次执行记录（含 seed、workflow_hash、日志、产物 hash）
* `StyleProfile`：风格配置包实体化（而不是散落在 prompt）

**存储产物建议结构（MinIO）**

* `projects/{project_id}/chapters/{chapter_id}/panels/{panel_id}/attempts/{attempt_id}/`

  * `full.png`
  * `char.png`
  * `bg.png`
  * `fg.png`
  * `mask.png`
  * `manifest.json`
  * `qa_report.json`

---

## 7. PanelSpec（分镜规格）标准（给编程 AI 的关键）

### 7.1 PanelSpec 最小稳定字段（V1）

> 先稳定，再扩展。字段稳定 = 自动化才稳定。

* `id / order_index`
* `duration_s`（为微动/视频准备）
* `canvas`（w/h/aspect）
* `scene`（scene_id / location_desc）
* `characters[]`（character_id / expression / placement / wardrobe_id）
* `camera`（shot_size / movement）
* `environment`（time/weather/lighting）
* `dialogue[]`（speaker/text/bubble_json_ref）
* `generation`（style_profile_id / quality_tier / seed_policy / controls）

### 7.2 StyleProfile（风格配置包）字段建议

* `model_stack`：checkpoint/vae/clip
* `lora_stack[]`：name/weight
* `prompt_templates`：positive/negative（支持占位符）
* `sampler_defaults`：steps/cfg/scheduler/denoise
* `output_policy`：layerpack_enabled、default_resolution、aspect_rules
* `postprocess`：可选（upscale/锐化/lut）

---

## 8. ComfyUI 集成（V1 实施清单）

### 8.1 你要实现的“真实 ComfyUI 工作流调试”到底是什么

目标不是“能跑一张图”，而是能稳定产出 **LayerPack**：

* R0：Full Render → `full.png`
* R1：Char Cutout → `char.png (+ alpha)`
* R2：BG Inpaint → `bg.png`
* R3：FG FX（可选）→ `fg.png`

### 8.2 V1 验收标准（ComfyUI）

* 后端给定 `PanelSpec + StyleProfile + Assets` 能生成 workflow_json
* workflow 复制进 ComfyUI 画布可直接跑通
* API 调用 ComfyUI 产物能落到 MinIO 并生成 manifest
* 任意失败能在 `render_attempts` 记录到可诊断信息（错误类型 + 日志）

---

## 9. 前端（Next.js + Konva）说明与 V1 补充

你现有页面结构清晰，V1 建议补充以下交互闭环：

### 9.1 Studio 必须具备的“工业化操作”

* **一键渲染整章**（批量 RenderJobs）
* **单镜头渲染/重渲**（基于版本）
* **NeedsFix 看板**（失败原因 + FixPlan 建议）
* **资产缺失提示**（缺 embedding / 缺 anchor / 缺风格包）
* **版本对比**（至少能回滚与查看历史产物）

### 9.2 WebSocket 推送事件建议统一格式

* `job.queued / job.running / job.progress / job.succeeded / job.failed`
* `artifact.created`（full/bg/char/fg）
* `qa.ready`
* `fixplan.ready / fixplan.applied`

---

## 10. 开发阶段规划（按“可交付”拆分）

### 10.1 MVP（你当前）

已完成：CRUD、工作台 UI、Konva 气泡、WS、Mock 渲染、条漫导出、多 LLM 支持、ComfyUI URL 配置。

**MVP DoD（你已基本满足）**

* 输入脚本 → 得到分镜 → 生成静态长条漫（哪怕用 Mock 图）

### 10.2 V1（现在要做的）

**V1 DoD（必须写清楚，给编程 AI 作为目标）**

1. **真实 ComfyUI 分层流水线**产出 LayerPack
2. **FaceID embedding 提取**并在渲染中生效
3. **SceneAnchor 控制图生成/缓存**并在渲染中生效
4. **QA 评分 + 自动重试**（至少换 seed / 提 Face 权重）
5. **视差微动 MP4 导出**（基于 LayerPack）
6. **整章批量渲染** + 失败看板 + 可解释原因

### 10.3 V2（工业化连载）

建议把 V2 列成“能力包”：

* 资产银行（背景/表情/pose）
* 协作与版本树（多人编辑）
* Vision QA 闭环（自动修复建议）
* 配额计费与成本面板
* 外部视频大模型更深集成（关键帧/分镜级路由）

---

## 11. 当前环境与启动（补齐编程 AI 常犯错点）

### 11.1 必须明确：Redis 目前未启动会影响什么

* 若你的 RenderJob、WS 或重试依赖 Redis：**V1 开始必须启动 Redis**
* 建议 docker compose 加上 redis 服务并纳入一键启动

### 11.2 推荐一键启动（开发）

建议把命令固化成：

* `docker compose up -d postgres minio redis`
* `make dev-api` / `make dev-web`（或 npm scripts）

### 11.3 必备环境变量（建议集中到 `.env.example`）

* `DATABASE_URL`
* `REDIS_URL`
* `MINIO_ENDPOINT / MINIO_ACCESS_KEY / MINIO_SECRET_KEY / MINIO_BUCKET`
* `COMFYUI_BASE_URL`
* `LLM_PROVIDER / OPENAI_API_KEY / DEEPSEEK_KEY / QWEN_KEY / DOUBAO_KEY`
* `PUBLIC_BASE_URL`（用于回调/资源访问）

---

## 12. V1 任务清单（可直接转 Issue）

### P0（必须先做）

* [ ] 建立 Workflow Contract + payload_builder 产物规范（避免类型错连）
* [ ] RenderJob + RenderAttempt + Artifact manifest（可追溯）
* [ ] Redis 启动并接入渲染队列（批量渲染的基础）

### P1（产出商业化质量的关键）

* [ ] 分层流水线：Full/Char/BG/FG（LayerPack）
* [ ] FaceID embedding 提取与应用
* [ ] SceneAnchor control maps 生成与注入
* [ ] QAReport + 自动重试（至少 2 条规则）

### P2（把“漫画”变“漫剧”）

* [ ] 视差微动 MP4 合成（parallax + fx + ffmpeg）
* [ ] 整章导出（串联 panel clip → chapter mp4）

---

## 13. 对编程 AI 的“开发指令”建议（非常重要）

> 你可以把下面这段作为 `CLAUDE.md` / `AGENTS.md` / `CONTRIBUTING.md` 的开头，让 AI 直接照着做。

* 本项目目标：实现脚本→分镜→LayerPack→排版→导出漫剧的生产线。
* V1 的核心是：**真实 ComfyUI 分层渲染 + QA/重试 + 微动 MP4 导出**。
* 所有工作必须遵循：

  1. PanelSpec / StyleProfile / LayerPack manifest 的 JSON 契约
  2. RenderJob / RenderAttempt 的可追溯记录
  3. MinIO 的产物路径规范
  4. WS 推送事件规范
* 实现新功能必须包含：

  * API 接口（OpenAPI 可见）
  * 数据库迁移（如新增表）
  * 单元测试或最小集成测试
  * 文档更新（本文件对应章节）

---


