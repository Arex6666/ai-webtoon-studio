"""
统计分析路由 - Analytics API
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
import random
import logging

from app.db.database import get_db

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Schemas ============

class ProviderStats(BaseModel):
    provider: str
    cost_used: float
    avg_score: float
    success_rate: float
    retry_rate: float
    job_count: int


class CharacterStats(BaseModel):
    asset_id: str
    asset_name: str
    cost_used: float
    avg_score: float
    success_rate: float
    usage_count: int


class ChapterSummary(BaseModel):
    total_cost: float
    avg_score: float
    total_clips: int
    succeeded: int
    needs_fix: int
    failed: int
    total_retries: int


class AnalyticsResponse(BaseModel):
    chapter_id: str
    by_provider: List[ProviderStats]
    by_character: List[CharacterStats]
    chapter_summary: ChapterSummary
    computed_at: str


# ============ In-memory Analytics Store (for mock) ============

_analytics_store: Dict[str, Dict[str, Any]] = {}


def generate_mock_analytics(chapter_id: str) -> Dict[str, Any]:
    """生成 Mock 分析数据"""
    return {
        "by_provider": [
            {"provider": "kling", "cost_used": 25, "avg_score": 0.82, "success_rate": 0.85, "retry_rate": 0.15, "job_count": 10},
            {"provider": "tongyi", "cost_used": 16, "avg_score": 0.78, "success_rate": 0.75, "retry_rate": 0.25, "job_count": 5},
            {"provider": "mock", "cost_used": 3, "avg_score": 0.70, "success_rate": 0.90, "retry_rate": 0.10, "job_count": 3},
        ],
        "by_character": [
            {"asset_id": "identity-zhouyu", "asset_name": "周屿", "cost_used": 20, "avg_score": 0.85, "success_rate": 0.90, "usage_count": 8},
            {"asset_id": "identity-linzhixia", "asset_name": "林知夏", "cost_used": 15, "avg_score": 0.80, "success_rate": 0.80, "usage_count": 6},
        ],
        "chapter_summary": {
            "total_cost": 44 + random.randint(0, 10),
            "avg_score": 0.79 + random.uniform(-0.05, 0.05),
            "total_clips": 18,
            "succeeded": 14,
            "needs_fix": 2,
            "failed": 2,
            "total_retries": 5,
        },
        "computed_at": datetime.utcnow().isoformat(),
    }


@router.get("/{chapter_id}/analytics", response_model=AnalyticsResponse)
async def get_analytics(chapter_id: str, db: Session = Depends(get_db)):
    """获取章节统计分析"""
    if chapter_id not in _analytics_store:
        # 生成 mock 数据
        _analytics_store[chapter_id] = generate_mock_analytics(chapter_id)
    
    data = _analytics_store[chapter_id]
    return AnalyticsResponse(
        chapter_id=chapter_id,
        by_provider=[ProviderStats(**p) for p in data["by_provider"]],
        by_character=[CharacterStats(**c) for c in data["by_character"]],
        chapter_summary=ChapterSummary(**data["chapter_summary"]),
        computed_at=data["computed_at"]
    )


@router.post("/{chapter_id}/analytics/recompute")
async def recompute_analytics(chapter_id: str, db: Session = Depends(get_db)):
    """重新计算章节统计分析"""
    # 生产环境应从数据库聚合计算
    _analytics_store[chapter_id] = generate_mock_analytics(chapter_id)
    
    logger.info(f"Analytics recomputed for chapter {chapter_id}")
    
    return {
        "message": "Analytics recomputed",
        "chapter_id": chapter_id,
        "computed_at": _analytics_store[chapter_id]["computed_at"]
    }
