"""
Doubao Audio/Video Pipeline - 豆包音视频完整Pipeline

处理两种场景：
1. 人物说话：角色图片 + 台词 → 对口型视频 + 字幕
2. 旁白：背景画面 + 旁白文本 → 语音视频 + 字幕

完整流程：
- 语音合成 (TTS)
- 对口型 (Lip Sync) - 仅人物说话时
- 字幕生成 (Subtitle)
- 视频合成 (Composition)
"""
import logging
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import timedelta

from .tts_provider import get_doubao_tts_provider, TTSResult
from .subtitle_provider import get_doubao_subtitle_provider, SubtitleResult, SubtitleCue
from .lip_sync_provider import get_doubao_lipsync_provider, LipSyncResult

logger = logging.getLogger(__name__)


class AudioType(str, Enum):
    """音频类型"""
    DIALOGUE = "dialogue"      # 人物对话（有角色图片）
    NARRATION = "narration"    # 旁白（无角色图片）


@dataclass
class ScriptSegment:
    """脚本片段"""
    index: int
    type: AudioType                  # 对话或旁白
    text: str                        # 文本内容
    character_name: Optional[str] = None    # 角色名（对话时）
    character_image_url: Optional[str] = None  # 角色图片（对话时）
    background_url: Optional[str] = None  # 背景图片（旁白时）
    duration_sec: float = 0.0       # 预计时长
    start_time: Optional[timedelta] = None  # 开始时间


@dataclass
class PipelineResult:
    """Pipeline 执行结果"""
    success: bool

    # 音频结果
    tts_results: List[TTSResult] = field(default_factory=list)

    # 对口型结果（仅对话）
    lipsync_results: List[LipSyncResult] = field(default_factory=list)

    # 字幕结果
    subtitle_result: Optional[SubtitleResult] = None

    # 输出
    audio_urls: List[str] = field(default_factory=list)      # 语音URL列表
    video_urls: List[str] = field(default_factory=list)       # 视频URL列表
    subtitle_url: Optional[str] = None                       # 字幕文件URL

    # 元数据
    total_duration_sec: float = 0.0
    segments: List[ScriptSegment] = field(default_factory=list)

    # 错误
    error: Optional[str] = None


class DoubaoAudioVideoPipeline:
    """
    豆包音视频 Pipeline

    统一处理人物对话和旁白两种场景
    """

    def __init__(self):
        self.tts_provider = get_doubao_tts_provider()
        self.subtitle_provider = get_doubao_subtitle_provider()
        self.lipsync_provider = get_doubao_lipsync_provider()

    async def process_script(
        self,
        segments: List[ScriptSegment],
        default_voice: str = "aio_invoice_male_bigtong",
        voice_map: Optional[Dict[str, str]] = None,
        default_speed: float = 1.0,
    ) -> PipelineResult:
        """
        处理完整脚本

        Args:
            segments: 脚本片段列表
            default_voice: 默认音色
            voice_map: 角色名→音色 映射
            default_speed: 默认语速

        Returns:
            PipelineResult
        """
        result = PipelineResult(
            success=False,
            segments=segments,
        )

        voice_map = voice_map or {}

        try:
            total_duration = 0.0
            current_time = 0.0

            # 按顺序处理每个片段
            for segment in segments:
                logger.info(f"[Pipeline] Processing segment {segment.index}: {segment.type.value} - {segment.text[:30]}...")

                # 确定音色
                voice_id = voice_map.get(segment.character_name, default_voice) if segment.character_name else default_voice

                # Step 1: TTS 语音合成
                tts_result = await self._generate_tts(
                    text=segment.text,
                    voice_id=voice_id,
                    speed=default_speed,
                )

                if not tts_result.success:
                    logger.warning(f"[Pipeline] TTS failed for segment {segment.index}: {tts_result.error}")
                    continue

                result.tts_results.append(tts_result)
                result.audio_urls.append(tts_result.audio_url)

                # 记录时长
                segment.duration_sec = tts_result.duration_sec or (len(segment.text) / 5.0)  # 估算
                segment.start_time = timedelta(seconds=current_time)
                current_time += segment.duration_sec

                # Step 2: 对口型或纯语音
                if segment.type == AudioType.DIALOGUE and segment.character_image_url:
                    # 人物对话：生成对口型视频
                    lipsync_result = await self._generate_lipsync(
                        image_url=segment.character_image_url,
                        audio_url=tts_result.audio_url,
                    )

                    if lipsync_result.success:
                        result.lipsync_results.append(lipsync_result)
                        result.video_urls.append(lipsync_result.video_url)
                    else:
                        logger.warning(f"[Pipeline] Lip sync failed: {lipsync_result.error}")
                        # 降级：使用纯音频
                        result.video_urls.append(tts_result.audio_url)

                else:
                    # 旁白：使用纯音频
                    result.video_urls.append(tts_result.audio_url)

            result.total_duration_sec = current_time

            # Step 3: 生成字幕
            all_text = " ".join([seg.text for seg in segments])
            subtitle_result = await self._generate_subtitle(
                text=all_text,
                duration_sec=result.total_duration_sec,
            )

            if subtitle_result.success:
                result.subtitle_result = subtitle_result
                # 保存字幕文件
                result.subtitle_url = await self._save_subtitle(
                    subtitle_result.content,
                    subtitle_result.format,
                )

            result.success = True
            logger.info(f"[Pipeline] Completed: {len(segments)} segments, {result.total_duration_sec}s total")

            return result

        except Exception as e:
            logger.error(f"[Pipeline] Error: {e}")
            result.error = str(e)
            return result

    async def _generate_tts(
        self,
        text: str,
        voice_id: str,
        speed: float,
    ) -> TTSResult:
        """生成语音"""
        return await self.tts_provider.generate_speech(
            text=text,
            voice_id=voice_id,
            speed=speed,
            save_to_storage=True,
        )

    async def _generate_lipsync(
        self,
        image_url: str,
        audio_url: str,
    ) -> LipSyncResult:
        """生成对口型"""
        return await self.lipsync_provider.generate_lip_sync(
            image_url=image_url,
            audio_url=audio_url,
            wait_for_completion=True,
        )

    async def _generate_subtitle(
        self,
        text: str,
        duration_sec: float,
    ) -> SubtitleResult:
        """生成字幕"""
        return await self.subtitle_provider.generate_subtitles(
            text=text,
            duration_sec=duration_sec,
            format="srt",
        )

    async def _save_subtitle(
        self,
        content: str,
        format: str,
    ) -> Optional[str]:
        """保存字幕文件"""
        try:
            from app.services.storage import get_object_store
            import uuid

            storage = get_object_store()
            filename = f"subtitles/{uuid.uuid4().hex}.{format}"

            await storage.upload_data(
                content.encode("utf-8"),
                filename,
                content_type="text/plain"
            )

            url = await storage.get_url(filename)
            logger.info(f"[Pipeline] Subtitle saved: {url}")
            return url

        except Exception as e:
            logger.error(f"[Pipeline] Save subtitle failed: {e}")
            return None

    async def process_mixed_script(
        self,
        script_data: List[Dict[str, Any]],
    ) -> PipelineResult:
        """
        处理混合脚本（自动识别对话/旁白）

        Args:
            script_data: [
                {"type": "dialogue", "text": "你好", "character": "小明", "image": "url"},
                {"type": "narration", "text": "这时天空..."},
            ]
        """
        segments = []

        for i, item in enumerate(script_data):
            segment = ScriptSegment(
                index=i,
                type=AudioType.DIALOGUE if item.get("type") == "dialogue" else AudioType.NARRATION,
                text=item.get("text", ""),
                character_name=item.get("character"),
                character_image_url=item.get("image"),
                background_url=item.get("background"),
            )
            segments.append(segment)

        return await self.process_script(segments)


# ============ 便捷函数 ============

_pipeline: Optional[DoubaoAudioVideoPipeline] = None


def get_audio_video_pipeline() -> DoubaoAudioVideoPipeline:
    """获取 Pipeline 单例"""
    global _pipeline
    if _pipeline is None:
        _pipeline = DoubaoAudioVideoPipeline()
    return _pipeline


async def process_dialogue_and_narration(
    script_data: List[Dict[str, Any]],
    voice_map: Optional[Dict[str, str]] = None,
) -> PipelineResult:
    """
    便捷函数：处理对话和旁白

    示例输入:
    [
        {"type": "dialogue", "text": "你好，我是小明", "character": "小明", "image": "http://.../xiaoming.png"},
        {"type": "narration", "text": "这时，天空突然暗了下来"},
        {"type": "dialogue", "text": "发生了什么？", "character": "小红", "image": "http://.../xiaohong.png"},
    ]
    """
    pipeline = get_audio_video_pipeline()
    return await pipeline.process_mixed_script(script_data)
