"""
Draft QA Scorer - 分镜草稿质量评估

集成 validator issues，计算 QA 评分和细节分析。
"""
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from pydantic import BaseModel, Field

from app.services.brain.repair import (
    validate_storyboard_draft,
    ValidationIssue,
    IssueCode
)


# ============ 评分配置 ============

class QAScoringConfig:
    """评分规则配置"""
    BASE_SCORE = 100
    ERROR_PENALTY = 12
    WARN_PENALTY = 3
    MAX_ERROR_DEDUCTION = 70
    MAX_WARN_DEDUCTION = 20
    
    # 关键 error 封顶
    CRITICAL_ERROR_CAP = 60
    CRITICAL_CODES = [
        IssueCode.MISSING_FIELD.value,
        IssueCode.ENUM_INVALID.value,
        IssueCode.BAD_SPAN.value,
        IssueCode.INVALID_JSON.value,
    ]
    
    # too_shallow 连续惩罚
    TOO_SHALLOW_BONUS_PENALTY = 10
    TOO_SHALLOW_THRESHOLD = 3


# ============ 数据结构 ============

class ScoreBreakdown(BaseModel):
    """评分细分"""
    structure: float = Field(default=100, description="结构分 (Pydantic/缺字段)")
    detail: float = Field(default=100, description="细节分 (too_shallow/visual_prompt)")
    continuity: float = Field(default=100, description="连续性分 (continuity_notes/source_span)")
    enums: float = Field(default=100, description="枚举分 (shot/camera/time/weather)")


class IssuesSummary(BaseModel):
    """issues 统计"""
    error: int = 0
    warn: int = 0
    total: int = 0


class DraftQAReport(BaseModel):
    """
    分镜草稿 QA 报告
    
    融合 validator issues 和评分
    """
    # 总分 (0-100)
    score: float = Field(default=100, ge=0, le=100)
    
    # 评分细分
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    
    # issues 统计
    issues_summary: IssuesSummary = Field(default_factory=IssuesSummary)
    
    # issues 列表 (可选：只返回 top N)
    issues: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 状态
    can_render: bool = Field(default=True, description="是否可渲染 (无 critical error)")
    needs_fix: bool = Field(default=False, description="是否需要修复")
    
    # 元数据
    panels_count: int = 0
    panels_with_issues: int = 0


# ============ 评分逻辑 ============

def calculate_draft_qa(
    draft_json: Dict[str, Any],
    duration_range: Tuple[float, float] = (1.5, 8.0),
    max_issues_returned: int = 20
) -> DraftQAReport:
    """
    计算分镜草稿的 QA 评分
    
    注意：只验证，不触发 repair
    
    Args:
        draft_json: 分镜 JSON (panels 列表)
        duration_range: 时长范围
        max_issues_returned: 返回的最大 issues 数量
    
    Returns:
        DraftQAReport
    """
    report = DraftQAReport()
    config = QAScoringConfig()
    
    # 提取 panels
    panels = draft_json.get("panels", [])
    report.panels_count = len(panels)
    
    if not panels:
        report.score = 0
        report.can_render = False
        report.issues.append({
            "code": "no_panels",
            "path": "panels",
            "message": "没有分镜",
            "severity": "error"
        })
        report.issues_summary.error = 1
        report.issues_summary.total = 1
        return report
    
    # 验证（不修复）
    ok, result = validate_storyboard_draft(draft_json, duration_range)
    
    if ok:
        # 完全通过
        report.score = 100
        report.can_render = True
        report.needs_fix = False
        return report
    
    # 有 issues
    issues: List[ValidationIssue] = result if isinstance(result, list) else []
    
    # 统计
    error_count = sum(1 for i in issues if i.severity == "error")
    warn_count = sum(1 for i in issues if i.severity == "warn")
    
    report.issues_summary = IssuesSummary(
        error=error_count,
        warn=warn_count,
        total=len(issues)
    )
    
    # 转换 issues 为 dict 列表
    report.issues = [
        {
            "code": i.code,
            "path": i.path,
            "message": i.message,
            "severity": i.severity,
            "hint": i.hint
        }
        for i in issues[:max_issues_returned]
    ]
    
    # 计算评分细分
    breakdown = _calculate_breakdown(issues)
    report.score_breakdown = breakdown
    
    # 计算总分
    score = config.BASE_SCORE
    
    # error 扣分
    error_deduction = min(error_count * config.ERROR_PENALTY, config.MAX_ERROR_DEDUCTION)
    score -= error_deduction
    
    # warn 扣分
    warn_deduction = min(warn_count * config.WARN_PENALTY, config.MAX_WARN_DEDUCTION)
    score -= warn_deduction
    
    # 关键 error 封顶
    has_critical = any(i.code in config.CRITICAL_CODES for i in issues)
    if has_critical:
        score = min(score, config.CRITICAL_ERROR_CAP)
    
    # too_shallow 连续惩罚
    too_shallow_count = sum(1 for i in issues if i.code == IssueCode.TOO_SHALLOW.value)
    if too_shallow_count >= config.TOO_SHALLOW_THRESHOLD:
        score -= config.TOO_SHALLOW_BONUS_PENALTY
    
    # 确保分数在 0-100
    report.score = max(0, min(100, score))
    
    # 状态判断
    report.can_render = not has_critical
    report.needs_fix = error_count > 0
    
    # 统计有问题的 panel
    panel_paths = set()
    for i in issues:
        if i.path.startswith("panels."):
            parts = i.path.split(".")
            if len(parts) >= 2:
                panel_paths.add(parts[1])
    report.panels_with_issues = len(panel_paths)
    
    return report


def _calculate_breakdown(issues: List[ValidationIssue]) -> ScoreBreakdown:
    """计算评分细分"""
    breakdown = ScoreBreakdown()
    
    structure_issues = 0
    detail_issues = 0
    continuity_issues = 0
    enum_issues = 0
    
    for issue in issues:
        code = issue.code
        severity_weight = 2 if issue.severity == "error" else 1
        
        # 结构类
        if code in [IssueCode.MISSING_FIELD.value, IssueCode.INVALID_TYPE.value, 
                    IssueCode.INVALID_JSON.value, IssueCode.SCHEMA_MISMATCH.value]:
            structure_issues += severity_weight
        
        # 细节类
        elif code in [IssueCode.TOO_SHALLOW.value, IssueCode.TOO_SHORT.value]:
            detail_issues += severity_weight
        
        # 连续性类
        elif code in [IssueCode.BAD_SPAN.value]:
            continuity_issues += severity_weight
        elif "continuity" in issue.path or "source_span" in issue.path:
            continuity_issues += severity_weight
        
        # 枚举类
        elif code == IssueCode.ENUM_INVALID.value:
            enum_issues += severity_weight
    
    # 转换为分数 (每个 issue 扣 10 分，最多扣 60)
    breakdown.structure = max(40, 100 - structure_issues * 10)
    breakdown.detail = max(40, 100 - detail_issues * 10)
    breakdown.continuity = max(40, 100 - continuity_issues * 10)
    breakdown.enums = max(40, 100 - enum_issues * 10)
    
    return breakdown


# ============ 便捷函数 ============

async def get_draft_qa(
    draft_id: str,
    db_session=None
) -> DraftQAReport:
    """
    获取分镜草稿的 QA 报告
    
    Args:
        draft_id: 草稿 ID
        db_session: 数据库会话
    
    Returns:
        DraftQAReport
    """
    from app.models.storyboard_draft import StoryboardDraft
    
    draft = db_session.query(StoryboardDraft).filter(
        StoryboardDraft.id == draft_id
    ).first()
    
    if not draft:
        return DraftQAReport(score=0, can_render=False)
    
    panels_json = draft.panels_json or []
    
    # 构建 draft_json 格式
    draft_json = {
        "schema_version": draft.schema_version or "storyboard_draft_v2",
        "panels": panels_json
    }
    
    return calculate_draft_qa(draft_json)


async def fix_draft_with_issues(
    draft_id: str,
    script_text: str,
    db_session=None,
    max_attempts: int = 2
) -> Tuple[bool, DraftQAReport]:
    """
    基于 issues 修复分镜草稿
    
    Args:
        draft_id: 草稿 ID
        script_text: 剧本文本
        db_session: 数据库会话
        max_attempts: 最大修复尝试
    
    Returns:
        (success, new_qa_report)
    """
    from app.models.storyboard_draft import StoryboardDraft
    from app.services.brain.repair import validate_and_repair_storyboard
    
    draft = db_session.query(StoryboardDraft).filter(
        StoryboardDraft.id == draft_id
    ).first()
    
    if not draft:
        return False, DraftQAReport(score=0, can_render=False)
    
    panels_json = draft.panels_json or []
    
    # 构建 draft_json 格式
    draft_json = {
        "schema_version": draft.schema_version or "storyboard_draft_v2",
        "prompt_version": draft.prompt_version or "pc_v1",
        "panels": panels_json
    }
    
    # 使用 repair loop 修复
    ok, repaired_data, plan = await validate_and_repair_storyboard(
        data=draft_json,
        script_text=script_text,
        max_attempts=max_attempts
    )
    
    if ok and repaired_data:
        # 更新 draft
        if hasattr(repaired_data, 'model_dump'):
            new_json = repaired_data.model_dump()
        else:
            new_json = repaired_data
        
        draft.panels_json = new_json.get("panels", panels_json)
        draft.version = (draft.version or 1) + 1
        db_session.commit()
    
    # 重新计算 QA
    new_draft_json = {
        "schema_version": draft.schema_version,
        "panels": draft.panels_json
    }
    new_qa = calculate_draft_qa(new_draft_json)
    
    return ok, new_qa
