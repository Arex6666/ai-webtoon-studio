# AI Webtoon Studio: 基于多智能体协作的AI漫剧自动化生产系统

> 论文框架与写作指南
> 生成日期: 2026-03-14

---

## 论文元信息

- **建议标题（中文）**：基于多智能体协作与结构化验证修复的AI漫剧自动化生产系统
- **建议标题（英文）**：AI Webtoon Studio: An Automated Webtoon Production System with Multi-Agent Collaboration and Structured Validation-Repair Pipelines
- **关键词**：多智能体系统、大语言模型、条漫生成、分镜自动化、角色一致性、人机协作
- **预计篇幅**：8000-12000字（正文），含图表约15-20张

---

## 第一章 绪论 (Introduction)

### 1.1 研究背景

**写什么：**
- 网络漫剧产业的市场规模与增长趋势。
- 传统漫剧生产流程的痛点：人力成本高、制作周期长（一集约1-2周）、专业门槛高
- AI生成技术（Stable Diffusion、DALL-E、Midjourney等）在视觉内容创作领域的突破
- 现有AI绘图工具的局限：缺乏叙事结构感知、跨画面一致性差、无法端到端自动化

**写作建议：**
- 引用漫剧产业报告（Webtoon Entertainment/Kakao数据）
- 引用AIGC在创意产业的综述文献

### 1.2 研究问题

**写什么：**
明确提出本文要解决的3个核心问题（与系统的3个核心创新对应）：

1. **结构化分镜生成的可靠性问题**：如何让LLM稳定输出符合漫剧制作规范的结构化分镜数据（JSON），而非自由文本？
2. **跨画面视觉一致性问题**：在AI生成的多面板漫剧中，如何保证同一角色在不同画面中外貌一致、同一场景空间结构稳定？
3. **人机协作效率问题**：如何设计系统让非专业用户也能高效参与漫剧创作，同时给专业用户精细控制能力？

### 1.3 研究贡献

**写什么：**
列出本文的4-5个主要贡献（来源于系统实际实现）：

1. 提出了**两阶段LLM分镜管线 + 验证修复循环**（Script→ScriptAnalysis→StoryboardDraft + 3轮自动修复），结构化输出成功率>95%
2. 设计了**FaceID嵌入+SceneAnchor控制图的双重一致性保障机制**，实现跨面板角色与场景的视觉连贯
3. 构建了**6种专业智能体+意图路由的多Agent协作架构**，支持14种工具调用和审批门控
4. 实现了**三级渲染策略（fast/normal/hero）+ 依赖图谱增量渲染**，降低30%生产成本
5. 开发了完整的端到端原型系统，覆盖从剧本输入到成品导出的全流程

### 1.4 论文组织

**写什么：**
简述各章内容安排，1-2句/章。

---

## 第二章 相关工作 (Related Work)

### 2.1 AI图像/视频生成技术

**写什么：**
- 扩散模型（Stable Diffusion, SDXL, FLUX）的发展
- 商业API（Midjourney, DALL-E 3, Doubao Seedream）
- ControlNet系列（depth, canny, lineart, pose）在可控生成中的作用
- 图生视频模型（SVD, AnimateDiff, 豆包即梦, 通义万相）

**与本系统的关系：** 本系统将这些模型作为可插拔引擎层（Engine Layer），通过统一的 `RenderProtocol` 抽象，支持 Doubao/ComfyUI/Tongyi/Mock 四种供应商无缝切换。

### 2.2 LLM在创意写作中的应用

**写什么：**
- LLM驱动的故事生成（ChatGPT, Claude用于叙事创作）
- 结构化输出的挑战（JSON Mode, Function Calling, 输出schema约束）
- 提示词工程在创意任务中的应用

**与本系统的关系：** 本系统的 Brain 服务 采用3层提示词组装（PromptComposer）+ JSON模式 + 30+条验证规则 + 最多3轮修复循环，解决LLM结构化输出不稳定的问题。

### 2.3 多智能体系统

**写什么：**
- LLM-based Agent框架（AutoGPT, LangChain Agents, CrewAI, MetaGPT）
- ReAct范式 vs 专业化Agent分工
- 工具调用与人在回路（Human-in-the-loop）

**与本系统的关系：** 本系统采用**意图路由+专业Agent分工**模式（而非ReAct自主循环），通过IntentRouter做LLM意图分类，将任务分发给6种专业Agent，每种Agent有独立的知识域和工具集，并引入审批门控保障安全。

### 2.4 角色一致性与视觉连贯

**写什么：**
- IP-Adapter系列（face, full）在角色一致性中的应用
- InsightFace/ArcFace人脸嵌入技术
- ControlNet在场景一致性中的作用
- 现有漫剧生成工具的一致性问题

**与本系统的关系：** 本系统构建了三级FaceID一致性保障（嵌入提取→标准肖像选择→渲染时注入）+ SceneAnchor三类控制图（depth/canny/lineart）的完整方案。

### 2.5 现有系统对比

**写什么：**
制作一张对比表，将本系统与以下方案做维度对比：

| 维度 | 本系统 | LangChain/AutoGPT | Midjourney+手工 | ComicFactory/StoryDiffusion |
|------|--------|-------------------|-----------------|----------------------------|
| 分镜生成 | 结构化JSON+验证修复 | 自由文本 | 手工拆分 | 简单模板 |
| 一致性保障 | FaceID+SceneAnchor+依赖图 | 无内置 | 手动种子管理 | 有限 |
| 智能体架构 | 意图路由→专业Agent | ReAct循环 | 无 | 无 |
| 质量控制 | 5项自动QA+分类修复 | 无 | 人工 | 无 |
| 人机协作 | 审批门+对话式+可视化编辑 | 全自动/全手动 | 全手动 | 有限 |

> **需要生成的图：**
> - 无（本章以文字综述+对比表为主）

---

## 第三章 系统总体设计 (System Architecture)

### 3.1 设计目标与原则

**写什么：**
- 端到端自动化：从剧本文本到成品条漫/动态视频的全流程
- 可插拔引擎：LLM/图像/视频供应商可替换
- 双模交互：专业工作台（Studio）+ 对话式（Agent Chat），共享同一资产库和后端管线
- 质量闭环：自动QA + 自动修复 + 人工兜底

### 3.2 分层架构

**写什么：**
详细描述系统的6层架构，每层的职责和技术选型：
1. 表现层（Next.js 14 + TypeScript + Tailwind + Konva画布）
2. API网关层（FastAPI + JWT鉴权 + WebSocket网关）
3. 业务逻辑层（Brain/Agent/LayerFactory/QA/Export 五大服务）
4. 引擎层（LLM/图像/视频/FaceID/VisionQA 五类引擎，均可插拔）
5. 异步任务层（Redis Broker + Celery Workers，5个专用队列）
6. 数据层（PostgreSQL + MinIO/S3 + pgvector可选）

> **需要生成的图：**
> - **图3-1：系统分层架构图**（6层，显示层间调用关系）
>   - 来源：paper-materials.md §1.1 的 Mermaid 图，重绘为学术风格
>   - 建议用 draw.io 或 TikZ 重绘，去掉emoji，使用英文标注

### 3.3 端到端数据流

**写什么：**
完整描述一话漫剧从剧本到导出的数据流转过程，对应系统中实际的数据模型：

```
Script → Brain/LLM → ScriptAnalysisV1（角色/场景/节拍）
  → StoryboardGenerator → StoryboardDraftV2（分镜面板列表）
    → 人工审核/调整
      → PayloadBuilder → PanelRenderContext
        → Celery Queue → GPU渲染（ComfyUI/Doubao）
          → LayerPack（full/char/bg/fg/mask + manifest）
            → ImageQA → QAReport
              → Pass: 进入时间线
              → Fail: AutoRetry → FixPlan → 重新渲染
                → Timeline编辑 → ExportBundle（ZIP）
```

> **需要生成的图：**
> - **图3-2：端到端数据流图**（水平流程图，标注每一步的输入输出数据模型名）
>   - 来源：paper-materials.md §1.2
>   - 重点标注数据模型名（ScriptAnalysisV1, StoryboardDraftV2, PanelRenderContext, LayerPack, QAReport, FixPlan）

### 3.4 技术选型

**写什么：**
用一张表总结关键技术选型及选型理由。

> **需要生成的图：**
> - **表3-1：核心技术选型表**
>   - 来源：paper-materials.md §2.1

### 3.5 双模交互架构

**写什么：**
解释系统提供两种交互模式的设计动机和实现差异：
- **Studio工作台**：4面板布局，面向专业用户的精细控制（类似After Effects/Premiere的工作流）
- **Agent Chat**：对话式交互，面向非专业用户的引导式创作（类似ChatGPT的交互方式）
- 两种模式**共享同一后端服务**和资产库，只是前端交互方式和控制粒度不同

> **需要生成的图：**
> - **图3-3：双模交互架构对比图**（左右对比：Studio 4面板布局 vs Agent Chat对话流，底部共享后端）

---

## 第四章 两阶段LLM分镜管线 (Two-Stage LLM Storyboarding Pipeline)

> 这是论文的**第一个核心贡献**，对应系统 `services/brain/` 模块

### 4.1 管线总览

**写什么：**
- 为什么需要两阶段：第一阶段提取叙事结构（角色/场景/节拍），第二阶段基于结构生成视觉分镜
- 单阶段直接生成分镜的问题：角色名不一致、场景引用错误、叙事节拍缺失
- 两阶段的优势：中间结果可验证、可修复、可人工干预

> **需要生成的图：**
> - **图4-1：两阶段管线总览图**（Stage1 → ScriptAnalysisV1 → Stage2 → StoryboardDraftV2，每阶段包含验证修复循环）
>   - 来源：paper-materials.md §6.1

### 4.2 第一阶段：剧本分析 (Script Analysis)

**写什么：**

#### 4.2.1 三段式提示词组装（PromptComposer）
- system prompt：设定角色（"你是专业漫剧分镜编剧"）
- context prompt：注入已有资产信息（项目中的角色、场景列表）
- user prompt：包含剧本文本 + 输出格式要求（JSON Schema）

#### 4.2.2 输出数据模型（ScriptAnalysisV1）
- `characters[]`：角色实体（canonical_name, aliases, role, appearance_traits≥2, personality_traits≥2, wardrobe_notes, signature_props, first_appearance_span）
- `locations[]`：场景实体（canonical_location, type, time_of_day_default, weather_default, anchor_hint≥5字）
- `beats[]`：叙事节拍（beat_id, summary, characters_involved, location_ref, emotional_tone, tension_level, source_span）
- 每个实体都包含 `source_span`（quote + start_line + end_line）实现**可溯源**

#### 4.2.3 验证规则（30+条）
- 角色名验证：≥2字、非80+项黑名单（排除动词片段"没敢多"、形容词"温和的"、占位符"角色A"、单字）
- 外貌特征 ≥2条、性格特征 ≥2条
- 场景 anchor_hint ≥5字
- source_span.quote 15-120字
- 所有枚举字段必须在白名单内

> **需要生成的图：**
> - **图4-2：ScriptAnalysisV1 数据模型类图**（UML类图，展示各实体关系）
>   - 来源：paper-materials.md §6.2

### 4.3 第二阶段：分镜生成 (Storyboard Generation)

**写什么：**

#### 4.3.1 上下文注入
- 将 Stage1 的分析结果注入 Stage2 的提示词
- 注入项目已有资产（角色FaceID、场景Anchor）
- 注入风格约束（StyleProfile）

#### 4.3.2 PanelDraft 数据模型
- 镜头参数：shot_type（ECU/CU/MS/LS/WS/OTS）, camera_move（static/pan/tilt/dolly/zoom/handheld）, duration_s（1.5-8.0s）
- 场景设定：location, time_of_day, weather
- 角色与动作：cast[], actions（≥10字）, dialogue_lines[]
- 视觉描述：composition_notes（≥2条）, continuity_notes（≥1条）, visual_prompt（≥20字）, negative_prompt
- **情感弧线系统**（6个字段）：emotion_label（10种情感）, emotion_intensity（0-1）, pacing（slow/moderate/fast/climax）, narrative_position（0-1自动计算）, transition_type（5种转场）, scene_tension（0-1, climax时≥0.7）

#### 4.3.3 情感弧线约束
- 相邻面板emotion_intensity最大变化Δ0.3（平滑约束）
- 节奏-时长对应关系：slow=4-8s, moderate=2.5-4s, fast=1.5-2.5s, climax=3-6s
- narrative_position自动计算 = (index-1)/(total-1)
- climax节奏时scene_tension ≥ 0.7

> **需要生成的图：**
> - **图4-3：PanelDraft 数据模型图**（展示完整字段，按类别分组）
>   - 来源：paper-materials.md §6.3
> - **图4-4：情感弧线示例图**（一组面板的emotion_intensity和scene_tension随narrative_position的变化曲线）
>   - 这张图需要**自行绘制**，用matplotlib或类似工具，展示一个示例章节的情感弧线走向

### 4.4 验证-修复循环 (Validation-Repair Loop)

**写什么：**
这是本管线的关键创新点——不是盲目重试，而是**问题感知的定向修复**。

#### 4.4.1 循环机制
1. LLM输出JSON → Pydantic解析 → 业务规则验证
2. 收集 `ValidationIssue` 列表，分级：error（阻塞）/ warning（非阻塞）/ info
3. 如果仅有warning → 通过（status=ok）
4. 如果有error且attempt < 3 → 生成修复提示词（包含**具体错误信息+枚举白名单**）→ LLM修复 → 重新验证
5. 如果3轮后仍有error → 返回status=failed + 最佳尝试 + 错误列表 → 人工兜底

#### 4.4.2 修复提示词设计
- 告诉LLM"你之前的输出有以下问题"
- 给出每个问题的**位置、类型、当前值、期望值**
- 附带枚举白名单（如shot_type的合法值列表）
- 要求LLM**只修改有问题的字段**，保持正确字段不变

#### 4.4.3 成功率分析
- 第1轮通过率（估计值，需实测）
- 经3轮修复后最终通过率 >95%
- 常见修复场景：枚举值拼写错误、字段缺失、数值超范围、角色名误提取

> **需要生成的图：**
> - **图4-5：验证-修复循环流程图**（3轮循环，标注每轮的pass/fail路径）
>   - 来源：paper-materials.md §6.5
> - **表4-1：验证规则汇总表**（规则名、适用阶段、约束条件、通过/失败示例）
>   - 来源：paper-materials.md §6.5 的表格，补充更多规则

---

## 第五章 多智能体协作架构 (Multi-Agent Collaboration Architecture)

> 这是论文的**第二个核心贡献**，对应 `services/agents/` 和 `services/conversation/` 模块

### 5.1 架构总览

**写什么：**
- 为什么选择专业Agent分工而非ReAct自主循环
  - ReAct的问题：工具选择不稳定、执行路径不可预测、难以成本控制
  - 专业分工的优势：每个Agent有独立system prompt和工具子集、意图路由可预测、审批门控可控
- 系统的3层架构：IntentRouter（意图分类）→ AgentOrchestrator（协调调度）→ SpecializedAgents（执行）

> **需要生成的图：**
> - **图5-1：多智能体协作架构总览图**（3层：Router → Orchestrator → 6个Agent，标注工具和数据流）
>   - 来源：paper-materials.md §3.1 类图 + §3.2 时序图，合并重绘

### 5.2 意图路由 (Intent Router)

**写什么：**
- LLM意图分类器的设计：输入用户消息+对话上下文 → 输出primary_intent + confidence + entities
- 6种意图类别：story_genesis（故事创作）、script（剧本/分镜）、asset（资产管理）、render（渲染）、qa（质量）、general（兜底）
- 关键词匹配兜底机制：当LLM返回无法解析的JSON时，降级为关键词匹配
- 意图与Agent的路由映射表

> **需要生成的图：**
> - **图5-2：意图路由流程图**（用户消息 → LLM分类器 → [成功] 路由 / [失败] 关键词兜底 → Agent选择）
>   - 来源：paper-materials.md §5.3

### 5.3 智能体层次结构

**写什么：**

#### 5.3.1 基础Agent（BaseAgent）
- 抽象接口：`process(message, intent, context) → AsyncGenerator`
- 共享能力：StandardLLMService（多供应商LLM统一接口）、流式响应、对话历史构建（最近5轮）

#### 5.3.2 六种专业Agent
每种Agent的职责、system prompt设计要点、工具集：

| Agent | 职责 | 工具 |
|-------|------|------|
| StoryAgent | 对话式故事创作（4阶段状态机） | generate_storyboard |
| ScriptAgent | 剧本生成/优化 | generate_storyboard, refine_script |
| AssetAgent | 角色/场景/道具管理 | create_character, create_scene, query_assets |
| RenderingAgent | 图像/视频渲染调度 | render_panels, generate_video, get_render_status |
| QAAgent | 质量分析与修复建议 | analyze_quality, suggest_fixes |
| DirectorAgent | 工作台精细控制 | SchemaGuard + PatchGenerator |

> **需要生成的图：**
> - **图5-3：Agent继承层次类图**（UML类图，BaseAgent → 6个子类，标注关键方法和属性）
>   - 来源：paper-materials.md §3.1

### 5.4 StoryAgent：对话式创作状态机

**写什么：**
详细描述StoryAgent的3阶段状态机（系统实际实现为3阶段，非4阶段）：

1. **INTAKE（灵感采集）**：LLM引导用户回答8个故事要素
   - 类型/风格偏好 + 正面/反面参考作品
   - 主角设计（优势+致命缺陷）
   - 核心关系（最需要的人 + 为何推开他们）
   - 故事引擎（每集产生新问题的机制）
   - 主题问题（一句话）
   - 基调护栏（分级/暴力/喜剧等级）
   - 设定+视觉关键词
   - 结局赌注（不可逆转的变化）
2. **BUILD（自动生成）**：基于CreativeBrief自动生成角色档案（Power Stack心理学：want/need/lie/ghost）+ 剧本（Goal/Obstacle/Turn/Cost结构）
3. **STORYBOARD（分镜转换）**：调用第四章的两阶段管线，将剧本转化为分镜面板

> **需要生成的图：**
> - **图5-4：StoryAgent 状态机图**（状态转换图，3个状态 + 转换条件）
>   - 来源：paper-materials.md §5.1，但修正为3阶段

### 5.5 工具注册与审批门控

**写什么：**
- ToolRegistry 的设计：名称→schema→handler 三元映射
- 14个工具的分类、参数schema、审批策略
- 审批门控机制（requires_approval标志）：
  - 免审批工具：查询类（query_assets, get_render_status）、分析类（analyze_quality）
  - 需审批工具：资源创建（create_character, create_scene）、高成本操作（render_panels, generate_video）
- 成本估算机制：render_panels=5.0×面板数, generate_video=3.0×面板数

> **需要生成的图：**
> - **表5-1：工具注册表**（14个工具的名称、分类、审批要求、成本等级）
>   - 来源：paper-materials.md §3.4

### 5.6 编排协作流程

**写什么：**
用一个完整示例描述从用户消息到Agent响应的全流程：
1. 用户发送消息 → 保存到DB
2. IntentRouter分析意图 → 选择Agent
3. Agent流式生成响应 → WebSocket推送给前端
4. Agent发出工具调用 → Orchestrator执行 → 判断是否需审批
5. 审批通过后执行工具 → 结果返回Agent → Agent继续生成
6. 保存完整对话记录（含意图、工具调用、结果）

> **需要生成的图：**
> - **图5-5：编排协作时序图**（用户 → Orchestrator → IntentRouter → Agent → ToolRegistry → DB → WebSocket 的完整时序）
>   - 来源：paper-materials.md §3.2

---

## 第六章 视觉一致性保障 (Visual Consistency Mechanisms)

> 这是论文的**第三个核心贡献**，对应 `services/portrait/`, `services/identity/`, `services/faceid/`, `services/scene_anchor/`, `services/scene/`

### 6.1 问题定义

**写什么：**
- AI生成图像的一致性挑战：同一提示词+不同种子 → 同一角色外貌差异巨大
- 漫剧对一致性的严格要求：读者需要跨面板识别角色、场景空间结构需要连贯
- 两类一致性需求：**角色一致性**（人脸/服装/体型）和 **场景一致性**（空间结构/光照/透视）

### 6.2 角色一致性：FaceID系统

**写什么：**

#### 6.2.1 三级保障架构
1. **Level 1 - 嵌入提取**：用户上传参考图 → InsightFace buffalo_l 人脸检测 → 512维归一化嵌入向量 → 存储到MinIO
2. **Level 2 - 标准肖像选择**：系统生成N张候选肖像 → 6维评分体系（人脸检测30分、大小20分、单人脸15分、居中度10分、正面姿态15分、质量分10分）→ 选择最佳候选作为标准参考
3. **Level 3 - 渲染时注入**：渲染每个面板时通过IP-Adapter注入FaceID嵌入 → 保证跨面板角色外貌一致

#### 6.2.2 多图平均嵌入
- 支持多张参考图（正面/侧面/表情）的嵌入向量取平均+归一化
- 比单图嵌入更稳定、更抗角度变化

#### 6.2.3 FaceID强度调控
- `faceid_strength` 参数（0.0-1.0）控制一致性约束强度
- QA检测到face drift时自动提升：`new_weight = 0.7 + 0.1 × retry_count`

> **需要生成的图：**
> - **图6-1：FaceID三级保障架构图**（3个level层叠，标注数据流和存储位置）
>   - 来源：paper-materials.md §9.1
> - **图6-2：候选肖像评分雷达图**（6维评分体系的雷达图，展示一个好候选和一个差候选的对比）
>   - 这张图需要**自行绘制**

### 6.3 场景一致性：SceneAnchor系统

**写什么：**

#### 6.3.1 三类控制图
- **Canny边缘图**：OpenCV Canny边缘检测 → 捕捉锐利结构轮廓
- **深度图**：MiDaS深度估计 → 灰度深度信息（近白远黑）
- **线稿图**：LineartDetector → 矢量化线条

#### 6.3.2 渲染时注入
- 通过ControlNet将3类控制图注入渲染过程
- `controlnet_strength` 参数控制约束力度
- 保证同一场景在不同面板中的**空间结构、透视关系、深度层次**一致

#### 6.3.3 存储结构
```
anchors/scenes/{scene_id}/
├── anchor.png     # 基础背景图
├── depth.png      # 深度控制图
├── canny.png      # 边缘控制图
├── lineart.png    # 线稿控制图
└── metadata.json  # 元数据
```

> **需要生成的图：**
> - **图6-3：SceneAnchor控制图生成流程**（一张背景图 → 3类控制图 → ControlNet注入渲染）
>   - 来源：paper-materials.md §10.1
> - **图6-4：场景一致性效果对比**（同一场景在不同面板中的渲染结果：无Anchor vs 有Anchor）
>   - 这张图需要**用系统实际生成结果截图**

### 6.4 依赖图谱与增量渲染

**写什么：**
- 资产变更影响分析：修改角色外貌 → 需要重新渲染所有包含该角色的面板
- 5种变更级别：对话修改（仅重排文字~5s）→ 镜头修改（单面板重渲染~30s）→ 角色修改（多面板）→ 场景修改（多面板）→ 风格修改（全局）
- RenderPlan 生成最小化渲染集合，避免全量重渲染
- 增量渲染加速效果：3-4×

> **需要生成的图：**
> - **图6-5：依赖图谱变更传播示意图**（资产修改 → 影响分析 → 最小渲染集合）
>   - 来源：paper-materials.md §11.2

---

## 第七章 渲染管线与质量保障 (Rendering Pipeline & Quality Assurance)

### 7.1 多供应商渲染架构

**写什么：**
- 统一渲染协议 `PanelRenderContext` 的设计：封装所有渲染所需信息（面板规格、资产锁定、镜头参数、风格设定、一致性控制）
- 供应商选择逻辑：Doubao（有API key时）→ ComfyUI（有URL时）→ Mock（兜底）
- 各供应商的特点和适用场景

#### 7.1.1 提示词自动编译（PromptCompiler）
- 6类Token按优先级排序拼接：Scene → Character → Action(CRITICAL) → Camera → Style → Quality
- 每类Token从PanelRenderContext的结构化字段自动生成
- 负面提示词默认值："text, watermark, blurry, low quality, deformed, nsfw"

> **需要生成的图：**
> - **图7-1：PanelRenderContext 数据结构图**（展示结构化字段分组：标识/资产锁/渲染参数/一致性控制/分级）
> - **图7-2：提示词编译流程图**（6类Token → 优先级排序 → 最终prompt）
>   - 来源：paper-materials.md §7.4

### 7.2 三级渲染策略

**写什么：**
- 三级策略定义：
  - fast：8步, 540×960, CFG=5.0, 成本0.2× → 预览验证
  - normal：20步, 1080×1920, CFG=7.0, 成本1.0× → 标准生产
  - hero：40步, 1440×2560, CFG=8.0, 成本2.5× → 精品级
- 两阶段工作流：fast全部面板 → 人工筛选（~50%通过）→ normal精渲
- 成本分析（30面板章节）：
  - 单次全渲染：30×$0.05 = $1.50
  - 两阶段策略：(30×$0.01) + (15×$0.05) = $1.05（**节省30%**）

> **需要生成的图：**
> - **图7-3：三级渲染策略对比图**（3级的参数对比 + 两阶段工作流示意）
>   - 来源：paper-materials.md §7.3
> - **表7-1：三级渲染参数与成本对比表**

### 7.3 ComfyUI 4阶段渲染流水线

**写什么：**
- R0 Full Render：加载模型+LoRA+文本编码+IP-Adapter FaceID+ControlNet → full.png
- R1 Layer Cutout：语义分割→精炼蒙版→抠图 → char.png
- R2 BG Inpaint：空洞蒙版→背景修复 → bg.png
- R3 FG Effects：特效蒙版→前景特效 → fg.png（可选）
- 输出：LayerPack（5层图+manifest.json）

> **需要生成的图：**
> - **图7-4：ComfyUI 4阶段渲染流水线图**（R0→R1→R2→R3 + 输入/输出标注）
>   - 来源：paper-materials.md §7.1

### 7.4 自动QA与修复

**写什么：**

#### 7.4.1 五项自动检测
1. 分辨率检测（min 1080×1920）→ ERROR
2. 黑图检测（均值亮度<10）→ ERROR
3. 过曝检测（均值亮度>245）→ WARNING
4. 模糊检测（Laplacian方差<100）→ WARNING
5. 信息熵检测（entropy<4.0）→ WARNING

评分公式：
- 有ERROR → score=0.0, passed=false
- 有WARNING → score=max(0.5, 1.0-0.1×N), passed=true
- 无问题 → score=1.0, passed=true

#### 7.4.2 自动修复策略矩阵
6类问题 × 3种策略（逐步升级），最多重试3次/面板：
- FACE_DRIFT：提升faceid权重 → 降低CFG → 人工
- NO_FACE：收紧景别 → 换种子 → 人工
- BLACK_IMAGE：换种子 → 增加步数 → 人工
- BLURRY：增加步数 → 超分辨率 → 人工

> **需要生成的图：**
> - **图7-5：QA检测与自动修复流程图**（LayerPack → 5项检测 → 评分 → Pass/Fail → FixPlan → 重试）
>   - 来源：paper-materials.md §12.1
> - **表7-2：自动修复策略矩阵**（问题类型×策略1/2/3）
>   - 来源：paper-materials.md §12.2

### 7.5 异步任务架构

**写什么：**
- Celery + Redis 的异步任务分发
- 5个专用队列：image, video, anchor, export, default
- WebSocket实时推送渲染进度（24种事件类型）
- 前端双模WebSocket客户端（real WS + mock fallback）

> **需要生成的图：**
> - **图7-6：异步任务与实时推送架构图**（API → Redis → Workers → MinIO → WebSocket → 前端）
>   - 来源：paper-materials.md §7.5 + §14.1 合并

---

## 第八章 前端交互设计 (Frontend Interaction Design)

### 8.1 Studio工作台

**写什么：**
- 4面板布局设计理念和功能划分
  - 左面板：剧本编辑器 + 资产浏览器
  - 中央面板：分镜网格视图（PanelCard）+ Konva画布（图层可视化/ROI选区/气泡拖拽）
  - 右面板：7个检查器Tab（Story/Cast/Layout/Layers/Timeline/Consistency/QA）
  - 底部面板：时间线轨道 + 任务控制台
- Zustand双Store架构：studioStore（1476行，管理工作台全状态）+ chatStore（382行，管理对话状态）
- 实时状态同步：WebSocket事件 → Store更新 → UI响应

> **需要生成的图：**
> - **图8-1：Studio 4面板布局示意图**（标注各面板功能区域）
>   - 来源：paper-materials.md §4.1，或截取系统运行时截图
> - **图8-2：双Store状态管理架构图**
>   - 来源：paper-materials.md §13.2

### 8.2 Agent Chat 对话式创作

**写什么：**
- 对话式交互流程：灵感输入 → 大纲生成 → 确认/完善 → 分集管理 → 单集剧本 → 分镜预览
- ActionCard 机制：Agent响应中嵌入可操作卡片（确认大纲/预览分镜/渲染面板等）
- 与Studio工作台的衔接：Agent Chat中确认的分镜可以无缝进入Studio进行精细编辑

> **需要生成的图：**
> - **图8-3：Agent Chat 交互流程时序图**（用户 → 界面 → API → LLM → 结果卡片）
>   - 来源：paper-materials.md §5.2

### 8.3 导出管线

**写什么：**
- 6步导出流程：收集快照 → 解析产物 → 下载到暂存区 → 写入面板文件夹 → 写入根文件 → ZIP打包上传
- 导出包结构（manifest.json + chapter.json + assets.json + provenance/ + panels/）

> **需要生成的图：**
> - **图8-4：导出包目录结构图**
>   - 来源：paper-materials.md §15.2

---

## 第九章 实验与评估 (Experiments & Evaluation)

### 9.1 实验设置

**写什么：**
- 硬件/软件环境
- 测试数据集：选取N个不同类型的剧本（如：校园、奇幻、悬疑，各若干话）
- 评估指标定义

### 9.2 分镜生成质量评估

**写什么：**
- **验证通过率实验**：
  - Stage1（ScriptAnalysis）的首次通过率、修复后通过率
  - Stage2（StoryboardDraft）的首次通过率、修复后通过率
  - 对照组：无修复循环的单次生成
- **结构完整性评估**：生成的分镜是否覆盖了原剧本的所有叙事节拍
- **情感弧线连贯性**：emotion_intensity的相邻变化是否满足Δ≤0.3约束

> **需要生成的图：**
> - **图9-1：修复循环各轮通过率柱状图**（Attempt1/2/3的通过率对比）
> - **图9-2：有/无修复循环的通过率对比图**
> - **表9-1：各类验证错误的出现频率和修复成功率**
>   - 这些图表需要**跑实验后用实际数据绘制**

### 9.3 视觉一致性评估

**写什么：**
- **角色一致性**：同一角色在不同面板中的FaceID相似度（余弦相似度）
  - 对照组：无FaceID注入 vs 有FaceID注入
  - 评估指标：平均余弦相似度、最低相似度、人工评分
- **场景一致性**：同一场景在不同面板中的结构相似度
  - 对照组：无SceneAnchor vs 有SceneAnchor
  - 评估方式：结构相似度（SSIM）+ 人工评分

> **需要生成的图：**
> - **图9-3：角色一致性对比图**（无FaceID vs 有FaceID的多面板渲染结果）
> - **图9-4：场景一致性对比图**（无Anchor vs 有Anchor的多面板渲染结果）
> - **表9-2：一致性量化指标表**
>   - 这些需要**用系统实际渲染结果截图+计算相似度**

### 9.4 渲染效率与成本评估

**写什么：**
- **三级渲染策略**的时间和成本对比
- **增量渲染**的加速比（修改单个参数后的重渲染面板数 vs 全量）
- **QA自动修复**的效果：自动修复成功率、平均重试次数、减少的人工干预比例

> **需要生成的图：**
> - **表9-3：三级渲染时间与成本对比**
> - **图9-5：增量渲染加速比图**（5种变更类型的重渲染面板比例）
> - **表9-4：QA自动修复统计**（各问题类型的出现率、修复成功率、平均重试次数）

### 9.5 系统整体性能

**写什么：**
- 30面板章节的端到端指标：

| 指标 | 数值 |
|------|------|
| 分镜生成延迟 | 20-50秒 |
| 单面板渲染(fast) | ~3秒 |
| 单面板渲染(normal) | ~30秒 |
| 全章节端到端 | ~5分钟 |
| QA通过率(含重试) | 92% |
| 两阶段成本节省 | 30% |
| 增量渲染加速 | 3-4× |

### 9.6 用户研究（可选）

**写什么：**
- 如有条件，招募N名用户（专业/非专业各半）进行试用
- 评估维度：任务完成时间、满意度评分、系统可用性量表（SUS）
- Studio vs Agent Chat 的用户偏好对比

---

## 第十章 总结与展望 (Conclusion & Future Work)

### 10.1 研究总结

**写什么：**
回顾3个核心贡献，总结每个贡献解决了什么问题、取得了什么效果。

### 10.2 局限性

**写什么：**
- 一致性保障依赖FaceID质量，极端角度/遮挡场景效果下降
- LLM分镜生成的创意性受限于提示词模板
- 系统对GPU资源的依赖（ComfyUI集群或商业API成本）
- 情感弧线约束目前是规则式的，未来可以用学习方法

### 10.3 未来工作

**写什么：**
- 引入更强的一致性模型（如角色LoRA自动训练）
- 支持更多漫剧风格和叙事类型
- 优化LLM管线性能（缓存、并行、更小模型微调）
- 加入读者反馈闭环（A/B测试 → 自动优化生成参数）
- 探索端到端多模态模型替代流水线式架构

---

## 附录

### 附录A：核心代码模块索引

| 模块 | 文件路径 | 代码行数 |
|------|---------|---------|
| LLM服务 | `services/brain/standard_llm.py` | ~700 |
| 分镜生成器 | `services/brain/storyboard_generator.py` | ~467 |
| 提示词编排 | `services/brain/prompt_composer.py` | ~480 |
| 验证器 | `services/brain/repair/validator.py` | ~616 |
| 编排器 | `services/conversation/agent_orchestrator.py` | ~400 |
| 意图路由 | `services/conversation/intent_router.py` | ~300 |
| 工具注册 | `services/conversation/tool_registry.py` | ~350 |
| 故事Agent | `services/agents/story_agent.py` | ~649 |
| 渲染协议 | `services/layer_factory/render_protocol.py` | ~400 |
| 面板渲染 | `services/layer_factory/panel_renderer.py` | ~500 |
| QA服务 | `services/qa/image_qa.py` | ~300 |
| 依赖图谱 | `services/graph/dependency_graph.py` | ~300 |
| Studio Store | `lib/store/studioStore.ts` | ~1476 |

### 附录B：枚举值速查表

- ShotType: ECU, CU, MS, LS, WS, OTS
- CameraMove: static, pan, tilt, dolly_in, dolly_out, zoom_in, zoom_out, handheld
- EmotionLabel: tense, calm, joyful, sad, angry, fearful, hopeful, melancholic, dramatic, neutral
- Pacing: slow, moderate, fast, climax
- TransitionType: cut, dissolve, fade_in, fade_out, wipe

### 附录C：完整验证规则清单

（从 validator.py 中提取的全部30+条规则的详细描述）

---

## 图表清单汇总

| 编号 | 图表名 | 类型 | 来源 | 需要额外工作 |
|------|--------|------|------|-------------|
| 图3-1 | 系统分层架构图 | 架构图 | paper-materials §1.1 | 重绘为学术风格 |
| 图3-2 | 端到端数据流图 | 流程图 | paper-materials §1.2 | 标注数据模型名 |
| 表3-1 | 核心技术选型表 | 表格 | paper-materials §2.1 | 直接使用 |
| 图3-3 | 双模交互架构对比 | 对比图 | 自行设计 | **新建** |
| 图4-1 | 两阶段管线总览 | 流程图 | paper-materials §6.1 | 重绘 |
| 图4-2 | ScriptAnalysisV1 类图 | UML类图 | paper-materials §6.2 | 重绘 |
| 图4-3 | PanelDraft 数据模型 | UML类图 | paper-materials §6.3 | 重绘 |
| 图4-4 | 情感弧线示例曲线 | 折线图 | 自行绘制 | **新建(matplotlib)** |
| 图4-5 | 验证-修复循环流程 | 流程图 | paper-materials §6.5 | 重绘 |
| 表4-1 | 验证规则汇总表 | 表格 | paper-materials §6.5 | 补充扩展 |
| 图5-1 | 多Agent协作总览 | 架构图 | paper-materials §3.1+§3.2 | **合并重绘** |
| 图5-2 | 意图路由流程 | 流程图 | paper-materials §5.3 | 重绘 |
| 图5-3 | Agent继承层次类图 | UML类图 | paper-materials §3.1 | 重绘 |
| 图5-4 | StoryAgent 状态机 | 状态图 | paper-materials §5.1 | 修正为3阶段 |
| 表5-1 | 工具注册表 | 表格 | paper-materials §3.4 | 直接使用 |
| 图5-5 | 编排协作时序图 | 时序图 | paper-materials §3.2 | 重绘 |
| 图6-1 | FaceID三级保障架构 | 架构图 | paper-materials §9.1 | 重绘 |
| 图6-2 | 候选肖像评分雷达图 | 雷达图 | 自行绘制 | **新建(matplotlib)** |
| 图6-3 | SceneAnchor控制图生成 | 流程图 | paper-materials §10.1 | 重绘 |
| 图6-4 | 场景一致性效果对比 | 截图对比 | 系统生成 | **实际运行截图** |
| 图6-5 | 依赖图谱变更传播 | 流程图 | paper-materials §11.2 | 重绘 |
| 图7-1 | PanelRenderContext 结构 | 数据结构图 | 自行设计 | **新建** |
| 图7-2 | 提示词编译流程 | 流程图 | paper-materials §7.4 | 重绘 |
| 图7-3 | 三级渲染策略对比 | 对比图 | paper-materials §7.3 | 重绘 |
| 表7-1 | 三级渲染参数成本表 | 表格 | paper-materials §7.3 | 直接使用 |
| 图7-4 | ComfyUI 4阶段流水线 | 流程图 | paper-materials §7.1 | 重绘 |
| 图7-5 | QA检测与修复流程 | 流程图 | paper-materials §12.1 | 重绘 |
| 表7-2 | 自动修复策略矩阵 | 表格 | paper-materials §12.2 | 直接使用 |
| 图7-6 | 异步任务与推送架构 | 架构图 | paper-materials §7.5+§14 | **合并重绘** |
| 图8-1 | Studio 4面板布局 | 界面截图 | 系统截图 | **实际运行截图** |
| 图8-2 | 双Store状态管理 | 架构图 | paper-materials §13.2 | 重绘 |
| 图8-3 | Agent Chat 时序图 | 时序图 | paper-materials §5.2 | 重绘 |
| 图8-4 | 导出包目录结构 | 树形图 | paper-materials §15.2 | 直接使用 |
| 图9-1 | 修复循环通过率 | 柱状图 | 实验数据 | **跑实验绘制** |
| 图9-2 | 有/无修复对比 | 柱状图 | 实验数据 | **跑实验绘制** |
| 表9-1 | 验证错误频率与修复率 | 表格 | 实验数据 | **跑实验填写** |
| 图9-3 | 角色一致性对比 | 截图对比 | 系统生成 | **实际运行截图** |
| 图9-4 | 场景一致性对比 | 截图对比 | 系统生成 | **实际运行截图** |
| 表9-2 | 一致性量化指标 | 表格 | 实验数据 | **跑实验填写** |
| 表9-3 | 渲染时间成本对比 | 表格 | 实验数据 | **跑实验填写** |
| 图9-5 | 增量渲染加速比 | 柱状图 | 实验数据 | **跑实验绘制** |
| 表9-4 | QA修复统计 | 表格 | 实验数据 | **跑实验填写** |

**图表统计：**

- 总计：~25张图 + ~12张表
- 可从paper-materials直接重绘：~18张
- 需要新建绘制：~4张（图3-3, 图4-4, 图6-2, 图7-1）
- 需要系统运行截图：~3张（图6-4, 图8-1, 图9-3/9-4）
- 需要实验数据：~7张（第九章全部图表）
