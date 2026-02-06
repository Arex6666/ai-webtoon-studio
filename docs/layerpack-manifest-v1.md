# LayerPack Manifest v1 规范

> 版本: 1.0.0  
> 最后更新: 2026-01-17

---

## 1. 面板基准规格

### 1.1 画幅标准

| 类型 | 宽度 | 高度 | 比例 | 用途 |
|------|------|------|------|------|
| **webtoon_standard** | 1080 | 1920 | 9:16 | 条漫标准（推荐） |
| webtoon_hd | 1440 | 2560 | 9:16 | 高清条漫 |
| square | 1024 | 1024 | 1:1 | 正方形场景 |
| landscape | 1920 | 1080 | 16:9 | 横向全景 |

**默认规格**: `1080×1920` (webtoon_standard)

### 1.2 输出格式

| 层类型 | 格式 | 色彩空间 | 质量/设置 |
|--------|------|----------|-----------|
| full | PNG | sRGB | 无损 |
| background | PNG | sRGB | 无损 |
| character | PNG | sRGB | 透明通道 |
| lineart | PNG | Grayscale | 透明通道 |
| alpha | PNG | Grayscale | 8-bit |

---

## 2. MinIO 目录规范

### 2.1 Key 模板

```
{bucket}/{project_id}/{chapter_id}/{panel_id}/{attempt_id}/{filename}
```

### 2.2 目录结构示例

```
webtoon-studio/
└── proj-abc123/
    └── ch-001/
        └── panel-001/
            ├── attempt-001/
            │   ├── manifest.json
            │   ├── full.png
            │   ├── background.png
            │   ├── character.png
            │   └── lineart.png
            └── attempt-002/
                ├── manifest.json
                └── full.png
```

### 2.3 命名规则

| 组件 | 格式 | 示例 |
|------|------|------|
| project_id | `proj-{uuid8}` | `proj-a1b2c3d4` |
| chapter_id | `ch-{3位序号}` | `ch-001` |
| panel_id | `panel-{3位序号}` | `panel-012` |
| attempt_id | `attempt-{3位序号}` | `attempt-001` |
| layerpack_id | `lp-{timestamp}-{uuid6}` | `lp-1737100800-abc123` |

---

## 3. Manifest 规范

### 3.1 最小必需字段

```json
{
  "version": "1.0.0",
  "id": "lp-1737100800-abc123",
  "panel_id": "panel-001",
  "project_id": "proj-a1b2c3d4",
  "chapter_id": "ch-001",
  "attempt": 1,
  
  "dimensions": {
    "width": 1080,
    "height": 1920,
    "aspect": "9:16"
  },
  
  "generation": {
    "seed": 42,
    "model": "flux-dev",
    "model_version": "1.0",
    "provider": "comfyui",
    "steps": 20,
    "cfg": 7.5,
    "sampler": "euler_a",
    "scheduler": "normal"
  },
  
  "prompts": {
    "positive": "...",
    "negative": "..."
  },
  
  "outputs": {
    "full": "full.png",
    "background": "background.png",
    "character": "character.png",
    "lineart": "lineart.png"
  },
  
  "metadata": {
    "created_at": "2026-01-17T01:00:00Z",
    "duration_ms": 12500,
    "cost": 3.0
  }
}
```

### 3.2 完整字段说明

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `version` | string | ✅ | Manifest 版本号 |
| `id` | string | ✅ | LayerPack 唯一ID |
| `panel_id` | string | ✅ | 所属面板ID |
| `project_id` | string | ✅ | 所属项目ID |
| `chapter_id` | string | ✅ | 所属章节ID |
| `attempt` | number | ✅ | 尝试序号 |
| `dimensions.width` | number | ✅ | 宽度像素 |
| `dimensions.height` | number | ✅ | 高度像素 |
| `dimensions.aspect` | string | ✅ | 宽高比 |
| `generation.seed` | number | ✅ | 随机种子 |
| `generation.model` | string | ✅ | 模型名称 |
| `generation.model_version` | string | ❌ | 模型版本 |
| `generation.provider` | string | ✅ | 生成服务 |
| `generation.steps` | number | ❌ | 采样步数 |
| `generation.cfg` | number | ❌ | 引导系数 |
| `prompts.positive` | string | ✅ | 正向提示词 |
| `prompts.negative` | string | ❌ | 负向提示词 |
| `outputs.full` | string | ✅ | 完整图相对路径 |
| `outputs.*` | string | ❌ | 其他图层相对路径 |
| `metadata.created_at` | string | ✅ | ISO8601 时间戳 |
| `metadata.duration_ms` | number | ❌ | 生成耗时毫秒 |
| `metadata.cost` | number | ❌ | 成本单位 |

### 3.3 可选扩展字段

```json
{
  "identity_assets": ["identity-zhouyu", "identity-linzhixia"],
  "scene_assets": ["scene-bookstore"],
  "style_profile_id": "style-webtoon-dark",
  "anchors": [
    { "kind": "depth", "weight": 0.8 }
  ],
  "qa": {
    "score": 0.85,
    "issues": []
  },
  "parent_layerpack_id": null
}
```

---

## 4. URL 构建规则

### 4.1 MinIO URL 格式

```
https://{minio_host}/{bucket}/{project_id}/{chapter_id}/{panel_id}/{attempt_id}/{filename}
```

### 4.2 示例

```
https://minio.example.com/webtoon-studio/proj-a1b2c3d4/ch-001/panel-001/attempt-001/full.png
```

### 4.3 CDN URL（可选）

```
https://cdn.example.com/layerpacks/{layerpack_id}/full.png
```

---

## 5. 版本兼容性

| Manifest 版本 | 最低前端版本 | 最低后端版本 |
|---------------|--------------|--------------|
| 1.0.0 | 0.1.0 | 0.1.0 |

---

## 6. 验收检查清单

- [ ] manifest.json 包含所有必需字段
- [ ] full.png 存在且可访问
- [ ] 目录路径符合 `{project}/{chapter}/{panel}/{attempt}` 格式
- [ ] seed 和 generation 参数完整，可用于复现
- [ ] created_at 为 ISO8601 格式
