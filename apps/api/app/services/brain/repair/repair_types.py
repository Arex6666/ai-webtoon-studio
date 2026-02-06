"""
Repair Types - 错误模型与分类

定义 ValidationIssue 和 RepairPlan，用于结构化错误归因和修复跟踪。
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal, Dict, Any
from datetime import datetime
from enum import Enum


# ============ 错误代码枚举 ============

class IssueCode(str, Enum):
    """错误代码"""
    # 结构性错误
    MISSING_FIELD = "missing_field"  # 缺少必须字段
    INVALID_TYPE = "invalid_type"  # 类型错误
    ENUM_INVALID = "enum_invalid"  # 枚举值非法
    
    # 约束性错误
    TOO_SHORT = "too_short"  # 内容过短
    TOO_LONG = "too_long"  # 内容过长
    OUT_OF_RANGE = "out_of_range"  # 数值超出范围
    INSUFFICIENT_ITEMS = "insufficient_items"  # 列表项不足
    
    # 业务性错误
    BAD_SPAN = "bad_span"  # source_span.quote 问题
    TOO_SHALLOW = "too_shallow"  # 细节不足
    DUPLICATE_REF = "duplicate_ref"  # 重复引用
    UNRESOLVED_REF = "unresolved_ref"  # 未定义引用
    
    # 格式错误
    INVALID_JSON = "invalid_json"  # JSON 解析失败
    SCHEMA_MISMATCH = "schema_mismatch"  # schema_version 不匹配


# ============ 验证问题 ============

class ValidationIssue(BaseModel):
    """
    验证问题 - 单个错误或警告
    
    设计用于：
    1. 结构化错误归因
    2. 指导 LLM 修复
    3. 前端展示
    """
    code: str = Field(
        ...,
        description="错误代码 (如 missing_field, enum_invalid)"
    )
    path: str = Field(
        ...,
        description="Pydantic 错误路径 (如 panels.3.composition_notes)"
    )
    message: str = Field(
        ...,
        description="人类可读的错误描述"
    )
    severity: Literal["error", "warn"] = Field(
        default="error",
        description="严重程度: error=阻塞, warn=建议"
    )
    hint: Optional[str] = Field(
        default=None,
        description="修复提示 (给 LLM 或人类)"
    )
    
    # 额外上下文
    expected: Optional[str] = None
    actual: Optional[str] = None
    
    def to_prompt_line(self) -> str:
        """转换为提示词行（用于 repair prompt）"""
        line = f"- [{self.severity.upper()}] {self.path}: {self.message}"
        if self.hint:
            line += f"\n  提示: {self.hint}"
        return line


# ============ 修复计划 ============

class RepairPlan(BaseModel):
    """
    修复计划 - 汇总所有问题和修复状态
    """
    issues: List[ValidationIssue] = Field(default_factory=list)
    
    # 修复状态
    can_auto_fix: bool = Field(
        default=True,
        description="是否可以自动修复 (所有 issues 都有 hint)"
    )
    attempts_used: int = Field(
        default=0,
        description="已使用的修复尝试次数"
    )
    max_attempts: int = Field(
        default=3,
        description="最大尝试次数"
    )
    final_status: Literal["pending", "ok", "repaired", "failed"] = Field(
        default="pending",
        description="最终状态"
    )
    
    # 追溯
    original_json: Optional[Dict[str, Any]] = None
    repaired_json: Optional[Dict[str, Any]] = None
    repair_history: List[Dict[str, Any]] = Field(default_factory=list)
    
    # 时间戳
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")
    
    @property
    def warn_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warn")
    
    @property
    def is_valid(self) -> bool:
        return self.error_count == 0
    
    def to_prompt_section(self) -> str:
        """转换为提示词部分（用于 repair prompt）"""
        if not self.issues:
            return "无校验问题"
        
        lines = ["## 需要修复的问题\n"]
        
        # 按路径分组
        errors = [i for i in self.issues if i.severity == "error"]
        warns = [i for i in self.issues if i.severity == "warn"]
        
        if errors:
            lines.append("### 必须修复 (Error)\n")
            for issue in errors:
                lines.append(issue.to_prompt_line())
        
        if warns:
            lines.append("\n### 建议修复 (Warning)\n")
            for issue in warns:
                lines.append(issue.to_prompt_line())
        
        return "\n".join(lines)
    
    def add_attempt(self, result_json: Optional[Dict], remaining_issues: List[ValidationIssue]):
        """记录一次修复尝试"""
        self.attempts_used += 1
        self.repair_history.append({
            "attempt": self.attempts_used,
            "timestamp": datetime.utcnow().isoformat(),
            "issues_before": len(self.issues),
            "issues_after": len(remaining_issues),
            "result_json_keys": list(result_json.keys()) if result_json else []
        })
        self.issues = remaining_issues
        if result_json:
            self.repaired_json = result_json


# ============ 便捷函数 ============

def create_issue(
    code: str,
    path: str,
    message: str,
    severity: str = "error",
    hint: Optional[str] = None,
    expected: Optional[str] = None,
    actual: Optional[str] = None
) -> ValidationIssue:
    """创建验证问题"""
    return ValidationIssue(
        code=code,
        path=path,
        message=message,
        severity=severity,
        hint=hint,
        expected=expected,
        actual=actual
    )


def pydantic_error_to_issues(validation_error) -> List[ValidationIssue]:
    """
    将 Pydantic ValidationError 转换为 ValidationIssue 列表
    """
    issues = []
    
    for error in validation_error.errors():
        # 构建路径
        path = ".".join(str(p) for p in error.get("loc", []))
        
        # 映射错误类型
        error_type = error.get("type", "")
        if "missing" in error_type:
            code = IssueCode.MISSING_FIELD.value
        elif "enum" in error_type:
            code = IssueCode.ENUM_INVALID.value
        elif "type" in error_type:
            code = IssueCode.INVALID_TYPE.value
        elif "min_length" in error_type or "too_short" in error_type:
            code = IssueCode.TOO_SHORT.value
        elif "max_length" in error_type or "too_long" in error_type:
            code = IssueCode.TOO_LONG.value
        elif "greater_than" in error_type or "less_than" in error_type:
            code = IssueCode.OUT_OF_RANGE.value
        else:
            code = "validation_error"
        
        # 生成 hint
        hint = _generate_hint(code, path, error)
        
        issues.append(ValidationIssue(
            code=code,
            path=path,
            message=error.get("msg", "Validation error"),
            severity="error",
            hint=hint,
            expected=str(error.get("ctx", {}).get("expected", ""))[:100] if error.get("ctx") else None,
            actual=str(error.get("input", ""))[:100] if error.get("input") else None
        ))
    
    return issues


def _generate_hint(code: str, path: str, error: Dict) -> str:
    """根据错误类型生成修复提示"""
    hints = {
        IssueCode.MISSING_FIELD.value: f"请添加缺失的字段 '{path.split('.')[-1]}'",
        IssueCode.ENUM_INVALID.value: f"请使用合法的枚举值，参考枚举白名单",
        IssueCode.TOO_SHORT.value: f"请增加内容长度，当前内容过短",
        IssueCode.TOO_LONG.value: f"请缩减内容长度，当前内容过长",
        IssueCode.OUT_OF_RANGE.value: f"请调整数值到有效范围内",
        IssueCode.INSUFFICIENT_ITEMS.value: f"请添加更多项目到列表中",
    }
    return hints.get(code, f"请检查并修复路径 {path} 的问题")
