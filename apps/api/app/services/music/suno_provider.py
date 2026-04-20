"""
Suno Music Provider - 通过 ComfyUI 生成音乐
使用 ComfyUI 的 Suno 插件生成背景音乐
"""
import logging
import uuid
import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import httpx

from app.core.config import settings
from app.services.storage import get_object_store

logger = logging.getLogger(__name__)


class MusicGenerationStatus(str, Enum):
    """音乐生成状态"""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class MusicGenerationRequest:
    """音乐生成请求"""
    prompt: str
    style: str = "cinematic"  # cinematic, pop, rock, jazz, electronic, classical, ambient
    duration: int = 30  # seconds: 30, 60, 90, 120
    title: str = ""


@dataclass
class MusicGenerationResult:
    """音乐生成结果"""
    success: bool
    audio_url: Optional[str] = None
    duration_sec: float = 0.0
    job_id: Optional[str] = None
    status: str = "pending"
    error: Optional[str] = None
    title: str = ""


class SunoViaComfyUIProvider:
    """
    Suno 音乐生成 Provider
    通过 ComfyUI 的 Suno 插件节点生成音乐
    """

    provider_name = "suno_via_comfyui"

    def __init__(self, comfyui_url: Optional[str] = None):
        self.comfyui_url = comfyui_url or settings.COMFYUI_URL
        if not self.comfyui_url:
            logger.warning("[SunoProvider] COMFYUI_URL not configured")

    def _build_suno_workflow(
        self,
        prompt: str,
        style: str = "cinematic",
        duration: int = 30,
        title: str = "",
    ) -> Dict[str, Any]:
        """
        构建 Suno 工作流 JSON

        注意：这是一个基础工作流模板，实际使用需要 ComfyUI 安装 Suno 插件
        """
        # Suno 插件节点通常是类似这样的节点 ID（需要根据实际插件调整）
        # 这里使用一个模拟的工作流结构
        workflow = {
            "nodes": [
                {
                    "id": 1,
                    "type": "SunoGenerate",
                    "pos": [100, 100],
                    "size": [300, 200],
                    "flags": {},
                    "order": 0,
                    "mode": 0,
                    "inputs": [],
                    "outputs": [
                        {"name": "AUDIOS", "type": "AUDIO", "slot_index": 0}
                    ],
                    "properties": {},
                    "widgets_values": {
                        "prompt": prompt,
                        "style": style,
                        "duration": duration,
                        "title": title or prompt[:50],
                    },
                },
                {
                    "id": 2,
                    "type": "SaveAudio",
                    "pos": [500, 100],
                    "size": [300, 200],
                    "flags": {},
                    "order": 1,
                    "mode": 0,
                    "inputs": [
                        {"name": "audio", "type": "AUDIO", "slot_index": 0}
                    ],
                    "outputs": [],
                    "properties": {},
                    "widgets_values": {
                        "filename_prefix": f"music_{uuid.uuid4().hex[:8]}",
                    },
                },
            ],
            "links": [
                [1, 1, 0, 2, 0, "AUDIO"],
            ],
            "groups": [],
            "config": {},
            "extra": {
                "ds": {
                    "scale": 1.0,
                    "offset": [0, 0],
                }
            },
            "version": 0.4,
        }

        return workflow

    async def generate_music(
        self,
        prompt: str,
        style: str = "cinematic",
        duration: int = 30,
        title: str = "",
    ) -> MusicGenerationResult:
        """
        生成音乐

        Args:
            prompt: 音乐描述提示词
            style: 音乐风格
            duration: 时长（秒）
            title: 音乐标题

        Returns:
            MusicGenerationResult
        """
        if not self.comfyui_url:
            # 返回模拟结果（开发模式）
            logger.warning("[SunoProvider] Running in mock mode")
            return await self._mock_generate_music(prompt, style, duration, title)

        try:
            import httpx

            workflow = self._build_suno_workflow(prompt, style, duration, title)

            async with httpx.AsyncClient(timeout=300.0) as client:
                # 提交工作流
                response = await client.post(
                    f"{self.comfyui_url}/prompt",
                    json={"prompt": workflow}
                )
                response.raise_for_status()
                data = response.json()
                job_id = data.get("prompt_id")

                if not job_id:
                    return MusicGenerationResult(
                        success=False,
                        error="Failed to get job_id from ComfyUI",
                    )

                # 轮询状态
                return await self._poll_job_status(client, job_id, prompt)

        except Exception as e:
            logger.error(f"[SunoProvider] Music generation failed: {e}")
            return MusicGenerationResult(
                success=False,
                error=str(e),
            )

    async def _poll_job_status(
        self,
        client: httpx.AsyncClient,
        job_id: str,
        prompt: str,
    ) -> MusicGenerationResult:
        """轮询任务状态"""
        max_retries = 120  # 最多等待 10 分钟
        retry_interval = 5  # 5 秒

        for i in range(max_retries):
            await asyncio.sleep(retry_interval)

            try:
                response = await client.get(
                    f"{self.comfyui_url}/history/{job_id}"
                )
                response.raise_for_status()
                data = response.json()

                if job_id in data:
                    job_data = data[job_id]
                    status = job_data.get("status", {})
                    status_str = status.get("status_str", "")

                    if status_str == "success":
                        outputs = job_data.get("outputs", {})

                        # 查找音频文件
                        audio_url = None
                        duration_sec = 0.0

                        for node_id, node_output in outputs.items():
                            if "audio" in node_output:
                                audio_info = node_output["audio"]
                                if "audio_path" in audio_info:
                                    # 从 ComfyUI 获取音频
                                    audio_url = f"{self.comfyui_url}/view?filename={audio_info['audio_path']}"
                                    duration_sec = audio_info.get("duration", 0.0)
                                    break

                        if audio_url:
                            return MusicGenerationResult(
                                success=True,
                                audio_url=audio_url,
                                duration_sec=duration_sec,
                                job_id=job_id,
                                status="completed",
                            )
                        else:
                            return MusicGenerationResult(
                                success=False,
                                error="No audio output found",
                                job_id=job_id,
                                status="failed",
                            )

                    elif status_str == "error":
                        error_msg = status.get("exception_message", "Unknown error")
                        return MusicGenerationResult(
                            success=False,
                            error=error_msg,
                            job_id=job_id,
                            status="failed",
                        )

            except Exception as e:
                logger.warning(f"[SunoProvider] Poll error (retry {i+1}): {e}")

        return MusicGenerationResult(
            success=False,
            error="Timeout waiting for music generation",
            job_id=job_id,
            status="timeout",
        )

    async def _mock_generate_music(
        self,
        prompt: str,
        style: str,
        duration: int,
        title: str,
    ) -> MusicGenerationResult:
        """模拟音乐生成（开发模式）"""
        # 模拟生成延迟
        await asyncio.sleep(2)

        # 返回一个模拟的音频 URL
        mock_job_id = f"mock_{uuid.uuid4().hex[:12]}"

        return MusicGenerationResult(
            success=True,
            audio_url=f"https://example.com/mock/music_{mock_job_id}.mp3",
            duration_sec=float(duration),
            job_id=mock_job_id,
            status="completed",
            title=title or prompt[:50],
        )


# 单例
_suno_provider: Optional[SunoViaComfyUIProvider] = None


def get_suno_provider() -> SunoViaComfyUIProvider:
    """获取 Suno Provider 单例"""
    global _suno_provider
    if _suno_provider is None:
        _suno_provider = SunoViaComfyUIProvider()
    return _suno_provider
