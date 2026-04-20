"""Panel binding request/response schemas."""
from typing import Literal, Optional, Dict, Any
from pydantic import BaseModel, Field


class PanelBindingPatch(BaseModel):
    """Request body for PATCH /panels/{panel_id}/bindings."""
    slot: Literal["character", "scene", "prop"] = Field(
        ..., description="Which slot in spec_json to update."
    )
    slot_index: int = Field(
        0,
        ge=0,
        description="Index into characters[]/props[]. Ignored for scene.",
    )
    asset_id: Optional[str] = Field(
        ..., description="Target asset id. null clears the binding."
    )
    asset_version_id: Optional[str] = Field(
        None, description="Optional version pin. Defaults to asset's current version."
    )


class PanelBindingResponse(BaseModel):
    panel_id: str
    spec_json: Dict[str, Any]
    chapter_bindings_updated: bool
