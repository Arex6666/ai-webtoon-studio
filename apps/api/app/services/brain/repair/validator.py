"""
Validator - 脚本分析 & 分镜校验器

实现业务层 QA 规则，将 Pydantic 校验和业务规则统一返回结构化 issues。
"""
import re
from typing import Dict, Any, Optional, Tuple, List, Union
from pydantic import ValidationError

from .repair_types import (
    ValidationIssue, RepairPlan, IssueCode,
    create_issue, pydantic_error_to_issues
)
from app.schemas.brain.script_analysis import ScriptAnalysisV1
from app.schemas.brain.storyboard_draft_v2 import StoryboardDraftV2
from app.schemas.brain.enums import (
    ShotType, CameraMove, TimeOfDay, Weather
)


# ============ 配置常量 ============

MIN_APPEARANCE_TRAITS = 2
MIN_PERSONALITY_TRAITS = 2
MIN_COMPOSITION_NOTES = 2
MIN_CONTINUITY_NOTES = 1
MIN_ACTIONS_LENGTH = 10
MIN_VISUAL_PROMPT_LENGTH = 20
MIN_QUOTE_LENGTH = 15
MAX_QUOTE_LENGTH = 200
MIN_DURATION_S = 1.5
MAX_DURATION_S = 8.0

# 细节增强阈值 (S4-01-03-07)
MIN_ACTIONS_CHARS = 15  # 中文字符
MIN_COMP_NOTE_CHARS = 8
VISUAL_PROMPT_KEYWORDS = ["环境", "光照", "光线", "材质", "氛围", "背景", "前景", "色调"]

# 角色名称验证 (资产提取稳定性修复)
MIN_CHARACTER_NAME_LENGTH = 2
# 黑名单：常见的误提取名称（对白片段、动词、形容词等）
CHARACTER_NAME_BLACKLIST = {
    # ===== 用户反馈的实际误提取 =====
    "这么好", "林晚问", "角色A", "角色B", "温和的", "佛在诉",
    "话没", "又看了", "老一小", "脸上的", "人物1", "人物2",
    
    # ===== 动词片段 =====
    "没敢多", "与一起", "仍不知", "已一起", "这句话", "那你看",
    "很快", "慢慢地", "轻轻地", "静静地", "默默地", "悄悄地",
    "突然", "忽然", "终于", "马上", "立刻", "连忙", "急忙",
    "走了", "来了", "去了", "看了", "说了", "听了", "想了",
    "做了", "问了", "答了", "笑了", "哭了", "转身", "回头",
    
    # ===== 形容词/状语 =====
    "温和的", "安静的", "快速的", "缓慢的", "轻柔的", "粗暴的",
    "高兴的", "悲伤的", "愤怒的", "恐惧的", "惊讶的", "厌恶的",
    
    # ===== 常见词语 =====
    "这个", "那个", "什么", "怎么", "一个", "一起", "一直",
    "不知", "不过", "不是", "只是", "但是", "所以", "因为",
    "可以", "可能", "应该", "已经", "正在", "后来", "之前",
    "如果", "虽然", "然而", "并且", "或者", "还是", "也是",
    
    # ===== 代词 =====
    "自己", "大家", "别人", "其他", "有人", "没人", "某人",
    "谁", "哪个", "这里", "那里", "这边", "那边",
    
    # ===== 量词/数词 =====
    "一次", "两次", "几次", "很多", "一些", "不少", "所有",
    "第一", "第二", "最后", "之后", "之中",
    
    # ===== 常见无效短语 =====
    "没多久", "过了", "后来", "然后", "接着", "说道", "问道",
    "心想", "想着", "看着", "听着", "感觉", "觉得", "认为",
    "知道", "明白", "理解", "发现", "注意", "意识",
    
    # ===== 占位符/通用词 =====
    "角色", "人物", "主角", "配角", "路人", "背景",
    "男主", "女主", "男配", "女配", "反派", "Boss",
}

# 额外的模式检测规则
CHARACTER_NAME_INVALID_PATTERNS = [
    r"^.{1}$",           # 单字
    r"^角色[A-Z\d]$",    # 角色A/角色1
    r"^人物\d+$",        # 人物1/人物2
    r"的$",              # 以"的"结尾
    r"了$",              # 以"了"结尾
    r"着$",              # 以"着"结尾
    r"^[一二三四五六七八九十]+$",  # 纯数字词
]



# ============ ScriptAnalysisV1 校验 ============

def validate_script_analysis(
    data: Dict[str, Any]
) -> Tuple[bool, Union[ScriptAnalysisV1, List[ValidationIssue]]]:
    """
    验证 ScriptAnalysisV1
    
    Returns:
        (ok, model_or_issues)
        - ok=True: 返回解析后的模型
        - ok=False: 返回 issues 列表
    """
    issues = []
    
    # 1. Pydantic 结构校验
    try:
        model = ScriptAnalysisV1(**data)
    except ValidationError as e:
        pydantic_issues = pydantic_error_to_issues(e)
        return False, pydantic_issues
    except Exception as e:
        return False, [create_issue(
            code=IssueCode.INVALID_JSON.value,
            path="",
            message=f"JSON 解析失败: {str(e)}",
            severity="error"
        )]
    
    # 2. 业务规则校验
    
    # 检查 schema_version
    if data.get("schema_version") != "script_analysis_v1":
        issues.append(create_issue(
            code=IssueCode.SCHEMA_MISMATCH.value,
            path="schema_version",
            message="schema_version 必须是 'script_analysis_v1'",
            severity="error",
            hint="设置 schema_version = 'script_analysis_v1'"
        ))
    
    # 检查角色
    characters = data.get("characters", [])
    canonical_names = set()
    
    for i, char in enumerate(characters):
        path_prefix = f"characters.{i}"
        name = char.get("canonical_name", "")
        
        # 检查重复 canonical_name
        if name in canonical_names:
            issues.append(create_issue(
                code=IssueCode.DUPLICATE_REF.value,
                path=f"{path_prefix}.canonical_name",
                message=f"角色名 '{name}' 重复定义",
                severity="warn"
            ))
        canonical_names.add(name)
        
        # 检查角色名称有效性 (资产提取稳定性修复)
        if len(name) < MIN_CHARACTER_NAME_LENGTH:
            issues.append(create_issue(
                code=IssueCode.TOO_SHORT.value,
                path=f"{path_prefix}.canonical_name",
                message=f"角色名 '{name}' 过短（需至少 {MIN_CHARACTER_NAME_LENGTH} 个字符）",
                severity="error",
                hint="角色名应是明确的人物姓名，如'林晓''周屿'，而非对白片段"
            ))
        
        if name in CHARACTER_NAME_BLACKLIST:
            issues.append(create_issue(
                code=IssueCode.INVALID_JSON.value,
                path=f"{path_prefix}.canonical_name",
                message=f"'{name}' 不是有效的角色名（可能是对白片段或常见词语）",
                severity="error",
                hint="只提取真实出场的人物姓名，不要提取动词、形容词或对白中的词汇"
            ))
        
        # 检查正则模式（如以"的"、"了"、"着"结尾）
        for pattern in CHARACTER_NAME_INVALID_PATTERNS:
            if re.match(pattern, name):
                issues.append(create_issue(
                    code=IssueCode.INVALID_JSON.value,
                    path=f"{path_prefix}.canonical_name",
                    message=f"'{name}' 匹配到无效模式，不是有效的角色名",
                    severity="error",
                    hint="角色名应是完整的人物姓名，不应以'的'、'了'、'着'等字结尾"
                ))
                break
        
        # 检查 appearance_traits
        traits = char.get("appearance_traits", [])
        if len(traits) < MIN_APPEARANCE_TRAITS:
            issues.append(create_issue(
                code=IssueCode.INSUFFICIENT_ITEMS.value,
                path=f"{path_prefix}.appearance_traits",
                message=f"appearance_traits 至少需要 {MIN_APPEARANCE_TRAITS} 个，当前 {len(traits)} 个",
                severity="error",
                hint="添加更多外观特征：发型、发色、眼睛、服装、体型等"
            ))
        
        # 检查 personality_traits
        traits = char.get("personality_traits", [])
        if len(traits) < MIN_PERSONALITY_TRAITS:
            issues.append(create_issue(
                code=IssueCode.INSUFFICIENT_ITEMS.value,
                path=f"{path_prefix}.personality_traits",
                message=f"personality_traits 至少需要 {MIN_PERSONALITY_TRAITS} 个，当前 {len(traits)} 个",
                severity="error",
                hint="添加更多性格特征：内向/开朗、冷静/热情等"
            ))
        
        # 检查 source_span.quote
        quote = char.get("first_appearance_span", {}).get("quote", "")
        _validate_quote(issues, f"{path_prefix}.first_appearance_span.quote", quote)
    
    # 检查地点
    locations = data.get("locations", [])
    location_names = set()
    
    for i, loc in enumerate(locations):
        path_prefix = f"locations.{i}"
        name = loc.get("canonical_location", "")
        
        if name in location_names:
            issues.append(create_issue(
                code=IssueCode.DUPLICATE_REF.value,
                path=f"{path_prefix}.canonical_location",
                message=f"地点名 '{name}' 重复定义",
                severity="warn"
            ))
        location_names.add(name)
        
        quote = loc.get("first_appearance_span", {}).get("quote", "")
        _validate_quote(issues, f"{path_prefix}.first_appearance_span.quote", quote)
    
    # 检查节拍
    beats = data.get("beats", [])
    for i, beat in enumerate(beats):
        path_prefix = f"beats.{i}"
        
        quote = beat.get("source_span", {}).get("quote", "")
        _validate_quote(issues, f"{path_prefix}.source_span.quote", quote)
        
        # 检查未定义引用 (仅警告)
        for char_ref in beat.get("characters_involved", []):
            if char_ref not in canonical_names:
                issues.append(create_issue(
                    code=IssueCode.UNRESOLVED_REF.value,
                    path=f"{path_prefix}.characters_involved",
                    message=f"引用了未定义的角色 '{char_ref}'",
                    severity="warn"
                ))
        
        loc_ref = beat.get("location_ref")
        if loc_ref and loc_ref not in location_names:
            issues.append(create_issue(
                code=IssueCode.UNRESOLVED_REF.value,
                path=f"{path_prefix}.location_ref",
                message=f"引用了未定义的地点 '{loc_ref}'",
                severity="warn"
            ))
    
    # 如果有 error 级别问题，返回失败
    if any(i.severity == "error" for i in issues):
        return False, issues
    
    # 如果只有 warn，返回成功但附带警告
    if issues:
        return True, model  # 警告不阻塞
    
    return True, model


# ============ StoryboardDraftV2 校验 ============

def validate_storyboard_draft(
    data: Dict[str, Any],
    duration_range: Tuple[float, float] = (MIN_DURATION_S, MAX_DURATION_S)
) -> Tuple[bool, Union[StoryboardDraftV2, List[ValidationIssue]]]:
    """
    验证 StoryboardDraftV2
    
    Returns:
        (ok, model_or_issues)
    """
    issues = []
    min_dur, max_dur = duration_range
    
    # 1. Pydantic 结构校验
    try:
        model = StoryboardDraftV2(**data)
    except ValidationError as e:
        pydantic_issues = pydantic_error_to_issues(e)
        return False, pydantic_issues
    except Exception as e:
        return False, [create_issue(
            code=IssueCode.INVALID_JSON.value,
            path="",
            message=f"JSON 解析失败: {str(e)}",
            severity="error"
        )]
    
    # 2. 业务规则校验
    
    # 检查 schema_version
    if data.get("schema_version") != "storyboard_draft_v2":
        issues.append(create_issue(
            code=IssueCode.SCHEMA_MISMATCH.value,
            path="schema_version",
            message="schema_version 必须是 'storyboard_draft_v2'",
            severity="error",
            hint="设置 schema_version = 'storyboard_draft_v2'"
        ))
    
    # 枚举白名单
    valid_shot_types = [e.value for e in ShotType]
    valid_camera_moves = [e.value for e in CameraMove]
    valid_time_of_day = [e.value for e in TimeOfDay]
    valid_weather = [e.value for e in Weather]
    
    panels = data.get("panels", [])
    
    for i, panel in enumerate(panels):
        idx = panel.get("index", i + 1)
        path_prefix = f"panels.{i}"
        
        # === 枚举检查 ===
        shot_type = panel.get("shot_type")
        if shot_type and shot_type not in valid_shot_types:
            issues.append(create_issue(
                code=IssueCode.ENUM_INVALID.value,
                path=f"{path_prefix}.shot_type",
                message=f"shot_type '{shot_type}' 不在枚举列表中",
                severity="error",
                hint=f"有效值: {', '.join(valid_shot_types)}",
                expected=str(valid_shot_types),
                actual=shot_type
            ))
        
        camera_move = panel.get("camera_move")
        if camera_move and camera_move not in valid_camera_moves:
            issues.append(create_issue(
                code=IssueCode.ENUM_INVALID.value,
                path=f"{path_prefix}.camera_move",
                message=f"camera_move '{camera_move}' 不在枚举列表中",
                severity="error",
                hint=f"有效值: {', '.join(valid_camera_moves)}"
            ))
        
        tod = panel.get("time_of_day")
        if tod and tod not in valid_time_of_day:
            issues.append(create_issue(
                code=IssueCode.ENUM_INVALID.value,
                path=f"{path_prefix}.time_of_day",
                message=f"time_of_day '{tod}' 不在枚举列表中",
                severity="error",
                hint=f"有效值: {', '.join(valid_time_of_day)}"
            ))
        
        weather = panel.get("weather")
        if weather and weather not in valid_weather:
            issues.append(create_issue(
                code=IssueCode.ENUM_INVALID.value,
                path=f"{path_prefix}.weather",
                message=f"weather '{weather}' 不在枚举列表中",
                severity="error",
                hint=f"有效值: {', '.join(valid_weather)}"
            ))
        
        # === 硬约束检查 ===
        
        # composition_notes >= 2
        comp_notes = panel.get("composition_notes", [])
        if len(comp_notes) < MIN_COMPOSITION_NOTES:
            issues.append(create_issue(
                code=IssueCode.INSUFFICIENT_ITEMS.value,
                path=f"{path_prefix}.composition_notes",
                message=f"composition_notes 至少需要 {MIN_COMPOSITION_NOTES} 条，当前 {len(comp_notes)} 条",
                severity="error",
                hint="添加构图要点：主体位置、景深、前景遮挡、光源方向、视觉焦点"
            ))
        
        # continuity_notes >= 1
        cont_notes = panel.get("continuity_notes", [])
        if len(cont_notes) < MIN_CONTINUITY_NOTES:
            issues.append(create_issue(
                code=IssueCode.INSUFFICIENT_ITEMS.value,
                path=f"{path_prefix}.continuity_notes",
                message=f"continuity_notes 至少需要 {MIN_CONTINUITY_NOTES} 条",
                severity="error",
                hint="添加连续性约束：服饰一致、道具延续、天气光线一致"
            ))
        
        # actions 检查
        actions = panel.get("actions", "")
        if len(actions) < MIN_ACTIONS_LENGTH:
            issues.append(create_issue(
                code=IssueCode.TOO_SHORT.value,
                path=f"{path_prefix}.actions",
                message=f"actions 至少需要 {MIN_ACTIONS_LENGTH} 字，当前 {len(actions)} 字",
                severity="error",
                hint="描述：起始姿态 → 动作变化 → 表情变化 → 情绪动机"
            ))
        
        # visual_prompt 检查
        visual = panel.get("visual_prompt", "")
        if len(visual) < MIN_VISUAL_PROMPT_LENGTH:
            issues.append(create_issue(
                code=IssueCode.TOO_SHORT.value,
                path=f"{path_prefix}.visual_prompt",
                message=f"visual_prompt 至少需要 {MIN_VISUAL_PROMPT_LENGTH} 字，当前 {len(visual)} 字",
                severity="error",
                hint="包含：主体描述 + 环境 + 光照 + 画风"
            ))
        
        # source_span.quote 检查
        quote = panel.get("source_span", {}).get("quote", "")
        _validate_quote(issues, f"{path_prefix}.source_span.quote", quote)
        
        # duration_s 范围检查
        duration = panel.get("duration_s", 0)
        if duration < min_dur or duration > max_dur:
            issues.append(create_issue(
                code=IssueCode.OUT_OF_RANGE.value,
                path=f"{path_prefix}.duration_s",
                message=f"duration_s ({duration}) 超出范围 {min_dur}~{max_dur}",
                severity="error",
                hint=f"调整到 {min_dur} ~ {max_dur} 秒之间"
            ))
        
        # cast 为空检查
        cast = panel.get("cast", [])
        is_establishing = panel.get("is_establishing", False)
        if not cast and not is_establishing:
            issues.append(create_issue(
                code=IssueCode.INSUFFICIENT_ITEMS.value,
                path=f"{path_prefix}.cast",
                message="cast 为空但不是建立镜头",
                severity="warn",
                hint="添加角色或设置 is_establishing=true"
            ))
        
        # === 细节增强检查 (S4-01-03-07) ===
        _check_detail_depth(issues, path_prefix, panel)
    
    # 如果有 error 级别问题，返回失败
    if any(i.severity == "error" for i in issues):
        return False, issues
    
    return True, model


# ============ 辅助函数 ============

def _validate_quote(issues: List[ValidationIssue], path: str, quote: str):
    """验证 source_span.quote"""
    if not quote or not quote.strip():
        issues.append(create_issue(
            code=IssueCode.BAD_SPAN.value,
            path=path,
            message="source_span.quote 不能为空",
            severity="error",
            hint="必须摘录原文 15~120 字"
        ))
    elif len(quote) < MIN_QUOTE_LENGTH:
        issues.append(create_issue(
            code=IssueCode.TOO_SHORT.value,
            path=path,
            message=f"quote 过短（{len(quote)} 字），至少需要 {MIN_QUOTE_LENGTH} 字",
            severity="error",
            hint="摘录更多原文内容"
        ))
    elif len(quote) > MAX_QUOTE_LENGTH:
        issues.append(create_issue(
            code=IssueCode.TOO_LONG.value,
            path=path,
            message=f"quote 过长（{len(quote)} 字），最多 {MAX_QUOTE_LENGTH} 字",
            severity="warn",
            hint="精简原文摘录"
        ))


def _check_detail_depth(issues: List[ValidationIssue], path_prefix: str, panel: Dict):
    """
    检查细节深度 (S4-01-03-07)
    
    检测 too_shallow 问题
    """
    # actions 过短
    actions = panel.get("actions", "")
    chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', actions))
    if chinese_chars < MIN_ACTIONS_CHARS:
        issues.append(create_issue(
            code=IssueCode.TOO_SHALLOW.value,
            path=f"{path_prefix}.actions",
            message=f"actions 细节不足（仅 {chinese_chars} 个汉字）",
            severity="error",
            hint="增强描述：角色姿态 + 动作变化 + 表情细节 + 情绪动机"
        ))
    
    # composition_notes 每条过短
    comp_notes = panel.get("composition_notes", [])
    for j, note in enumerate(comp_notes):
        note_chars = len(re.findall(r'[\u4e00-\u9fff]', note))
        if note_chars < MIN_COMP_NOTE_CHARS:
            issues.append(create_issue(
                code=IssueCode.TOO_SHALLOW.value,
                path=f"{path_prefix}.composition_notes.{j}",
                message=f"构图注释过短（{note_chars} 字）",
                severity="warn",
                hint="详细描述：主体位置/景深/前景遮挡/光源方向"
            ))
    
    # visual_prompt 缺少关键词
    visual = panel.get("visual_prompt", "")
    has_keywords = any(kw in visual for kw in VISUAL_PROMPT_KEYWORDS)
    if not has_keywords:
        issues.append(create_issue(
            code=IssueCode.TOO_SHALLOW.value,
            path=f"{path_prefix}.visual_prompt",
            message="visual_prompt 缺少环境/光照描述",
            severity="warn",
            hint=f"建议包含关键词：{', '.join(VISUAL_PROMPT_KEYWORDS[:4])}"
        ))
