"""
QA API - 质量检测路由
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Depends, Form
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
import logging

from app.core.database import get_db
from app.models.asset import Asset
from app.services.qa import get_drift_detector, get_auto_retry_manager
from app.services.qa.auto_retry import RetryReason
from app.services.identity import get_embedding_storage

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Response Models ============

class DriftCheckResponse(BaseModel):
    """漂移检测响应"""
    is_drifted: bool
    similarity: float
    threshold: float
    severity: str
    suggestion: Optional[str] = None


class RetryRecommendation(BaseModel):
    """重试建议"""
    should_retry: bool
    action_type: str
    parameter_changes: dict
    message: str
    retry_count: int
    max_retries: int


# ============ Routes ============

@router.post("/check-drift", response_model=DriftCheckResponse)
async def check_drift(
    character_id: str = Form(..., description="角色资产 ID"),
    file: UploadFile = File(..., description="待检测的生成图像"),
    threshold: float = Form(0.7, description="相似度阈值"),
    db: Session = Depends(get_db)
):
    """
    检测生成图像是否与角色存在脸漂移
    
    用于渲染后的 QA 检测：
    1. 上传生成的图像
    2. 系统与角色的 Embedding 对比
    3. 返回相似度和建议
    """
    # 检查角色是否有 embedding
    asset = db.query(Asset).filter(Asset.id == character_id).first()
    if not asset:
        raise HTTPException(status_code=404, detail="Character asset not found")
    
    data_json = asset.data_json or {}
    if data_json.get("embedding_status") != "ready":
        raise HTTPException(
            status_code=400,
            detail="Character embedding not ready. Please extract embedding first."
        )
    
    # 加载参考 embedding
    storage = get_embedding_storage()
    ref_embedding = await storage.load_embedding(character_id)
    
    if ref_embedding is None:
        raise HTTPException(status_code=404, detail="Embedding file not found")
    
    # 读取上传图像
    image_data = await file.read()
    
    # 执行检测
    detector = get_drift_detector()
    result = await detector.check_drift(
        generated_image=image_data,
        reference_embedding=ref_embedding,
        threshold=threshold
    )
    
    return DriftCheckResponse(
        is_drifted=result.is_drifted,
        similarity=result.similarity,
        threshold=result.threshold,
        severity=result.severity,
        suggestion=result.suggestion
    )


@router.post("/should-retry", response_model=RetryRecommendation)
async def should_retry(
    panel_id: str = Form(..., description="分镜 ID"),
    issue_type: str = Form(..., description="问题类型: face_drift, no_face, low_quality, segmentation_fail"),
    current_params: str = Form(..., description="当前参数 JSON"),
    quality_score: float = Form(0.0, description="质量分数（用于 face_drift）")
):
    """
    判断是否应该自动重试
    
    根据问题类型和重试历史，返回重试建议和参数调整方案
    """
    import json
    
    try:
        params = json.loads(current_params)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in current_params")
    
    try:
        reason = RetryReason(issue_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid issue_type. Must be one of: {[r.value for r in RetryReason]}"
        )
    
    manager = get_auto_retry_manager()
    action = manager.should_retry(
        panel_id=panel_id,
        issue_type=reason,
        current_params=params,
        quality_score=quality_score
    )
    
    return RetryRecommendation(
        should_retry=action.action_type in ["retry", "adjust_and_retry"],
        action_type=action.action_type,
        parameter_changes=action.parameter_changes,
        message=action.message,
        retry_count=action.retry_count,
        max_retries=action.max_retries
    )


@router.post("/record-retry")
async def record_retry(
    panel_id: str = Form(..., description="分镜 ID"),
    action_json: str = Form(..., description="执行的动作 JSON"),
    result_json: str = Form(..., description="执行结果 JSON")
):
    """
    记录重试结果
    
    用于跟踪重试历史，供后续决策使用
    """
    import json
    
    try:
        action_data = json.loads(action_json)
        result_data = json.loads(result_json)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    
    from app.services.qa.auto_retry import RetryAction
    
    action = RetryAction(**action_data)
    
    manager = get_auto_retry_manager()
    manager.record_retry(panel_id, action, result_data)
    
    return {"message": "Retry recorded", "panel_id": panel_id}


@router.post("/clear-retry-history")
async def clear_retry_history(panel_id: str = Form(...)):
    """
    清除分镜的重试历史（成功后调用）
    """
    manager = get_auto_retry_manager()
    manager.clear_history(panel_id)
    
    return {"message": "Retry history cleared", "panel_id": panel_id}


@router.get("/retry-history/{panel_id}")
async def get_retry_history(panel_id: str):
    """
    获取分镜的重试历史
    """
    manager = get_auto_retry_manager()
    history = manager.get_history(panel_id)
    
    return {
        "panel_id": panel_id,
        "total_retries": len(history),
        "history": history
    }


@router.post("/get-adjustment-recommendation")
async def get_adjustment_recommendation(
    current_similarity: float = Form(..., description="当前相似度"),
    current_weight: float = Form(0.7, description="当前 FaceID 权重")
):
    """
    获取参数调整建议
    
    根据当前相似度，推荐最佳的 FaceID 权重
    """
    detector = get_drift_detector()
    recommendation = detector.get_recommended_adjustment(
        current_similarity=current_similarity,
        current_weight=current_weight
    )
    
    return recommendation
