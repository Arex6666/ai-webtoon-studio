"""
Repair Prompt - 只修 JSON，不重写剧情

这是修复提示词和生成提示词是两套的关键落点。
"""
import json
from typing import Dict, Any, Optional, List

from .repair_types import ValidationIssue, RepairPlan
from app.schemas.brain.enums import (
    ShotType, CameraMove, TimeOfDay, Weather
)


# ============ 修复提示词模板 ============

REPAIR_SYSTEM_PROMPT = """你是一个 JSON 修复专家。你的任务是根据校验问题修复 JSON 数据。

## 核心规则

1. **只输出 JSON**：不要输出任何解释文字，只输出一个完整的 JSON object
2. **只修不改**：不要改动已有内容的含义，只补缺字段、纠正枚举、增加细节
3. **保持版本**：schema_version 和 prompt_version 必须保持不变
4. **严格遵循提示**：按照每个问题的 hint 进行修复

## 修复优先级
1. 补缺字段
2. 纠正非法枚举值
3. 补足 composition_notes / continuity_notes
4. 补充 source_span.quote
5. 增强细节深度
"""

REPAIR_DEVELOPER_ANALYSIS = """## 修复 ScriptAnalysisV1

### 枚举白名单
- role: protagonist | supporting | minor | unknown
- type (location): interior | exterior | semi
- time_of_day_default: ${TIME_OF_DAY}
- weather_default: ${WEATHER}

### 必须字段
- characters[].canonical_name 不能为空
- characters[].appearance_traits 至少 2 个
- characters[].personality_traits 至少 2 个
- characters[].first_appearance_span.quote 15~120 字
- locations[].anchor_hint 不能为空
- beats[].source_span.quote 15~120 字

### 修复原则
- 保留原有内容，只做增量修复
- 如果需要 quote，从用户提供的剧本中摘录
"""

REPAIR_DEVELOPER_STORYBOARD = """## 修复 StoryboardDraftV2

### 枚举白名单（只能选这些值）
- shot_type: ${SHOT_TYPES}
- camera_move: ${CAMERA_MOVES}
- time_of_day: ${TIME_OF_DAY}
- weather: ${WEATHER}

### 硬约束
- panels[].composition_notes 至少 2 条
- panels[].continuity_notes 至少 1 条
- panels[].actions 至少 15 个汉字
- panels[].visual_prompt 至少 20 字，需包含环境/光照
- panels[].source_span.quote 15~120 字
- panels[].duration_s 范围 1.5~8.0

### 细节增强模板

**构图 (composition_notes)**：
- 主体位置：如 "人物置于画面右三分之一处"
- 景深：如 "前景虚化，背景清晰"
- 前景遮挡：如 "窗框形成画中画构图"
- 光源方向：如 "左侧窗户透入的侧光"
- 视觉焦点：如 "视线引导至人物手中的信封"

**动作 (actions)**：
- 起始姿态 → 动作变化 → 表情变化 → 情绪动机
- 示例：周昀站在书架旁，右手轻轻拂过书脊，目光望向窗外的雨，眼神中带着若有所思的神色，嘴角微微上扬

**连续性 (continuity_notes)**：
- 服饰：如 "保持白色衬衫 + 米色毛衣穿搭"
- 道具：如 "手中的咖啡杯始终是蓝色"
- 天气：如 "保持雨天昏暗氛围"
- 光线：如 "延续窗边暖色调光线"
"""


def compose_repair_prompt(
    kind: str,  # "analysis" or "storyboard"
    original_json: Dict[str, Any],
    issues: List[ValidationIssue],
    script_text: Optional[str] = None,
    constraints: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """
    生成修复提示词
    
    Args:
        kind: "analysis" 或 "storyboard"
        original_json: 原始 JSON
        issues: 校验问题列表
        script_text: 剧本文本（用于摘录 quote）
        constraints: 约束配置
    
    Returns:
        {"system": ..., "developer": ..., "user": ...}
    """
    # 枚举列表
    enums = {
        "SHOT_TYPES": ", ".join(e.value for e in ShotType),
        "CAMERA_MOVES": ", ".join(e.value for e in CameraMove),
        "TIME_OF_DAY": ", ".join(e.value for e in TimeOfDay),
        "WEATHER": ", ".join(e.value for e in Weather),
    }
    
    # 选择 developer 模板
    if kind == "analysis":
        developer = REPAIR_DEVELOPER_ANALYSIS
    else:
        developer = REPAIR_DEVELOPER_STORYBOARD
    
    # 替换枚举变量
    for key, value in enums.items():
        developer = developer.replace(f"${{{key}}}", value)
    
    # 构建 user prompt
    user_parts = []
    
    # 1. 原始 JSON
    user_parts.append("## 需要修复的 JSON\n")
    user_parts.append("```json")
    user_parts.append(json.dumps(original_json, ensure_ascii=False, indent=2))
    user_parts.append("```\n")
    
    # 2. 问题列表
    user_parts.append("## 校验问题\n")
    for issue in issues:
        severity = "❌" if issue.severity == "error" else "⚠️"
        user_parts.append(f"{severity} **{issue.path}**: {issue.message}")
        if issue.hint:
            user_parts.append(f"   → 提示: {issue.hint}")
        user_parts.append("")
    
    # 3. 剧本文本（用于 quote）
    if script_text:
        user_parts.append("## 原始剧本（用于摘录 quote）\n")
        user_parts.append("```")
        # 限制长度
        if len(script_text) > 3000:
            user_parts.append(script_text[:3000] + "\n...(已截断)")
        else:
            user_parts.append(script_text)
        user_parts.append("```\n")
    
    # 4. 约束
    if constraints:
        user_parts.append("## 约束\n")
        if "duration_range" in constraints:
            min_d, max_d = constraints["duration_range"]
            user_parts.append(f"- 单镜头时长: {min_d} ~ {max_d} 秒")
        user_parts.append("")
    
    # 5. 任务
    user_parts.append("## 任务\n")
    user_parts.append("请修复上述 JSON，输出完整的修复后 JSON。只输出 JSON，不要任何解释。")
    
    return {
        "system": REPAIR_SYSTEM_PROMPT,
        "developer": developer,
        "user": "\n".join(user_parts)
    }


def compose_detail_enhancement_prompt(
    panel_json: Dict[str, Any],
    script_context: str
) -> Dict[str, str]:
    """
    生成细节增强提示词（单个 panel）
    
    用于主动增强分镜细节
    """
    system = """你是一个专业的漫画分镜增强专家。你的任务是为分镜增加更丰富的视觉细节。

## 规则
1. 只输出 JSON
2. 保留原有内容，只做增量增强
3. 重点增强：构图、动作细节、视觉描述
"""
    
    developer = """## 增强要点

### composition_notes（目标：4-6 条）
必须涵盖：
- 主体位置和比例
- 视觉焦点和引导线
- 光源方向和质感
- 景深和层次
- 前中后景安排

### actions（目标：25+ 汉字）
必须包含：
- 完整的动作序列
- 表情细节
- 微动作和小动作
- 情绪表达

### visual_prompt（目标：50+ 字）
必须包含：
- 主体详细描述
- 环境氛围
- 光照效果
- 材质和质感
- 色调和画风
"""
    
    user = f"""## 需要增强的分镜

```json
{json.dumps(panel_json, ensure_ascii=False, indent=2)}
```

## 剧本上下文

```
{script_context[:1000]}
```

## 任务

请增强这个分镜的细节，输出完整的增强后 JSON。
"""
    
    return {
        "system": system,
        "developer": developer,
        "user": user
    }
