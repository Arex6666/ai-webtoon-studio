"""
Doubao TTS Provider - 豆包语音合成
基于火山引擎方舟大模型 API 实现

支持:
- 文字转语音 (Text-to-Speech)
- 多音色选择
- 语速/音调调节
"""
import httpx
import logging
import base64
import uuid
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from app.core.config import settings
from app.services.storage import get_object_store

logger = logging.getLogger(__name__)


# TTS API 配置
TTS_API_URL = "https://ark.cn-beijing.volces.com/api/v3/audio/generations"
TTS_MODEL = "doubao-tts-1-flash"


@dataclass
class TTSRequest:
    """TTS 请求"""
    text: str
    voice_id: str = "aio_invoice_male_bigtong"  # 默认音色
    speed: float = 1.0  # 语速 0.5-2.0
    pitch: float = 1.0  # 音调 0.5-2.0
    volume: float = 1.0  # 音量 0.5-2.0
    sample_rate: int = 24000  # 采样率


@dataclass
class TTSResult:
    """TTS 结果"""
    success: bool
    audio_url: Optional[str] = None
    audio_data: Optional[bytes] = None
    duration_sec: float = 0.0
    provider: str = "doubao"
    cost: float = 0.0
    generation_time_ms: int = 0
    error: Optional[str] = None
    error_code: Optional[str] = None


# 可用音色列表
VOICE_OPTIONS = {
    # 男声
    "aio_invoice_male_bigtong": "男声-大童",
    "aio_invoice_male_jingying": "男声-精英",
    "aio_invoice_male_boshi": "男声-博士",
    "aio_invoice_male_yujie": "男声-御姐",
    "aio_invoice_male_zhisheng": "男声-知声",
    # 女声
    "aio_invoice_female_aili": "女声-艾丽",
    "aio_invoice_female_aisheng": "女声-爱生",
    "aio_invoice_female_jingxuan": "女声-精选",
    "aio_invoice_female_yujie": "女声-御姐",
    "aio_invoice_female_xiaoyuan": "女声-小媛",
}


@dataclass
class VoiceInfo:
    """音色信息"""
    voice_id: str
    name: str
    gender: str  # "male" / "female"
    age_group: str  # "child" / "adult" / "senior"
    description: str = ""


def get_available_voices() -> List[VoiceInfo]:
    """获取可用音色列表"""
    return [
        VoiceInfo(
            voice_id="aio_invoice_male_bigtong",
            name="男声-大童",
            gender="male",
            age_group="child",
            description="活泼可爱的小男孩声音",
        ),
        VoiceInfo(
            voice_id="aio_invoice_male_jingying",
            name="男声-精英",
            gender="male",
            age_group="adult",
            description="成熟稳重的精英男声",
        ),
        VoiceInfo(
            voice_id="aio_invoice_male_boshi",
            name="男声-博士",
            gender="male",
            age_group="adult",
            description="博学多才的学者声音",
        ),
        VoiceInfo(
            voice_id="aio_invoice_male_yujie",
            name="男声-御姐",
            gender="male",
            age_group="adult",
            description="成熟男性声音",
        ),
        VoiceInfo(
            voice_id="aio_invoice_male_zhisheng",
            name="男声-知声",
            gender="male",
            age_group="adult",
            description="知性温和的声音",
        ),
        VoiceInfo(
            voice_id="aio_invoice_female_aili",
            name="女声-艾丽",
            gender="female",
            age_group="adult",
            description="温柔的成年女性声音",
        ),
        VoiceInfo(
            voice_id="aio_invoice_female_aisheng",
            name="女声-爱生",
            gender="female",
            age_group="adult",
            description="充满爱心的女性声音",
        ),
        VoiceInfo(
            voice_id="aio_invoice_female_jingxuan",
            name="女声-精选",
            gender="female",
            age_group="adult",
            description="清晰明亮的女声",
        ),
        VoiceInfo(
            voice_id="aio_invoice_female_yujie",
            name="女声-御姐",
            gender="female",
            age_group="adult",
            description="成熟的御姐声音",
        ),
        VoiceInfo(
            voice_id="aio_invoice_female_xiaoyuan",
            name="女声-小媛",
            gender="female",
            age_group="child",
            description="甜美可爱的小女孩声音",
        ),
    ]


class DoubaoTTSProvider:
    """
    豆包 TTS Provider

    使用火山引擎方舟大模型 API 进行语音合成
    """

    provider_name = "doubao"

    def __init__(self):
        self.api_key = getattr(settings, 'DOUBAO_API_KEY', None) or getattr(settings, 'ARK_API_KEY', None)

        if not self.api_key:
            logger.warning("[DoubaoTTS] No API Key configured")

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=30.0),
            verify=True,
            follow_redirects=True,
        )

    async def generate_speech(
        self,
        text: str,
        voice_id: str = "aio_invoice_male_bigtong",
        speed: float = 1.0,
        pitch: float = 1.0,
        volume: float = 1.0,
        sample_rate: int = 24000,
        save_to_storage: bool = True,
    ) -> TTSResult:
        """
        生成语音

        Args:
            text: 要转换的文本
            voice_id: 音色 ID
            speed: 语速 (0.5-2.0)
            pitch: 音调 (0.5-2.0)
            volume: 音量 (0.5-2.0)
            sample_rate: 采样率
            save_to_storage: 是否保存到存储

        Returns:
            TTSResult
        """
        import time
        start_time = time.time()

        if not self.api_key:
            return TTSResult(
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
                "model": TTS_MODEL,
                "input": {
                    "text": text,
                },
                "voice_settings": {
                    "voice_id": voice_id,
                    "speed": speed,
                    "pitch": pitch,
                    "volume": volume,
                },
                "audio_settings": {
                    "sample_rate": sample_rate,
                    "format": "mp3",
                },
            }

            logger.info(f"[DoubaoTTS] Generating speech for text: {text[:50]}...")

            response = await self.client.post(
                TTS_API_URL,
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                error_msg = f"API error: {response.status_code} - {response.text}"
                logger.error(f"[DoubaoTTS] {error_msg}")
                return TTSResult(
                    success=False,
                    error=error_msg,
                    error_code="API_ERROR",
                )

            result = response.json()

            # 解析响应
            audio_data_b64 = result.get("data", {}).get("audio", "")
            if not audio_data_b64:
                return TTSResult(
                    success=False,
                    error="No audio data in response",
                    error_code="NO_AUDIO_DATA",
                )

            # 解码 Base64
            audio_data = base64.b64decode(audio_data_b64)

            audio_url = None
            if save_to_storage:
                storage = get_object_store()
                audio_url = await self._save_audio(
                    storage,
                    audio_data,
                    f"tts_{uuid.uuid4().hex}.mp3"
                )

            duration_sec = result.get("data", {}).get("duration", 0.0)
            cost = result.get("usage", {}).get("total_tokens", 0) / 1000  # 估算

            generation_time_ms = int((time.time() - start_time) * 1000)

            return TTSResult(
                success=True,
                audio_url=audio_url,
                audio_data=audio_data,
                duration_sec=duration_sec,
                cost=cost,
                generation_time_ms=generation_time_ms,
            )

        except Exception as e:
            logger.error(f"[DoubaoTTS] Generation failed: {e}")
            return TTSResult(
                success=False,
                error=str(e),
                error_code="GENERATION_FAILED",
            )

    async def _save_audio(
        self,
        storage,
        audio_data: bytes,
        filename: str,
    ) -> str:
        """保存音频到存储"""
        try:
            path = f"tts/{filename}"
            await storage.upload_data(audio_data, path, content_type="audio/mp3")
            url = await storage.get_url(path)
            return url
        except Exception as e:
            logger.warning(f"[DoubaoTTS] Failed to save audio: {e}")
            return None

    async def close(self):
        """关闭客户端"""
        await self.client.aclose()

    def list_voices(self) -> List[VoiceInfo]:
        """列出可用音色"""
        return get_available_voices()


# 单例
_tts_provider: Optional[DoubaoTTSProvider] = None


def get_doubao_tts_provider() -> DoubaoTTSProvider:
    """获取 TTS Provider 单例"""
    global _tts_provider
    if _tts_provider is None:
        _tts_provider = DoubaoTTSProvider()
    return _tts_provider
