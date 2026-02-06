"""
ToolRegistry - 工具注册表
管理智能体可以调用的工具/函数
"""
import logging
from typing import Dict, Any, List, Callable, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ToolParameter(BaseModel):
    """工具参数定义"""
    name: str
    type: str  # string, int, float, bool, list, dict
    description: str
    required: bool = True
    default: Optional[Any] = None


class ToolDefinition(BaseModel):
    """工具定义"""
    name: str
    description: str
    parameters: List[ToolParameter]
    category: str  # script, asset, render, qa


class ToolRegistry:
    """工具注册表"""

    def __init__(self):
        self.tools: Dict[str, Dict[str, Any]] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        """注册默认工具"""

        # 剧本相关工具
        self.register_tool(
            name="generate_storyboard",
            description="根据故事描述生成分镜",
            parameters=[
                ToolParameter(name="story", type="string", description="故事描述"),
                ToolParameter(name="panel_count", type="int", description="分镜数量", default=4),
                ToolParameter(name="style", type="string", description="风格", required=False),
            ],
            category="script",
            handler=None,  # 由 ScriptAgent 实现
        )

        self.register_tool(
            name="refine_script",
            description="根据反馈优化剧本",
            parameters=[
                ToolParameter(name="script_id", type="string", description="剧本ID"),
                ToolParameter(name="feedback", type="string", description="反馈内容"),
            ],
            category="script",
            handler=None,
        )

        # 资产相关工具
        self.register_tool(
            name="create_character",
            description="创建角色资产",
            parameters=[
                ToolParameter(name="name", type="string", description="角色名称"),
                ToolParameter(name="description", type="string", description="角色描述"),
                ToolParameter(name="appearance", type="string", description="外貌特征"),
            ],
            category="asset",
            handler=None,  # 由 AssetAgent 实现
        )

        self.register_tool(
            name="create_scene",
            description="创建场景资产",
            parameters=[
                ToolParameter(name="name", type="string", description="场景名称"),
                ToolParameter(name="description", type="string", description="场景描述"),
            ],
            category="asset",
            handler=None,
        )

        self.register_tool(
            name="query_assets",
            description="查询现有资产",
            parameters=[
                ToolParameter(name="asset_type", type="string", description="资产类型: character, scene, prop"),
                ToolParameter(name="query", type="string", description="查询关键词", required=False),
            ],
            category="asset",
            handler=None,
        )

        # 渲染相关工具
        self.register_tool(
            name="render_panels",
            description="渲染指定的分镜",
            parameters=[
                ToolParameter(name="panel_ids", type="list", description="分镜ID列表"),
                ToolParameter(name="quality", type="string", description="质量: draft, final", default="draft"),
            ],
            category="render",
            handler=None,  # 由 RenderingAgent 实现
        )

        self.register_tool(
            name="get_render_status",
            description="获取渲染状态",
            parameters=[
                ToolParameter(name="job_ids", type="list", description="任务ID列表"),
            ],
            category="render",
            handler=None,
        )

        # QA相关工具
        self.register_tool(
            name="analyze_quality",
            description="分析分镜质量",
            parameters=[
                ToolParameter(name="panel_id", type="string", description="分镜ID"),
            ],
            category="qa",
            handler=None,  # 由 QAAgent 实现
        )

        self.register_tool(
            name="suggest_fixes",
            description="建议修复方案",
            parameters=[
                ToolParameter(name="panel_id", type="string", description="分镜ID"),
                ToolParameter(name="issues", type="list", description="问题列表"),
            ],
            category="qa",
            handler=None,
        )

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: List[ToolParameter],
        category: str,
        handler: Optional[Callable] = None,
    ):
        """注册工具"""
        self.tools[name] = {
            "definition": ToolDefinition(
                name=name,
                description=description,
                parameters=parameters,
                category=category,
            ),
            "handler": handler,
        }
        logger.info(f"Registered tool: {name} (category: {category})")

    def get_tool_schema(self, category: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取工具定义（供 LLM 使用）

        Args:
            category: 工具类别（可选，用于过滤）

        Returns:
            工具定义列表
        """
        schemas = []

        for tool_name, tool_data in self.tools.items():
            definition = tool_data["definition"]

            # 类别过滤
            if category and definition.category != category:
                continue

            # 构建参数schema
            parameters_schema = {
                "type": "object",
                "properties": {},
                "required": [],
            }

            for param in definition.parameters:
                parameters_schema["properties"][param.name] = {
                    "type": param.type,
                    "description": param.description,
                }
                if param.default is not None:
                    parameters_schema["properties"][param.name]["default"] = param.default

                if param.required:
                    parameters_schema["required"].append(param.name)

            schemas.append(
                {
                    "name": definition.name,
                    "description": definition.description,
                    "parameters": parameters_schema,
                }
            )

        return schemas

    def get_tool(self, tool_name: str) -> Optional[Dict[str, Any]]:
        """获取工具"""
        return self.tools.get(tool_name)

    def validate_tool_call(self, tool_name: str, parameters: Dict[str, Any]) -> bool:
        """
        验证工具调用参数

        Args:
            tool_name: 工具名称
            parameters: 参数

        Returns:
            是否有效
        """
        tool = self.get_tool(tool_name)
        if not tool:
            logger.error(f"Tool not found: {tool_name}")
            return False

        definition = tool["definition"]

        # 检查必需参数
        for param in definition.parameters:
            if param.required and param.name not in parameters:
                logger.error(f"Missing required parameter: {param.name} for tool {tool_name}")
                return False

        return True

    async def execute_tool(
        self, tool_name: str, parameters: Dict[str, Any], handler: Optional[Callable] = None
    ) -> Dict[str, Any]:
        """
        执行工具

        Args:
            tool_name: 工具名称
            parameters: 参数
            handler: 自定义处理器（可选）

        Returns:
            执行结果
        """
        # 验证工具调用
        if not self.validate_tool_call(tool_name, parameters):
            return {
                "success": False,
                "error": f"Invalid tool call: {tool_name}",
            }

        tool = self.get_tool(tool_name)
        if not tool:
            return {
                "success": False,
                "error": f"Tool not found: {tool_name}",
            }

        # 使用自定义处理器或注册的处理器
        tool_handler = handler or tool["handler"]
        if not tool_handler:
            return {
                "success": False,
                "error": f"No handler for tool: {tool_name}",
            }

        try:
            # 执行工具
            result = await tool_handler(**parameters)
            return {
                "success": True,
                "result": result,
            }
        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}, error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def list_tools(self, category: Optional[str] = None) -> List[str]:
        """列出所有工具名称"""
        if category:
            return [
                name
                for name, tool_data in self.tools.items()
                if tool_data["definition"].category == category
            ]
        return list(self.tools.keys())

    def bind_handlers(self, db: "Session"):
        """
        绑定实际的工具处理函数
        
        Args:
            db: 数据库会话
        """
        from app.services.conversation.tool_handlers import ToolHandlers
        
        handlers = ToolHandlers(db)
        handler_map = handlers.get_all_handlers()
        
        for tool_name, handler in handler_map.items():
            if tool_name in self.tools:
                self.tools[tool_name]["handler"] = handler
                logger.info(f"Bound handler for tool: {tool_name}")
            else:
                logger.warning(f"Tool not found in registry: {tool_name}")

