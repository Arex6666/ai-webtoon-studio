"""
Brain Enums - 统一枚举源

所有 Schema 中的枚举字段必须使用这里定义的枚举类型。
这是"强约束"的基础，确保 JSON 抽取稳定。
"""
from enum import Enum
from typing import Literal


# ============ ShotType 镜头类型 ============

class ShotType(str, Enum):
    """
    镜头类型枚举
    
    验收：任何 schema 中 shot_type 字段只能取这些值，否则 Pydantic 校验失败
    """
    ECU = "ECU"   # Extreme Close-Up 极特写
    CU = "CU"     # Close-Up 特写
    MS = "MS"     # Medium Shot 中景
    LS = "LS"     # Long Shot 远景
    WS = "WS"     # Wide Shot 大远景
    OTS = "OTS"   # Over-the-Shoulder 过肩


# Literal 版本用于 Pydantic 严格校验
ShotTypeLiteral = Literal["ECU", "CU", "MS", "LS", "WS", "OTS"]


# ============ CameraMove 运镜类型 ============

class CameraMove(str, Enum):
    """
    运镜类型枚举
    """
    STATIC = "static"
    PAN = "pan"
    TILT = "tilt"
    DOLLY_IN = "dolly_in"
    DOLLY_OUT = "dolly_out"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    HANDHELD = "handheld"


CameraMoveLiteral = Literal[
    "static", "pan", "tilt", "dolly_in", "dolly_out", 
    "zoom_in", "zoom_out", "handheld"
]


# ============ TimeOfDay 时间段 ============

class TimeOfDay(str, Enum):
    """
    时间段枚举
    """
    DAY = "day"
    NIGHT = "night"
    DAWN = "dawn"
    DUSK = "dusk"


TimeOfDayLiteral = Literal["day", "night", "dawn", "dusk"]


# ============ Weather 天气 ============

class Weather(str, Enum):
    """
    天气枚举
    """
    CLEAR = "clear"
    RAINY = "rainy"
    CLOUDY = "cloudy"
    FOGGY = "foggy"
    SNOWY = "snowy"


WeatherLiteral = Literal["clear", "rainy", "cloudy", "foggy", "snowy"]


# ============ CameraHeight 机位高度 ============

class CameraHeight(str, Enum):
    """
    机位高度枚举
    """
    EYE = "eye"
    HIGH = "high"
    LOW = "low"


CameraHeightLiteral = Literal["eye", "high", "low"]


# ============ Role 角色类型 ============

class CharacterRole(str, Enum):
    """
    角色类型枚举
    """
    PROTAGONIST = "protagonist"
    SUPPORTING = "supporting"
    MINOR = "minor"
    UNKNOWN = "unknown"


CharacterRoleLiteral = Literal["protagonist", "supporting", "minor", "unknown"]


# ============ LocationType 地点类型 ============

class LocationType(str, Enum):
    """
    地点类型枚举
    """
    INTERIOR = "interior"
    EXTERIOR = "exterior"
    SEMI = "semi"


LocationTypeLiteral = Literal["interior", "exterior", "semi"]


# ============ 辅助函数 ============

def get_shot_type_description(shot_type: ShotType) -> str:
    """获取镜头类型的中文描述"""
    descriptions = {
        ShotType.ECU: "极特写 - 眼睛/细节/物品特写",
        ShotType.CU: "特写 - 面部表情",
        ShotType.MS: "中景 - 腰部以上",
        ShotType.LS: "远景 - 全身",
        ShotType.WS: "大远景 - 人物+环境",
        ShotType.OTS: "过肩 - 越肩视角",
    }
    return descriptions.get(shot_type, "未知")


def get_camera_move_description(camera_move: CameraMove) -> str:
    """获取运镜类型的中文描述"""
    descriptions = {
        CameraMove.STATIC: "静止",
        CameraMove.PAN: "摇摄 (左右)",
        CameraMove.TILT: "俯仰 (上下)",
        CameraMove.DOLLY_IN: "推 (靠近)",
        CameraMove.DOLLY_OUT: "拉 (远离)",
        CameraMove.ZOOM_IN: "变焦推",
        CameraMove.ZOOM_OUT: "变焦拉",
        CameraMove.HANDHELD: "手持 (微晃)",
    }
    return descriptions.get(camera_move, "未知")
