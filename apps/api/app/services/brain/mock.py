# Mock Brain Service - 开发/测试用
import asyncio
import random
import re
import logging
from typing import Dict, Any, List, Optional

from .base import (
    BaseBrainService, 
    ParsedPanel, 
    ContinuityIssue, 
    ScriptParseResult, 
    ContinuityCheckResult
)

logger = logging.getLogger(__name__)


class MockBrainService(BaseBrainService):
    """Mock LLM 服务 - 模拟脚本解析和智能建议"""
    
    async def analyze_script(self, script_text: str) -> List[Dict[str, Any]]:
        """简单脚本分析（旧版兼容）"""
        await asyncio.sleep(0.3)
        paragraphs = [p.strip() for p in script_text.split("\n\n") if p.strip()]
        if not paragraphs:
            paragraphs = [p.strip() for p in script_text.split("\n") if p.strip()]
        
        return [
            {
                "order": i, 
                "action_description": para, 
                "shot_type": random.choice(["close", "medium", "full", "wide"]),
                "emotion": random.choice(["neutral", "happy", "sad", "angry"])
            } 
            for i, para in enumerate(paragraphs[:10])
        ]

    async def parse_script(
        self, 
        script_text: str, 
        style_hint: Optional[str] = None
    ) -> ScriptParseResult:
        """
        解析剧本为分镜（增强版）
        支持：
        - 一句话生成多个分镜
        - 完整剧本解析
        - 角色/场景自动检测
        """
        await asyncio.sleep(0.5)
        
        script_text = script_text.strip()
        panels: List[ParsedPanel] = []
        detected_characters: set = set()
        detected_scenes: set = set()
        
        # 景别和情绪选项
        shot_types = ["extreme_close", "close", "medium", "full", "wide", "extreme_wide"]
        emotions = ["neutral", "happy", "sad", "angry", "surprised", "fear", "contempt"]
        
        # 判断是一句话还是完整剧本
        is_short = len(script_text) < 150 and "\n" not in script_text
        
        if is_short:
            # 一句话模式：生成 3-5 个分镜
            panels = self._generate_panels_from_sentence(script_text, shot_types, emotions)
            # 从句子中提取可能的角色和场景
            detected_characters, detected_scenes = self._extract_entities_from_text(script_text)
        else:
            # 完整剧本模式：按段落解析
            paragraphs = [p.strip() for p in script_text.split("\n\n") if p.strip()]
            if not paragraphs:
                paragraphs = [p.strip() for p in script_text.split("\n") if p.strip()]
            
            for i, para in enumerate(paragraphs[:20]):
                panel, chars, scenes = self._parse_paragraph(i, para, shot_types, emotions)
                panels.append(panel)
                detected_characters.update(chars)
                detected_scenes.update(scenes)
        
        # 添加检测到的角色/场景引用到分镜
        char_list = list(detected_characters)
        scene_list = list(detected_scenes)
        
        for panel in panels:
            # 随机分配角色到分镜
            if char_list:
                panel.character_refs = random.sample(char_list, min(2, len(char_list)))
            # 分配场景
            if scene_list:
                panel.scene_ref = random.choice(scene_list)
        
        # 计算总时长
        total_duration = sum(p.suggested_duration for p in panels)
        
        logger.info(f"Mock Brain: Parsed script into {len(panels)} panels, "
                   f"detected {len(detected_characters)} characters, "
                   f"{len(detected_scenes)} scenes")
        
        return ScriptParseResult(
            panels=panels,
            detected_characters=list(detected_characters),
            detected_scenes=list(detected_scenes),
            total_duration=total_duration,
            continuity_issues=[]
        )
    
    def _generate_panels_from_sentence(
        self, 
        sentence: str,
        shot_types: List[str],
        emotions: List[str]
    ) -> List[ParsedPanel]:
        """从一句话生成多个分镜"""
        panels = []
        
        # 1. 开场 - 远景建立环境
        panels.append(ParsedPanel(
            panel_index=0,
            action_description=f"建立镜头：{sentence[:50]}...",
            shot_type="wide",
            emotion="neutral",
            suggested_duration=2.5
        ))
        
        # 2. 主要动作 - 中景
        panels.append(ParsedPanel(
            panel_index=1,
            action_description=sentence,
            shot_type="medium",
            emotion=random.choice(emotions),
            suggested_duration=3.0
        ))
        
        # 3. 如果有对话，检测并添加对话分镜
        dialogue_match = re.search(r'["""「『]([^"""」』]+)["""」』]', sentence)
        if dialogue_match:
            dialogue_text = dialogue_match.group(1)
            panels.append(ParsedPanel(
                panel_index=2,
                action_description="对话特写",
                dialogue=dialogue_text,
                shot_type="close",
                emotion=self._detect_emotion(dialogue_text),
                suggested_duration=2.0
            ))
        
        # 4. 反应镜头 - 近景
        panels.append(ParsedPanel(
            panel_index=len(panels),
            action_description="反应镜头",
            shot_type="close",
            emotion=random.choice(emotions),
            suggested_duration=1.5
        ))
        
        return panels
    
    def _parse_paragraph(
        self, 
        index: int, 
        para: str,
        shot_types: List[str],
        emotions: List[str]
    ) -> tuple:
        """解析单个段落"""
        characters = set()
        scenes = set()
        
        # 提取对话
        dialogue = None
        dialogue_match = re.search(r'["""「『]([^"""」』]+)["""」』]', para)
        if dialogue_match:
            dialogue = dialogue_match.group(1)
        
        # 提取角色和场景
        chars, scns = self._extract_entities_from_text(para)
        characters.update(chars)
        scenes.update(scns)
        
        # 根据内容选择景别
        shot_type = self._suggest_shot_type(para)
        emotion = self._detect_emotion(para)
        
        # 计算建议时长
        duration = 2.0
        if dialogue:
            duration += len(dialogue) * 0.05  # 每字约 0.05 秒
        if len(para) > 100:
            duration += 0.5
        
        panel = ParsedPanel(
            panel_index=index,
            action_description=para[:200] if len(para) > 200 else para,
            dialogue=dialogue,
            shot_type=shot_type,
            emotion=emotion,
            characters=list(characters),
            suggested_duration=min(duration, 5.0)
        )
        
        return panel, characters, scenes
    
    def _extract_entities_from_text(self, text: str) -> tuple:
        """从文本中提取角色和场景"""
        characters = set()
        scenes = set()
        
        # 角色检测模式
        char_patterns = [
            r"(男主|女主|主角|男一|女一)",
            r"([A-Z][a-z]+)",  # 英文名
            r"(小[明红丽华强])|(老[王李张])",  # 常见中文名
            r"([\u4e00-\u9fa5]{2,3})(?:说|道|问|答|笑|哭|看|走|跑|站|坐)"  # 动词前的名字
        ]
        
        for pattern in char_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    for m in match:
                        if m:
                            characters.add(m)
                elif match:
                    characters.add(match)
        
        # 场景检测模式
        scene_patterns = [
            r"(咖啡厅|餐厅|公司|办公室|学校|教室|医院|公园|街道|家里|客厅|卧室|厨房|阳台)",
            r"([\u4e00-\u9fa5]{2,4})(?:里|内|外|上|下|中)"
        ]
        
        for pattern in scene_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if isinstance(match, tuple):
                    for m in match:
                        if m:
                            scenes.add(m)
                elif match:
                    scenes.add(match)
        
        # 默认值
        if not characters:
            characters = {"角色A", "角色B"}
        if not scenes:
            scenes = {"场景1"}
        
        return characters, scenes
    
    def _suggest_shot_type(self, text: str) -> str:
        """根据文本内容建议景别"""
        if any(kw in text for kw in ["表情", "眼神", "嘴角", "眉头", "脸"]):
            return "extreme_close"
        if any(kw in text for kw in ["说", "道", "问", "答", "对话"]):
            return "close"
        if any(kw in text for kw in ["走", "跑", "站", "坐", "动作"]):
            return "medium"
        if any(kw in text for kw in ["人群", "全景", "环境"]):
            return "wide"
        if any(kw in text for kw in ["城市", "天空", "远方", "风景"]):
            return "extreme_wide"
        return "medium"
    
    def _detect_emotion(self, text: str) -> str:
        """检测文本情绪"""
        if any(kw in text for kw in ["笑", "开心", "高兴", "快乐", "喜悦"]):
            return "happy"
        if any(kw in text for kw in ["哭", "伤心", "难过", "悲伤", "痛苦"]):
            return "sad"
        if any(kw in text for kw in ["怒", "生气", "愤怒", "恼火"]):
            return "angry"
        if any(kw in text for kw in ["惊", "震惊", "吃惊", "意外"]):
            return "surprised"
        if any(kw in text for kw in ["怕", "害怕", "恐惧", "紧张"]):
            return "fear"
        return "neutral"

    async def suggest_bubble_positions(
        self, 
        panel_spec: Dict[str, Any], 
        layer_bbox: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """建议气泡位置"""
        await asyncio.sleep(0.2)
        
        bubbles = panel_spec.get("dialogue", []) or panel_spec.get("bubbles", [])
        suggestions = []
        
        # 获取角色边界框
        char_bbox = layer_bbox.get("char_bbox", {"x": 0.3, "y": 0.2, "width": 0.4, "height": 0.6})
        
        for i, bubble in enumerate(bubbles):
            bubble_type = bubble.get("type", bubble.get("style", "speech"))
            
            # 根据气泡类型和角色位置计算建议位置
            if bubble_type == "thought":
                x = char_bbox.get("x", 0.3) + char_bbox.get("width", 0.4) / 2
                y = max(0.05, char_bbox.get("y", 0.2) - 0.15)
            elif bubble_type == "narration":
                x = 0.5
                y = 0.05 if i % 2 == 0 else 0.85
            else:
                if char_bbox.get("x", 0.3) < 0.5:
                    x = char_bbox.get("x", 0.3) + char_bbox.get("width", 0.4) + 0.05
                else:
                    x = char_bbox.get("x", 0.3) - 0.25
                y = char_bbox.get("y", 0.2) + 0.1
            
            suggestions.append({
                "dialogue_id": bubble.get("id", f"bubble_{i}"),
                "suggested_x": min(0.9, max(0.1, x)),
                "suggested_y": min(0.9, max(0.05, y)),
                "suggested_width": 0.25 if bubble_type == "narration" else 0.2,
                "confidence": random.uniform(0.7, 0.95)
            })
        
        return suggestions

    async def enhance_prompt(self, base_prompt: str, style: str) -> str:
        """增强提示词"""
        await asyncio.sleep(0.1)
        
        style_additions = {
            "korean_webtoon": "korean webtoon style, clean lineart, soft shading, vibrant colors",
            "manga": "manga style, detailed linework, dramatic shadows, screentone",
            "manhwa": "manhwa style, romantic atmosphere, pastel colors",
            "comic": "western comic book style, bold colors, dynamic composition"
        }
        
        quality = "masterpiece, best quality, highly detailed, sharp focus"
        style_prompt = style_additions.get(style, style_additions["korean_webtoon"])
        
        return f"{base_prompt}, {style_prompt}, {quality}"

    async def qa_analyze(
        self, 
        panel_spec: Dict[str, Any], 
        rendered_images: List[str]
    ) -> Dict[str, Any]:
        """质量分析"""
        await asyncio.sleep(0.3)
        
        overall_score = random.uniform(0.75, 0.98)
        issues = []
        
        possible_issues = [
            {"type": "white_edge", "severity": "warning", "description": "人物边缘有轻微白边"},
            {"type": "low_resolution", "severity": "info", "description": "部分区域细节略糊"},
            {"type": "composition", "severity": "info", "description": "构图可以更紧凑"},
            {"type": "face_drift", "severity": "warning", "description": "人脸与参考图有轻微偏差"},
        ]
        
        if overall_score < 0.85:
            issues = random.sample(possible_issues, k=random.randint(1, 2))
        
        return {
            "overall_score": overall_score,
            "consistency_score": random.uniform(0.8, 1.0),
            "segmentation_score": random.uniform(0.7, 1.0),
            "composition_score": random.uniform(0.75, 1.0),
            "style_score": random.uniform(0.8, 1.0),
            "issues": issues,
            "needs_manual_fix": overall_score < 0.7,
            "passed": overall_score >= 0.7
        }

    async def check_continuity(
        self, 
        panels: List[Dict[str, Any]], 
        characters: Optional[Dict[str, Any]] = None, 
        scenes: Optional[Dict[str, Any]] = None
    ) -> ContinuityCheckResult:
        """检测连续性"""
        await asyncio.sleep(0.3)
        
        issues = []
        
        # 模拟检测一些连续性问题
        if len(panels) > 3 and random.random() < 0.3:
            issues.append(ContinuityIssue(
                panel_index=2,
                panel_ids=["panel_2", "panel_3"],
                type="weather_change",
                severity="warning",
                description="天气从晴天突然变成雨天，缺少过渡",
                suggestion="添加天气变化的过渡镜头"
            ))
        
        if len(panels) > 5 and random.random() < 0.2:
            issues.append(ContinuityIssue(
                panel_index=4,
                panel_ids=["panel_4", "panel_5"],
                type="costume_change",
                severity="error",
                description="角色服装在同一场景中发生变化",
                suggestion="检查角色服装一致性"
            ))
        
        return ContinuityCheckResult(
            is_valid=len(issues) == 0,
            issues=issues,
            auto_fix_available=any(i.type == "weather_change" for i in issues),
            suggested_fixes=[]
        )

    async def suggest_fix(
        self, 
        issue: ContinuityIssue, 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """建议修复方案"""
        await asyncio.sleep(0.2)
        
        fix_map = {
            "weather_change": {
                "action": "add_transition",
                "message": "建议在两个分镜之间添加天气变化的过渡镜头",
                "auto_apply": True
            },
            "costume_change": {
                "action": "update_character",
                "message": "建议统一角色服装，保持场景一致性",
                "auto_apply": False
            },
            "face_drift": {
                "action": "regenerate",
                "message": "建议提高 FaceID 权重后重新生成",
                "params": {"faceid_strength": 0.9},
                "auto_apply": True
            }
        }
        
        return fix_map.get(issue.type, {
            "action": "manual_review",
            "message": "需要手动检查和修复",
            "auto_apply": False
        })
