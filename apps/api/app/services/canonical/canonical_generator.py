"""
Canonical Generator - 角色基准资产自动生成
P0-CH-03~06: 完整 Worker 管线

流程:
1. collect_inputs: 收集角色信息和风格配置
2. generate_candidates: 为每个角色生成 N 张候选定妆照
3. score_candidates: 评分候选照
4. select_best_candidate: 选择最佳并保存
5. extract_face_embedding: 提取 FaceID Embedding
6. persist_results: 写 DB + AssetsLock 联动
7. done: 完成
"""
import asyncio
import logging
import uuid
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from app.core.database import SessionLocal
from app.models import CharacterCanonical, CanonicalStatus, FaceEmbedding
from app.services.layer_factory.comfyui_client import get_comfyui_client
from app.services.layer_factory.workflow_builder import build_flux_workflow
from app.services.storage import get_object_store
from app.api.routes.asset_autobuild import update_job

logger = logging.getLogger(__name__)


# ============ MinIO 路径规范 ============

def get_candidate_path(chapter_id: str, character_id: str, index: int) -> str:
    return f"canon/characters/{chapter_id}/{character_id}/cand_{index}.png"

def get_selected_path(chapter_id: str, character_id: str) -> str:
    return f"canon/characters/{chapter_id}/{character_id}/selected.png"

def get_embedding_path(chapter_id: str, character_id: str, provider: str, img_hash: str) -> str:
    return f"embeddings/{chapter_id}/{character_id}/{provider}_{img_hash[:12]}.npy"

def get_embedding_meta_path(chapter_id: str, character_id: str, provider: str, img_hash: str) -> str:
    return f"embeddings/{chapter_id}/{character_id}/{provider}_{img_hash[:12]}_meta.json"


# ============ Prompt 模板 ============

def build_character_portrait_prompt(character: Dict[str, Any], style_profile: Optional[str] = None) -> Tuple[str, str]:
    positive_parts = [
        "masterpiece, best quality, highly detailed",
        "portrait, solo, 1person",
        "looking at viewer, front view",
        "clear face, detailed facial features",
        "upper body, waist up",
        "natural lighting, soft lighting",
        "clean background, simple background",
    ]
    
    if style_profile:
        if "anime" in style_profile.lower() or "2d" in style_profile.lower():
            positive_parts.insert(0, "anime style, illustration")
        elif "realistic" in style_profile.lower() or "photo" in style_profile.lower():
            positive_parts.insert(0, "photorealistic, cinematic")
    
    if character.get("gender"):
        positive_parts.append(character["gender"])
    if character.get("age_range"):
        positive_parts.append(character["age_range"])
    if character.get("appearance"):
        positive_parts.extend(character["appearance"][:5])
    
    positive_prompt = ", ".join(positive_parts)
    
    negative_prompt = (
        "bad quality, low quality, blurry, "
        "multiple people, crowd, group, "
        "cropped face, obscured face, covered face, masked, "
        "back view, side view, looking away, "
        "extreme angle, dutch angle, fish eye, "
        "exaggerated expression, distorted, "
        "text, watermark, signature, logo, "
        "nsfw, nude"
    )
    
    return positive_prompt, negative_prompt


# ============ Worker 主函数 ============

async def run_autobuild_characters(
    job_id: str,
    chapter_id: str,
    characters: List[Dict[str, Any]],
    config: Dict[str, Any],
):
    """
    后台任务：自动生成 + 评分 + 选优 + Embedding
    
    Stages: collect_inputs → generate_candidates → score_candidates 
            → select_best_candidate → extract_face_embedding → persist_results → done
    """
    logger.info(f"[{job_id}] Starting autobuild characters")
    
    candidate_count = config.get("candidate_count", 4)
    style_profile = config.get("style_profile")
    
    db = SessionLocal()
    storage = get_object_store()
    comfy_client = get_comfyui_client()
    
    # 进度计算: 每个角色 = generate(N) + score(1) + select(1) + embed(1)
    steps_per_char = candidate_count + 3
    total_steps = len(characters) * steps_per_char + 2  # +2 for collect + final persist
    current_step = 0
    
    # 存储生成的候选数据 (path -> bytes)
    generated_images: Dict[str, bytes] = {}
    
    try:
        # ========== Stage 1: collect_inputs ==========
        update_job(job_id, status="running", stage="collect_inputs", progress=0,
                   started_at=datetime.utcnow(), message=f"收集 {len(characters)} 个角色信息...")
        logger.info(f"[{job_id}] Stage: collect_inputs")
        await _emit_progress(job_id, "collect_inputs", 0, chapter_id)
        
        valid_characters = [c for c in characters if c.get("id")]
        current_step = 1
        
        # ========== Stage 2: generate_candidates ==========
        update_job(job_id, stage="generate_candidates", message="生成候选定妆照...")
        logger.info(f"[{job_id}] Stage: generate_candidates")
        
        for char_idx, char in enumerate(valid_characters):
            character_id = char["id"]
            character_name = char.get("name", character_id)
            
            canonical = db.query(CharacterCanonical).filter(
                CharacterCanonical.chapter_id == chapter_id,
                CharacterCanonical.character_id == character_id,
            ).first()
            
            if canonical:
                canonical.status = CanonicalStatus.RUNNING
                db.commit()
            
            candidate_paths = []
            
            for cand_idx in range(candidate_count):
                try:
                    positive, negative = build_character_portrait_prompt(char, style_profile)
                    import time
                    seed = int(time.time() * 1000 + cand_idx * 12345) % 2147483647
                    
                    workflow = build_flux_workflow(
                        positive_prompt=positive, negative_prompt=negative,
                        width=768, height=1024, seed=seed, steps=25,
                    )
                    
                    prompt_id = await comfy_client.submit_workflow(workflow)
                    status = await _wait_comfyui_completion(comfy_client, prompt_id, timeout=180)
                    
                    if status.get("status") == "completed":
                        outputs = await comfy_client.fetch_outputs(prompt_id)
                        if outputs:
                            image_data = outputs[0]
                            storage_key = get_candidate_path(chapter_id, character_id, cand_idx + 1)
                            await storage.upload_file(file_content=image_data, key=storage_key, content_type="image/png")
                            candidate_paths.append(storage_key)
                            generated_images[storage_key] = image_data
                            logger.info(f"[{job_id}] Generated candidate {cand_idx+1} for {character_name}")
                
                except Exception as e:
                    logger.error(f"[{job_id}] Failed candidate {cand_idx+1} for {character_name}: {e}")
                
                current_step += 1
                progress = (current_step / total_steps) * 100
                update_job(job_id, progress=progress, message=f"{character_name} 候选 {cand_idx+1}/{candidate_count}")
                await _emit_progress(job_id, "generate_candidates", progress, chapter_id,
                                     character_id=character_id, character_name=character_name, candidate_index=cand_idx+1)
            
            if canonical:
                canonical.candidate_paths = candidate_paths
                db.commit()
        
        # ========== Stage 3: score_candidates ==========
        update_job(job_id, stage="score_candidates", message="评分候选...")
        logger.info(f"[{job_id}] Stage: score_candidates")
        await _emit_progress(job_id, "score_candidates", progress, chapter_id)
        
        from app.services.canonical.selector import score_and_select
        
        for char in valid_characters:
            character_id = char["id"]
            character_name = char.get("name", character_id)
            
            canonical = db.query(CharacterCanonical).filter(
                CharacterCanonical.chapter_id == chapter_id,
                CharacterCanonical.character_id == character_id,
            ).first()
            
            if not canonical or not canonical.candidate_paths:
                continue
            
            # 准备候选数据
            candidates_data = []
            for path in canonical.candidate_paths:
                if path in generated_images:
                    candidates_data.append((path, generated_images[path]))
                else:
                    # 尝试从存储读取
                    try:
                        img_data = await storage.download_file(path)
                        candidates_data.append((path, img_data))
                    except:
                        logger.warning(f"Could not load candidate {path}")
            
            if not candidates_data:
                continue
            
            # 评分并选择
            all_scores, best = await score_and_select(candidates_data, char, style_profile)
            
            current_step += 1
            progress = (current_step / total_steps) * 100
            
            if best:
                # 记录评分到 meta
                scores_summary = {s.path: {"total": s.total, "breakdown": s.breakdown, "flags": s.flags} for s in all_scores}
                
                await _emit_progress(job_id, "score_candidates", progress, chapter_id,
                                     character_id=character_id, character_name=character_name,
                                     message=f"最佳: {best.path.split('/')[-1]} (score={best.total:.0f})")
                
                # ========== Stage 4: select_best_candidate ==========
                update_job(job_id, stage="select_best_candidate", message=f"选择 {character_name} 最佳...")
                logger.info(f"[{job_id}] Stage: select_best_candidate for {character_name}")
                
                # 复制最佳到 selected.png
                selected_path = get_selected_path(chapter_id, character_id)
                if best.path in generated_images:
                    selected_data = generated_images[best.path]
                else:
                    selected_data = await storage.download_file(best.path)
                
                await storage.upload_file(file_content=selected_data, key=selected_path, content_type="image/png")
                
                # 更新 DB
                canonical.selected_path = selected_path
                canonical.selected_score = best.total
                canonical.selection_reason = best.notes
                db.commit()
                
                logger.info(f"[{job_id}] Selected {selected_path} (score={best.total:.1f}) for {character_name}")
                
                current_step += 1
                progress = (current_step / total_steps) * 100
                await _emit_progress(job_id, "select_best_candidate", progress, chapter_id,
                                     character_id=character_id, character_name=character_name)
                
                # ========== Stage 5: extract_face_embedding ==========
                update_job(job_id, stage="extract_face_embedding", message=f"提取 {character_name} FaceID...")
                logger.info(f"[{job_id}] Stage: extract_face_embedding for {character_name}")
                
                try:
                    embedding_result = await _extract_and_save_embedding(
                        db, storage, chapter_id, character_id, selected_path, selected_data
                    )
                    
                    if embedding_result.get("success"):
                        logger.info(f"[{job_id}] Extracted embedding for {character_name}: {embedding_result.get('embedding_path')}")
                    else:
                        logger.warning(f"[{job_id}] Embedding extraction failed for {character_name}: {embedding_result.get('error')}")
                
                except Exception as e:
                    logger.error(f"[{job_id}] Embedding extraction error for {character_name}: {e}")
                
                current_step += 1
                progress = (current_step / total_steps) * 100
                await _emit_progress(job_id, "extract_face_embedding", progress, chapter_id,
                                     character_id=character_id, character_name=character_name)
        
        # ========== Stage 6: persist_results ==========
        update_job(job_id, stage="persist_results", progress=95, message="保存结果...")
        logger.info(f"[{job_id}] Stage: persist_results")
        await _emit_progress(job_id, "persist_results", 95, chapter_id)
        
        # 更新所有角色状态为成功
        for char in valid_characters:
            canonical = db.query(CharacterCanonical).filter(
                CharacterCanonical.chapter_id == chapter_id,
                CharacterCanonical.character_id == char["id"],
            ).first()
            if canonical and canonical.selected_path:
                canonical.status = CanonicalStatus.SUCCEEDED
        
        db.commit()
        
        # ========== Stage 7: done ==========
        update_job(job_id, status="succeeded", stage="done", progress=100, message="完成")
        logger.info(f"[{job_id}] Stage: done")
        await _emit_progress(job_id, "done", 100, chapter_id)
        
    except Exception as e:
        logger.error(f"[{job_id}] Autobuild failed: {e}", exc_info=True)
        update_job(job_id, status="failed", message=f"失败: {str(e)}")
        await _emit_progress(job_id, "failed", 0, chapter_id, message=str(e))
    finally:
        db.close()


async def _extract_and_save_embedding(
    db, storage, chapter_id: str, character_id: str, selected_path: str, image_data: bytes
) -> Dict[str, Any]:
    """提取并保存 FaceID Embedding"""
    result = {"success": False, "embedding_path": None, "error": None}
    
    try:
        from app.services.identity import get_face_extractor
        
        extractor = get_face_extractor()
        embedding, bbox_info = extractor.extract_embedding(image_data, return_bbox=True)
        
        if embedding is None:
            result["error"] = "No face detected in selected image"
            return result
        
        # 计算图片哈希
        img_hash = hashlib.sha256(image_data).hexdigest()
        
        # 保存 embedding 到 MinIO
        import numpy as np
        embedding_bytes = embedding.astype(np.float32).tobytes()
        embedding_path = get_embedding_path(chapter_id, character_id, "insightface", img_hash)
        await storage.upload_file(file_content=embedding_bytes, key=embedding_path, content_type="application/octet-stream")
        
        # 保存 meta
        import json
        meta = {
            "provider": "insightface",
            "model_name": "buffalo_l",
            "dim": 512,
            "det_score": bbox_info.get("det_score") if bbox_info else None,
            "bbox": bbox_info.get("bbox") if bbox_info else None,
            "source_image_path": selected_path,
            "source_image_hash": img_hash,
            "created_at": datetime.utcnow().isoformat(),
        }
        meta_path = get_embedding_meta_path(chapter_id, character_id, "insightface", img_hash)
        await storage.upload_file(file_content=json.dumps(meta).encode(), key=meta_path, content_type="application/json")
        
        # 写入 DB (FaceEmbedding)
        # 查找或创建 character asset
        from app.models import Asset
        asset = db.query(Asset).filter(
            Asset.asset_type == "character",
            Asset.name.ilike(f"%{character_id}%")
        ).first()
        
        if asset:
            face_emb = FaceEmbedding(
                id=str(uuid.uuid4()),
                character_asset_id=asset.id,
                provider="insightface",
                model_name="buffalo_l",
                dim=512,
                embedding_path=embedding_path,
                reference_image_path=selected_path,
                quality_score=bbox_info.get("det_score", 0.0) if bbox_info else 0.0,
                status="active",
            )
            db.add(face_emb)
            db.commit()
        
        result["success"] = True
        result["embedding_path"] = embedding_path
        result["meta_path"] = meta_path
        
    except Exception as e:
        logger.error(f"Embedding extraction failed: {e}")
        result["error"] = str(e)
    
    return result


async def _wait_comfyui_completion(client, prompt_id: str, timeout: int = 180) -> dict:
    import time
    start_time = time.time()
    while time.time() - start_time < timeout:
        status = await client.poll_status(prompt_id)
        if status.get("status") in ["completed", "failed"]:
            return status
        await asyncio.sleep(1.0)
    return {"status": "timeout"}


async def _emit_progress(
    job_id: str, stage: str, progress: float, chapter_id: str,
    character_id: str = None, character_name: str = None,
    candidate_index: int = None, message: str = None,
):
    """推送 WS 进度事件"""
    try:
        from app.api.routes.ws import broadcast_to_chapter
        event = {
            "type": "asset_autobuild_progress",
            "job_id": job_id,
            "scope": "characters",
            "stage": stage,
            "progress": progress,
            "character_id": character_id,
            "character_name": character_name,
            "candidate_index": candidate_index,
            "message": message,
        }
        await broadcast_to_chapter(chapter_id, event)
    except Exception as e:
        logger.debug(f"WS emit failed: {e}")
