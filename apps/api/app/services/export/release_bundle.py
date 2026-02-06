"""
Release Bundle 生成器
生成可交付的章节发布包
"""
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class PanelExportInfo:
    """面板导出信息"""
    panel_id: str
    order_index: int
    layerpack_id: Optional[str]
    manifest_url: Optional[str]
    full_url: Optional[str]
    typeset_url: Optional[str]  # 嵌字后图片
    exported_url: str  # 最终使用的图片
    qa_score: float
    status: str


@dataclass
class ExportStats:
    """导出统计"""
    total_panels: int
    rendered_panels: int
    typeset_panels: int
    avg_qa_score: float
    total_cost: float
    export_duration_ms: int


@dataclass
class ReleaseBundle:
    """发布包结构"""
    version: str
    release_id: str
    chapter_id: str
    chapter_title: str
    project_id: str
    
    # 导出结果
    strip_url: str
    strip_format: str
    strip_width: int
    strip_height: int
    
    # 面板信息
    panels: List[PanelExportInfo]
    
    # 统计
    stats: ExportStats
    
    # 时间戳
    created_at: str
    exported_by: str


class ReleaseBundleGenerator:
    """Release Bundle 生成器"""
    
    def __init__(self):
        self.version = "1.0.0"
    
    def generate(
        self,
        release_id: str,
        chapter_id: str,
        chapter_title: str,
        project_id: str,
        strip_url: str,
        strip_width: int,
        strip_height: int,
        panels: List[Dict[str, Any]],
        total_cost: float = 0,
        export_duration_ms: int = 0,
    ) -> Dict[str, Any]:
        """
        生成 release bundle JSON
        
        Args:
            release_id: 发布 ID
            chapter_id: 章节 ID
            chapter_title: 章节标题
            project_id: 项目 ID
            strip_url: 长条漫 URL
            strip_width: 宽度
            strip_height: 高度
            panels: 面板信息列表
            total_cost: 总成本
            export_duration_ms: 导出耗时
        
        Returns:
            release bundle dict
        """
        # 构建面板导出信息
        panel_infos = []
        rendered_count = 0
        typeset_count = 0
        qa_scores = []
        
        for i, p in enumerate(panels):
            info = PanelExportInfo(
                panel_id=p.get("panel_id", ""),
                order_index=i,
                layerpack_id=p.get("layerpack_id"),
                manifest_url=p.get("manifest_url"),
                full_url=p.get("full_url"),
                typeset_url=p.get("typeset_url"),
                exported_url=p.get("exported_url", p.get("full_url", "")),
                qa_score=p.get("qa_score", 0.0),
                status=p.get("status", "unknown"),
            )
            panel_infos.append(info)
            
            if info.full_url:
                rendered_count += 1
            if info.typeset_url:
                typeset_count += 1
            if info.qa_score > 0:
                qa_scores.append(info.qa_score)
        
        # 统计
        stats = ExportStats(
            total_panels=len(panels),
            rendered_panels=rendered_count,
            typeset_panels=typeset_count,
            avg_qa_score=sum(qa_scores) / len(qa_scores) if qa_scores else 0,
            total_cost=total_cost,
            export_duration_ms=export_duration_ms,
        )
        
        # 构建 bundle
        bundle = ReleaseBundle(
            version=self.version,
            release_id=release_id,
            chapter_id=chapter_id,
            chapter_title=chapter_title,
            project_id=project_id,
            strip_url=strip_url,
            strip_format="png",
            strip_width=strip_width,
            strip_height=strip_height,
            panels=[asdict(p) for p in panel_infos],
            stats=asdict(stats),
            created_at=datetime.utcnow().isoformat() + "Z",
            exported_by="ai-webtoon-studio",
        )
        
        return asdict(bundle)
    
    def to_json(self, bundle: Dict[str, Any], pretty: bool = True) -> str:
        """转换为 JSON 字符串"""
        if pretty:
            return json.dumps(bundle, indent=2, ensure_ascii=False)
        return json.dumps(bundle, ensure_ascii=False)


def get_bundle_generator() -> ReleaseBundleGenerator:
    """获取 generator 实例"""
    return ReleaseBundleGenerator()
