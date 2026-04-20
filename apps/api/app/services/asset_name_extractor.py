"""
Asset name extraction helpers.

Normalize character/scene names from storyboard panels so we do not
accidentally create assets from dialogue fragments or verbose scene descriptions.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, List, Optional, Sequence, Tuple

from app.services.brain.scene_resolver import get_scene_resolver

_CHAR_SPLIT_RE = re.compile(r"[，,、/|；;]+")
_CHAR_PREFIX_RE = re.compile(r"^(?:角色|人物|姓名|name|character)\s*[:：]\s*", re.IGNORECASE)
_SCENE_PREFIX_RE = re.compile(r"^(?:场景|地点|背景|scene)\s*[:：]\s*", re.IGNORECASE)
_SCENE_TIME_PREFIX_RE = re.compile(
    r"^(?:在|于)?(?:凌晨|清晨|早晨|上午|中午|下午|傍晚|黄昏|夜晚|深夜|白天|黎明|雨夜|雪夜|雨天|晴天|阴天)+(?:时分|时候|时|之际)?"
)
_CHAR_VALID_RE = re.compile(r"^[\u4e00-\u9fffA-Za-z·'`\- ]{2,20}$")
_SCENE_PLACEHOLDER_RE = re.compile(r"^(?:场景|地点|背景)\s*\d+$")
_SCENE_FIELD_RE = re.compile(r"(?:地点|场景|位置)\s*[:：]\s*([^；;。]+)")
_SCENE_CORE_RE = re.compile(
    r"([\u4e00-\u9fffA-Za-z0-9]{2,20}?(?:书店|咖啡厅|办公室|教室|厨房|客厅|卧室|阳台|公园|医院|学校|公司|街道|巷子|巷|店|铺|馆|室|厅|街|路|楼|房|院|园|站|桥|门))"
)

_CHAR_PLACEHOLDERS = {
    "角色", "人物", "角色a", "角色b", "人物a", "人物b",
    "主角", "男主", "女主", "路人", "群众",
    "他", "她", "他们", "她们", "我", "你", "我们",
    "unknown", "none", "n/a",
}
_SCENE_STOPWORDS = {"未指定", "未知", "场景", "地点", "背景", "scene", "时间"}
_CHAR_ACTION_SUFFIXES = (
    "说", "道", "问", "答", "笑", "哭", "看", "走", "跑", "站", "坐", "想", "听", "喊"
)
_SCENE_COMMON_NAMES = {
    "家里", "家中", "室内", "户外", "街道", "巷子", "学校", "医院", "公园", "办公室",
    "教室", "厨房", "客厅", "卧室", "阳台", "天台", "车站",
}
_SCENE_LOCATION_KEYWORDS = (
    "店", "铺", "馆", "室", "厅", "街", "巷", "路", "楼", "房", "院", "园", "站", "桥", "门", "校", "城", "村"
)

_scene_resolver = None


def _get_scene_resolver():
    global _scene_resolver
    if _scene_resolver is None:
        _scene_resolver = get_scene_resolver()
    return _scene_resolver


def _dedupe_preserve_order(values: Iterable[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _split_raw_values(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        values: List[str] = []
        for item in raw:
            values.extend(_split_raw_values(item))
        return values
    text = str(raw).strip()
    if not text:
        return []
    parts = [p.strip() for p in _CHAR_SPLIT_RE.split(text) if p.strip()]
    return parts if parts else [text]


def _split_scene_values(raw: Any) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, (list, tuple, set)):
        values: List[str] = []
        for item in raw:
            values.extend(_split_scene_values(item))
        return values
    text = str(raw).strip()
    if not text:
        return []
    return [text]


def _looks_like_scene_location(value: str) -> bool:
    if value in _SCENE_COMMON_NAMES:
        return True
    return any(keyword in value for keyword in _SCENE_LOCATION_KEYWORDS)


def _merge_scene_name_variants(names: List[str]) -> List[str]:
    merged: List[str] = []
    for name in names:
        replaced = False
        for idx, existing in enumerate(merged):
            if name == existing:
                replaced = True
                break
            if name in existing and len(name) >= 2:
                merged[idx] = name
                replaced = True
                break
            if existing in name and len(existing) >= 2:
                replaced = True
                break
        if not replaced:
            merged.append(name)
    return merged


def sanitize_character_name(raw_name: Any) -> Optional[str]:
    if raw_name is None:
        return None

    name = str(raw_name).strip()
    if not name:
        return None

    name = name.strip("\"'`“”‘’[]【】（）() ")
    name = _CHAR_PREFIX_RE.sub("", name).strip()
    name = re.sub(r"[（(].*?[)）]$", "", name).strip()
    name = re.sub(r"[。.!！？?：:；;]+$", "", name).strip()
    if not name:
        return None

    lowered = name.lower()
    if lowered in _CHAR_PLACEHOLDERS:
        return None
    if re.fullmatch(r"(?:角色|人物)\s*[A-Za-z0-9一二三四五六七八九十]+", name):
        return None
    if any(ch.isdigit() for ch in name):
        return None
    if name.endswith(_CHAR_ACTION_SUFFIXES):
        return None
    if any(token in name for token in ("时分", "镜头", "场景", "光线", "天气", "对白")):
        return None
    if not _CHAR_VALID_RE.fullmatch(name):
        return None
    if re.fullmatch(r"[\u4e00-\u9fff]+", name) and len(name) > 6:
        return None

    return name


def sanitize_character_names(raw_names: Iterable[Any]) -> List[str]:
    cleaned: List[str] = []
    for raw_name in raw_names or []:
        for name_part in _split_raw_values(raw_name):
            normalized = sanitize_character_name(name_part)
            if normalized:
                cleaned.append(normalized)
    return _dedupe_preserve_order(cleaned)


def sanitize_scene_name(raw_scene: Any) -> Optional[str]:
    if raw_scene is None:
        return None

    scene = str(raw_scene).strip()
    if not scene:
        return None

    scene = scene.strip("\"'`“”‘’[]【】（）() ")
    scene = _SCENE_PREFIX_RE.sub("", scene).strip()
    scene = re.sub(r"[。.!！？?]+$", "", scene).strip()
    if not scene:
        return None

    location_match = _SCENE_FIELD_RE.search(scene)
    if location_match:
        candidate = location_match.group(1).strip()
        candidate = re.split(r"[，,](?:光线|氛围|背景|天气|时间|构图|镜头|色调)\s*[:：]?", candidate)[0].strip()
        candidate = re.split(r"[；;。]", candidate)[0].strip()
    else:
        # 先在整句里抓一次“地点类名词”，避免复杂模板文本解析失败
        core_any_match = _SCENE_CORE_RE.search(scene)
        if core_any_match:
            candidate = core_any_match.group(1).strip()
        else:
            candidate = ""

        parsed = _get_scene_resolver().parse_scene_description(scene)
        if not candidate:
            candidate = (parsed.get("base_location") or "").strip()
        if not candidate:
            candidate = re.split(r"[，,：:；;。]", scene)[0].strip()

    candidate = re.split(r"[，,、/|]", candidate)[0].strip()
    candidate = re.split(r"(?:和|与|及)", candidate)[0].strip()

    candidate = re.sub(r"^(?:在|于|到|从|镜头切到|画面来到|来到|位于)", "", candidate).strip()
    candidate = _SCENE_TIME_PREFIX_RE.sub("", candidate).strip("，,：: ")
    candidate = re.sub(r"^的+", "", candidate).strip()
    candidate = re.sub(r"(?:光线|氛围|背景|构图).*$", "", candidate).strip("，,：: ")

    # 统一「教室里/教室内/教室外」这种方位后缀，保留基础地点
    if candidate.endswith(("里", "内", "外")) and len(candidate) > 2:
        candidate = candidate[:-1]

    if "的" in candidate:
        tail = candidate.split("的")[-1].strip()
        if tail and _looks_like_scene_location(tail):
            candidate = tail

    core_match = _SCENE_CORE_RE.search(candidate)
    if core_match:
        candidate = core_match.group(1).strip()

    if not candidate:
        return None
    if candidate in _SCENE_STOPWORDS:
        return None
    if _SCENE_PLACEHOLDER_RE.fullmatch(candidate):
        return None
    if len(candidate) > 20:
        return None
    if any(token in candidate for token in ("时分", "镜头", "对白")):
        return None
    if not _looks_like_scene_location(candidate):
        return None

    return candidate


def sanitize_scene_names(raw_scenes: Iterable[Any]) -> List[str]:
    cleaned: List[str] = []
    for raw_scene in raw_scenes or []:
        for scene_part in _split_scene_values(raw_scene):
            normalized = sanitize_scene_name(scene_part)
            if normalized:
                cleaned.append(normalized)

    deduped = _dedupe_preserve_order(cleaned)
    if not deduped:
        return []

    normalized_scenes = _get_scene_resolver().normalize_locations(
        [{"canonical_location": name, "anchor_hint": name} for name in deduped]
    )
    names = [
        (item.get("canonical_location") or "").strip()
        for item in normalized_scenes
    ]
    compact = _dedupe_preserve_order([name for name in names if name])
    return _merge_scene_name_variants(compact)


def extract_asset_names_from_panels(panels: Sequence[dict]) -> Tuple[List[str], List[str]]:
    character_candidates: List[Any] = []
    scene_candidates: List[Any] = []

    for panel_data in panels or []:
        if not isinstance(panel_data, dict):
            continue

        characters = panel_data.get("characters", [])
        if isinstance(characters, dict):
            characters = [characters]
        elif isinstance(characters, str):
            characters = [characters]

        for char in characters or []:
            if isinstance(char, dict):
                name = char.get("name") or char.get("character_id")
            else:
                name = char
            if name:
                character_candidates.append(name)

        scene = panel_data.get("scene")
        if isinstance(scene, dict):
            scene_name = scene.get("location") or scene.get("name") or scene.get("scene_id")
        else:
            scene_name = scene

        if scene_name and scene_name != "未指定":
            scene_candidates.append(scene_name)

    return (
        sanitize_character_names(character_candidates),
        sanitize_scene_names(scene_candidates),
    )
