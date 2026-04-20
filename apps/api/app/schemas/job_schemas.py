"""Unified Job API request/response schemas."""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    type: Literal["image", "video", "storyboard", "export"]
    target_id: str
    provider: str = "mock"
    params: dict = Field(default_factory=dict)


class JobStatusResponse(BaseModel):
    job_id: str
    type: str
    status: str
    progress: float = 0.0
    message: Optional[str] = None
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True
