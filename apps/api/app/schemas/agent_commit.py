"""Agent → Studio commit schemas."""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AgentArtStyle(BaseModel):
    base_style: str = ""
    color_tone: str = ""
    atmosphere: str = ""


class AgentCharacter(BaseModel):
    name: str
    visual_prompt: Optional[str] = None
    temp_image_url: Optional[str] = None
    appearance_traits: List[str] = Field(default_factory=list)
    personality_traits: List[str] = Field(default_factory=list)
    wardrobe_notes: Optional[str] = None


class AgentScene(BaseModel):
    name: str
    visual_prompt: Optional[str] = None
    temp_image_url: Optional[str] = None
    time_of_day: Optional[str] = None
    weather: Optional[str] = None
    mood: Optional[str] = None


class AgentPanel(BaseModel):
    id: str
    order: int = 0
    scene_name: Optional[str] = None
    characters: List[str] = Field(default_factory=list)
    scene_description: str = ""
    dialogue: Optional[str] = None
    shot_type: str = "MS"
    camera_angle: str = "eye-level"
    emotion: Optional[str] = None
    composition: Optional[str] = None
    temp_image_url: Optional[str] = None


class CommitToStudioRequest(BaseModel):
    """Full payload if frontend has the data; or lean if only conversation+episode given.

    If `panels` is empty, backend will try to reconstruct from the conversation.
    """
    conversation_id: str
    episode_number: int = Field(..., ge=1)
    episode_title: str = ""
    outline_summary: str = ""
    art_style: AgentArtStyle = Field(default_factory=AgentArtStyle)
    characters: List[AgentCharacter] = Field(default_factory=list)
    scenes: List[AgentScene] = Field(default_factory=list)
    panels: List[AgentPanel] = Field(default_factory=list)


class CommitCreatedCounts(BaseModel):
    characters: int = 0
    scenes: int = 0


class CommitToStudioResponse(BaseModel):
    chapter_id: str
    chapter_title: str
    status: str  # "created" | "already_exists"
    created_assets: CommitCreatedCounts
    created_panels: int
    studio_url: str
    warnings: List[str] = Field(default_factory=list)
    payload_source: str = "request"  # "request" | "conversation"
