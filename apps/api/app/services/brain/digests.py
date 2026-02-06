"""
Digests - 输入上下文的 Hash 工具

用于保证：
1. 可复现同一次生成
2. 版本冲突/409 时解释来源
3. 顺序不同但内容相同 -> digest 相同（最关键）
"""
import hashlib
import json
from typing import Dict, Any, List, Optional


def digest_text(text: str, prefix_len: int = 16) -> str:
    """
    对文本做 SHA256 摘要
    
    Args:
        text: 输入文本
        prefix_len: 返回的摘要长度 (16-24)
    
    Returns:
        SHA256 摘要的前 N 位
    """
    if not text:
        return "empty_" + "0" * (prefix_len - 6)
    
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
    return digest[:prefix_len]


def digest_assets(assets_context: Dict[str, Any], prefix_len: int = 16) -> str:
    """
    对资产上下文做稳定化摘要
    
    关键：顺序不同但内容相同 -> digest 相同
    
    Args:
        assets_context: 资产上下文字典，包含 characters, scenes, styles 等
        prefix_len: 返回的摘要长度
    
    Returns:
        稳定化后的 SHA256 摘要
    """
    if not assets_context:
        return "empty_" + "0" * (prefix_len - 6)
    
    # 稳定化字典
    stable_dict = _stabilize_dict(assets_context)
    
    # 转换为稳定 JSON
    stable_json = json.dumps(stable_dict, sort_keys=True, ensure_ascii=False)
    
    digest = hashlib.sha256(stable_json.encode('utf-8')).hexdigest()
    return digest[:prefix_len]


def digest_enums(enums: Dict[str, List[str]], prefix_len: int = 16) -> str:
    """
    对枚举定义做稳定化摘要
    
    Args:
        enums: 枚举字典，如 {"shot_type": ["ECU", "CU", ...], "camera_move": [...]}
        prefix_len: 返回的摘要长度
    
    Returns:
        稳定化后的 SHA256 摘要
    """
    if not enums:
        return "empty_" + "0" * (prefix_len - 6)
    
    # 对每个枚举类型的值排序
    stable_enums = {}
    for key in sorted(enums.keys()):
        values = enums[key]
        if isinstance(values, list):
            stable_enums[key] = sorted(values)
        else:
            stable_enums[key] = values
    
    stable_json = json.dumps(stable_enums, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(stable_json.encode('utf-8')).hexdigest()
    return digest[:prefix_len]


def _stabilize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """
    稳定化字典：按 key 排序，对列表按特定字段排序
    """
    result = {}
    
    for key in sorted(d.keys()):
        value = d[key]
        
        if isinstance(value, dict):
            result[key] = _stabilize_dict(value)
        elif isinstance(value, list):
            result[key] = _stabilize_list(value)
        else:
            result[key] = value
    
    return result


def _stabilize_list(lst: List[Any]) -> List[Any]:
    """
    稳定化列表：如果是字典列表，按 id 或 name 排序
    """
    if not lst:
        return []
    
    # 检查是否是字典列表
    if isinstance(lst[0], dict):
        # 尝试按 id 排序
        if all('id' in item for item in lst):
            sorted_list = sorted(lst, key=lambda x: str(x.get('id', '')))
        # 尝试按 name 排序
        elif all('name' in item for item in lst):
            sorted_list = sorted(lst, key=lambda x: str(x.get('name', '')))
        # 尝试按 canonical_name 排序
        elif all('canonical_name' in item for item in lst):
            sorted_list = sorted(lst, key=lambda x: str(x.get('canonical_name', '')))
        else:
            sorted_list = lst
        
        return [_stabilize_dict(item) if isinstance(item, dict) else item for item in sorted_list]
    
    # 基本类型列表直接排序
    try:
        return sorted(lst)
    except TypeError:
        # 无法排序则保持原序
        return lst


# ============ 完整上下文摘要 ============

def digest_full_context(
    script_text: str,
    assets_context: Optional[Dict[str, Any]] = None,
    style_profile: Optional[Dict[str, Any]] = None,
    constraints: Optional[Dict[str, Any]] = None,
    prefix_len: int = 24
) -> str:
    """
    对完整上下文做摘要
    
    用于判断两次生成的输入是否完全相同
    """
    parts = [
        f"script:{digest_text(script_text)}"
    ]
    
    if assets_context:
        parts.append(f"assets:{digest_assets(assets_context)}")
    
    if style_profile:
        style_json = json.dumps(style_profile, sort_keys=True, ensure_ascii=False)
        parts.append(f"style:{hashlib.sha256(style_json.encode()).hexdigest()[:8]}")
    
    if constraints:
        constraints_json = json.dumps(constraints, sort_keys=True, ensure_ascii=False)
        parts.append(f"constraints:{hashlib.sha256(constraints_json.encode()).hexdigest()[:8]}")
    
    combined = "|".join(parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:prefix_len]


# ============ 枚举定义获取 ============

def get_current_enums() -> Dict[str, List[str]]:
    """
    获取当前系统的枚举定义
    
    从 brain/enums.py 获取
    """
    from app.schemas.brain.enums import (
        ShotType, CameraMove, TimeOfDay, Weather
    )
    
    return {
        "shot_type": [e.value for e in ShotType],
        "camera_move": [e.value for e in CameraMove],
        "time_of_day": [e.value for e in TimeOfDay],
        "weather": [e.value for e in Weather],
    }


def get_enum_digest() -> str:
    """获取当前枚举定义的摘要"""
    return digest_enums(get_current_enums())
