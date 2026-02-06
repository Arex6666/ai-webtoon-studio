"""
ComfyUI Workflow 模板管理与参数注入
"""
import json
import re
import os
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Workflow 模板目录
WORKFLOWS_DIR = Path(__file__).parent / "workflows"


class WorkflowBuilder:
    """Workflow 模板加载与参数注入"""
    
    def __init__(self):
        self.templates: Dict[str, Dict] = {}
        self._load_templates()
    
    def _load_templates(self):
        """加载所有 workflow 模板"""
        if not WORKFLOWS_DIR.exists():
            WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
            return
        
        for file in WORKFLOWS_DIR.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    template = json.load(f)
                    name = file.stem
                    self.templates[name] = template
                    logger.info(f"Loaded workflow template: {name}")
            except Exception as e:
                logger.warning(f"Failed to load workflow {file}: {e}")
    
    def get_template_names(self) -> list:
        """获取所有模板名称"""
        return list(self.templates.keys())
    
    def build_workflow(
        self,
        template_name: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        构建 workflow，注入参数
        
        Args:
            template_name: 模板名称 (如 "flux_basic")
            params: 参数字典 (positive_prompt, seed, width, height, etc.)
        
        Returns:
            可提交到 ComfyUI 的 workflow JSON
        """
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found. Available: {self.get_template_names()}")
        
        template = self.templates[template_name]
        nodes = template.get("nodes", {})
        defaults = template.get("defaults", {})
        
        # 合并默认值和传入参数
        merged_params = {**defaults, **params}
        
        # 深拷贝节点并注入参数
        workflow = {}
        for node_id, node_data in nodes.items():
            workflow[node_id] = self._inject_params(node_data, merged_params)
        
        return workflow
    
    def _inject_params(self, data: Any, params: Dict[str, Any]) -> Any:
        """递归注入参数"""
        if isinstance(data, dict):
            return {k: self._inject_params(v, params) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._inject_params(item, params) for item in data]
        elif isinstance(data, str):
            # 检查是否是模板变量 {{key}}
            match = re.match(r"^\{\{(\w+)\}\}$", data)
            if match:
                key = match.group(1)
                return params.get(key, data)
            # 替换字符串中的模板变量
            def replace(m):
                key = m.group(1)
                return str(params.get(key, m.group(0)))
            return re.sub(r"\{\{(\w+)\}\}", replace, data)
        else:
            return data


# 全局实例
_workflow_builder: Optional[WorkflowBuilder] = None


def get_workflow_builder() -> WorkflowBuilder:
    """获取 WorkflowBuilder 单例"""
    global _workflow_builder
    if _workflow_builder is None:
        _workflow_builder = WorkflowBuilder()
    return _workflow_builder


def build_flux_workflow(
    positive_prompt: str,
    negative_prompt: str = "",
    width: int = 1080,
    height: int = 1920,
    seed: int = 42,
    steps: int = 20,
    sampler: str = "euler",
    scheduler: str = "normal",
) -> Dict[str, Any]:
    """
    构建 Flux 生成 workflow
    
    便捷函数，直接返回可提交的 workflow
    """
    builder = get_workflow_builder()
    
    return builder.build_workflow("flux_basic", {
        "positive_prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
        "seed": seed,
        "steps": steps,
        "sampler": sampler,
        "scheduler": scheduler,
    })
