"""
Repair Loop - 自动修复循环

最多 N 次重试，直到通过校验或放弃。
"""
import json
import logging
from typing import Dict, Any, Optional, Literal, Tuple
from datetime import datetime

from .repair_types import ValidationIssue, RepairPlan, IssueCode
from .validator import validate_script_analysis, validate_storyboard_draft
from .repair_prompt import compose_repair_prompt

logger = logging.getLogger(__name__)


async def repair_until_valid(
    kind: Literal["analysis", "storyboard"],
    original_json: Dict[str, Any],
    context: Dict[str, Any],
    llm_client=None,
    max_attempts: int = 3
) -> RepairPlan:
    """
    自动修复循环
    
    Args:
        kind: "analysis" 或 "storyboard"
        original_json: 原始 LLM 输出的 JSON
        context: 上下文信息 (script_text, constraints 等)
        llm_client: LLM 客户端
        max_attempts: 最大尝试次数
    
    Returns:
        RepairPlan 包含最终状态和 issues
    """
    plan = RepairPlan(
        original_json=original_json,
        max_attempts=max_attempts,
        started_at=datetime.utcnow()
    )
    
    current_json = original_json
    
    for attempt in range(1, max_attempts + 1):
        logger.info(f"[RepairLoop] {kind} 校验尝试 {attempt}/{max_attempts}")
        
        # 1. 校验当前 JSON
        ok, result = _validate(kind, current_json, context)
        
        if ok:
            # 校验通过
            plan.final_status = "repaired" if attempt > 1 else "ok"
            plan.repaired_json = current_json
            plan.issues = []
            plan.completed_at = datetime.utcnow()
            plan.attempts_used = attempt
            logger.info(f"[RepairLoop] {kind} 校验通过 (attempt {attempt})")
            return plan
        
        # 2. 有问题，记录 issues
        issues = result if isinstance(result, list) else []
        plan.issues = issues
        plan.attempts_used = attempt
        
        # 检查是否可以自动修复
        error_count = sum(1 for i in issues if i.severity == "error")
        if error_count == 0:
            # 只有警告，视为通过
            plan.final_status = "ok"
            plan.repaired_json = current_json
            plan.completed_at = datetime.utcnow()
            return plan
        
        # 3. 最后一次尝试失败
        if attempt == max_attempts:
            logger.warning(f"[RepairLoop] {kind} 修复失败，已达最大尝试次数")
            plan.final_status = "failed"
            plan.repaired_json = current_json
            plan.completed_at = datetime.utcnow()
            return plan
        
        # 4. 生成修复 prompt 并调用 LLM
        logger.info(f"[RepairLoop] {kind} 开始修复 (attempt {attempt})")
        
        try:
            repaired_json = await _call_repair_llm(
                kind=kind,
                original_json=current_json,
                issues=issues,
                context=context,
                llm_client=llm_client
            )
            
            if repaired_json:
                plan.add_attempt(repaired_json, issues)
                current_json = repaired_json
            else:
                logger.warning("[RepairLoop] LLM 修复返回空结果")
                
        except Exception as e:
            logger.error(f"[RepairLoop] 修复 LLM 调用失败: {e}")
    
    plan.final_status = "failed"
    plan.completed_at = datetime.utcnow()
    return plan


def _validate(
    kind: str,
    data: Dict[str, Any],
    context: Dict[str, Any]
) -> Tuple[bool, Any]:
    """调用对应的校验器"""
    if kind == "analysis":
        return validate_script_analysis(data)
    else:
        duration_range = context.get("duration_range", (1.5, 8.0))
        return validate_storyboard_draft(data, duration_range)


async def _call_repair_llm(
    kind: str,
    original_json: Dict[str, Any],
    issues: list,
    context: Dict[str, Any],
    llm_client=None
) -> Optional[Dict[str, Any]]:
    """调用 LLM 进行修复"""
    from app.services.brain.base import get_brain_service
    
    # 生成修复 prompt
    prompt = compose_repair_prompt(
        kind=kind,
        original_json=original_json,
        issues=issues,
        script_text=context.get("script_text"),
        constraints=context.get("constraints")
    )
    
    # 合并 system 和 developer
    messages = [
        {"role": "system", "content": prompt["system"] + "\n\n" + prompt["developer"]},
        {"role": "user", "content": prompt["user"]}
    ]
    
    try:
        brain = llm_client or get_brain_service()
        response = await brain._chat_completion(
            messages=messages,
            response_format="json"
        )
        
        # 解析 JSON
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试清理
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                response = response.split("```")[1].split("```")[0]
            return json.loads(response.strip())
            
    except Exception as e:
        logger.error(f"[RepairLoop] LLM 调用失败: {e}")
        return None


# ============ 便捷函数 ============

async def validate_and_repair_analysis(
    data: Dict[str, Any],
    script_text: str,
    max_attempts: int = 3
) -> Tuple[bool, Any, RepairPlan]:
    """
    校验并修复 ScriptAnalysisV1
    
    Returns:
        (ok, model_or_data, plan)
    """
    context = {"script_text": script_text}
    plan = await repair_until_valid("analysis", data, context, max_attempts=max_attempts)
    
    if plan.final_status in ("ok", "repaired"):
        final_data = plan.repaired_json or data
        ok, result = validate_script_analysis(final_data)
        return True, result if ok else final_data, plan
    
    return False, plan.repaired_json or data, plan


async def validate_and_repair_storyboard(
    data: Dict[str, Any],
    script_text: str,
    duration_range: Tuple[float, float] = (1.5, 8.0),
    max_attempts: int = 3
) -> Tuple[bool, Any, RepairPlan]:
    """
    校验并修复 StoryboardDraftV2
    
    Returns:
        (ok, model_or_data, plan)
    """
    context = {
        "script_text": script_text,
        "duration_range": duration_range,
        "constraints": {"duration_range": duration_range}
    }
    plan = await repair_until_valid("storyboard", data, context, max_attempts=max_attempts)
    
    if plan.final_status in ("ok", "repaired"):
        final_data = plan.repaired_json or data
        ok, result = validate_storyboard_draft(final_data, duration_range)
        return True, result if ok else final_data, plan
    
    return False, plan.repaired_json or data, plan
