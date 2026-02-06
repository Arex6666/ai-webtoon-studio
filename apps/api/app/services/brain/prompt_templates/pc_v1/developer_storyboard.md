# Developer Prompt - StoryboardDraftV2 (pc_v1)

## 目标 Schema: storyboard_draft_v2

你必须输出一个符合 StoryboardDraftV2 规范的 JSON 对象。

---

## 必须字段

| 字段 | 类型 | 规则 |
|------|------|------|
| `schema_version` | string | 必须是 `"storyboard_draft_v2"` |
| `prompt_version` | string | 必须是 `"pc_v1"` |
| `panels` | array | 至少 1 个分镜 |

---

## 枚举白名单（只能选这些值）

### shot_type（镜头类型）
`${SHOT_TYPES}`

### camera_move（运镜）
`${CAMERA_MOVES}`

### time_of_day（时间段）
`${TIME_OF_DAY}`

### weather（天气）
`${WEATHER}`

⚠️ **使用枚举以外的值将导致校验失败**

---

## 分镜规则 (PanelDraft)

每个分镜必须包含：

```json
{
  "index": 1,  // 从 1 开始
  "beat_ref": "b001 或 null",
  
  "shot_type": "MS",  // 必须是枚举值
  "camera_move": "static",  // 必须是枚举值
  "duration_s": 3.5,  // ${PER_PANEL_DURATION_MIN} ~ ${PER_PANEL_DURATION_MAX} 秒
  "lens_hint": "50mm",
  "mood": "温柔",  // 至少 1 个情绪词
  
  "location": "旧书店",  // 不能为空
  "time_of_day": "day",  // 必须是枚举值
  "weather": "rainy",  // 必须是枚举值
  
  "cast": ["周昀", "林知夏"],
  "actions": "周昀站在书架旁，目光望向窗外的雨，眼神中带着若有所思的神色",  // 至少 10 字
  "dialogue_lines": ["对话内容"],
  
  "composition_notes": [
    "人物置于右三分之一处",
    "窗户在左侧形成明暗对比"
  ],  // 至少 2 条
  
  "visual_prompt": "一个年轻男子站在昏黄灯光的旧书店内，望着窗外的雨，书架在身后，柔和的暖色调，韩式条漫风格",  // 至少 20 字
  
  "continuity_notes": [
    "保持书店昏黄灯光和雨天氛围"
  ],  // 至少 1 条
  
  "source_span": {
    "quote": "原文摘录 15~120 字"  // 必须
  }
}
```

---

## 硬约束（Detail Threshold）

### actions 质量
- 必须包含"主体动作 + 情绪/动机"
- 最少 10 字

### composition_notes 质量
- **至少 2 条**
- 应包含：镜头位置 / 主体构图 / 光照氛围 / 前中后景

### continuity_notes 质量
- **至少 1 条**
- 应包含：服饰 / 发型 / 道具 / 天气 / 光一致性

### visual_prompt 质量
- 最少 20 字
- 必须包含至少 2 类：主体 + 环境 + 光照 + 画风

### source_span.quote 规则
- 必须摘录原文 15~120 字
- 不能为空

---

## 节奏约束（Pacing Constraint）

- **总时长**：${TOTAL_DURATION_MIN} ~ ${TOTAL_DURATION_MAX} 秒
- **分镜数**：${MIN_PANELS} ~ ${MAX_PANELS} 个
- **单镜头时长**：${PER_PANEL_DURATION_MIN} ~ ${PER_PANEL_DURATION_MAX} 秒

如果超出范围，请自行调整 duration_s 或分镜数量。

---

## 失败条件（任一触发则输出无效）

1. ❌ `shot_type` / `camera_move` / `time_of_day` / `weather` 不在枚举内
2. ❌ `composition_notes` 少于 2 条
3. ❌ `continuity_notes` 为空
4. ❌ `source_span.quote` 为空
5. ❌ `duration_s` 超出 ${PER_PANEL_DURATION_MIN} ~ ${PER_PANEL_DURATION_MAX}
6. ❌ `visual_prompt` 少于 20 字
7. ❌ `schema_version` 不是 `"storyboard_draft_v2"`
