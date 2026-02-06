# AI 漫剧系统 - 物品资产管理与全自动化流程设计

**设计日期**: 2026-01-19
**版本**: 1.0
**状态**: 设计完成，待实施

## 1. 概述

### 1.1 设计目标

本设计旨在为 AI Webtoon Studio 添加完整的物品资产管理系统，实现从剧本输入到最终渲染的全自动化流程。核心目标包括：

1. **物品资产系统**: 支持 HandProp（手持物品）、Wardrobe（服装）、SetDressing（场景陈设）三类资产
2. **全自动化流程**: 剧本 → LLM 提取 → 资产生成 → 渲染 → 质量评估 → 自动修复
3. **渲染提供者抽象**: 统一 ComfyUI 和大模型（Kling/Tongyi/Runway）的接口
4. **智能质量控制**: 多维度评估 + 智能修复策略 + 预算感知

### 1.2 核心价值

- **降低创作门槛**: 用户只需输入剧本，系统自动处理所有技术细节
- **提升一致性**: 物品、服装、角色在整个章节中保持视觉一致
- **优化成本**: 智能选择渲染提供者，预算感知的重试策略
- **提高质量**: 多维度质量评估，自动修复常见问题

### 1.3 设计原则

1. **YAGNI (You Aren't Gonna Need It)**: 只实现当前必需的功能，避免过度设计
2. **渐进式增强**: 先实现核心流程，再优化细节
3. **可扩展性**: 预留扩展点，但不提前实现
4. **用户体验优先**: 所有技术决策服务于用户体验

## 2. 系统架构

### 2.1 整体架构层次

```
┌─────────────────────────────────────────────────────────────────┐
│                         前端层 (Next.js)                          │
│  - 剧本编辑器 (ScriptEditor)                                      │
│  - 资产管理面板 (AssetPanel)                                      │
│  - 故事板视图 (StoryboardView)                                    │
│  - 属性检查器 (Inspector)                                         │
│  - 时间轴 (Timeline)                                              │
│  - 渲染队列 (RenderQueue)                                         │
│  - 资产关系图 (AssetGraphView - React Flow)                      │
└─────────────────────────────────────────────────────────────────┘
                              ↕ HTTP/WebSocket
┌─────────────────────────────────────────────────────────────────┐
│                      API 层 (FastAPI)                            │
│  路由层: /chapters, /assets, /props, /render, /qa, /ws          │
│  服务层:                                                          │
│    - BrainService (LLM 解析和分镜)                               │
│    - AssetService (资产管理)                                      │
│    - RenderService (渲染编排)                                     │
│    - QAService (质量评估)                                         │
│    - RepairService (智能修复)                                     │
│    - ProviderManager (提供者管理)                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                    数据层 (PostgreSQL)                           │
│  - Projects, Chapters, Panels, Assets                           │
│  - PropAssets, OutfitVariants, AssetRelations                   │
│  - PanelRenderContexts, RenderJobs, QAReports                   │
└─────────────────────────────────────────────────────────────────┘
                              ↕
┌─────────────────────────────────────────────────────────────────┐
│                  外部服务层 (External)                            │
│  - LLM Providers (DeepSeek/GPT-4/Tongyi/Doubao)                 │
│  - ComfyUI Provider (本地/云端)                                  │
│  - GenImage Providers (Kling/Tongyi/Runway)                     │
│  - MinIO (S3 存储)                                               │
│  - Redis (缓存/队列)                                              │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心数据流

**完整流程**: 剧本输入 → LLM 解析 → 资产注册 → 资产生成 → LLM 分镜 → 渲染上下文构建 → 智能渲染 → 质量评估 → 智能修复 → 气泡渲染 → 导出

详细流程见第 3 节。

## 3. 数据模型设计

### 3.1 PropAsset (物品资产)

```python
class PropAsset(Base, TimestampMixin):
    """物品资产模型 - HandProp 和 SetDressing"""
    __tablename__ = "prop_assets"

    id = Column(String(36), primary_key=True)
    project_id = Column(String(36), ForeignKey("projects.id"))

    # 基本信息
    canonical_name = Column(String(100), nullable=False, index=True)
    aliases = Column(JSON, default=list)  # 别名
    category = Column(String(50), nullable=False)  # hand_prop | set_dressing

    # 视觉描述
    visual_brief = Column(Text, nullable=True)  # 简要描述
    material = Column(String(100), nullable=True)  # 材质
    colors = Column(JSON, default=list)  # 颜色列表
    shape = Column(String(100), nullable=True)  # 形状
    key_features = Column(JSON, default=list)  # 关键特征

    # 生成参数
    default_prompt_tokens = Column(JSON, default=list)  # 默认提示词

    # 参考图
    ref_image_paths = Column(JSON, default=list)  # 候选参考图
    ref_image_status = Column(String(50), default="none")  # none|generating|ready|failed

    # 特征提取
    embedding_path = Column(String(512), nullable=True)  # CLIP/DINOv2 embedding

    # 状态
    status = Column(String(50), default="pending")  # pending|ready|failed
```

**设计要点**:
- `category` 区分手持物品和场景陈设，渲染策略不同
- `ref_image_paths` 存储多个候选图，支持选优
- `embedding_path` 用于图像检索和一致性检查

### 3.2 OutfitVariant (服装变体)

```python
class OutfitVariant(Base, TimestampMixin):
    """服装变体 - 作为 Character 的子资源"""
    __tablename__ = "outfit_variants"

    id = Column(String(36), primary_key=True)
    character_asset_id = Column(String(36), ForeignKey("assets.id"))

    # 服装信息
    outfit_name = Column(String(100), nullable=False)  # 如 "战袍", "便服"
    outfit_description = Column(Text, nullable=False)  # 详细描述
    garment_items = Column(JSON, default=list)  # ["上衣", "裤子", "鞋子"]
    colors = Column(JSON, default=list)  # 颜色列表
    materials = Column(JSON, default=list)  # 材质列表

    # 生成参数
    outfit_prompt = Column(Text, nullable=False)  # 完整的服装提示词

    # 参考图
    ref_image_path = Column(String(512), nullable=True)

    # 默认标记
    is_default = Column(Boolean, default=False)

    # 关系
    character_asset = relationship("Asset", back_populates="outfit_variants")
```

**设计要点**:
- 服装作为角色的变体，而非独立资产
- `outfit_prompt` 直接集成到角色生成提示词中
- `is_default` 标记默认服装，未指定时使用

### 3.3 AssetRelation (资产关系)

```python
class AssetRelation(Base, TimestampMixin):
    """资产关系图谱"""
    __tablename__ = "asset_relations"

    id = Column(String(36), primary_key=True)
    chapter_id = Column(String(36), ForeignKey("chapters.id"))

    # 关系类型
    relation_type = Column(String(50), nullable=False)
    # WEARS, HOLDS, APPEARS_IN, CONTAINS, INTERACTS_WITH

    # 主体
    subject_id = Column(String(36), nullable=False)
    subject_type = Column(String(50), nullable=False)  # character|scene|prop

    # 客体
    object_id = Column(String(36), nullable=False)
    object_type = Column(String(50), nullable=False)

    # 元数据
    metadata = Column(JSON, default=dict)  # 额外信息，如频率、重要性
```

**关系类型**:
- `WEARS`: Character → OutfitVariant
- `HOLDS`: Character → PropAsset (hand_prop)
- `APPEARS_IN`: Character → Scene
- `CONTAINS`: Scene → PropAsset (set_dressing)
- `INTERACTS_WITH`: Character → PropAsset (动作关联)

### 3.4 PanelRenderContext (渲染上下文)

```python
class PanelRenderContext(Base, TimestampMixin):
    """Panel 渲染上下文 - 显式化所有渲染参数"""
    __tablename__ = "panel_render_contexts"

    id = Column(String(36), primary_key=True)
    panel_id = Column(String(36), ForeignKey("panels.id"), unique=True)

    # 角色上下文
    characters_context = Column(JSON, default=list)
    # [{asset_id, face_embedding_path, outfit_id, outfit_prompt}]

    # 手持物品
    props_in_hand = Column(JSON, default=list)
    # [{prop_id, ref_image_path, mask_hint, character_ref, position_hint}]

    # 场景物品
    props_in_scene = Column(JSON, default=list)
    # [{prop_id, prompt_tokens, weight}]

    # 场景锚点
    scene_anchor_id = Column(String(36), nullable=True)

    # 控制图
    control_maps = Column(JSON, default=dict)
    # {depth: path, lineart: path, pose: path}

    # 关系
    panel = relationship("Panel", back_populates="render_context")
```

**设计要点**:
- 将所有渲染参数显式化，避免运行时计算
- 支持预览和调试
- 便于版本追溯

