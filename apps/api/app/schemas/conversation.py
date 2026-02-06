"""
Conversation Schemas - 对话相关的 Pydantic 模型
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


# ========== ConversationMessage Schemas ==========

class ConversationMessageBase(BaseModel):
    """消息基础模型"""
    role: str = Field(..., description="消息角色: user, assistant, system, tool")
    content: str = Field(..., description="消息内容")
    content_type: str = Field(default="text", description="内容类型: text, image, asset_preview, panel_preview")


class ConversationMessageCreate(ConversationMessageBase):
    """创建消息"""
    conversation_id: str
    intent: Optional[str] = None
    entities_json: Optional[Dict[str, Any]] = None
    tool_calls_json: Optional[List[Dict[str, Any]]] = None
    tool_results_json: Optional[List[Dict[str, Any]]] = None
    model_used: Optional[str] = None
    tokens_used: int = 0
    latency_ms: Optional[int] = None


class ConversationMessageResponse(ConversationMessageBase):
    """消息响应"""
    id: str
    conversation_id: str
    intent: Optional[str] = None
    entities_json: Optional[Dict[str, Any]] = None
    tool_calls_json: Optional[List[Dict[str, Any]]] = None
    tool_results_json: Optional[List[Dict[str, Any]]] = None
    model_used: Optional[str] = None
    tokens_used: int
    latency_ms: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== ConversationAction Schemas ==========

class ConversationActionBase(BaseModel):
    """动作基础模型"""
    action_type: str = Field(..., description="动作类型: create_asset, generate_storyboard, render_panel, analyze_quality")
    action_params_json: Optional[Dict[str, Any]] = None


class ConversationActionCreate(ConversationActionBase):
    """创建动作"""
    conversation_id: str
    message_id: str
    job_id: Optional[str] = None


class ConversationActionResponse(ConversationActionBase):
    """动作响应"""
    id: str
    conversation_id: str
    message_id: str
    status: str  # pending, running, completed, failed
    job_id: Optional[str] = None
    result_json: Optional[Dict[str, Any]] = None
    error_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ========== Conversation Schemas ==========

class ConversationBase(BaseModel):
    """对话基础模型"""
    title: str = Field(..., description="对话标题")


class ConversationCreate(ConversationBase):
    """创建对话"""
    project_id: str
    chapter_id: Optional[str] = None
    episode_number: Optional[int] = None  # 分集编号


class ConversationUpdate(BaseModel):
    """更新对话"""
    title: Optional[str] = None
    status: Optional[str] = None  # active, paused, completed, archived
    current_intent: Optional[str] = None
    context_json: Optional[Dict[str, Any]] = None


class ConversationResponse(ConversationBase):
    """对话响应"""
    id: str
    project_id: str
    chapter_id: Optional[str] = None
    episode_number: Optional[int] = None  # 分集编号
    status: str
    current_intent: Optional[str] = None
    context_json: Optional[Dict[str, Any]] = None
    message_count: int
    total_tokens_used: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ConversationWithMessages(ConversationResponse):
    """对话及其消息"""
    messages: List[ConversationMessageResponse] = []
    actions: List[ConversationActionResponse] = []


# ========== WebSocket Message Schemas ==========

class WSUserMessage(BaseModel):
    """用户发送的WebSocket消息"""
    type: str = "user_message"
    content: str
    conversation_id: str


class WSAssistantMessage(BaseModel):
    """助手响应的WebSocket消息"""
    type: str = "assistant_message"
    message_id: str
    content: str
    streaming: bool = False
    intent: Optional[str] = None
    entities: Optional[Dict[str, Any]] = None


class WSAssistantMessageChunk(BaseModel):
    """流式响应的消息块"""
    type: str = "assistant_message_chunk"
    message_id: str
    chunk: str
    is_final: bool = False


class WSActionNotification(BaseModel):
    """动作通知"""
    type: str  # action_started, action_progress, action_completed, action_failed
    action_id: str
    action_type: str
    description: Optional[str] = None
    progress: Optional[float] = None  # 0.0 - 1.0
    current_step: Optional[str] = None
    preview_url: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


# ========== Intent Analysis Schemas ==========

class IntentAnalysisResult(BaseModel):
    """意图分析结果"""
    primary_intent: str  # script, asset, render, qa, general
    secondary_intents: List[str] = []
    entities: Dict[str, Any] = {}
    confidence: float = 0.0


# ========== Tool Call Schemas ==========

class ToolCall(BaseModel):
    """工具调用"""
    tool_name: str
    parameters: Dict[str, Any]


class ToolResult(BaseModel):
    """工具执行结果"""
    tool_name: str
    success: bool
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
