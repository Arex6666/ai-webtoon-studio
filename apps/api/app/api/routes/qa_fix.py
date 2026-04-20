"""
QA Fix Workflow Routes (E5: NeedsFix Workflow with Guided Repair)
"""
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from pydantic import BaseModel
from datetime import datetime
import uuid
import logging

from app.db.database import get_db
from app.models.panel import Panel
from app.models.qa_report import QAReport
from app.models.fix_plan import FixPlan
from app.models.job import Job
from app.services.qa.fix_plan_generator import generate_fix_options, get_best_fix, FixOption
from app.api.deps import get_current_user
from app.models.user import User

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Schemas ============

class FixOptionResponse(BaseModel):
    fix_type: str
    description: str
    parameter_changes: Dict[str, Any]
    estimated_cost: float
    success_probability: float
    priority: int


class FixOptionsResponse(BaseModel):
    panel_id: str
    issues: List[Dict[str, Any]]
    options: List[FixOptionResponse]


class ApplyFixRequest(BaseModel):
    fix_type: str
    parameter_overrides: Optional[Dict[str, Any]] = None


class ApplyFixResponse(BaseModel):
    panel_id: str
    fix_plan_id: str
    new_job_id: str
    fix_type: str
    message: str


# ============ Routes ============

@router.post("/panels/{panel_id}/fix-options", response_model=FixOptionsResponse)
async def get_fix_options(panel_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """E5: Get fix options for a panel with QA issues."""
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")

    # Get latest QA report for this panel
    issues = _get_panel_issues(panel_id, db)

    if not issues:
        return FixOptionsResponse(
            panel_id=panel_id,
            issues=[],
            options=[],
        )

    # Get cost info
    cost_per_render = 0.04  # default
    try:
        from app.services.cost.cost_service import CostService
        cost_service = CostService(db)
        cost_per_render = cost_service.estimate_job_cost("doubao", "render", "normal")
    except Exception:
        pass

    options = generate_fix_options(
        issues=issues,
        panel_id=panel_id,
        cost_per_render=cost_per_render,
    )

    return FixOptionsResponse(
        panel_id=panel_id,
        issues=issues,
        options=[FixOptionResponse(**o.model_dump()) for o in options],
    )


@router.post("/panels/{panel_id}/apply-fix", response_model=ApplyFixResponse)
async def apply_fix(
    panel_id: str,
    request: ApplyFixRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """E5: Apply a specific fix to a panel."""
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")

    issues = _get_panel_issues(panel_id, db)
    options = generate_fix_options(issues=issues, panel_id=panel_id)

    # Find the requested fix type
    selected = next((o for o in options if o.fix_type == request.fix_type), None)
    if not selected:
        raise HTTPException(status_code=400, detail=f"Fix type '{request.fix_type}' not available")

    # Merge parameter overrides
    params = dict(selected.parameter_changes)
    if request.parameter_overrides:
        params.update(request.parameter_overrides)

    # Create FixPlan record
    fix_plan = FixPlan(
        id=str(uuid.uuid4()),
        render_job_id=_get_latest_job_id(panel_id, db) or "unknown",
        plan_json={
            "fix_type": selected.fix_type,
            "description": selected.description,
            "parameters": params,
        },
        status="applied",
        panel_id=panel_id,
        fix_type=selected.fix_type,
        estimated_cost=selected.estimated_cost,
        success_probability=selected.success_probability,
        applied_by="user",
        applied_at=datetime.utcnow(),
    )
    db.add(fix_plan)

    # Create new render job with adjusted parameters
    new_job = Job(
        id=str(uuid.uuid4()),
        type="image_job",
        provider="doubao",
        project_id=getattr(panel, 'project_id', None),
        chapter_id=panel.chapter_id,
        panel_id=panel_id,
        inputs_json={"fix_params": params, "fix_type": selected.fix_type, "tier": "normal"},
        status="queued",
        progress=0.0,
        attempt=1,
        max_attempts=3,
        cost_estimated=selected.estimated_cost,
        cost_used=0.0,
    )
    db.add(new_job)
    db.commit()

    # Dispatch to worker
    try:
        from app.workers.image_worker import execute_image_job
        execute_image_job.delay(new_job.id, panel_id)
    except Exception as e:
        logger.warning(f"Failed to dispatch fix job: {e}")

    logger.info(f"Fix applied for panel {panel_id}: {selected.fix_type}, new job {new_job.id}")

    return ApplyFixResponse(
        panel_id=panel_id,
        fix_plan_id=fix_plan.id,
        new_job_id=new_job.id,
        fix_type=selected.fix_type,
        message=f"Fix '{selected.description}' applied. New render job queued.",
    )


@router.post("/panels/{panel_id}/auto-fix", response_model=ApplyFixResponse)
async def auto_fix(panel_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """E5: Auto-apply the best fix for a panel."""
    panel = db.query(Panel).filter(Panel.id == panel_id).first()
    if not panel:
        raise HTTPException(status_code=404, detail="Panel not found")

    issues = _get_panel_issues(panel_id, db)
    if not issues:
        raise HTTPException(status_code=400, detail="No issues found for this panel")

    best = get_best_fix(issues=issues, panel_id=panel_id)
    if not best:
        raise HTTPException(status_code=400, detail="No fix strategy available")

    # Reuse apply_fix logic
    request = ApplyFixRequest(fix_type=best.fix_type)
    return await apply_fix(panel_id, request, db)


# ============ Helpers ============

def _get_panel_issues(panel_id: str, db: Session) -> List[Dict[str, Any]]:
    """Get QA issues for a panel from the latest QA report or job."""
    # Try QA reports linked to jobs for this panel
    jobs = db.query(Job).filter(
        Job.panel_id == panel_id,
        Job.status == "needs_fix",
    ).order_by(Job.created_at.desc()).limit(1).all()

    if jobs:
        qa_json = jobs[0].qa_json or {}
        if isinstance(qa_json, dict) and "issues" in qa_json:
            return qa_json["issues"]

    # Try QA reports via render jobs
    from app.models.render_job import RenderJob
    render_jobs = db.query(RenderJob).filter(
        RenderJob.panel_id == panel_id,
    ).order_by(RenderJob.created_at.desc()).limit(1).all()

    if render_jobs:
        qa_reports = db.query(QAReport).filter(
            QAReport.render_job_id == render_jobs[0].id,
        ).order_by(QAReport.created_at.desc()).limit(1).all()

        if qa_reports:
            report = qa_reports[0]
            issues_json = getattr(report, 'issues_json', None) or []
            if issues_json:
                return issues_json
            # Fallback to checks_json
            checks = report.checks_json or {}
            issues = []
            for code, value in checks.items():
                if isinstance(value, (int, float)) and value < 0.5:
                    issues.append({"code": code.upper(), "level": "error", "message": f"{code} score: {value}"})
            return issues

    return []


def _get_latest_job_id(panel_id: str, db: Session) -> Optional[str]:
    """Get latest render job ID for a panel."""
    from app.models.render_job import RenderJob
    rj = db.query(RenderJob).filter(
        RenderJob.panel_id == panel_id,
    ).order_by(RenderJob.created_at.desc()).first()
    return rj.id if rj else None
