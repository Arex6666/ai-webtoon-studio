"""
Automation API - 自动化流程 API 路由

提供全自动分镜生成的 HTTP API 接口
"""
import asyncio
import logging
import uuid
from typing import Dict, Optional
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.schemas.automation import (
    AutomationConfig,
    AutomationResult,
    AutomationStage,
    AutomationProgress,
    RunAutomationRequest,
    AutomationStatusResponse,
)
from app.services.auto_storyboard_orchestrator import AutoStoryboardOrchestrator

logger = logging.getLogger(__name__)
router = APIRouter()

# 任务状态存储 (生产环境应使用 Redis)
_job_store: Dict[str, AutomationResult] = {}


# ============ Routes ============

@router.post(
    "/full-pipeline/{chapter_id}",
    response_model=AutomationStatusResponse,
    summary="运行完整自动化流程",
    description="""
    运行完整的 AI 分镜自动化流程：
    
    1. **Parse**: LLM 解析剧本，提取角色、场景、剧情节拍
    2. **角色链**: 
       - 查找/创建角色资产
       - 提取 FaceID Embedding
       - 绑定 character_id
    3. **场景链**:
       - 查找/创建场景资产
       - 生成控制图 (Depth/Canny/Lineart)
       - 绑定 scene_id
    4. **Plan**: 生成分镜计划
    5. **保存**: 保存为 StoryboardDraft
    
    该接口会立即返回 job_id，可通过 GET /status/{job_id} 查询进度。
    """
)
async def run_full_pipeline(
    chapter_id: str,
    request: RunAutomationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """运行完整自动化流程"""
    job_id = str(uuid.uuid4())
    
    # 初始化结果
    result = AutomationResult(
        success=False,
        chapter_id=chapter_id,
        progress=AutomationProgress(
            stage=AutomationStage.PENDING,
            progress=0.0,
            current_task="任务已提交",
        ),
    )
    _job_store[job_id] = result
    
    # 在后台运行
    background_tasks.add_task(
        _run_automation_task,
        job_id,
        chapter_id,
        request.script_text,
        request.config,
        db,
    )
    
    return AutomationStatusResponse(
        job_id=job_id,
        chapter_id=chapter_id,
        status=AutomationStage.PENDING,
        progress=0.0,
    )


async def _run_automation_task(
    job_id: str,
    chapter_id: str,
    script_text: str,
    config: AutomationConfig,
    db: Session,
):
    """后台运行自动化任务"""
    try:
        orchestrator = AutoStoryboardOrchestrator(db)
        
        # 注册进度回调
        def on_progress(progress: AutomationProgress):
            if job_id in _job_store:
                _job_store[job_id].progress = progress
        
        orchestrator.on_progress(on_progress)
        
        # 运行
        result = await orchestrator.run_full_automation(
            chapter_id=chapter_id,
            script_text=script_text,
            config=config,
        )
        
        _job_store[job_id] = result
        logger.info(f"自动化任务 {job_id} 完成: success={result.success}")
        
    except Exception as e:
        logger.error(f"自动化任务 {job_id} 失败: {e}", exc_info=True)
        if job_id in _job_store:
            _job_store[job_id].errors.append(str(e))
            _job_store[job_id].progress.stage = AutomationStage.FAILED


@router.get(
    "/status/{job_id}",
    response_model=AutomationStatusResponse,
    summary="获取自动化任务状态",
)
async def get_automation_status(job_id: str):
    """获取自动化任务状态"""
    if job_id not in _job_store:
        raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在")
    
    result = _job_store[job_id]
    
    return AutomationStatusResponse(
        job_id=job_id,
        chapter_id=result.chapter_id,
        status=result.progress.stage,
        progress=result.progress.progress,
        result=result if result.progress.stage in [
            AutomationStage.COMPLETED,
            AutomationStage.FAILED,
        ] else None,
        error=result.errors[0] if result.errors else None,
    )


@router.get(
    "/result/{job_id}",
    response_model=AutomationResult,
    summary="获取自动化任务完整结果",
)
async def get_automation_result(job_id: str):
    """获取自动化任务完整结果"""
    if job_id not in _job_store:
        raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在")
    
    result = _job_store[job_id]
    
    if result.progress.stage not in [
        AutomationStage.COMPLETED,
        AutomationStage.FAILED,
    ]:
        raise HTTPException(
            status_code=400,
            detail=f"任务尚未完成，当前状态: {result.progress.stage}",
        )
    
    return result


@router.post(
    "/character-chain/{chapter_id}",
    summary="单独运行角色处理链",
    description="仅处理角色资产的入库和 embedding 提取",
)
async def run_character_chain(
    chapter_id: str,
    request: RunAutomationRequest,
    db: Session = Depends(get_db),
):
    """单独运行角色处理链"""
    from app.services.script_pipeline import ScriptPipelineService
    
    pipeline = ScriptPipelineService()
    
    # Parse
    parse_result = await pipeline.task_parse(request.script_text)
    if not parse_result.success:
        raise HTTPException(status_code=400, detail=parse_result.errors)
    
    # 处理角色链
    orchestrator = AutoStoryboardOrchestrator(db)
    progress = AutomationProgress()
    
    results = await orchestrator._process_character_chain(
        parse_result.script_ir.characters,
        request.config,
        progress,
    )
    
    return {
        "chapter_id": chapter_id,
        "characters": [r.model_dump() for r in results],
        "total": len(results),
        "created": sum(1 for r in results if r.asset_created),
        "embeddings": sum(1 for r in results if r.embedding_extracted),
    }


@router.post(
    "/scene-chain/{chapter_id}",
    summary="单独运行场景处理链",
    description="仅处理场景资产的入库和控制图生成",
)
async def run_scene_chain(
    chapter_id: str,
    request: RunAutomationRequest,
    db: Session = Depends(get_db),
):
    """单独运行场景处理链"""
    from app.services.script_pipeline import ScriptPipelineService
    
    pipeline = ScriptPipelineService()
    
    # Parse
    parse_result = await pipeline.task_parse(request.script_text)
    if not parse_result.success:
        raise HTTPException(status_code=400, detail=parse_result.errors)
    
    # 处理场景链
    orchestrator = AutoStoryboardOrchestrator(db)
    progress = AutomationProgress()
    
    results = await orchestrator._process_scene_chain(
        parse_result.script_ir.scenes,
        request.config,
        progress,
    )
    
    return {
        "chapter_id": chapter_id,
        "scenes": [r.model_dump() for r in results],
        "total": len(results),
        "created": sum(1 for r in results if r.asset_created),
        "control_maps": sum(len(r.control_maps) for r in results),
    }


@router.delete(
    "/job/{job_id}",
    summary="删除任务记录",
)
async def delete_job(job_id: str):
    """删除任务记录"""
    if job_id in _job_store:
        del _job_store[job_id]
        return {"status": "deleted", "job_id": job_id}
    raise HTTPException(status_code=404, detail=f"任务 {job_id} 不存在")
