"""
Bundle Builder - 章节打包核心流水线

实现 6 步构建流程：
1. collect_chapter_snapshot - 收集章节快照
2. resolve_panel_artifacts - 解析面板产物
3. fetch_files_to_staging - 拉取文件到暂存区
4. write_panel_folder - 写入面板目录
5. write_bundle_root_files - 写入根目录文件
6. zip_and_upload - 打包并上传
"""
import os
import json
import shutil
import zipfile
import logging
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable

from sqlalchemy.orm import Session

from app.models import Chapter, Panel, LayerPack, Job, RenderJob
from app.schemas.bundle_manifest import (
    BundleManifest, BundlePanelEntry, BundleChapterInfo,
    BundleProvenance, BundleQASummary, ChapterJsonSpec, PanelJsonSpec,
    AssetsLockSpec, ProvenanceJobsSpec, BundleChapterVideo,
)
from app.schemas.layerpack_manifest import (
    LayerPackManifest, create_layerpack_manifest_from_db
)
from app.services.export.bundle_models import (
    ChapterSnapshot, PanelSnapshot, PanelArtifactPlan, 
    BundleBuildContext, BundleBuildResult, GateCheckResult
)
from app.services.export.bundle_errors import (
    BundleBuildError, MissingArtifactError, CorruptManifestError,
    ChapterNotFoundError, NoPanelsError, NoLayerPackError
)
from app.services.export.asset_lock_resolver import AssetLockResolver
from app.services.export.provenance_collector import ProvenanceCollector
from app.services.export.export_gate import ExportGate
from app.services.storage.object_store import get_object_store

logger = logging.getLogger(__name__)


class BundleBuilder:
    """Bundle 构建器"""
    
    SPEC_VERSION = "1.0.0"
    
    def __init__(self, db: Session, context: BundleBuildContext):
        self.db = db
        self.context = context
        self.object_store = get_object_store()
    
    # ==================== Step 1: 收集章节快照 ====================
    
    def collect_chapter_snapshot(self, chapter_id: str) -> ChapterSnapshot:
        """
        Step 1: 收集章节快照
        
        从数据库读取章节和面板信息，生成快照
        """
        logger.info(f"[Bundle] Step 1: Collecting chapter snapshot for {chapter_id}")
        
        # 查询章节
        chapter = self.db.query(Chapter).filter(Chapter.id == chapter_id).first()
        if not chapter:
            raise ChapterNotFoundError(chapter_id)
        
        # 查询面板（按顺序）
        panels = self.db.query(Panel).filter(
            Panel.chapter_id == chapter_id
        ).order_by(Panel.order_index).all()
        
        if not panels:
            raise NoPanelsError(chapter_id)
        
        # 构建面板快照列表
        panel_snapshots = []
        for i, panel in enumerate(panels):
            index_str = str(i + 1).zfill(4)  # "0001", "0002"...
            
            # 获取 PanelSpec（从 spec_json 或 params_json）
            panel_spec = panel.spec_json or panel.params_json or {}
            
            # 确定选中的 LayerPack
            selected_lp_id = None
            if panel.active_layer_pack_id:
                selected_lp_id = panel.active_layer_pack_id
            else:
                # 取最新成功的
                latest_lp = self.db.query(LayerPack).filter(
                    LayerPack.panel_id == panel.id,
                    LayerPack.status == "completed"
                ).order_by(LayerPack.created_at.desc()).first()
                if latest_lp:
                    selected_lp_id = latest_lp.id
            
            panel_snapshots.append(PanelSnapshot(
                panel_id=panel.id,
                index_str=index_str,
                order_index=panel.order_index,
                panel_spec_json=panel_spec,
                selected_layerpack_id=selected_lp_id,
                selected_typeset_id=None,  # TODO: 如果有 typeset 表
                render_status=panel.render_status or "unknown",
                qa_score=panel.qa_score,
                needs_fix=panel.render_status == "needs_fix",
                duration_sec=panel_spec.get("shot", {}).get("durationSec")
            ))
        
        return ChapterSnapshot(
            chapter_id=chapter.id,
            project_id=chapter.project_id,
            title=chapter.title or f"Chapter {chapter.order_index}",
            version=1,
            panels=panel_snapshots,
            style_profile_snapshot=getattr(chapter, "style_profile_json", None)
        )
    
    # ==================== Step 2: 解析面板产物 ====================
    
    def resolve_panel_artifacts(self, panel_snapshot: PanelSnapshot) -> PanelArtifactPlan:
        """
        Step 2: 解析单个面板的产物计划
        
        决定导出时使用哪个 LayerPack、Typeset 等
        """
        plan = PanelArtifactPlan(
            panel_id=panel_snapshot.panel_id,
            panel_index_str=panel_snapshot.index_str
        )
        
        # 获取选定的 LayerPack
        if panel_snapshot.selected_layerpack_id:
            layerpack = self.db.query(LayerPack).filter(
                LayerPack.id == panel_snapshot.selected_layerpack_id
            ).first()
            
            if layerpack:
                plan.layerpack_id = layerpack.id
                plan.layerpack_manifest_url = layerpack.manifest_url
                
                # 添加文件到计划
                # full.png (必须)
                full_url = layerpack.full_url or layerpack.file_full
                if full_url:
                    plan.add_layerpack_file(
                        full_url,
                        f"panels/{plan.panel_index_str}/layerpack/full.png",
                        required=True
                    )
                    plan.preview_image_url = full_url
                else:
                    plan.is_valid = False
                    plan.validation_errors.append("Missing full.png")
                
                # char.png (可选)
                if layerpack.file_char:
                    plan.add_layerpack_file(
                        layerpack.file_char,
                        f"panels/{plan.panel_index_str}/layerpack/char.png",
                        required=False
                    )
                
                # bg.png (可选)
                if layerpack.file_bg:
                    plan.add_layerpack_file(
                        layerpack.file_bg,
                        f"panels/{plan.panel_index_str}/layerpack/bg.png",
                        required=False
                    )
                
                # fg.png (可选)
                if layerpack.file_fg:
                    plan.add_layerpack_file(
                        layerpack.file_fg,
                        f"panels/{plan.panel_index_str}/layerpack/fg.png",
                        required=False
                    )
                
                # mask.png (可选)
                if layerpack.file_mask:
                    plan.add_layerpack_file(
                        layerpack.file_mask,
                        f"panels/{plan.panel_index_str}/layerpack/char_mask.png",
                        required=False
                    )
        else:
            # 尝试从 Panel 获取预览图
            panel = self.db.query(Panel).filter(Panel.id == panel_snapshot.panel_id).first()
            if panel and panel.preview_url:
                plan.add_layerpack_file(
                    panel.preview_url,
                    f"panels/{plan.panel_index_str}/layerpack/full.png",
                    required=True
                )
                plan.preview_image_url = panel.preview_url
            else:
                plan.is_valid = False
                plan.validation_errors.append("No LayerPack available")
        
        # Typeset (从 Panel 表获取)
        panel = self.db.query(Panel).filter(Panel.id == panel_snapshot.panel_id).first()
        if panel and panel.typeset_image_url:
            plan.typeset_png_url = panel.typeset_image_url
            plan.preview_image_url = panel.typeset_image_url  # typeset 优先
        
        # Bubbles JSON (从 Panel 表获取)
        bubbles = getattr(panel, "bubbles_json", None) if panel else None
        if bubbles:
            plan.bubbles_json = bubbles
        
        # QA 数据
        if panel_snapshot.qa_score is not None:
            plan.qa_data = {
                "score": panel_snapshot.qa_score,
                "needs_fix": panel_snapshot.needs_fix
            }
        
        return plan
    
    # ==================== Step 3: 拉取文件到暂存区 ====================
    
    async def fetch_files_to_staging(
        self, 
        plan: PanelArtifactPlan, 
        staging_dir: str
    ) -> None:
        """
        Step 3: 拉取文件到暂存目录
        
        流式下载以避免 OOM
        """
        logger.info(f"[Bundle] Step 3: Fetching files for panel {plan.panel_index_str}")
        
        # 创建目录结构
        panel_dir = os.path.join(staging_dir, "panels", plan.panel_index_str)
        layerpack_dir = os.path.join(panel_dir, "layerpack")
        typeset_dir = os.path.join(panel_dir, "typeset")
        
        os.makedirs(layerpack_dir, exist_ok=True)
        os.makedirs(typeset_dir, exist_ok=True)
        
        # 下载 LayerPack 文件
        for file_ref in plan.layerpack_files:
            local_path = os.path.join(staging_dir, file_ref.dest_relpath)
            
            try:
                await self.object_store.download_to_file(
                    file_ref.storage_key,
                    local_path
                )
                logger.debug(f"Downloaded: {file_ref.storage_key} -> {local_path}")
            except Exception as e:
                if file_ref.required:
                    raise MissingArtifactError(
                        plan.panel_index_str,
                        os.path.basename(local_path),
                        file_ref.storage_key
                    )
                else:
                    logger.warning(f"Optional file not found: {file_ref.storage_key}")
        
        # 下载 Typeset PNG
        if plan.typeset_png_url:
            typeset_path = os.path.join(typeset_dir, "typeset.png")
            try:
                await self.object_store.download_to_file(
                    plan.typeset_png_url,
                    typeset_path
                )
            except Exception as e:
                logger.warning(f"Failed to download typeset: {e}")
    
    # ==================== Step 4: 写入面板目录 ====================
    
    def write_panel_folder(
        self,
        staging_dir: str,
        panel_snapshot: PanelSnapshot,
        plan: PanelArtifactPlan,
        layerpack: Optional[LayerPack] = None
    ) -> None:
        """
        Step 4: 写入面板的 JSON 文件
        """
        logger.info(f"[Bundle] Step 4: Writing panel folder for {panel_snapshot.index_str}")
        
        panel_dir = os.path.join(staging_dir, "panels", panel_snapshot.index_str)
        layerpack_dir = os.path.join(panel_dir, "layerpack")
        typeset_dir = os.path.join(panel_dir, "typeset")
        
        os.makedirs(layerpack_dir, exist_ok=True)
        os.makedirs(typeset_dir, exist_ok=True)
        
        # 写入 panel.json
        panel_json = PanelJsonSpec(
            panel_id=panel_snapshot.panel_id,
            index=panel_snapshot.index_str,
            order_index=panel_snapshot.order_index,
            panel_spec=panel_snapshot.panel_spec_json,
            export_selected_layerpack_id=plan.layerpack_id,
            export_selected_typeset_id=plan.typeset_id,
            render_status=panel_snapshot.render_status,
            qa_score=panel_snapshot.qa_score,
            needs_fix=panel_snapshot.needs_fix,
            exported_at=datetime.utcnow().isoformat()
        )
        
        with open(os.path.join(panel_dir, "panel.json"), "w", encoding="utf-8") as f:
            json.dump(panel_json.model_dump(), f, ensure_ascii=False, indent=2)
        
        # 写入 layerpack/manifest.json
        if layerpack:
            manifest = create_layerpack_manifest_from_db(layerpack)
            with open(os.path.join(layerpack_dir, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(manifest.model_dump(), f, ensure_ascii=False, indent=2)
        else:
            # 创建最小 manifest
            minimal_manifest = {
                "spec_version": "1.0.0",
                "layerpack_id": plan.layerpack_id or "unknown",
                "panel_id": panel_snapshot.panel_id,
                "version": 1,
                "files": {
                    "full": {
                        "url": "full.png",
                        "width": 1080,
                        "height": 1920,
                        "format": "png"
                    }
                },
                "geometry": {"width": 1080, "height": 1920},
                "created_at": datetime.utcnow().isoformat()
            }
            with open(os.path.join(layerpack_dir, "manifest.json"), "w", encoding="utf-8") as f:
                json.dump(minimal_manifest, f, ensure_ascii=False, indent=2)
        
        # 写入 typeset/bubbles.json
        if plan.bubbles_json:
            with open(os.path.join(typeset_dir, "bubbles.json"), "w", encoding="utf-8") as f:
                json.dump(plan.bubbles_json, f, ensure_ascii=False, indent=2)
        
        # 写入 qa.json
        if plan.qa_data:
            with open(os.path.join(panel_dir, "qa.json"), "w", encoding="utf-8") as f:
                json.dump(plan.qa_data, f, ensure_ascii=False, indent=2)
    
    # ==================== Step 4.5: 上传预览图 ====================
    
    async def upload_panel_previews(
        self,
        staging_dir: str,
        panel_plans: List[PanelArtifactPlan]
    ) -> None:
        """
        Step 4.5: 上传面板预览图（用于在线预览）
        """
        logger.info(f"[Bundle] Step 4.5: Uploading panel previews")
        
        for plan in panel_plans:
            # 确定本地文件路径（优先 typeset，其次 full）
            local_rel_path = None
            if plan.typeset_png_url:
                local_rel_path = f"panels/{plan.panel_index_str}/typeset/typeset.png"
            elif plan.layerpack_id: 
                local_rel_path = f"panels/{plan.panel_index_str}/layerpack/full.png"
            
            if not local_rel_path:
                continue
                
            local_path = os.path.join(staging_dir, local_rel_path)
            if not os.path.exists(local_path):
                logger.warning(f"Preview file not found at {local_path} for panel {plan.panel_index_str}")
                continue
            
            # 上传 Key: exports/{chapter}/{export}/previews/{index}.png
            preview_key = f"exports/{self.context.chapter_id}/{self.context.export_id}/previews/{plan.panel_index_str}.png"
            
            try:
                # 假设 upload_file 返回可访问 URL（签名或公开）
                url = await self.object_store.upload_file(local_path, preview_key, "image/png")
                plan.uploaded_preview_url = url
            except Exception as e:
                logger.warning(f"Failed to upload preview for panel {plan.panel_index_str}: {e}")

    # ==================== Step 4.6: Phase E — chapter video ====================

    def _collect_chapter_video(
        self, chapter_snapshot: ChapterSnapshot
    ) -> Optional[tuple[BundleChapterVideo, str]]:
        """Phase E: find the D compose job whose episode_number matches this
        chapter's order_index. Returns (manifest_entry, minio_video_url) or
        None. Picks the most recent succeeded compose if multiple exist.
        """
        chapter = self.db.query(Chapter).filter(
            Chapter.id == chapter_snapshot.chapter_id
        ).first()
        if chapter is None or chapter.order_index is None:
            return None

        candidates = (
            self.db.query(Job)
            .filter(
                Job.type == "episode_video_compose",
                Job.project_id == chapter_snapshot.project_id,
                Job.status == "succeeded",
            )
            .all()
        )
        matching = [
            j for j in candidates
            if (j.inputs_json or {}).get("episode_number") == chapter.order_index
        ]
        if not matching:
            return None

        latest = max(matching, key=lambda j: j.finished_at or datetime.min)
        outputs = latest.outputs_json or {}
        video_url = outputs.get("video_url")
        if not video_url:
            return None

        info = BundleChapterVideo(
            path="chapter_video/compose.mp4",
            source_compose_job_id=latest.id,
            duration_sec=outputs.get("duration_sec"),
            clip_count=outputs.get("clip_count"),
            size_bytes=outputs.get("size_bytes"),
        )
        return info, video_url

    async def _fetch_chapter_video(
        self, staging_dir: str, video_url: str
    ) -> None:
        """Phase E: download the chapter compose MP4 into the staging directory.

        Caller is responsible for handling exceptions — the silent-skip policy
        lives at the build() call site, not here, so this helper stays simple
        and testable.
        """
        target_dir = os.path.join(staging_dir, "chapter_video")
        os.makedirs(target_dir, exist_ok=True)
        target_path = os.path.join(target_dir, "compose.mp4")
        await self.object_store.download_to_file(video_url, target_path)
        logger.info(f"[Bundle] Downloaded chapter video to {target_path}")

    # ==================== Step 5: 写入根目录文件 ====================

    def write_bundle_root_files(
        self,
        staging_dir: str,
        chapter_snapshot: ChapterSnapshot,
        panel_plans: List[PanelArtifactPlan],
        assets_lock: Optional[AssetsLockSpec] = None,
        provenance_jobs: Optional[ProvenanceJobsSpec] = None,
        chapter_video: Optional[BundleChapterVideo] = None,
    ) -> BundleManifest:
        """
        Step 5: 写入 Bundle 根目录文件
        """
        logger.info(f"[Bundle] Step 5: Writing bundle root files")
        
        now = datetime.utcnow()
        bundle_id = f"bundle-{self.context.export_id[:12]}"
        
        # 准备面板条目
        panel_entries = []
        needs_fix_panels = []
        qa_scores = []
        
        for plan in panel_plans:
            snapshot = next(
                (p for p in chapter_snapshot.panels if p.panel_id == plan.panel_id),
                None
            )
            
            # 确定预览图路径
            if plan.typeset_png_url:
                preview_image = f"panels/{plan.panel_index_str}/typeset/typeset.png"
            else:
                preview_image = f"panels/{plan.panel_index_str}/layerpack/full.png"
            
            entry = BundlePanelEntry(
                index=plan.panel_index_str,
                panel_id=plan.panel_id,
                path=f"panels/{plan.panel_index_str}",
                layerpack_path=f"panels/{plan.panel_index_str}/layerpack",
                typeset_path=f"panels/{plan.panel_index_str}/typeset" if plan.typeset_png_url else None,
                preview_image=preview_image,
                duration_sec=snapshot.duration_sec if snapshot else None,
                qa_score=snapshot.qa_score if snapshot else None,
                needs_fix=snapshot.needs_fix if snapshot else False,
                selected_layerpack_id=plan.layerpack_id,
                selected_typeset_id=plan.typeset_id,
                online_preview_url=plan.uploaded_preview_url
            )
            panel_entries.append(entry)
            
            if snapshot and snapshot.needs_fix:
                needs_fix_panels.append(plan.panel_index_str)
            if snapshot and snapshot.qa_score is not None:
                qa_scores.append(snapshot.qa_score)
        
        # 计算 QA 汇总
        qa_summary = None
        if qa_scores:
            qa_summary = BundleQASummary(
                total_panels=len(panel_entries),
                passed_panels=len([s for s in qa_scores if s >= 0.6]),
                failed_panels=len([s for s in qa_scores if s < 0.6]),
                needs_fix_count=len(needs_fix_panels),
                min_score=min(qa_scores) if qa_scores else None,
                max_score=max(qa_scores) if qa_scores else None,
                avg_score=sum(qa_scores) / len(qa_scores) if qa_scores else None,
                needs_fix_panels=needs_fix_panels
            )
        
        # 构建 manifest
        manifest = BundleManifest(
            spec_version=self.SPEC_VERSION,
            bundle_id=bundle_id,
            chapter=BundleChapterInfo(
                chapter_id=chapter_snapshot.chapter_id,
                chapter_title=chapter_snapshot.title,
                chapter_version=chapter_snapshot.version,
                project_id=chapter_snapshot.project_id,
                panel_count=chapter_snapshot.panel_count,
                total_duration_sec=chapter_snapshot.total_duration_sec
            ),
            panels=panel_entries,
            qa_summary=qa_summary,
            provenance=BundleProvenance(
                generated_at=now.isoformat(),
                export_job_id=self.context.job_id,
                bundle_spec_version=self.SPEC_VERSION
            ),
            chapter_video=chapter_video,
        )
        
        # 写入 manifest.json
        with open(os.path.join(staging_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest.model_dump(), f, ensure_ascii=False, indent=2)
        
        # 写入 chapter.json
        chapter_json = ChapterJsonSpec(
            chapter_id=chapter_snapshot.chapter_id,
            title=chapter_snapshot.title,
            version=chapter_snapshot.version,
            project_id=chapter_snapshot.project_id,
            panel_count=chapter_snapshot.panel_count,
            total_duration_sec=chapter_snapshot.total_duration_sec,
            style_profile_snapshot=chapter_snapshot.style_profile_snapshot,
            exported_at=now.isoformat()
        )
        with open(os.path.join(staging_dir, "chapter.json"), "w", encoding="utf-8") as f:
            json.dump(chapter_json.model_dump(), f, ensure_ascii=False, indent=2)
        
        # 写入 assets.json
        if assets_lock:
            with open(os.path.join(staging_dir, "assets.json"), "w", encoding="utf-8") as f:
                json.dump(assets_lock.model_dump(), f, ensure_ascii=False, indent=2)
        else:
            # 空的 assets.json
            empty_assets = AssetsLockSpec(
                spec_version="1.0.0",
                chapter_id=chapter_snapshot.chapter_id,
                exported_at=now.isoformat()
            )
            with open(os.path.join(staging_dir, "assets.json"), "w", encoding="utf-8") as f:
                json.dump(empty_assets.model_dump(), f, ensure_ascii=False, indent=2)
        
        # 写入 provenance/jobs.json
        provenance_dir = os.path.join(staging_dir, "provenance")
        os.makedirs(provenance_dir, exist_ok=True)
        
        if provenance_jobs:
            with open(os.path.join(provenance_dir, "jobs.json"), "w", encoding="utf-8") as f:
                json.dump(provenance_jobs.model_dump(), f, ensure_ascii=False, indent=2)
        else:
            # 空的 jobs.json
            empty_jobs = ProvenanceJobsSpec(
                spec_version="1.0.0",
                chapter_id=chapter_snapshot.chapter_id,
                exported_at=now.isoformat()
            )
            with open(os.path.join(provenance_dir, "jobs.json"), "w", encoding="utf-8") as f:
                json.dump(empty_jobs.model_dump(), f, ensure_ascii=False, indent=2)
        
        # 写入 README.txt
        readme = f"""AI Webtoon Studio - Chapter Bundle
=====================================
Bundle ID: {bundle_id}
Chapter: {chapter_snapshot.title}
Panels: {chapter_snapshot.panel_count}
Generated: {now.isoformat()}
Spec Version: {self.SPEC_VERSION}

Files:
- manifest.json: Bundle manifest (start here)
- chapter.json: Chapter metadata
- assets.json: Asset version lock
- provenance/jobs.json: Job run history
- panels/*/: Panel data
  - panel.json: Panel spec snapshot
  - layerpack/: Generated images
  - typeset/: Text overlay

For more info, see manifest.json
"""
        with open(os.path.join(staging_dir, "README.txt"), "w", encoding="utf-8") as f:
            f.write(readme)
        
        return manifest
    
    # ==================== Step 6: 打包并上传 ====================
    
    async def zip_and_upload(
        self, 
        staging_dir: str
    ) -> tuple[str, str, int]:
        """
        Step 6: 创建 zip 并上传
        
        Returns:
            (bundle_url, manifest_url, size_bytes)
        """
        logger.info(f"[Bundle] Step 6: Zipping and uploading")
        
        # 创建 zip 文件名
        zip_name = f"chapter_{self.context.chapter_id}_export_{self.context.export_id}.zip"
        zip_path = os.path.join(os.path.dirname(staging_dir), zip_name)
        
        # 创建 zip（流式写入）
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(staging_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, staging_dir)
                    zf.write(file_path, arcname)
        
        # 获取文件大小
        size_bytes = os.path.getsize(zip_path)
        
        # 上传 zip
        target_key = f"exports/{self.context.chapter_id}/{self.context.export_id}/{zip_name}"
        bundle_url = await self.object_store.upload_file(zip_path, target_key, "application/zip")
        
        # 单独上传 manifest.json（方便预览）
        manifest_path = os.path.join(staging_dir, "manifest.json")
        manifest_key = f"exports/{self.context.chapter_id}/{self.context.export_id}/manifest.json"
        manifest_url = await self.object_store.upload_file(manifest_path, manifest_key, "application/json")
        
        # 清理 zip 文件
        os.remove(zip_path)
        
        return bundle_url, manifest_url, size_bytes
    
    # ==================== 主流程 ====================
    
    async def build(self) -> BundleBuildResult:
        """
        执行完整的 Bundle 构建流程
        """
        import tempfile
        
        start_time = datetime.utcnow()
        staging_dir = None
        
        try:
            # 创建临时目录
            staging_dir = tempfile.mkdtemp(prefix="bundle_")
            self.context.staging_dir = staging_dir
            
            # Step 1: 收集章节快照
            self.context.report_progress("collecting", 0.05, "Collecting chapter data...")
            chapter_snapshot = self.collect_chapter_snapshot(self.context.chapter_id)
            
            total_panels = len(chapter_snapshot.panels)
            panel_plans = []
            
            # Step 2 & 3: 解析并拉取每个面板
            for i, panel_snapshot in enumerate(chapter_snapshot.panels):
                progress = 0.1 + (i / total_panels) * 0.5
                self.context.report_progress(
                    "fetching", 
                    progress, 
                    f"Processing panel {i+1}/{total_panels}",
                    panel_snapshot.index_str
                )
                
                # Step 2: 解析产物计划
                plan = self.resolve_panel_artifacts(panel_snapshot)
                panel_plans.append(plan)
                
                if not plan.is_valid:
                    raise NoLayerPackError(plan.panel_index_str, plan.panel_id)
                
                # Step 3: 拉取文件
                await self.fetch_files_to_staging(plan, staging_dir)
                
                # Step 4: 写入面板目录
                layerpack = None
                if plan.layerpack_id:
                    layerpack = self.db.query(LayerPack).filter(
                        LayerPack.id == plan.layerpack_id
                    ).first()
                
                self.write_panel_folder(staging_dir, panel_snapshot, plan, layerpack)
            
            # Step 4.5: 上传预览图
            self.context.report_progress("packaging", 0.65, "Uploading previews...")
            await self.upload_panel_previews(staging_dir, panel_plans)

            # Step 4.6 (Phase E): collect assets lock, provenance, chapter video
            self.context.report_progress("packaging", 0.67, "Collecting assets and provenance...")
            assets_lock = AssetLockResolver(self.db).resolve(chapter_snapshot, panel_plans)
            provenance_jobs = ProvenanceCollector(self.db).collect(chapter_snapshot, panel_plans)

            chapter_video_info = None
            chapter_video_result = self._collect_chapter_video(chapter_snapshot)
            if chapter_video_result is not None:
                chapter_video_info, video_url = chapter_video_result
                try:
                    await self._fetch_chapter_video(staging_dir, video_url)
                except Exception as e:
                    logger.warning(
                        f"[Bundle] chapter_video download failed: {e}; bundling without video"
                    )
                    chapter_video_info = None

            # Step 4.7 (Phase E): export gate
            self.context.report_progress("packaging", 0.68, "Running export gate...")
            ExportGate(self.db).validate_or_raise(
                chapter_snapshot, panel_plans, allow_qa_failure=True
            )

            # Step 5: 写入根目录文件
            self.context.report_progress("packaging", 0.7, "Generating bundle files...")
            manifest = self.write_bundle_root_files(
                staging_dir,
                chapter_snapshot,
                panel_plans,
                assets_lock=assets_lock,
                provenance_jobs=provenance_jobs,
                chapter_video=chapter_video_info,
            )
            
            # Step 6: 打包并上传
            self.context.report_progress("uploading", 0.85, "Uploading bundle...")
            bundle_url, manifest_url, size_bytes = await self.zip_and_upload(staging_dir)
            
            # 计算耗时
            duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            self.context.report_progress("done", 1.0, f"Bundle created: {total_panels} panels")
            
            return BundleBuildResult(
                success=True,
                staging_dir=staging_dir,
                bundle_url=bundle_url,
                manifest_url=manifest_url,
                panel_count=total_panels,
                total_bytes=size_bytes,
                duration_ms=duration_ms,
                qa_summary=manifest.qa_summary.model_dump() if manifest.qa_summary else None,
                needs_fix_panels=manifest.qa_summary.needs_fix_panels if manifest.qa_summary else []
            )
            
        except BundleBuildError as e:
            logger.error(f"Bundle build error: {e}")
            return BundleBuildResult(
                success=False,
                error_code=e.code,
                error_message=e.message,
                error_panel_index=e.panel_index
            )
        except Exception as e:
            logger.exception(f"Unexpected error building bundle: {e}")
            return BundleBuildResult(
                success=False,
                error_code="UNEXPECTED_ERROR",
                error_message=str(e)
            )
        finally:
            # 清理临时目录
            if staging_dir and os.path.exists(staging_dir):
                shutil.rmtree(staging_dir, ignore_errors=True)


def get_bundle_builder(db: Session, context: BundleBuildContext) -> BundleBuilder:
    """获取 Bundle 构建器实例"""
    return BundleBuilder(db, context)
