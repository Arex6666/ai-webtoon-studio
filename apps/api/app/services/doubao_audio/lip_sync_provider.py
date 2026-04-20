"""
Doubao Lip Sync Provider - 豆包对口型
基于火山引擎方舟大模型 API 实现

支持:
- 音频驱动的口型动画生成
- 视频口型同步
- 音频特征提取
"""
import httpx
import logging
import uuid
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass

from app.core.config import settings
from app.services.storage import get_object_store

logger = logging.getLogger(__name__)


# Lip Sync API 配置
LIPSYNC_API_URL = "https://ark.cn-beijing.volces.com/api/v3/video/lipsync"
LIPSYNC_MODEL = "doubao-lipsync-1"


@dataclass
class LipSyncRequest:
    """对口型请求"""
    image_url: str  # 输入图片 URL
    audio_url: str  # 输入音频 URL
    prompt: str = ""  # 可选的提示词


@dataclass
class LipSyncResult:
    """对口型结果"""
    success: bool
    video_url: Optional[str] = None
    video_data: Optional[bytes] = None
    duration_sec: float = 0.0
    provider: str = "doubao"
    cost: float = 0.0
    generation_time_ms: int = 0
    error: Optional[str] = None
    error_code: Optional[str] = None


class DoubaoLipSyncProvider:
    """
    豆包对口型 Provider

    使用火山引擎方舟大模型 API 进行口型同步
    """

    provider_name = "doubao"

    def __init__(self):
        self.api_key = getattr(settings, 'DOUBAO_API_KEY', None) or getattr(settings, 'ARK_API_KEY', None)

        if not self.api_key:
            logger.warning("[DoubaoLipSync] No API Key configured")

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(180.0, connect=30.0),
            verify=True,
            follow_redirects=True,
        )

    async def generate_lip_sync(
        self,
        image_url: str = None,
        video_url: str = None,
        audio_url: str = None,
        prompt: str = "",
        wait_for_completion: bool = True,
    ) -> LipSyncResult:
        """
        生成对口型视频

        Args:
            image_url: 输入图片 URL (图片驱动口型)
            video_url: 输入视频 URL (视频驱动口型/替换音频)
            audio_url: 输入音频 URL (TTS生成的语音)
            prompt: 可选的提示词
            wait_for_completion: 是否等待完成

        Returns:
            LipSyncResult
        """
        import time
        start_time = time.time()

        if not self.api_key:
            return LipSyncResult(
                success=False,
                error="DOUBAO_API_KEY not configured",
                error_code="NO_API_KEY",
            )

        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            payload = {
                "model": LIPSYNC_MODEL,
                "input": {
                    "audio_url": audio_url,
                },
            }

            # 支持图片或视频输入
            if image_url:
                payload["input"]["image_url"] = image_url
            if video_url:
                payload["input"]["video_url"] = video_url

            if prompt:
                payload["input"]["prompt"] = prompt

            logger.info(f"[DoubaoLipSync] Submitting lip sync job")

            # 提交任务
            response = await self.client.post(
                LIPSYNC_API_URL,
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                error_msg = f"API error: {response.status_code} - {response.text}"
                logger.error(f"[DoubaoLipSync] {error_msg}")
                return LipSyncResult(
                    success=False,
                    error=error_msg,
                    error_code="API_ERROR",
                )

            result = response.json()
            task_id = result.get("task_id")

            if not task_id:
                return LipSyncResult(
                    success=False,
                    error="No task_id in response",
                    error_code="NO_TASK_ID",
                )

            # 如果不等待完成，返回任务 ID
            if not wait_for_completion:
                return LipSyncResult(
                    success=True,
                    video_url=f"task://{task_id}",  # 临时标记
                )

            # 轮询等待完成
            video_url = await self._poll_for_result(task_id, headers)

            if not video_url:
                return LipSyncResult(
                    success=False,
                    error="Generation timeout or failed",
                    error_code="TIMEOUT",
                )

            generation_time_ms = int((time.time() - start_time) * 1000)

            return LipSyncResult(
                success=True,
                video_url=video_url,
                duration_sec=0.0,  # 从结果中获取
                generation_time_ms=generation_time_ms,
            )

        except Exception as e:
            logger.error(f"[DoubaoLipSync] Generation failed: {e}")
            return LipSyncResult(
                success=False,
                error=str(e),
                error_code="GENERATION_FAILED",
            )

    async def _poll_for_result(
        self,
        task_id: str,
        headers: Dict[str, str],
        timeout: int = 120,
        poll_interval: float = 2.0,
    ) -> Optional[str]:
        """轮询等待结果"""
        import asyncio
        import time

        status_url = f"{LIPSYNC_API_URL}/{task_id}"
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = await self.client.get(status_url, headers=headers)

                if response.status_code != 200:
                    await asyncio.sleep(poll_interval)
                    continue

                result = response.json()
                status = result.get("status")

                if status == "completed":
                    return result.get("output", {}).get("video_url")
                elif status == "failed":
                    logger.error(f"[DoubaoLipSync] Task failed: {result.get('error')}")
                    return None

                await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.warning(f"[DoubaoLipSync] Poll error: {e}")
                await asyncio.sleep(poll_interval)

        return None

    async def generate_lip_sync_from_audio_feature(
        self,
        image_url: str,
        audio_data: bytes,
    ) -> LipSyncResult:
        """
        从音频数据生成对口型（使用音频特征）

        Args:
            image_url: 输入图片 URL
            audio_data: 输入音频数据

        Returns:
            LipSyncResult
        """
        # 先上传音频获取 URL
        try:
            storage = get_object_store()
            audio_path = f"temp/lipsync_{uuid.uuid4().hex}.mp3"
            await storage.upload_data(audio_data, audio_path, content_type="audio/mp3")
            audio_url = await storage.get_url(audio_path)

            return await self.generate_lip_sync(image_url, audio_url)

        except Exception as e:
            logger.error(f"[DoubaoLipSync] Upload audio failed: {e}")
            return LipSyncResult(
                success=False,
                error=str(e),
                error_code="UPLOAD_FAILED",
            )

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    async def generate_with_tts(
        self,
        text: str,
        image_url: str = None,
        video_url: str = None,
        voice_id: str = "aio_invoice_male_bigtong",
        speed: float = 1.0,
        prompt: str = "",
        wait_for_completion: bool = True,
    ) -> Dict[str, Any]:
        """
        完整流程：配音 + 对口型

        1. 使用 TTS 将文本转为语音
        2. 使用语音驱动口型同步

        Args:
            text: 台词文本
            image_url: 输入图片 URL
            video_url: 输入视频 URL (可选)
            voice_id: 音色 ID
            speed: 语速
            prompt: 口型提示词
            wait_for_completion: 是否等待完成

        Returns:
            {
                "tts_result": TTSResult,
                "lipsync_result": LipSyncResult,
                "audio_url": 生成的语音URL,
                "video_url": 对口型视频URL,
            }
        """
        from .tts_provider import get_doubao_tts_provider

        result = {
            "success": False,
            "tts_result": None,
            "lipsync_result": None,
            "audio_url": None,
            "video_url": None,
            "error": None,
        }

        try:
            # Step 1: 生成配音 (TTS)
            logger.info(f"[DoubaoLipSync] Step 1: Generating TTS for text: {text[:50]}...")
            tts_provider = get_doubao_tts_provider()

            tts_result = await tts_provider.generate_speech(
                text=text,
                voice_id=voice_id,
                speed=speed,
                save_to_storage=True,
            )

            if not tts_result.success:
                result["error"] = f"TTS failed: {tts_result.error}"
                return result

            result["tts_result"] = tts_result
            result["audio_url"] = tts_result.audio_url
            logger.info(f"[DoubaoLipSync] TTS generated: {tts_result.audio_url}")

            # Step 2: 对口型
            logger.info(f"[DoubaoLipSync] Step 2: Generating lip sync...")
            lipsync_result = await self.generate_lip_sync(
                image_url=image_url,
                video_url=video_url,
                audio_url=tts_result.audio_url,
                prompt=prompt,
                wait_for_completion=wait_for_completion,
            )

            result["lipsync_result"] = lipsync_result

            if lipsync_result.success:
                result["success"] = True
                result["video_url"] = lipsync_result.video_url
                logger.info(f"[DoubaoLipSync] Lip sync completed: {lipsync_result.video_url}")
            else:
                result["error"] = f"Lip sync failed: {lipsync_result.error}"

            return result

        except Exception as e:
            logger.error(f"[DoubaoLipSync] Complete flow failed: {e}")
            result["error"] = str(e)
            return result


# 单例
_lipsync_provider: Optional[DoubaoLipSyncProvider] = None


def get_doubao_lipsync_provider() -> DoubaoLipSyncProvider:
    """获取对口型 Provider 单例"""
    global _lipsync_provider
    if _lipsync_provider is None:
        _lipsync_provider = DoubaoLipSyncProvider()
    return _lipsync_provider
