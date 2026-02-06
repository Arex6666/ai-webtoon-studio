"""
Panel Attribute Filler - 分镜属性智能填充服务

根据分镜描述自动推断并填充镜头参数、环境属性等。
"""
import logging
import json
from typing import Dict, Any, Optional, List
from app.services.brain.standard_llm import StandardLLMService
from app.schemas.brain.enums import ShotType, CameraMove, TimeOfDay, Weather

logger = logging.getLogger(__name__)


# 默认值配置
DEFAULT_DURATION_S = 3.0
DEFAULT_FPS = 8

# 关键词映射表
SHOT_TYPE_KEYWORDS = {
    ShotType.EXTREME_CLOSE_UP: ["眼睛", "嘴唇", "手指", "特写", "局部"],
    ShotType.CLOSE_UP: ["脸", "表情", "眼神", "近景"],
    ShotType.MEDIUM_CLOSE_UP: ["上半身", "胸部以上"],
    ShotType.MEDIUM: ["半身", "站着", "坐着", "中景"],
    ShotType.MEDIUM_FULL: ["膝盖以上", "大半身"],
    ShotType.FULL: ["全身", "站立", "走路", "全景"],
    ShotType.WIDE: ["远景", "环境", "场景", "远处", "街道", "建筑"],
    ShotType.EXTREME_WIDE: ["大远景", "天际线", "全貌", "俯瞰"],
}

CAMERA_MOVE_KEYWORDS = {
    CameraMove.STATIC: ["静止", "不动", "凝视"],
    CameraMove.PUSH: ["推进", "靠近", "逼近"],
    CameraMove.PULL: ["拉远", "后退", "远离"],
    CameraMove.PAN_LEFT: ["左移", "向左"],
    CameraMove.PAN_RIGHT: ["右移", "向右"],
    CameraMove.TILT_UP: ["抬头", "仰望", "看天"],
    CameraMove.TILT_DOWN: ["低头", "俯视", "看地"],
    CameraMove.FOLLOW: ["跟随", "跟踪", "追随", "跟着"],
    CameraMove.ZOOM: ["变焦", "放大"],
}

TIME_KEYWORDS = {
    TimeOfDay.DAWN: ["黎明", "破晓", "清晨", "天刚亮"],
    TimeOfDay.MORNING: ["早晨", "上午", "早上", "清晨"],
    TimeOfDay.NOON: ["中午", "正午", "午间"],
    TimeOfDay.AFTERNOON: ["下午", "午后"],
    TimeOfDay.DUSK: ["傍晚", "黄昏", "日落", "夕阳"],
    TimeOfDay.NIGHT: ["夜晚", "晚上", "深夜", "夜间", "夜色"],
}

WEATHER_KEYWORDS = {
    Weather.CLEAR: ["晴朗", "晴天", "阳光"],
    Weather.CLOUDY: ["多云", "阴天", "乌云"],
    Weather.OVERCAST: ["阴沉", "灰暗"],
    Weather.RAIN: ["雨", "细雨", "小雨", "大雨", "暴雨", "雨天"],
    Weather.SNOW: ["雪", "下雪", "雪花"],
    Weather.FOG: ["雾", "迷雾", "浓雾"],
    Weather.STORM: ["暴风", "狂风", "风暴"],
}

MOOD_KEYWORDS = {
    "紧张": ["紧张", "焦虑", "不安", "担心", "恐惧"],
    "悲伤": ["悲伤", "难过", "伤心", "眼泪", "哭"],
    "温馨": ["温馨", "温暖", "幸福", "甜蜜", "微笑"],
    "怀旧": ["怀旧", "回忆", "往事", "曾经"],
    "神秘": ["神秘", "未知", "迷茫", "困惑"],
    "浪漫": ["浪漫", "爱情", "心跳", "喜欢"],
    "激动": ["激动", "兴奋", "热血", "澎湃"],
    "平静": ["平静", "安宁", "安静", "祥和"],
}


class PanelAttributeFiller:
    """分镜属性智能填充"""
    
    def __init__(self, llm_service: Optional[StandardLLMService] = None):
        self.llm = llm_service or StandardLLMService()
    
    async def fill_attributes(self, panel: Dict[str, Any]) -> Dict[str, Any]:
        """从分镜描述推断并填充属性
        
        Args:
            panel: 分镜数据，包含 description, actions, visual_prompt 等
        
        Returns:
            填充后的分镜数据，包含:
            - shot_type: 景别
            - camera_move: 运镜
            - duration_s: 时长 (秒)
            - mood: 氛围
            - time_of_day: 时间
            - weather: 天气
            - motion_description: 运镜描述
        """
        # 收集所有文本用于分析
        text_sources = [
            panel.get("description", ""),
            panel.get("actions", ""),
            panel.get("visual_prompt", ""),
            panel.get("location", ""),
        ]
        combined_text = " ".join(filter(None, text_sources))
        
        # 规则优先填充
        filled = panel.copy()
        
        # 1. 景别
        if not filled.get("shot_type"):
            filled["shot_type"] = self._infer_shot_type(combined_text)
        
        # 2. 运镜
        if not filled.get("camera_move"):
            filled["camera_move"] = self._infer_camera_move(combined_text)
        
        # 3. 时间
        if not filled.get("time_of_day"):
            filled["time_of_day"] = self._infer_time_of_day(combined_text)
        
        # 4. 天气
        if not filled.get("weather"):
            filled["weather"] = self._infer_weather(combined_text)
        
        # 5. 氛围
        if not filled.get("mood"):
            filled["mood"] = self._infer_mood(combined_text)
        
        # 6. 时长 (默认值)
        if not filled.get("duration_s"):
            filled["duration_s"] = DEFAULT_DURATION_S
        
        # 7. 运镜描述
        if not filled.get("motion_description"):
            filled["motion_description"] = self._generate_motion_description(
                filled.get("camera_move", CameraMove.STATIC.value),
                combined_text
            )
        
        return filled
    
    async def fill_batch(self, panels: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量填充多个分镜"""
        return [await self.fill_attributes(p) for p in panels]
    
    async def fill_with_llm(self, panel: Dict[str, Any]) -> Dict[str, Any]:
        """使用 LLM 进行更智能的填充（当规则无法确定时）"""
        text = panel.get("description", "") or panel.get("actions", "")
        
        if not text:
            return await self.fill_attributes(panel)
        
        prompt = f"""根据以下分镜描述，推断镜头属性。

分镜描述：
{text}

请返回 JSON：
{{
    "shot_type": "景别 (extreme_close_up/close_up/medium_close_up/medium/medium_full/full/wide/extreme_wide)",
    "camera_move": "运镜 (static/push/pull/pan_left/pan_right/tilt_up/tilt_down/follow/zoom)",
    "time_of_day": "时间 (dawn/morning/noon/afternoon/dusk/night)",
    "weather": "天气 (clear/cloudy/overcast/rain/snow/fog/storm)",
    "mood": "氛围描述词",
    "duration_s": 预估秒数 (1.5-8.0),
    "motion_description": "运镜描述 (20字以内)"
}}

只返回 JSON。"""

        try:
            result = await self.llm._chat_completion(
                messages=[{"role": "user", "content": prompt}],
                response_format="json"
            )
            llm_attrs = json.loads(result.strip())
            
            # 合并到 panel
            filled = panel.copy()
            for key in ["shot_type", "camera_move", "time_of_day", "weather", 
                        "mood", "duration_s", "motion_description"]:
                if not filled.get(key) and llm_attrs.get(key):
                    filled[key] = llm_attrs[key]
            
            return filled
        except Exception as e:
            logger.warning(f"LLM 属性填充失败: {e}, 回退到规则填充")
            return await self.fill_attributes(panel)
    
    def _infer_shot_type(self, text: str) -> str:
        """根据文本推断景别"""
        for shot_type, keywords in SHOT_TYPE_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    return shot_type.value
        return ShotType.MEDIUM.value  # 默认中景
    
    def _infer_camera_move(self, text: str) -> str:
        """根据文本推断运镜"""
        for camera_move, keywords in CAMERA_MOVE_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    return camera_move.value
        return CameraMove.STATIC.value  # 默认静止
    
    def _infer_time_of_day(self, text: str) -> str:
        """根据文本推断时间"""
        for time_of_day, keywords in TIME_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    return time_of_day.value
        return TimeOfDay.AFTERNOON.value  # 默认下午
    
    def _infer_weather(self, text: str) -> str:
        """根据文本推断天气"""
        for weather, keywords in WEATHER_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    return weather.value
        return Weather.CLEAR.value  # 默认晴朗
    
    def _infer_mood(self, text: str) -> List[str]:
        """根据文本推断氛围"""
        moods = []
        for mood, keywords in MOOD_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    moods.append(mood)
                    break
        return moods if moods else ["平静"]
    
    def _generate_motion_description(self, camera_move: str, text: str) -> str:
        """生成运镜描述"""
        descriptions = {
            CameraMove.STATIC.value: "镜头固定，静态取景",
            CameraMove.PUSH.value: "镜头缓缓推进，聚焦主体",
            CameraMove.PULL.value: "镜头后拉，展现全景",
            CameraMove.PAN_LEFT.value: "镜头向左平移",
            CameraMove.PAN_RIGHT.value: "镜头向右平移",
            CameraMove.TILT_UP.value: "镜头向上抬起",
            CameraMove.TILT_DOWN.value: "镜头向下俯视",
            CameraMove.FOLLOW.value: "镜头跟随人物移动",
            CameraMove.ZOOM.value: "镜头变焦拉近",
        }
        return descriptions.get(camera_move, "镜头固定")
