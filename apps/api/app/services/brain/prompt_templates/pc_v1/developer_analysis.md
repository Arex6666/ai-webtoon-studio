# Developer Prompt - ScriptAnalysisV1 (pc_v1)

## 目标 Schema: script_analysis_v1

你必须输出一个符合 ScriptAnalysisV1 规范的 JSON 对象。

---

## 必须字段

| 字段 | 类型 | 规则 |
|------|------|------|
| `schema_version` | string | 必须是 `"script_analysis_v1"` |
| `language` | string | `"zh"` 或 `"en"` |
| `script_digest` | string | 剧本的标识，可用随机字符串 |
| `characters` | array | 至少 1 个角色 |
| `locations` | array | 至少 1 个地点 |
| `beats` | array | 至少 1 个节拍 |

---

## 角色规则 (CharacterEntity)

每个角色必须基于整个剧本的上下文进行精准、细致的特征提取：

```json
{
  "canonical_name": "角色名（必须非空，且准确匹配剧本）",
  "aliases": ["别名1", "别名2"],
  "role": "protagonist | supporting | minor | unknown",
  "appearance_traits": ["特征1", "特征2", "特征3"],  // 至少 3 个详细的外貌/体态/气质特征
  "personality_traits": ["性格1", "性格2", "性格3"],  // 至少 3 个深度的性格/行为特征
  "wardrobe_notes": "详细的常服/穿着描述（必须结合剧本上下文详尽描述，例如款式、颜色、材质。如果剧本毫无暗示，必须默认填写：'三视图 穿着白衬衣黑裤子'）",
  "signature_props": ["标志物"],
  "first_appearance_span": {
    "quote": "原文摘录 15~120 字"  // 必须精确摘录
  }
}
```

**硬约束**：
- 必须通读全文，提取隐晦的描述，不可敷衍。
- `appearance_traits` 少于 3 个 → ❌ 失败
- `personality_traits` 少于 3 个 → ❌ 失败
- `wardrobe_notes` 过于简短（少于15字） → ❌ 失败
- `first_appearance_span.quote` 为空 → ❌ 失败

---

## 地点规则 (LocationEntity)

场景提取必须准确且富有画面感：

```json
{
  "canonical_location": "地点名（必须非空，精确定位）",
  "type": "interior | exterior | semi",
  "time_of_day_default": "day | night | dawn | dusk",
  "weather_default": "clear | rainy | cloudy | foggy | snowy",
  "anchor_hint": "极具画面感的场景详细描述（至少 3 句，描述空间大小、光线、家具/地貌、氛围等细节）",
  "is_reused": false, // 是否是重复出现的已知场景
  "first_appearance_span": {
    "quote": "精确的原文摘录"  // 必须
  }
}
```

---

## 节拍规则 (Beat)

```json
{
  "beat_id": "b001",  // 格式必须是 bXXX
  "summary": "节拍摘要（至少 1 句）",
  "characters_involved": ["角色名"],
  "location_ref": "地点名 或 null",
  "emotional_tone": "情绪描述",
  "source_span": {
    "quote": "原文摘录 15~120 字"  // 必须
  }
}
```

---

## 失败条件（任一触发则输出无效）

1. `appearance_traits` 或 `personality_traits` 少于 3 个
2. 任何 `source_span.quote` 为空
3. `schema_version` 不是 `"script_analysis_v1"`
4. `canonical_name` 或 `canonical_location` 为空
