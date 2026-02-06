"""
Brain API - 剧本解析和智能分析路由
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
import logging

from app.core.database import get_db
from app.services.brain.base import (
    get_brain_service,
    ScriptParseResult,
    ContinuityCheckResult,
    ContinuityIssue,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Request/Response Models ============

class ParseScriptRequest(BaseModel):
    """剧本解析请求"""
    script_text: str
    style_hint: Optional[str] = None  # korean_webtoon, manga, manhwa, comic


class CheckContinuityRequest(BaseModel):
    """连续性检测请求"""
    panels: List[dict]
    characters: Optional[dict] = None
    scenes: Optional[dict] = None


class SuggestFixRequest(BaseModel):
    """修复建议请求"""
    issue: dict
    context: dict


class EnhancePromptRequest(BaseModel):
    """提示词增强请求"""
    base_prompt: str
    style: str = "korean_webtoon"


class EnhancePromptResponse(BaseModel):
    """提示词增强响应"""
    enhanced_prompt: str


# ============ Routes ============

@router.post("/parse-script", response_model=ScriptParseResult)
async def parse_script(request: ParseScriptRequest):
    """
    解析剧本为分镜
    
    支持：
    - 一句话输入：自动扩展为多个分镜
    - 完整剧本：按段落解析
    
    返回：
    - 分镜列表（包含景别、情绪、对话等）
    - 检测到的角色
    - 检测到的场景
    - 连续性问题提示
    """
    if not request.script_text.strip():
        raise HTTPException(status_code=400, detail="Script text cannot be empty")
    
    brain = get_brain_service()
    
    try:
        result = await brain.parse_script(
            script_text=request.script_text,
            style_hint=request.style_hint
        )
        
        logger.info(f"Parsed script: {len(result.panels)} panels, "
                   f"{len(result.detected_characters)} characters")
        
        return result
        
    except Exception as e:
        logger.error(f"Script parsing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Script parsing failed: {str(e)}")


@router.post("/check-continuity", response_model=ContinuityCheckResult)
async def check_continuity(request: CheckContinuityRequest):
    """
    检测分镜序列的连续性
    
    检测项目：
    - 时间跳跃（白天→夜晚）
    - 天气变化
    - 场景切换
    - 服装变化（如果提供角色资产信息）
    
    返回：
    - 是否通过检测
    - 问题列表
    - 自动修复建议
    """
    if not request.panels:
        raise HTTPException(status_code=400, detail="Panels list cannot be empty")
    
    brain = get_brain_service()
    
    try:
        result = await brain.check_continuity(
            panels=request.panels,
            characters=request.characters,
            scenes=request.scenes
        )
        
        logger.info(f"Continuity check: {len(result.issues)} issues found")
        
        return result
        
    except Exception as e:
        logger.error(f"Continuity check failed: {e}")
        raise HTTPException(status_code=500, detail=f"Continuity check failed: {str(e)}")


@router.post("/suggest-fix")
async def suggest_fix(request: SuggestFixRequest):
    """
    为连续性问题提供修复建议
    
    返回具体的修改方案，支持一键应用
    """
    brain = get_brain_service()
    
    try:
        # 将 dict 转换为 ContinuityIssue
        issue = ContinuityIssue(**request.issue)
        
        result = await brain.suggest_fix(issue=issue, context=request.context)
        
        return result
        
    except Exception as e:
        logger.error(f"Suggest fix failed: {e}")
        raise HTTPException(status_code=500, detail=f"Suggest fix failed: {str(e)}")


@router.post("/enhance-prompt", response_model=EnhancePromptResponse)
async def enhance_prompt(request: EnhancePromptRequest):
    """
    增强/优化提示词
    
    根据风格自动添加质量标签和风格描述
    """
    brain = get_brain_service()
    
    try:
        enhanced = await brain.enhance_prompt(
            base_prompt=request.base_prompt,
            style=request.style
        )
        
        return EnhancePromptResponse(enhanced_prompt=enhanced)
        
    except Exception as e:
        logger.error(f"Prompt enhancement failed: {e}")
        raise HTTPException(status_code=500, detail=f"Prompt enhancement failed: {str(e)}")


@router.post("/analyze-script")
async def analyze_script_legacy(script_text: str):
    """
    旧版脚本分析接口（保持向后兼容）
    
    建议使用 /parse-script 替代
    """
    brain = get_brain_service()
    
    try:
        result = await brain.analyze_script(script_text)
        return {"panels": result}
        
    except Exception as e:
        logger.error(f"Script analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Script analysis failed: {str(e)}")
