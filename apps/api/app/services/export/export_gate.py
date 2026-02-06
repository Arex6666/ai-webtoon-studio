"""
Export Gate - 导出门禁

负责在打包前进行质量检查，决定是否允许导出
"""
import logging
from typing import List, Dict, Optional
from sqlalchemy.orm import Session

from app.models import Panel, LayerPack
from app.services.export.bundle_models import (
    ChapterSnapshot, PanelArtifactPlan, GateCheckResult
)
from app.services.export.bundle_errors import GateRejectedError

logger = logging.getLogger(__name__)


class ExportGate:
    """导出门禁"""
    
    def __init__(self, db: Session):
        self.db = db
        
    def check(
        self, 
        chapter_snapshot: ChapterSnapshot, 
        panel_plans: List[PanelArtifactPlan],
        allow_qa_failure: bool = True
    ) -> GateCheckResult:
        """
        执行门禁检查
        """
        logger.info(f"Running export gate for chapter {chapter_snapshot.chapter_id}")
        
        result = GateCheckResult(passed=True)
        
        for plan in panel_plans:
            # 1. 检查必须文件 (Required Artifacts)
            has_full_image = False
            
            # 检查 LayerPack
            if plan.layerpack_id:
                has_full_path = any(
                    f for f in plan.layerpack_files 
                    if f.dest_relpath.endswith("full.png")
                )
                if has_full_path:
                    has_full_image = True
            
            # 检查 Preview (Fallback)
            if plan.preview_image_url:
                has_full_image = True
                
            if not has_full_image:
                result.missing_required.append(plan.panel_index_str)
                result.passed = False
                
            # 2. 检查 Typeset (Warning)
            if not plan.typeset_png_url:
                result.missing_typeset.append(plan.panel_index_str)
            
            # 3. 检查 Manifest 完整性
            if plan.layerpack_id and not plan.layerpack_manifest_url:
                # 只是警告，因为我们会自动生成最小 manifest
                pass
                
            # 4. 检查 QA 分数 (Warning)
            if plan.qa_data and plan.qa_data.get("score") is not None:
                score = plan.qa_data.get("score")
                if score < 0.6:  # 阈值可配置
                    result.low_qa_panels.append(plan.panel_index_str)
                    
        # 决定是否拒绝
        if result.error_count > 0:
            result.passed = False
            
        # 若不允许 QA 失败且有低分
        if not allow_qa_failure and result.low_qa_panels:
            result.passed = False
            logger.warning(f"Gate rejected due to low QA panels: {result.low_qa_panels}")
            
        logger.info(f"Gate check result: passed={result.passed}, errors={result.error_count}, warnings={result.warning_count}")
        return result
        
    def validate_or_raise(self, *args, **kwargs):
        """执行检查，若失败则抛出异常"""
        result = self.check(*args, **kwargs)
        if not result.passed:
            reason = f"Export gate rejected with {result.error_count} errors"
            if result.missing_required:
                reason += f" (Missing required files: {result.missing_required})"
            
            raise GateRejectedError(reason=reason, gate_result=result.to_dict())
        return result
