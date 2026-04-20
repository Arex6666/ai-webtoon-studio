"""
Doubao Subtitle Provider - 豆包字幕生成
基于火山引擎方舟大模型 API 实现

支持:
- 文字转字幕 (SRT/ASS 格式)
- 时间轴对齐
- 多语言支持
"""
import logging
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import timedelta

from app.core.config import settings
from app.services.brain.standard_llm import get_llm_service

logger = logging.getLogger(__name__)


@dataclass
class SubtitleRequest:
    """字幕请求"""
    text: str  # 完整台词文本
    duration_sec: float = 3.0  # 总时长
    format: str = "srt"  # srt 或 ass
    language: str = "zh-CN"  # 语言


@dataclass
class SubtitleCue:
    """单条字幕"""
    index: int
    start_time: timedelta
    end_time: timedelta
    text: str


@dataclass
class SubtitleResult:
    """字幕结果"""
    success: bool
    content: Optional[str] = None  # 字幕文本内容
    cues: List[SubtitleCue] = None  # 解析后的字幕片段
    format: str = "srt"
    provider: str = "doubao"
    error: Optional[str] = None
    error_code: Optional[str] = None


class DoubaoSubtitleProvider:
    """
    豆包字幕生成 Provider

    使用豆包大模型进行时间轴对齐和字幕生成
    """

    provider_name = "doubao"

    def __init__(self):
        self.llm = None

    async def generate_subtitles(
        self,
        text: str,
        duration_sec: float = 3.0,
        format: str = "srt",
        language: str = "zh-CN",
    ) -> SubtitleResult:
        """
        生成字幕

        Args:
            text: 完整台词文本
            duration_sec: 总时长（秒）
            format: 字幕格式 (srt/ass)
            language: 语言

        Returns:
            SubtitleResult
        """
        try:
            # 使用 LLM 进行时间轴对齐
            time_aligned = await self._align_timeline(text, duration_sec, language)

            if not time_aligned:
                # 降级：平均分配时间
                cues = self._simple_split(text, duration_sec)
            else:
                cues = time_aligned

            # 生成字幕文本
            if format == "srt":
                content = self._generate_srt(cues)
            elif format == "ass":
                content = self._generate_ass(cues)
            else:
                return SubtitleResult(
                    success=False,
                    error=f"Unsupported format: {format}",
                    error_code="UNSUPPORTED_FORMAT",
                )

            return SubtitleResult(
                success=True,
                content=content,
                cues=cues,
                format=format,
            )

        except Exception as e:
            logger.error(f"[DoubaoSubtitle] Generation failed: {e}")
            return SubtitleResult(
                success=False,
                error=str(e),
                error_code="GENERATION_FAILED",
            )

    async def _align_timeline(
        self,
        text: str,
        duration_sec: float,
        language: str,
    ) -> Optional[List[SubtitleCue]]:
        """使用 LLM 进行时间轴对齐"""
        try:
            llm = get_llm_service()

            # 构建 prompt
            prompt = f"""请将以下台词按时间轴分割，每个片段时长根据句子长度比例分配。
总时长: {duration_sec}秒
语言: {language}

台词:
{text}

请以 JSON 格式返回，格式如下:
[
  {{"index": 1, "start_pct": 0, "end_pct": 0.3, "text": "第一句台词"}},
  {{"index": 2, "start_pct": 0.3, "end_pct": 0.7, "text": "第二句台词"}},
  ...
]

start_pct 和 end_pct 是时间百分比 (0-1)。
只返回 JSON，不要其他内容。"""

            response = await llm.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )

            import json
            data = json.loads(response)

            # 转换为 SubtitleCue
            cues = []
            for item in data:
                start_sec = item["start_pct"] * duration_sec
                end_sec = item["end_pct"] * duration_sec
                cues.append(SubtitleCue(
                    index=item["index"],
                    start_time=timedelta(seconds=start_sec),
                    end_time=timedelta(seconds=end_sec),
                    text=item["text"],
                ))

            return cues

        except Exception as e:
            logger.warning(f"[DoubaoSubtitle] LLM alignment failed: {e}")
            return None

    def _simple_split(
        self,
        text: str,
        duration_sec: float,
    ) -> List[SubtitleCue]:
        """简单按句子分割（降级方案）"""
        # 按标点分割句子
        sentences = re.split(r'[。！？\n]+', text)
        sentences = [s.strip() for s in sentences if s.strip()]

        if not sentences:
            return [SubtitleCue(
                index=1,
                start_time=timedelta(0),
                end_time=timedelta(seconds=duration_sec),
                text=text,
            )]

        # 平均分配时间
        avg_duration = duration_sec / len(sentences)
        cues = []
        current_time = 0.0

        for i, sentence in enumerate(sentences):
            cues.append(SubtitleCue(
                index=i + 1,
                start_time=timedelta(seconds=current_time),
                end_time=timedelta(seconds=current_time + avg_duration),
                text=sentence,
            ))
            current_time += avg_duration

        return cues

    def _generate_srt(self, cues: List[SubtitleCue]) -> str:
        """生成 SRT 格式字幕"""
        lines = []

        for cue in cues:
            # 格式化时间 (HH:MM:SS,mmm)
            start = self._format_srt_time(cue.start_time)
            end = self._format_srt_time(cue.end_time)

            lines.append(str(cue.index))
            lines.append(f"{start} --> {end}")
            lines.append(cue.text)
            lines.append("")  # 空行

        return "\n".join(lines)

    def _generate_ass(self, cues: List[SubtitleCue]) -> str:
        """生成 ASS 格式字幕"""
        lines = [
            "[Script Info]",
            "ScriptType: v4.00+",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Arial,40,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,10,10,10,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]

        for cue in cues:
            start = self._format_ass_time(cue.start_time)
            end = self._format_ass_time(cue.end_time)

            # 转义文本
            text = cue.text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")
            lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

        return "\n".join(lines)

    def _format_srt_time(self, td: timedelta) -> str:
        """格式化 SRT 时间"""
        total_sec = td.total_seconds()
        hours = int(total_sec // 3600)
        minutes = int((total_sec % 3600) // 60)
        seconds = int(total_sec % 60)
        millis = int((total_sec % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"

    def _format_ass_time(self, td: timedelta) -> str:
        """格式化 ASS 时间"""
        total_sec = td.total_seconds()
        hours = int(total_sec // 3600)
        minutes = int((total_sec % 3600) // 60)
        seconds = total_sec % 60
        return f"{hours}:{minutes:02d}:{seconds:05.2f}"


# 单例
_subtitle_provider: Optional[DoubaoSubtitleProvider] = None


def get_doubao_subtitle_provider() -> DoubaoSubtitleProvider:
    """获取字幕 Provider 单例"""
    global _subtitle_provider
    if _subtitle_provider is None:
        _subtitle_provider = DoubaoSubtitleProvider()
    return _subtitle_provider
