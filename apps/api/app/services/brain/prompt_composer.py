"""
PromptComposer - 提示词拼装器

根据输入拼出三段式提示词（system / developer / user），
并严格内置"硬规则块"。
"""
import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from string import Template

from .prompt_contract import (
    PromptContract, PromptMeta, PromptConstraints, StyleProfile,
    get_default_style
)
from .digests import (
    digest_text, digest_assets, digest_enums, 
    get_current_enums, get_enum_digest
)


class PromptComposer:
    """
    提示词拼装器
    
    输入：
    - script_text: 剧本文本
    - style_profile: 风格配置
    - assets_context: 资产上下文
    - constraints: 生成约束
    
    输出：
    - PromptContract (pc_v1)
    """
    
    def __init__(
        self,
        script_text: str,
        style_profile: Optional[StyleProfile] = None,
        assets_context: Optional[Dict[str, Any]] = None,
        constraints: Optional[PromptConstraints] = None,
        prompt_version: str = "pc_v1",
        chapter_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ):
        self.script_text = script_text
        self.style_profile = style_profile or get_default_style()
        self.assets_context = assets_context or {}
        self.constraints = constraints or PromptConstraints()
        self.prompt_version = prompt_version
        self.chapter_id = chapter_id
        self.project_id = project_id
        
        # 计算各种 digest
        self.script_digest = digest_text(script_text)
        self.assets_digest = digest_assets(assets_context) if assets_context else None
        self.enum_digest = get_enum_digest()
        self.enums = get_current_enums()
        
        # 模板目录
        self.template_dir = Path(__file__).parent / "prompt_templates" / prompt_version
    
    def compose_analysis_contract(self) -> PromptContract:
        """
        生成 ScriptAnalysisV1 的 PromptContract
        
        用于第一阶段：剧本 → 结构化分析
        """
        system = self._load_template("system.md")
        developer = self._load_template("developer_analysis.md")
        user = self._compose_analysis_user()
        
        meta = PromptMeta(
            script_digest=self.script_digest,
            style_profile=self.style_profile,
            assets_digest=self.assets_digest,
            enum_digest=self.enum_digest,
            constraints=self.constraints,
            chapter_id=self.chapter_id,
            project_id=self.project_id,
        )
        
        return PromptContract(
            prompt_version=self.prompt_version,
            schema_target="script_analysis_v1",
            system=system,
            developer=developer,
            user=user,
            meta=meta,
        )
    
    def compose_storyboard_contract(
        self,
        analysis_json: Optional[Dict[str, Any]] = None
    ) -> PromptContract:
        """
        生成 StoryboardDraftV2 的 PromptContract
        
        用于第二阶段：分析 + 资产 → 分镜
        
        Args:
            analysis_json: 第一阶段生成的 ScriptAnalysisV1 JSON
        """
        system = self._load_template("system.md")
        developer = self._load_template("developer_storyboard.md")
        user = self._compose_storyboard_user(analysis_json)
        
        meta = PromptMeta(
            script_digest=self.script_digest,
            style_profile=self.style_profile,
            assets_digest=self.assets_digest,
            enum_digest=self.enum_digest,
            constraints=self.constraints,
            chapter_id=self.chapter_id,
            project_id=self.project_id,
        )
        
        return PromptContract(
            prompt_version=self.prompt_version,
            schema_target="storyboard_draft_v2",
            system=system,
            developer=developer,
            user=user,
            meta=meta,
        )
    
    def _load_template(self, filename: str) -> str:
        """加载模板文件"""
        filepath = self.template_dir / filename
        
        if not filepath.exists():
            # 返回内置默认模板
            return self._get_builtin_template(filename)
        
        with open(filepath, 'r', encoding='utf-8') as f:
            template = f.read()
        
        # 替换变量
        return self._apply_template_vars(template)
    
    def _apply_template_vars(self, template: str) -> str:
        """应用模板变量"""
        vars = {
            "SHOT_TYPES": ", ".join(self.enums.get("shot_type", [])),
            "CAMERA_MOVES": ", ".join(self.enums.get("camera_move", [])),
            "TIME_OF_DAY": ", ".join(self.enums.get("time_of_day", [])),
            "WEATHER": ", ".join(self.enums.get("weather", [])),
            "MIN_PANELS": str(self.constraints.target_panels_min),
            "MAX_PANELS": str(self.constraints.target_panels_max),
            "TOTAL_DURATION_MIN": str(self.constraints.target_total_duration_s_min),
            "TOTAL_DURATION_MAX": str(self.constraints.target_total_duration_s_max),
            "PER_PANEL_DURATION_MIN": str(self.constraints.per_panel_duration_s_min),
            "PER_PANEL_DURATION_MAX": str(self.constraints.per_panel_duration_s_max),
            "STYLE_PROFILE": self.style_profile.to_prompt_text(),
        }
        
        for key, value in vars.items():
            template = template.replace(f"${{{key}}}", value)
            template = template.replace(f"${key}", value)
        
        return template
    
    def _compose_analysis_user(self) -> str:
        """生成分析阶段的 user prompt"""
        parts = []
        
        parts.append("# 剧本文本\n")
        parts.append("```")
        parts.append(self.script_text)
        parts.append("```\n")
        
        if self.style_profile:
            parts.append(f"# 风格要求\n{self.style_profile.to_prompt_text()}\n")
        
        parts.append("# 任务\n请分析上述剧本，输出 ScriptAnalysisV1 JSON。")
        
        return "\n".join(parts)
    
    def _compose_storyboard_user(
        self,
        analysis_json: Optional[Dict[str, Any]] = None
    ) -> str:
        """生成分镜阶段的 user prompt"""
        import json
        
        parts = []
        
        # 分析结果
        if analysis_json:
            parts.append("# 剧本分析结果 (ScriptAnalysisV1)\n")
            parts.append("```json")
            parts.append(json.dumps(analysis_json, ensure_ascii=False, indent=2))
            parts.append("```\n")
        else:
            # 没有分析结果，直接给剧本
            parts.append("# 剧本文本\n")
            parts.append("```")
            parts.append(self.script_text)
            parts.append("```\n")
        
        # 风格
        parts.append(f"# 风格要求\n{self.style_profile.to_prompt_text()}\n")
        
        # 资产上下文
        if self.assets_context:
            parts.append("# 可用资产\n")
            
            characters = self.assets_context.get("characters", [])
            if characters:
                parts.append("## 角色资产")
                for c in characters:
                    parts.append(f"- {c.get('name', c.get('canonical_name', '未知'))}")
                parts.append("")
            
            scenes = self.assets_context.get("scenes", [])
            if scenes:
                parts.append("## 场景资产")
                for s in scenes:
                    parts.append(f"- {s.get('name', s.get('canonical_location', '未知'))}")
                parts.append("")
        
        # 约束
        parts.append("# 生成约束")
        parts.append(f"- 分镜数量: {self.constraints.target_panels_min} ~ {self.constraints.target_panels_max}")
        parts.append(f"- 总时长: {self.constraints.target_total_duration_s_min} ~ {self.constraints.target_total_duration_s_max} 秒")
        parts.append(f"- 单镜头时长: {self.constraints.per_panel_duration_s_min} ~ {self.constraints.per_panel_duration_s_max} 秒")
        parts.append("")
        
        parts.append("# 任务\n请根据上述剧本分析和约束，生成 StoryboardDraftV2 JSON。")
        
        return "\n".join(parts)
    
    def _get_builtin_template(self, filename: str) -> str:
        """获取内置默认模板"""
        templates = {
            "system.md": BUILTIN_SYSTEM,
            "developer_analysis.md": BUILTIN_DEVELOPER_ANALYSIS,
            "developer_storyboard.md": BUILTIN_DEVELOPER_STORYBOARD,
            "user.md": "",
        }
        return templates.get(filename, "")


# ============ 内置模板 ============

BUILTIN_SYSTEM = """你是一个专业的漫画分镜导演和剧本分析师。

## 核心规则
1. **只输出 JSON**：不要输出任何解释文字，只输出一个完整的 JSON object
2. **严格遵循 Schema**：必须填写 schema_version 字段
3. **原文溯源**：每个结构化元素必须有 source_span.quote 引用原文

## 输出格式
直接输出 JSON，不要使用 markdown 代码块包裹。
"""

BUILTIN_DEVELOPER_ANALYSIS = """## ScriptAnalysisV1 规则

### 必须字段
- `schema_version`: 必须是 "script_analysis_v1"
- `script_digest`: 剧本的 hash 标识
- `characters`: 角色列表（至少 1 个）
- `locations`: 地点列表（至少 1 个）
- `beats`: 节拍列表（至少 1 个）
- `props`: 物品列表（可选，重要道具）

---

## ⚠️ 角色提取规则 (CharacterEntity) - 严格执行

### 第一步：识别真正的角色

在提取角色之前，请先回答这个问题：
**"这个剧本中，有哪些明确出场、有行为动作或对白的人物？"**

只有符合以下条件的才是真正的角色：
1. ✅ 在剧本中有**主动行为**（如"她说"、"他推开门"、"XX走了过来"）
2. ✅ 有**对白或内心独白**（引号内的台词）
3. ✅ 被**其他角色明确称呼**（如"林晓，你来了"）
4. ✅ 是**具体的人物姓名**（如"林晓"、"周屿"、"陈爷爷"、"小王"）

### 第二步：剔除非角色

以下内容**绝对禁止**作为角色提取：

| 类型 | 示例 | 说明 |
|------|------|------|
| 动词片段 | 这么好、又看了、话没、佛在诉、没敢多 | 对白中的词汇碎片 |
| 形容词/副词 | 温和的、慢慢地、静静地、突然 | 修饰语 |
| 占位符 | 角色A、角色B、人物1 | 通用占位 |
| 代词 | 他、她、我、自己、大家、别人 | 不是姓名 |
| 称谓 | 老一小、脸上的 | 不完整的称谓 |
| 物品 | 雨伞、书、戒指 | 应放入 props |

### 第三步：验证规则

**角色名必须满足:**
- `canonical_name`: 完整人物姓名，长度 >= 2 个汉字
- 必须是**名词性**的人名（如"林晓"而非"没敢多"）
- 必须在剧本中有**明确的行为主体**地位

**必填字段:**
- `canonical_name`: 人物全名（必须是真实姓名）
- `appearance_traits`: 至少 2 个外貌特征
- `personality_traits`: 至少 2 个性格特征
- `first_appearance_span`: 必须包含原文引用
- `gender`: 性别 (male/female/unknown)
- `age_range`: 年龄范围

### ❌ 失败示例（绝对不要这样）
```json
{"canonical_name": "这么好"}  // ❌ 对白片段
{"canonical_name": "温和的"}  // ❌ 形容词
{"canonical_name": "角色A"}   // ❌ 占位符
{"canonical_name": "话没"}    // ❌ 词汇碎片
```

### ✅ 正确示例
```json
{"canonical_name": "林晓", "appearance_traits": ["长发", "穿白裙"]}
{"canonical_name": "周屿", "appearance_traits": ["高个子", "戴眼镜"]}
{"canonical_name": "陈爷爷", "appearance_traits": ["白发", "慈祥"]}
```

---

## ⚠️ 场景提取规则 (LocationEntity) - 结构化提取

### 场景去重原则

**同一地点的不同描述应合并为一个基础资产：**
- "杂货铺柜台前" + "杂货铺门口" + "杂货铺内部" → 基础地点: `杂货铺`

**不同时间/光照条件创建变体：**
- 杂货铺(傍晚/昏暗) ≠ 杂货铺(夜晚/灯笼光) → 不同变体

### 必填字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `canonical_location` | **基础地点名**（不含时间/子位置） | `杂货铺`、`青石板巷` |
| `sub_location` | 具体位置（可选） | `门口`、`柜台前`、`内部` |
| `time_of_day` | 时间 | `morning`/`afternoon`/`dusk`/`night` |
| `lighting` | 光照/氛围 | `dim`/`bright`/`sunset`/`lantern` |
| `anchor_hint` | 完整环境描述 | 至少 1 句 |
| `is_primary` | 是否主要场景 | true/false |

### ❌ 错误示例
```json
// 把完整描述当作 canonical_location
{"canonical_location": "傍晚时分，杂货铺柜台前，光线昏暗"}  // ❌ 太长
{"canonical_location": "夜晚的杂货铺门口"}  // ❌ 包含时间
```

### ✅ 正确示例
```json
{
  "canonical_location": "杂货铺",
  "sub_location": "柜台前",
  "time_of_day": "dusk",
  "lighting": "dim",
  "anchor_hint": "傍晚时分，杂货铺柜台前，光线昏暗，柜台区域为主...",
  "is_primary": true
}
```

### 时间枚举
- `dawn`: 黎明/清晨
- `morning`: 早晨/上午
- `noon`: 中午
- `afternoon`: 下午
- `dusk`: 傍晚/黄昏
- `night`: 夜晚
- `late_night`: 深夜

### 光照枚举
- `bright`: 明亮
- `dim`: 昏暗
- `dark`: 阴暗
- `sunset`: 夕阳
- `lantern`: 灯笼光
- `moonlight`: 月光
- `warm`: 温馨

---

### 物品规则 (PropEntity)
提取剧情中的重要道具：
- `canonical_name`: 物品名称（如"雨伞"、"书"、"小王子书"）
- `description`: 简短描述
- `owner`: 所属角色（如有）
- `significance`: 剧情意义（low/medium/high）

---

### 节拍规则 (Beat)
- `beat_id`: 格式如 "b001"
- `source_span.quote`: 必须摘录原文 15~120 字

---

### 最终检查清单
提交前请确认：
1. [ ] 每个角色都是剧本中**真正出场**的人物
2. [ ] 没有提取对白中的**词汇片段**
3. [ ] 角色名是**完整的姓名**而非碎片
4. [ ] 每个角色都有**外貌和性格特征**
"""


BUILTIN_DEVELOPER_STORYBOARD = """## StoryboardDraftV2 规则

### 必须字段
- `schema_version`: 必须是 "storyboard_draft_v2"
- `prompt_version`: 必须是 "pc_v1"
- `panels`: 分镜列表（至少 1 个）

### 枚举白名单（只能选这些值）
- `shot_type`: ${SHOT_TYPES}
- `camera_move`: ${CAMERA_MOVES}
- `time_of_day`: ${TIME_OF_DAY}
- `weather`: ${WEATHER}

### 分镜规则 (PanelDraft)

#### 必填字段
- `index`: 从 1 开始的序号
- `shot_type`: 必须是枚举值
- `camera_move`: 必须是枚举值
- `duration_s`: ${PER_PANEL_DURATION_MIN} ~ ${PER_PANEL_DURATION_MAX} 秒
- `mood`: 至少 1 个情绪词
- `location`: 不能为空
- `time_of_day`: 必须是枚举值
- `weather`: 必须是枚举值
- `actions`: 至少 10 字，必须包含"主体动作 + 情绪/动机"
- `visual_prompt`: 至少 20 字，必须包含主体+环境+光照+画风

#### 硬约束
- `composition_notes`: 至少 2 条（镜头位置/主体构图/光照氛围/前中后景）
- `continuity_notes`: 至少 1 条（服饰/发型/道具/天气/光一致性）
- `source_span.quote`: 必须摘原文 15~120 字

### 节奏约束
- 总时长: ${TOTAL_DURATION_MIN} ~ ${TOTAL_DURATION_MAX} 秒
- 分镜数: ${MIN_PANELS} ~ ${MAX_PANELS} 个
- 超出范围请自行调整 duration_s

### 失败条件
- composition_notes 少于 2 条 → 拒绝
- continuity_notes 为空 → 拒绝
- source_span.quote 为空 → 拒绝
- duration_s 超出范围 → 拒绝
- shot_type/camera_move 不在枚举内 → 拒绝
"""
