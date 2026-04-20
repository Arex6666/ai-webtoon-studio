"""
Doubao Audio Module - 豆包音频服务

提供以下功能:
- TTS (文字转语音)
- 字幕生成 (SRT/ASS 格式)
- 对口型 (Lip Sync)
- 完整Pipeline (对话+旁白)
"""
from .tts_provider import (
    DoubaoTTSProvider,
    TTSRequest,
    TTSResult,
    VOICE_OPTIONS,
    get_doubao_tts_provider,
)

from .subtitle_provider import (
    DoubaoSubtitleProvider,
    SubtitleRequest,
    SubtitleCue,
    SubtitleResult,
    get_doubao_subtitle_provider,
)

from .lip_sync_provider import (
    DoubaoLipSyncProvider,
    LipSyncRequest,
    LipSyncResult,
    get_doubao_lipsync_provider,
)

from .pipeline import (
    DoubaoAudioVideoPipeline,
    AudioType,
    ScriptSegment,
    PipelineResult,
    get_audio_video_pipeline,
    process_dialogue_and_narration,
)

__all__ = [
    # TTS
    "DoubaoTTSProvider",
    "TTSRequest",
    "TTSResult",
    "VOICE_OPTIONS",
    "get_doubao_tts_provider",
    # Subtitle
    "DoubaoSubtitleProvider",
    "SubtitleRequest",
    "SubtitleCue",
    "SubtitleResult",
    "get_doubao_subtitle_provider",
    # Lip Sync
    "DoubaoLipSyncProvider",
    "LipSyncRequest",
    "LipSyncResult",
    "get_doubao_lipsync_provider",
    # Pipeline
    "DoubaoAudioVideoPipeline",
    "AudioType",
    "ScriptSegment",
    "PipelineResult",
    "get_audio_video_pipeline",
    "process_dialogue_and_narration",
]
