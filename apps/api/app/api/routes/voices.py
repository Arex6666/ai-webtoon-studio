"""
Voice Agent 路由 - AI 配音智能体管理
"""
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from pydantic import ConfigDict, BaseModel
from datetime import datetime

from app.core.database import get_db
from app.models.voice_asset import VoiceAgent
from app.models.asset import Asset
from app.services.doubao_audio.tts_provider import (
    get_doubao_tts_provider,
    get_available_voices,
    VoiceInfo,
)

router = APIRouter()


# Request/Response Models
class VoiceAgentCreate(BaseModel):
    """创建配音智能体请求"""
    project_id: str
    character_asset_id: str
    name: str
    voice_id: str
    provider: str = "doubao"
    voice_config: Optional[Dict[str, Any]] = None
    is_default: bool = False


class VoiceAgentUpdate(BaseModel):
    """更新配音智能体请求"""
    name: Optional[str] = None
    voice_id: Optional[str] = None
    voice_config: Optional[Dict[str, Any]] = None
    sample_audio_url: Optional[str] = None
    is_default: Optional[bool] = None
    status: Optional[str] = None


class VoiceAgentResponse(BaseModel):
    """配音智能体响应"""
    id: str
    project_id: str
    character_asset_id: str
    name: str
    voice_id: str
    provider: str
    voice_config: Dict[str, Any]
    sample_audio_url: Optional[str]
    is_default: bool
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes = True)

class VoiceAgentListResponse(BaseModel):
    items: List[VoiceAgentResponse]
    total: int


class VoicePreviewRequest(BaseModel):
    """配音预览请求"""
    text: str
    voice_id: Optional[str] = None
    speed: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0


class VoicePreviewResponse(BaseModel):
    """配音预览响应"""
    audio_url: Optional[str]
    duration_sec: float
    success: bool
    error: Optional[str] = None


class AvailableVoiceResponse(BaseModel):
    """可用音色响应"""
    voice_id: str
    name: str
    gender: str
    age_group: str
    description: str


# Routes

@router.get("/project/{project_id}", response_model=VoiceAgentListResponse)
async def list_voice_agents(
    project_id: str,
    character_asset_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """获取项目的所有配音智能体"""
    query = db.query(VoiceAgent).filter(
        VoiceAgent.project_id == project_id,
        VoiceAgent.status == "active"
    )

    if character_asset_id:
        query = query.filter(VoiceAgent.character_asset_id == character_asset_id)

    voice_agents = query.order_by(VoiceAgent.created_at.desc()).all()

    items = [
        VoiceAgentResponse(
            id=va.id,
            project_id=va.project_id,
            character_asset_id=va.character_asset_id,
            name=va.name,
            voice_id=va.voice_id,
            provider=va.provider,
            voice_config=va.voice_config or {},
            sample_audio_url=va.sample_audio_url,
            is_default=va.is_default,
            status=va.status,
            created_at=va.created_at,
            updated_at=va.updated_at,
        )
        for va in voice_agents
    ]

    return VoiceAgentListResponse(items=items, total=len(items))


@router.post("", response_model=VoiceAgentResponse)
async def create_voice_agent(
    voice_agent: VoiceAgentCreate,
    db: Session = Depends(get_db)
):
    """创建配音智能体"""
    # 验证角色资产存在且是 character 类型
    character_asset = db.query(Asset).filter(
        Asset.id == voice_agent.character_asset_id,
        Asset.type == "character",
        Asset.status == "active"
    ).first()

    if not character_asset:
        raise HTTPException(
            status_code=404,
            detail="Character asset not found or is not a character type"
        )

    # 如果设为默认，需要取消其他默认
    if voice_agent.is_default:
        db.query(VoiceAgent).filter(
            VoiceAgent.character_asset_id == voice_agent.character_asset_id,
            VoiceAgent.is_default == True
        ).update({"is_default": False})

    # 使用默认名称
    name = voice_agent.name
    if not name:
        name = f"{character_asset.name}的配音"

    db_voice_agent = VoiceAgent(
        project_id=voice_agent.project_id,
        character_asset_id=voice_agent.character_asset_id,
        name=name,
        voice_id=voice_agent.voice_id,
        provider=voice_agent.provider,
        voice_config=voice_agent.voice_config or {
            "speed": 1.0,
            "pitch": 1.0,
            "volume": 1.0,
        },
        is_default=voice_agent.is_default,
        status="active",
    )

    db.add(db_voice_agent)
    db.commit()
    db.refresh(db_voice_agent)

    return VoiceAgentResponse(
        id=db_voice_agent.id,
        project_id=db_voice_agent.project_id,
        character_asset_id=db_voice_agent.character_asset_id,
        name=db_voice_agent.name,
        voice_id=db_voice_agent.voice_id,
        provider=db_voice_agent.provider,
        voice_config=db_voice_agent.voice_config or {},
        sample_audio_url=db_voice_agent.sample_audio_url,
        is_default=db_voice_agent.is_default,
        status=db_voice_agent.status,
        created_at=db_voice_agent.created_at,
        updated_at=db_voice_agent.updated_at,
    )


@router.get("/{voice_agent_id}", response_model=VoiceAgentResponse)
async def get_voice_agent(
    voice_agent_id: str,
    db: Session = Depends(get_db)
):
    """获取配音智能体详情"""
    voice_agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == voice_agent_id
    ).first()

    if not voice_agent:
        raise HTTPException(status_code=404, detail="Voice agent not found")

    return VoiceAgentResponse(
        id=voice_agent.id,
        project_id=voice_agent.project_id,
        character_asset_id=voice_agent.character_asset_id,
        name=voice_agent.name,
        voice_id=voice_agent.voice_id,
        provider=voice_agent.provider,
        voice_config=voice_agent.voice_config or {},
        sample_audio_url=voice_agent.sample_audio_url,
        is_default=voice_agent.is_default,
        status=voice_agent.status,
        created_at=voice_agent.created_at,
        updated_at=voice_agent.updated_at,
    )


@router.put("/{voice_agent_id}", response_model=VoiceAgentResponse)
async def update_voice_agent(
    voice_agent_id: str,
    voice_agent_update: VoiceAgentUpdate,
    db: Session = Depends(get_db)
):
    """更新配音智能体"""
    voice_agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == voice_agent_id
    ).first()

    if not voice_agent:
        raise HTTPException(status_code=404, detail="Voice agent not found")

    # 更新字段
    if voice_agent_update.name is not None:
        voice_agent.name = voice_agent_update.name
    if voice_agent_update.voice_id is not None:
        voice_agent.voice_id = voice_agent_update.voice_id
    if voice_agent_update.voice_config is not None:
        voice_agent.voice_config = voice_agent_update.voice_config
    if voice_agent_update.sample_audio_url is not None:
        voice_agent.sample_audio_url = voice_agent_update.sample_audio_url
    if voice_agent_update.status is not None:
        voice_agent.status = voice_agent_update.status

    # 处理默认设置
    if voice_agent_update.is_default is not None:
        if voice_agent_update.is_default:
            # 取消同角色的其他默认
            db.query(VoiceAgent).filter(
                VoiceAgent.character_asset_id == voice_agent.character_asset_id,
                VoiceAgent.is_default == True,
                VoiceAgent.id != voice_agent_id
            ).update({"is_default": False})
        voice_agent.is_default = voice_agent_update.is_default

    db.commit()
    db.refresh(voice_agent)

    return VoiceAgentResponse(
        id=voice_agent.id,
        project_id=voice_agent.project_id,
        character_asset_id=voice_agent.character_asset_id,
        name=voice_agent.name,
        voice_id=voice_agent.voice_id,
        provider=voice_agent.provider,
        voice_config=voice_agent.voice_config or {},
        sample_audio_url=voice_agent.sample_audio_url,
        is_default=voice_agent.is_default,
        status=voice_agent.status,
        created_at=voice_agent.created_at,
        updated_at=voice_agent.updated_at,
    )


@router.delete("/{voice_agent_id}")
async def delete_voice_agent(
    voice_agent_id: str,
    db: Session = Depends(get_db)
):
    """删除配音智能体"""
    voice_agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == voice_agent_id
    ).first()

    if not voice_agent:
        raise HTTPException(status_code=404, detail="Voice agent not found")

    # 软删除
    voice_agent.status = "archived"
    db.commit()

    return {"message": "Voice agent deleted", "id": voice_agent_id}


@router.post("/{voice_agent_id}/preview", response_model=VoicePreviewResponse)
async def preview_voice(
    voice_agent_id: str,
    preview_request: VoicePreviewRequest,
    db: Session = Depends(get_db)
):
    """预览配音"""
    voice_agent = db.query(VoiceAgent).filter(
        VoiceAgent.id == voice_agent_id
    ).first()

    if not voice_agent:
        raise HTTPException(status_code=404, detail="Voice agent not found")

    # 使用请求中的参数或默认参数
    voice_id = preview_request.voice_id or voice_agent.voice_id
    voice_config = voice_agent.voice_config or {}

    tts_provider = get_doubao_tts_provider()
    result = await tts_provider.generate_speech(
        text=preview_request.text,
        voice_id=voice_id,
        speed=preview_request.speed,
        pitch=preview_request.pitch,
        volume=preview_request.volume,
    )

    if result.success:
        return VoicePreviewResponse(
            audio_url=result.audio_url,
            duration_sec=result.duration_sec,
            success=True,
        )
    else:
        return VoicePreviewResponse(
            audio_url=None,
            duration_sec=0.0,
            success=False,
            error=result.error,
        )


@router.get("/available-voices", response_model=List[AvailableVoiceResponse])
async def list_available_voices():
    """获取可用音色列表"""
    voices = get_available_voices()
    return [
        AvailableVoiceResponse(
            voice_id=v.voice_id,
            name=v.name,
            gender=v.gender,
            age_group=v.age_group,
            description=v.description,
        )
        for v in voices
    ]
