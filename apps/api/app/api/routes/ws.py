"""
WebSocket 路由 - 实时任务状态推送和对话
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, Set, Optional
import asyncio
import json
import logging

# B-1 Phase E Batch 2: AgentOrchestrator + IntentRouter and the legacy /chat WS
# handler have been removed. Chat streaming now lives at /v1/agent/chat (SSE).
# This file retains the /jobs WS endpoint and push_* helpers used by workers.
from app.core.config import settings
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

router = APIRouter()

# 连接管理器
class ConnectionManager:
    """WebSocket 连接管理器"""
    
    def __init__(self):
        # 按章节 ID 分组的活跃连接
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # 全局连接（订阅所有更新）
        self.global_connections: Set[WebSocket] = set()
        self._redis_pubsub_task = None
        self._redis_pool = None
        
    async def _start_redis_listener(self):
        if self._redis_pubsub_task is not None:
            return
            
        try:
            self._redis_pool = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            pubsub = self._redis_pool.pubsub()
            await pubsub.subscribe("ws_events")
            
            async def listen():
                try:
                    async for message in pubsub.listen():
                        if message["type"] == "message":
                            try:
                                data = json.loads(message["data"])
                                chapter_id = data.get("chapter_id")
                                msg = data.get("message")
                                if chapter_id and msg:
                                    await self._send_to_chapter_local(chapter_id, msg)
                            except Exception as e:
                                logger.error(f"Redis ws_events parse error: {e}")
                except Exception as e:
                    logger.error(f"Redis ws_events listener crashed: {e}")
            
            self._redis_pubsub_task = asyncio.create_task(listen())
            logger.info("Started Redis PubSub listener for WebSockets")
        except Exception as e:
            logger.error(f"Failed to start Redis PubSub: {e}")
    
    async def connect(self, websocket: WebSocket, chapter_id: Optional[str] = None):
        """建立连接"""
        await websocket.accept()
        await self._start_redis_listener()
        
        if chapter_id:
            if chapter_id not in self.active_connections:
                self.active_connections[chapter_id] = set()
            self.active_connections[chapter_id].add(websocket)
            logger.info(f"WebSocket connected for chapter {chapter_id}")
        else:
            self.global_connections.add(websocket)
            logger.info("WebSocket connected (global)")
    
    def disconnect(self, websocket: WebSocket, chapter_id: Optional[str] = None):
        """断开连接"""
        if chapter_id and chapter_id in self.active_connections:
            self.active_connections[chapter_id].discard(websocket)
            if not self.active_connections[chapter_id]:
                del self.active_connections[chapter_id]
        
        self.global_connections.discard(websocket)
        logger.info(f"WebSocket disconnected")
    
    async def _send_to_chapter_local(self, chapter_id: str, message: dict):
        """仅向当前进程内的 WebSocket 客户端真正发送数据"""
        connections = self.active_connections.get(chapter_id, set())
        
        # 同时发送给全局连接
        all_connections = connections | self.global_connections
        
        if not all_connections:
            return
        
        message_json = json.dumps(message)
        disconnected = []
        
        for connection in all_connections:
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.warning(f"Failed to send message: {e}")
                disconnected.append((connection, chapter_id if connection in connections else None))
        
        # 清理断开的连接
        for conn, cid in disconnected:
            self.disconnect(conn, cid)
    
    async def broadcast(self, message: dict):
        """广播消息给所有连接"""
        message_json = json.dumps(message)
        
        all_connections = self.global_connections.copy()
        for connections in self.active_connections.values():
            all_connections.update(connections)
        
        disconnected = []
        for connection in all_connections:
            try:
                await connection.send_text(message_json)
            except Exception:
                disconnected.append(connection)
        
        # 清理断开的连接
        for conn in disconnected:
            self.global_connections.discard(conn)
            for connections in self.active_connections.values():
                connections.discard(conn)


# 全局连接管理器实例
manager = ConnectionManager()


@router.websocket("/jobs")
async def websocket_jobs(
    websocket: WebSocket,
    chapter_id: Optional[str] = Query(default=None)
):
    """
    任务状态 WebSocket 端点
    
    连接示例: ws://localhost:8000/api/v1/ws/jobs?chapter_id=xxx
    
    接收的事件格式:
    {
        "event": "job_status_update",
        "job_id": "xxx",
        "panel_id": "xxx",
        "status": "processing",
        "progress": 50,
        "current_step": "generating_layers",
        "result_urls": null
    }
    """
    await manager.connect(websocket, chapter_id)
    
    try:
        while True:
            # 保持连接并等待客户端消息（心跳等）
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                
                # 处理心跳
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                
                # 处理订阅请求
                elif message.get("type") == "subscribe":
                    new_chapter_id = message.get("chapter_id")
                    if new_chapter_id and new_chapter_id != chapter_id:
                        # 取消旧订阅
                        if chapter_id:
                            manager.active_connections.get(chapter_id, set()).discard(websocket)
                        
                        # 添加新订阅
                        if new_chapter_id not in manager.active_connections:
                            manager.active_connections[new_chapter_id] = set()
                        manager.active_connections[new_chapter_id].add(websocket)
                        
                        await websocket.send_text(json.dumps({
                            "type": "subscribed",
                            "chapter_id": new_chapter_id
                        }))
                
            except json.JSONDecodeError:
                pass
                
    except WebSocketDisconnect:
        manager.disconnect(websocket, chapter_id)


# ===== 辅助函数：用于其他模块推送消息 =====

async def push_job_update(
    chapter_id: str,
    job_id: str,
    panel_id: Optional[str],
    status: str,
    progress: float = 0,
    current_step: Optional[str] = None,
    result_urls: Optional[dict] = None,
    error: Optional[str] = None
):
    """推送任务状态更新"""
    message = {
        "event": "job_status_update",
        "job_id": job_id,
        "panel_id": panel_id,
        "status": status,
        "progress": progress,
        "current_step": current_step,
        "result_urls": result_urls,
        "error": error
    }
    # Uses Redid PubSub bridge below
    await push_chapter_update(chapter_id, "job_status_update", message)


async def push_panel_update(
    chapter_id: str,
    panel_id: str,
    render_status: str,
    preview_url: Optional[str] = None,
    qa_score: float = 0.0
):
    """推送分镜状态更新"""
    message = {
        "event": "panel_update",
        "panel_id": panel_id,
        "render_status": render_status,
        "preview_url": preview_url,
        "qa_score": qa_score
    }
    await push_chapter_update(chapter_id, "panel_update", message)


async def push_chapter_update(
    chapter_id: str,
    event_type: str,
    data: dict
):
    """推送章节级别更新 (发布到 Redis)"""
    message = {
        "event": event_type,
        "chapter_id": chapter_id,
        **data
    }
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_client.publish("ws_events", json.dumps({
            "chapter_id": chapter_id,
            "message": message
        }))
        await redis_client.aclose()
    except Exception as e:
        logger.error(f"Failed to publish to redis: {e}")


async def push_unified_job_event(
    chapter_id: str,
    event_type: str,
    job_id: str,
    payload: dict,
):
    """Push a unified job event. event_type is one of: job_progress, job_status, job_result."""
    await push_chapter_update(chapter_id, event_type, {
        "jobId": job_id,
        **payload,
    })


async def broadcast_to_chapter(chapter_id: str, event: dict):
    """
    推送事件到章节 (P0-CH Worker 使用)

    event 格式:
    {
        "type": "asset_autobuild_progress",
        "job_id": "...",
        "scope": "characters",
        "stage": "generate_candidates",
        "progress": 50,
        "character_id": "...",
        ...
    }
    """
    try:
        redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await redis_client.publish("ws_events", json.dumps({
            "chapter_id": chapter_id,
            "message": event
        }))
        await redis_client.aclose()
    except Exception as e:
        logger.error(f"Failed to publish to redis: {e}")


