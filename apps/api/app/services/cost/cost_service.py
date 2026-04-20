"""
CostService - 成本计算服务 (E4: Real Cost Metering)
"""
import logging
import time
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)

# In-memory cache for cost configs
_config_cache: Dict[str, Any] = {}
_cache_ttl = 300  # 5 minutes
_cache_time = 0.0

# Default cost rates (used when no DB config exists)
DEFAULT_COSTS = {
    "doubao": {
        "cost_per_image": 0.04,
        "cost_per_video_second": 0.30,
        "cost_per_1k_input_tokens": 0.001,
        "cost_per_1k_output_tokens": 0.002,
        "tier_multipliers": {"fast": 0.2, "normal": 1.0, "hero": 2.5},
    },
    "tongyi": {
        "cost_per_image": 0.08,
        "cost_per_video_second": 0.25,
        "cost_per_1k_input_tokens": 0.002,
        "cost_per_1k_output_tokens": 0.004,
        "tier_multipliers": {"fast": 0.2, "normal": 1.0, "hero": 2.5},
    },
    "comfyui": {
        "cost_per_image": 0.02,
        "cost_per_video_second": 0.15,
        "cost_per_1k_input_tokens": 0.0,
        "cost_per_1k_output_tokens": 0.0,
        "tier_multipliers": {"fast": 0.2, "normal": 1.0, "hero": 2.5},
    },
    "mock": {
        "cost_per_image": 0.0,
        "cost_per_video_second": 0.0,
        "cost_per_1k_input_tokens": 0.0,
        "cost_per_1k_output_tokens": 0.0,
        "tier_multipliers": {"fast": 0.2, "normal": 1.0, "hero": 2.5},
    },
}


class CostService:
    """Cost estimation and recording service."""

    def __init__(self, db: Session):
        self.db = db

    def _get_config(self, provider: str) -> Dict[str, Any]:
        """Get cost config for a provider (cached)."""
        global _config_cache, _cache_time

        now = time.time()
        if now - _cache_time > _cache_ttl or not _config_cache:
            self._refresh_cache()
            _cache_time = now

        return _config_cache.get(provider, DEFAULT_COSTS.get(provider, DEFAULT_COSTS["mock"]))

    def _refresh_cache(self):
        """Refresh the in-memory config cache from DB."""
        global _config_cache
        try:
            from app.models.cost_config import ProviderCostConfig
            configs = self.db.query(ProviderCostConfig).filter(
                ProviderCostConfig.active == True
            ).all()

            _config_cache = {}
            for c in configs:
                _config_cache[c.provider] = {
                    "cost_per_image": c.cost_per_image or 0.0,
                    "cost_per_video_second": c.cost_per_video_second or 0.0,
                    "cost_per_1k_input_tokens": c.cost_per_1k_input_tokens or 0.0,
                    "cost_per_1k_output_tokens": c.cost_per_1k_output_tokens or 0.0,
                    "tier_multipliers": c.tier_multipliers or {"fast": 0.2, "normal": 1.0, "hero": 2.5},
                }

            # Merge defaults for providers not in DB
            for provider, defaults in DEFAULT_COSTS.items():
                if provider not in _config_cache:
                    _config_cache[provider] = defaults

        except Exception as e:
            logger.warning(f"Failed to refresh cost config cache: {e}")
            _config_cache = dict(DEFAULT_COSTS)

    def estimate_job_cost(
        self,
        provider: str,
        job_type: str,
        tier: str = "normal",
        duration_sec: float = 0.0,
    ) -> float:
        """Estimate cost for a job before execution."""
        config = self._get_config(provider)
        multipliers = config.get("tier_multipliers", {})
        tier_mult = multipliers.get(tier, 1.0)

        if job_type in ("image_job", "render"):
            return config["cost_per_image"] * tier_mult
        elif job_type in ("video_job", "video"):
            return config["cost_per_video_second"] * max(duration_sec, 3.0)
        else:
            return 0.0

    def record_actual_cost(
        self,
        job_id: str,
        provider: str,
        job_type: str,
        tier: str = "normal",
        usage: Optional[Dict[str, Any]] = None,
    ) -> float:
        """Record actual cost after job completion. Returns computed cost."""
        from app.models.job import Job

        config = self._get_config(provider)
        multipliers = config.get("tier_multipliers", {})
        tier_mult = multipliers.get(tier, 1.0)

        cost = 0.0
        if job_type in ("image_job", "render"):
            cost = config["cost_per_image"] * tier_mult
        elif job_type in ("video_job", "video"):
            duration = (usage or {}).get("duration_sec", 3.0)
            cost = config["cost_per_video_second"] * duration

        # Update job record
        job = self.db.query(Job).filter(Job.id == job_id).first()
        if job:
            job.cost_used = cost
            self.db.commit()

        return cost

    def get_chapter_cost_summary(self, chapter_id: str) -> Dict[str, Any]:
        """Get cost summary for a chapter from real job data."""
        from app.models.job import Job

        jobs = self.db.query(Job).filter(Job.chapter_id == chapter_id).all()

        total_cost = sum(j.cost_used or 0.0 for j in jobs)
        total_estimated = sum(j.cost_estimated or 0.0 for j in jobs)
        by_provider: Dict[str, float] = {}
        by_type: Dict[str, float] = {}
        succeeded = sum(1 for j in jobs if j.status == "succeeded")
        failed = sum(1 for j in jobs if j.status == "failed")
        needs_fix = sum(1 for j in jobs if j.status == "needs_fix")

        for j in jobs:
            p = j.provider or "unknown"
            by_provider[p] = by_provider.get(p, 0.0) + (j.cost_used or 0.0)
            t = j.type or "unknown"
            by_type[t] = by_type.get(t, 0.0) + (j.cost_used or 0.0)

        return {
            "chapter_id": chapter_id,
            "total_cost": round(total_cost, 4),
            "total_estimated": round(total_estimated, 4),
            "total_jobs": len(jobs),
            "succeeded": succeeded,
            "failed": failed,
            "needs_fix": needs_fix,
            "by_provider": by_provider,
            "by_type": by_type,
        }

    def get_project_cost_summary(self, project_id: str) -> Dict[str, Any]:
        """Get cost summary for an entire project."""
        from app.models.job import Job

        jobs = self.db.query(Job).filter(Job.project_id == project_id).all()

        total_cost = sum(j.cost_used or 0.0 for j in jobs)
        by_chapter: Dict[str, float] = {}
        for j in jobs:
            ch = j.chapter_id or "unknown"
            by_chapter[ch] = by_chapter.get(ch, 0.0) + (j.cost_used or 0.0)

        return {
            "project_id": project_id,
            "total_cost": round(total_cost, 4),
            "total_jobs": len(jobs),
            "by_chapter": by_chapter,
        }


# Singleton helper
_cost_service: Optional[CostService] = None


def get_cost_service(db: Session) -> CostService:
    """Get or create CostService."""
    return CostService(db)
