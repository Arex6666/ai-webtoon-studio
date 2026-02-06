"""
Draft QA Service (S3-05)

评估 AI 生成的 Draft 质量，检测问题，提供自动修复。
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Literal
from app.models.storyboard_draft import StoryboardDraft


class IssueSeverity(str, Enum):
    ERROR = "error"      # 必须修复
    WARNING = "warning"  # 建议修复
    INFO = "info"        # 提示信息


@dataclass
class QAIssue:
    """单个问题"""
    panel_index: int
    field: str
    severity: IssueSeverity
    message: str
    auto_fixable: bool = False
    suggested_fix: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "panel_index": self.panel_index,
            "field": self.field,
            "severity": self.severity.value,
            "message": self.message,
            "auto_fixable": self.auto_fixable,
            "suggested_fix": self.suggested_fix
        }


@dataclass
class QAResult:
    """QA 评估结果"""
    score: float  # 0-100
    issues: List[QAIssue] = field(default_factory=list)
    passed: bool = True
    
    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.ERROR)
    
    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == IssueSeverity.WARNING)
    
    @property
    def fixable_count(self) -> int:
        return sum(1 for i in self.issues if i.auto_fixable)
    
    def to_dict(self) -> Dict:
        return {
            "score": round(self.score, 1),
            "passed": self.passed,
            "error_count": self.error_count,
            "warning_count": self.warning_count,
            "fixable_count": self.fixable_count,
            "issues": [i.to_dict() for i in self.issues]
        }


class DraftQA:
    """
    Draft 质量评估服务
    
    评分权重：
    - 必填字段完整性: 30%
    - 约束合法性: 25%
    - 结构合理性: 25%
    - 完整性: 20%
    """
    
    # 有效的镜头类型
    VALID_SHOT_TYPES = {"ECU", "CU", "MCU", "MS", "MLS", "LS", "ELS", "OTS", "POV"}
    
    # 有效的镜头运动
    VALID_CAMERA_MOVES = {"static", "pan", "tilt", "zoom_in", "zoom_out", "dolly", "track", "crane"}
    
    # 有效的时间/天气
    VALID_TIME_OF_DAY = {"dawn", "morning", "noon", "afternoon", "evening", "dusk", "night", "day"}
    VALID_WEATHER = {"clear", "cloudy", "rainy", "snowy", "foggy", "stormy", "windy"}
    
    # 约束
    MIN_DURATION = 0.5
    MAX_DURATION = 15.0
    MIN_PANELS = 2
    MAX_PANELS = 50
    MAX_DIALOGUE_LENGTH = 200
    
    # 评分阈值
    PASS_THRESHOLD = 60.0
    
    def __init__(self):
        pass
    
    def evaluate(self, draft: StoryboardDraft) -> QAResult:
        """
        评估 Draft 质量
        
        Returns:
            QAResult 包含分数和问题列表
        """
        issues: List[QAIssue] = []
        panels = draft.panels_json or []
        
        if not panels:
            return QAResult(
                score=0,
                issues=[QAIssue(
                    panel_index=-1,
                    field="panels",
                    severity=IssueSeverity.ERROR,
                    message="没有生成任何分镜",
                    auto_fixable=False
                )],
                passed=False
            )
        
        # 检查面板数量
        if len(panels) < self.MIN_PANELS:
            issues.append(QAIssue(
                panel_index=-1,
                field="panels_count",
                severity=IssueSeverity.WARNING,
                message=f"分镜数量过少 ({len(panels)}), 建议至少 {self.MIN_PANELS} 个",
                auto_fixable=False
            ))
        
        if len(panels) > self.MAX_PANELS:
            issues.append(QAIssue(
                panel_index=-1,
                field="panels_count",
                severity=IssueSeverity.WARNING,
                message=f"分镜数量过多 ({len(panels)}), 建议不超过 {self.MAX_PANELS} 个",
                auto_fixable=False
            ))
        
        # 逐个检查每个 panel
        for i, panel in enumerate(panels):
            self._check_panel(i, panel, issues)
        
        # 计算分数
        score = self._calculate_score(panels, issues)
        passed = score >= self.PASS_THRESHOLD and not any(
            i.severity == IssueSeverity.ERROR for i in issues
        )
        
        return QAResult(score=score, issues=issues, passed=passed)
    
    def _check_panel(self, index: int, panel: Dict, issues: List[QAIssue]):
        """检查单个 panel"""
        
        # 1. 必填字段检查
        self._check_required_fields(index, panel, issues)
        
        # 2. 约束合法性检查
        self._check_constraints(index, panel, issues)
        
        # 3. 对白长度检查
        self._check_dialogue(index, panel, issues)
    
    def _check_required_fields(self, index: int, panel: Dict, issues: List[QAIssue]):
        """检查必填字段"""
        
        # shot_type
        shot = panel.get("shot", {})
        shot_type = shot.get("shotType")
        if not shot_type:
            issues.append(QAIssue(
                panel_index=index,
                field="shot.shotType",
                severity=IssueSeverity.ERROR,
                message="缺少镜头类型 (shot_type)",
                auto_fixable=True,
                suggested_fix="MS"  # 默认中景
            ))
        
        # duration
        duration = shot.get("durationSec")
        if duration is None:
            issues.append(QAIssue(
                panel_index=index,
                field="shot.durationSec",
                severity=IssueSeverity.ERROR,
                message="缺少时长 (duration)",
                auto_fixable=True,
                suggested_fix="3.0"
            ))
        
        # P0-SHOT-FIX-01: cameraMove 必填检查
        camera_move = shot.get("cameraMove")
        if not camera_move:
            issues.append(QAIssue(
                panel_index=index,
                field="shot.cameraMove",
                severity=IssueSeverity.WARNING,
                message="缺少镜头运动 (cameraMove)",
                auto_fixable=True,
                suggested_fix="static"  # 默认静止
            ))
        
        # location/scene
        scene = panel.get("scene", {})
        location = scene.get("location")
        if not location or location == "未指定":
            issues.append(QAIssue(
                panel_index=index,
                field="scene.location",
                severity=IssueSeverity.WARNING,
                message="未指定场景位置",
                auto_fixable=True,
                suggested_fix="室内"
            ))
        
        # description
        description = panel.get("description") or panel.get("action_description", "")
        if not description or len(description.strip()) < 5:
            issues.append(QAIssue(
                panel_index=index,
                field="description",
                severity=IssueSeverity.WARNING,
                message="动作描述过短或缺失",
                auto_fixable=False
            ))
    
    def _check_constraints(self, index: int, panel: Dict, issues: List[QAIssue]):
        """检查约束合法性"""
        
        shot = panel.get("shot", {})
        
        # shot_type 枚举
        shot_type = shot.get("shotType", "").upper()
        if shot_type and shot_type not in self.VALID_SHOT_TYPES:
            issues.append(QAIssue(
                panel_index=index,
                field="shot.shotType",
                severity=IssueSeverity.WARNING,
                message=f"无效的镜头类型: {shot_type}",
                auto_fixable=True,
                suggested_fix="MS"
            ))
        
        # duration 范围
        duration = shot.get("durationSec", 0)
        if isinstance(duration, (int, float)):
            if duration < self.MIN_DURATION:
                issues.append(QAIssue(
                    panel_index=index,
                    field="shot.durationSec",
                    severity=IssueSeverity.WARNING,
                    message=f"时长过短: {duration}s (最小 {self.MIN_DURATION}s)",
                    auto_fixable=True,
                    suggested_fix=str(self.MIN_DURATION)
                ))
            elif duration > self.MAX_DURATION:
                issues.append(QAIssue(
                    panel_index=index,
                    field="shot.durationSec",
                    severity=IssueSeverity.WARNING,
                    message=f"时长过长: {duration}s (最大 {self.MAX_DURATION}s)",
                    auto_fixable=True,
                    suggested_fix=str(self.MAX_DURATION)
                ))
        
        # camera move 枚举
        camera = panel.get("camera", {})
        camera_move = camera.get("move", "").lower()
        if camera_move and camera_move not in self.VALID_CAMERA_MOVES:
            issues.append(QAIssue(
                panel_index=index,
                field="camera.move",
                severity=IssueSeverity.INFO,
                message=f"未知的镜头运动: {camera_move}",
                auto_fixable=True,
                suggested_fix="static"
            ))
        
        # time_of_day 枚举
        scene = panel.get("scene", {})
        time_of_day = scene.get("timeOfDay", "").lower()
        if time_of_day and time_of_day not in self.VALID_TIME_OF_DAY:
            issues.append(QAIssue(
                panel_index=index,
                field="scene.timeOfDay",
                severity=IssueSeverity.INFO,
                message=f"未知的时间: {time_of_day}",
                auto_fixable=True,
                suggested_fix="day"
            ))
        
        # weather 枚举
        weather = scene.get("weather", "").lower()
        if weather and weather not in self.VALID_WEATHER:
            issues.append(QAIssue(
                panel_index=index,
                field="scene.weather",
                severity=IssueSeverity.INFO,
                message=f"未知的天气: {weather}",
                auto_fixable=True,
                suggested_fix="clear"
            ))
    
    def _check_dialogue(self, index: int, panel: Dict, issues: List[QAIssue]):
        """检查对白"""
        
        dialogues = panel.get("dialogue", [])
        for j, dlg in enumerate(dialogues):
            text = dlg.get("text", "")
            if len(text) > self.MAX_DIALOGUE_LENGTH:
                issues.append(QAIssue(
                    panel_index=index,
                    field=f"dialogue[{j}].text",
                    severity=IssueSeverity.WARNING,
                    message=f"对白过长 ({len(text)} 字), 建议不超过 {self.MAX_DIALOGUE_LENGTH} 字",
                    auto_fixable=True,
                    suggested_fix="考虑拆分为多个分镜"
                ))
    
    def _calculate_score(self, panels: List[Dict], issues: List[QAIssue]) -> float:
        """
        计算综合分数 (0-100)
        
        扣分规则：
        - ERROR: -10 分
        - WARNING: -5 分
        - INFO: -1 分
        """
        base_score = 100.0
        
        for issue in issues:
            if issue.severity == IssueSeverity.ERROR:
                base_score -= 10
            elif issue.severity == IssueSeverity.WARNING:
                base_score -= 5
            elif issue.severity == IssueSeverity.INFO:
                base_score -= 1
        
        return max(0, min(100, base_score))
    
    def auto_fix(self, draft: StoryboardDraft, issue_indices: Optional[List[int]] = None) -> Dict:
        """
        自动修复可修复的问题
        
        Args:
            draft: 要修复的 Draft
            issue_indices: 要修复的问题索引，None 表示全部
            
        Returns:
            修复结果
        """
        # 先评估获取问题列表
        result = self.evaluate(draft)
        fixable_issues = [i for i in result.issues if i.auto_fixable]
        
        if issue_indices is not None:
            fixable_issues = [
                i for j, i in enumerate(fixable_issues) 
                if j in issue_indices
            ]
        
        if not fixable_issues:
            return {"fixed_count": 0, "panels_modified": []}
        
        # 执行修复
        panels = draft.panels_json or []
        panels_modified = set()
        fixed_count = 0
        
        for issue in fixable_issues:
            if issue.panel_index < 0 or issue.panel_index >= len(panels):
                continue
            
            panel = panels[issue.panel_index]
            fixed = self._apply_fix(panel, issue)
            if fixed:
                fixed_count += 1
                panels_modified.add(issue.panel_index)
        
        # 更新 Draft
        draft.panels_json = panels
        
        return {
            "fixed_count": fixed_count,
            "panels_modified": sorted(panels_modified)
        }
    
    def _apply_fix(self, panel: Dict, issue: QAIssue) -> bool:
        """应用单个修复"""
        if not issue.suggested_fix:
            return False
        
        # 解析字段路径 (e.g., "shot.shotType")
        parts = issue.field.split(".")
        
        try:
            obj = panel
            for part in parts[:-1]:
                if "[" in part:
                    # 数组索引: dialogue[0]
                    name = part.split("[")[0]
                    idx = int(part.split("[")[1].rstrip("]"))
                    obj = obj.setdefault(name, [])
                    while len(obj) <= idx:
                        obj.append({})
                    obj = obj[idx]
                else:
                    obj = obj.setdefault(part, {})
            
            # 设置值
            final_key = parts[-1]
            if "[" in final_key:
                name = final_key.split("[")[0]
                obj[name] = issue.suggested_fix
            else:
                # 类型转换
                if issue.suggested_fix.replace(".", "").isdigit():
                    obj[final_key] = float(issue.suggested_fix)
                else:
                    obj[final_key] = issue.suggested_fix
            
            return True
        except Exception:
            return False


def get_draft_qa() -> DraftQA:
    """获取 DraftQA 实例"""
    return DraftQA()
