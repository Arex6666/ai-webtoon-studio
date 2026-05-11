"""
Storyboard operations for chapters
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel

from app.core.database import get_db
from app.models.chapter import Chapter
from app.models.render_job import RenderJob
from app.models.storyboard_draft import StoryboardDraft
from app.api.deps import get_current_user
from app.models.user import User
import logging
import uuid

logger = logging.getLogger(__name__)

router = APIRouter()


# Request/Response Models
class CreateStoryboardRequest(BaseModel):
    provider: Optional[str] = "mock"
    target_panels: Optional[int] = None
    style_hint: Optional[str] = "korean_webtoon"
    auto_apply: Optional[bool] = True


class StoryboardResponse(BaseModel):
    """分镜生成响应"""
    job_id: str
    status: str
    message: str = "queued"


@router.post("/{chapter_id}/storyboard", response_model=StoryboardResponse)
async def create_storyboard(
    chapter_id: str,
    request: CreateStoryboardRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    创建 AI 分镜任务（同步执行）

    该 API 会等待分镜生成完成后返回 job_id
    """
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    # 校验：剧本非空
    if not chapter.script_raw or not chapter.script_raw.strip():
        raise HTTPException(
            status_code=400,
            detail="Script is empty. Please save a script first."
        )

    # 创建 Job 记录
    try:
        job_id = str(uuid.uuid4())
        job = RenderJob(
            id=job_id,
            chapter_id=chapter_id,
            panel_id=None,
            job_type="storyboard",
            engine=request.provider or "mock",
            status="running",
            input_params={
                "script": chapter.script_raw,
                "style_hint": request.style_hint,
                "target_panels": request.target_panels,
                "provider": request.provider or "mock"
            }
        )
        db.add(job)
        db.commit()

        # 直接运行任务（不使用 BackgroundTasks）
        await run_storyboard_task(
            job_id=job_id,
            chapter_id=chapter_id,
            script=chapter.script_raw,
            style_hint=request.style_hint or "korean_webtoon",
            provider=request.provider or "mock",
            auto_apply=request.auto_apply if request.auto_apply is not None else True,
        )

        return StoryboardResponse(job_id=job_id, status="succeeded", message="completed")

    except HTTPException as he:
        raise he
    except Exception as e:
        import traceback
        error_msg = f"Failed to create job: {str(e)}"
        print(traceback.format_exc())
        # 更新 job 状态为失败
        job = db.query(RenderJob).filter(RenderJob.id == job_id).first()
        if job:
            job.status = "failed"
            job.error_message = str(e)
            db.commit()
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=500, content={"message": error_msg, "trace": traceback.format_exc()})


# ============================================================
# Multi-Agent Classes
# ============================================================

class BaseStoryAgent:
    """Agent 基类：封装 WebSocket 推送"""
    def __init__(self, name: str, chapter_id: str, job_id: str):
        self.name = name
        self.chapter_id = chapter_id
        self.job_id = job_id

    async def emit_thought(self, progress: float, message: str):
        from app.api.routes.ws import push_unified_job_event
        await push_unified_job_event(self.chapter_id, "job_progress", self.job_id, {
            "progress": progress, "agent": self.name, "message": message
        })


class OrchestratorAgent(BaseStoryAgent):
    """总调度 Agent：分解任务并编排子 Agent"""
    def __init__(self, chapter_id: str, job_id: str):
        super().__init__("Orchestrator Agent", chapter_id, job_id)

    async def plan(self):
        import asyncio
        await self.emit_thought(0.05, "任务已接收，正在编排 Agent Cluster 工作流...")
        await asyncio.sleep(0.5)
        await self.emit_thought(0.1, "任务分解完成:\n1. 资产提取(Script & Asset Agent)\n2. 运镜设计(Director Agent)\n3. 结构映射(Layout Agent)")


class ScriptAssetAgent(BaseStoryAgent):
    """脚本资产 Agent：解构剧本并提取角色/场景"""
    def __init__(self, chapter_id: str, job_id: str):
        super().__init__("Script & Asset Agent", chapter_id, job_id)

    async def extract(self, brain, composer) -> dict:
        import asyncio
        import json as _json
        await self.emit_thought(0.2, "深度思考中：正在解构剧情节拍，并强制提取含有'三视图'约定的角色与独立场景资产...")
        if hasattr(brain, "_chat_completion"):
            contract = composer.compose_analysis_contract()
            res = await brain._chat_completion(contract.to_messages(), response_format="json")
            try:
                return _json.loads(res)
            except Exception:
                pass
        await asyncio.sleep(1)
        return {"characters": [], "locations": [], "beats": []}


class DirectorAgent(BaseStoryAgent):
    """导演 Agent：设计机位、运镜和 Visual Prompt"""
    def __init__(self, chapter_id: str, job_id: str):
        super().__init__("Director Agent", chapter_id, job_id)

    async def design_storyboard(self, brain, composer, analysis_json: dict) -> dict:
        import asyncio
        import json as _json
        await self.emit_thought(0.5, "导演就位：开始根据资产数据与剧情节拍，设计包含机位、运镜以及极其细致视觉提示词（Visual Prompt）的硬约束分镜表...")
        if hasattr(brain, "_chat_completion"):
            contract = composer.compose_storyboard_contract(analysis_json)
            res = await brain._chat_completion(contract.to_messages(), response_format="json")
            try:
                return _json.loads(res)
            except Exception:
                pass
        await asyncio.sleep(1)
        return {"panels": []}


class LayoutAgent(BaseStoryAgent):
    """布局 Agent：将导演数据映射为前端所需的 Panel JSON"""
    def __init__(self, chapter_id: str, job_id: str):
        super().__init__("Layout Assistant", chapter_id, job_id)

    async def map_assets(self, analysis_json: dict, storyboard_json: dict) -> tuple:
        panels_json: list = []
        panels_data = storyboard_json.get("panels", [])
        total = max(len(panels_data), 1)

        for i, panel in enumerate(panels_data):
            p = 0.7 + 0.15 * (i / total)
            await self.emit_thought(p, f"正在进行骨骼映射并封装第 {i+1} 个镜头的底层视觉提示词(Visual Prompt)...")

            panel_id = str(uuid.uuid4())
            action = panel.get("actions", "")
            visual_prompt = panel.get("visual_prompt", action)
            comp_notes = "\n".join(panel.get("composition_notes", []))

            spec: dict = {
                "id": panel_id,
                "index": i,
                "shot": {
                    "shotType": str(panel.get("shot_type", "MS")).upper(),
                    "cameraMove": panel.get("camera_move", "static"),
                    "durationSec": float(panel.get("duration_s", 3.0)),
                    "description": action,
                    "lensHint": panel.get("lens_hint", "")
                },
                "scene": {
                    "location": panel.get("location", "未指定"),
                    "timeOfDay": panel.get("time_of_day", "day"),
                    "weather": panel.get("weather", "clear"),
                    "mood": ", ".join(panel.get("mood", [])) if isinstance(panel.get("mood"), list) else panel.get("mood", "neutral")
                },
                "characters": [],
                "dialogue": {
                    "lines": []
                },
                "style": {
                    "styleProfileId": "default",
                    "negativePrompt": ""
                },
                "render": {
                    "status": "Draft",
                    "lastRenderAt": None,
                    "warnings": []
                },
                "meta": {
                    "createdAt": str(i),
                    "updatedAt": str(i),
                    "visual_prompt": visual_prompt,
                    "composition_notes": comp_notes,
                    "continuity_notes": "\n".join(panel.get("continuity_notes", []))
                }
            }

            # Dialogue
            for d_idx, dlg in enumerate(panel.get("dialogue_lines", [])):
                spec["dialogue"]["lines"].append({
                    "speaker": "Unknown",
                    "text": dlg,
                    "type": "speech"
                })

            # Cast
            for ref in panel.get("cast", []):
                spec["characters"].append(ref)

            panels_json.append(spec)

        # Characters JSON from analysis
        characters_json: list = []
        for char in analysis_json.get("characters", []):
            name = char.get("canonical_name") or char.get("name")
            traits_list = char.get("appearance_traits", [])
            traits = ", ".join(traits_list) if traits_list else "从分镜自动创建"
            desc = char.get("wardrobe_notes", "") or char.get("role_description", "") or char.get("role", "")
            characters_json.append({
                "name": name,
                "appearances": 0,
                "appearance_traits": traits_list,
                "personality_traits": char.get("personality_traits", []),
                "description": f"{desc}\n外貌: {traits}".strip()
            })

        # Scenes JSON from analysis
        scenes_json: list = []
        for loc in analysis_json.get("locations", []):
            name = loc.get("canonical_location")
            desc = loc.get("anchor_hint", "")
            scenes_json.append({
                "name": name,
                "appearances": 0,
                "description": desc,
                "timeOfDay": loc.get("time_of_day_default", "day"),
                "weather": loc.get("weather_default", "clear"),
                "is_reused": loc.get("is_reused", False)
            })

        # Count appearances
        for panel in panels_json:
            for char_name in panel.get("characters", []):
                for c in characters_json:
                    if c["name"] == char_name:
                        c["appearances"] += 1
            loc_name = panel.get("scene", {}).get("location")
            for s in scenes_json:
                if s["name"] == loc_name:
                    s["appearances"] += 1

        return panels_json, characters_json, scenes_json


# ============================================================
# run_storyboard_task - Multi-Agent Pipeline
# ============================================================

async def run_storyboard_task(
    job_id: str,
    chapter_id: str,
    script: str,
    style_hint: str,
    provider: str,
    auto_apply: bool = True
):
    """
    后台执行 AI 分镜任务：使用多智能体(Multi-Agent)模式进行大模型管线作业并推送实时进程
    """
    from app.core.database import SessionLocal
    from app.api.routes.ws import push_unified_job_event

    db = SessionLocal()
    try:
        from app.models.job import Job as UnifiedJob
        render_job = db.query(RenderJob).filter(RenderJob.id == job_id).first()
        unified_job = db.query(UnifiedJob).filter(UnifiedJob.id == job_id).first() if not render_job else None
        job = render_job

        if render_job:
            render_job.status = "running"
            render_job.current_step = "validating"
            db.commit()
        if unified_job:
            unified_job.status = "running"
            unified_job.progress = 0.0
            db.commit()

        await push_unified_job_event(chapter_id, "job_status", job_id, {"status": "running"})

        # Initialize Agents
        orchestrator = OrchestratorAgent(chapter_id, job_id)
        analyst = ScriptAssetAgent(chapter_id, job_id)
        director = DirectorAgent(chapter_id, job_id)
        layout_agent = LayoutAgent(chapter_id, job_id)

        # 1. Orchestrator Plan
        await orchestrator.plan()

        # Load Brain
        from app.services.brain.base import get_brain_service
        if provider == "mock":
            from app.services.brain.mock import MockBrainService
            brain = MockBrainService()
        else:
            brain = get_brain_service()

        from app.services.brain.prompt_composer import PromptComposer
        from app.services.brain.prompt_contract import get_style_by_name
        composer = PromptComposer(script_text=script, style_profile=get_style_by_name(style_hint or "韩漫"))

        # 2. Asset & Script Analysis
        analysis_json = await analyst.extract(brain, composer)

        # 3. Storyboard Direction
        storyboard_json = await director.design_storyboard(brain, composer, analysis_json)

        # 4. Layout & Asset Mapping
        panels_json, characters_json, scenes_json = await layout_agent.map_assets(analysis_json, storyboard_json)

        # 5. Building Draft
        await orchestrator.emit_thought(0.85, "正在合并分镜数据并生成总控草案...")

        chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            raise Exception("Chapter not found")

        draft_id = str(uuid.uuid4())
        draft = StoryboardDraft(
            id=draft_id,
            chapter_id=chapter_id,
            job_id=job_id,
            status="completed",
            version=1,
            panels_json=panels_json,
            characters_json=characters_json,
            scenes_json=scenes_json,
            script_snapshot=script,
            provider=provider,
            style_hint=style_hint,
            generated_panels_count=len(panels_json),
            generated_characters_count=len(characters_json),
            generated_scenes_count=len(scenes_json)
        )
        db.add(draft)

        chapter_layout = chapter.layout_json or {}
        chapter.layout_json = {**chapter_layout, "pending_draft_id": draft_id, "storyboard_job_id": job_id}

        if job:
            job.status = "succeeded"
            job.current_step = "done"
            job.progress = 100
            job.output_data = {
                "draft_id": draft_id,
                "panels_count": len(panels_json)
            }
        if unified_job:
            from datetime import datetime
            unified_job.status = "succeeded"
            unified_job.progress = 1.0
            unified_job.finished_at = datetime.utcnow()
            unified_job.outputs_json = {
                "draft_id": draft_id,
                "panels_count": len(panels_json)
            }
        db.commit()

        await orchestrator.emit_thought(1.0, "分镜生成完毕！")
        await push_unified_job_event(chapter_id, "job_result", job_id, {
            "type": "storyboard",
            "result": {
                "draft_id": draft_id,
                "panels_count": len(panels_json)
            }
        })
        await push_unified_job_event(chapter_id, "job_status", job_id, {"status": "succeeded"})

        # Auto-apply Draft
        if auto_apply:
            try:
                from app.api.routes.drafts import apply_draft_internal
                await apply_draft_internal(db, draft_id, create_missing_assets=True)
                chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
                if chapter and chapter.layout_json:
                    layout_dict = dict(chapter.layout_json)
                    layout_dict.pop("pending_draft_id", None)
                    chapter.layout_json = layout_dict
                    db.commit()
            except Exception as apply_err:
                raise Exception(f"Auto-apply draft failed: {apply_err}") from apply_err

            # ── Phase 6: Auto-generate asset images ──────────────────────
            await orchestrator.emit_thought(0.92, "正在为角色和场景自动生成参考图...")
            try:
                from app.models.asset import Asset
                draft_obj = db.query(StoryboardDraft).filter(StoryboardDraft.id == draft_id).first()
                project_id = chapter.project_id if chapter else None

                # 6a. Auto-generate character portraits
                if draft_obj and project_id:
                    from app.services.portrait.retry_strategy import enqueue_portrait_generation
                    for char_info in (draft_obj.characters_json or []):
                        char_name = char_info.get("name")
                        if not char_name:
                            continue
                        # Find the Asset record that was just created
                        asset = db.query(Asset).filter(
                            Asset.project_id == project_id,
                            Asset.name == char_name,
                            Asset.type == "character"
                        ).first()
                        if asset:
                            await orchestrator.emit_thought(0.93, f"正在为角色 '{char_name}' 生成参考图...")
                            try:
                                await enqueue_portrait_generation(
                                    character_id=asset.id,
                                    project_id=project_id,
                                    character_name=char_name,
                                    character_description=char_info.get("description"),
                                    appearance_traits=char_info.get("appearance_traits", []),
                                    provider=provider if provider != "mock" else "mock",
                                    db_session=None  # Will create its own session
                                )
                            except Exception as portrait_err:
                                logger.warning(f"Portrait generation failed for {char_name}: {portrait_err}")

                    # 6b. Auto-generate scene anchors
                    from app.services.scene.retry_strategy import enqueue_scene_anchor_generation
                    for scene_info in (draft_obj.scenes_json or []):
                        scene_name = scene_info.get("name")
                        if not scene_name:
                            continue
                        asset = db.query(Asset).filter(
                            Asset.project_id == project_id,
                            Asset.name == scene_name,
                            Asset.type == "scene"
                        ).first()
                        if asset:
                            await orchestrator.emit_thought(0.95, f"正在为场景 '{scene_name}' 生成锚点图...")
                            try:
                                await enqueue_scene_anchor_generation(
                                    scene_id=asset.id,
                                    project_id=project_id,
                                    scene_name=scene_name,
                                    location=scene_info.get("location"),
                                    time_of_day=scene_info.get("time_of_day"),
                                    mood=scene_info.get("mood"),
                                    db_session=None,
                                )
                            except Exception as scene_err:
                                logger.warning(f"Scene anchor generation failed for {scene_name}: {scene_err}")

                await orchestrator.emit_thought(0.98, "资产参考图已全部入队生成！")
            except Exception as gen_err:
                logger.warning(f"Asset auto-generation failed (non-fatal): {gen_err}")

    except Exception as e:
        db.rollback()
        logger.error(f"Storyboard task failed for job {job_id}: {e}", exc_info=True)
        try:
            rj = db.query(RenderJob).filter(RenderJob.id == job_id).first()
            if rj:
                rj.status = "failed"
                rj.error_message = str(e)
            from app.models.job import Job as UnifiedJob
            uj = db.query(UnifiedJob).filter(UnifiedJob.id == job_id).first()
            if uj:
                from datetime import datetime
                uj.status = "failed"
                uj.error_json = {"message": str(e)}
                uj.finished_at = datetime.utcnow()
            db.commit()
            await push_unified_job_event(chapter_id, "job_status", job_id, {"status": "failed", "error": str(e)})
        except Exception:
            logger.debug("Could not mark job as failed", exc_info=True)
    finally:
        db.close()
