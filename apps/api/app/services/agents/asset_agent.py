"""
AssetAgent - 资产智能体
处理角色、场景、道具的创建和管理
"""
import logging
from typing import Dict, Any, AsyncGenerator
from sqlalchemy.orm import Session

from app.services.agents.base_agent import BaseAgent
from app.services.asset_image_generator import get_asset_image_generator
from app.models.asset import Asset, AssetType
from app.schemas.conversation import IntentAnalysisResult

logger = logging.getLogger(__name__)


ASSET_AGENT_PROMPT = """你是一个资产管理助手。你的职责是：
1. 创建和管理角色、场景、道具资产
2. 帮助用户查询现有资产
3. 生成资产的参考图片

当用户要创建资产时，你需要：
- 提取资产的名称和描述
- 确定资产类型（角色/场景/道具）
- 生成详细的视觉描述

请用友好、专业的语气与用户交流。"""


class AssetAgent(BaseAgent):
    """资产智能体"""

    def __init__(self, db: Session):
        super().__init__(
            name="asset_agent",
            description="处理资产创建和管理",
        )
        self.db = db
        self.asset_generator = get_asset_image_generator()

    async def process(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
        streaming: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """处理资产相关请求"""
        try:
            # 判断操作类型
            if self._should_create_character(user_message):
                async for event in self._create_character(user_message, intent, context):
                    yield event
            elif self._should_create_scene(user_message):
                async for event in self._create_scene(user_message, intent, context):
                    yield event
            elif self._should_query_assets(user_message):
                async for event in self._query_assets(user_message, intent, context):
                    yield event
            else:
                # 一般对话
                async for event in self._chat_response(user_message, context, streaming):
                    yield event

        except Exception as e:
            logger.error(f"AssetAgent error: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
            }

    def _should_create_character(self, user_message: str) -> bool:
        """判断是否创建角色"""
        keywords = ["创建角色", "新建角色", "角色", "人物", "主角", "配角"]
        message_lower = user_message.lower()
        return any(keyword in message_lower for keyword in keywords)

    def _should_create_scene(self, user_message: str) -> bool:
        """判断是否创建场景"""
        keywords = ["创建场景", "新建场景", "场景", "背景", "地点"]
        message_lower = user_message.lower()
        return any(keyword in message_lower for keyword in keywords)

    def _should_query_assets(self, user_message: str) -> bool:
        """判断是否查询资产"""
        keywords = ["查看", "显示", "列出", "有哪些", "所有"]
        message_lower = user_message.lower()
        return any(keyword in message_lower for keyword in keywords)

    async def _create_character(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """创建角色"""
        try:
            # 1. 提取角色信息
            character_info = await self._extract_character_info(user_message)

            yield {
                "type": "message",
                "content": f"好的，我来创建角色「{character_info['name']}」...",
            }

            # 2. 调用工具
            yield {
                "type": "tool_call",
                "tool_call": {
                    "tool_name": "create_character",
                    "parameters": character_info,
                },
            }

            # 3. 创建资产记录
            # TODO: 获取 project_id
            project_id = context.get("project_id", "default")

            asset = Asset(
                project_id=project_id,
                name=character_info["name"],
                type=AssetType.CHARACTER,
                description=character_info["description"],
                data_json={"appearance": character_info["appearance"]},
            )
            self.db.add(asset)
            self.db.commit()
            self.db.refresh(asset)

            # 4. 生成定妆照（可选）
            yield {
                "type": "action_started",
                "action_id": f"generate_portrait_{asset.id}",
                "action_type": "generate_portrait",
                "description": f"正在生成{character_info['name']}的定妆照...",
            }

            # TODO: 调用 AssetImageGenerator 生成图片
            # portrait_result = await self.asset_generator.generate_character_portrait(...)

            yield {
                "type": "action_completed",
                "action_id": f"generate_portrait_{asset.id}",
                "action_type": "generate_portrait",
                "result": {
                    "asset_id": asset.id,
                    "asset_name": asset.name,
                    # "preview_url": portrait_result.get("url"),
                },
            }

            # 5. 响应
            response = f"""✓ 角色「{character_info['name']}」创建成功！

📝 **描述**: {character_info['description']}
👤 **外貌**: {character_info['appearance']}

接下来您可以：
- 说"生成定妆照"来生成角色参考图
- 继续创建其他角色或场景
- 说"开始创作故事"来使用这个角色"""

            yield {
                "type": "message",
                "content": response,
            }

        except Exception as e:
            logger.error(f"Character creation failed: {e}", exc_info=True)
            yield {
                "type": "message",
                "content": f"抱歉，创建角色时出现错误：{str(e)}",
            }

    async def _create_scene(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """创建场景"""
        try:
            # 提取场景信息
            scene_info = await self._extract_scene_info(user_message)

            yield {
                "type": "message",
                "content": f"好的，我来创建场景「{scene_info['name']}」...",
            }

            # TODO: 实现场景创建逻辑
            yield {
                "type": "message",
                "content": f"场景「{scene_info['name']}」创建成功！",
            }

        except Exception as e:
            logger.error(f"Scene creation failed: {e}", exc_info=True)
            yield {
                "type": "message",
                "content": f"抱歉，创建场景时出现错误：{str(e)}",
            }

    async def _query_assets(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """查询资产"""
        try:
            # TODO: 查询数据库
            project_id = context.get("project_id", "default")

            characters = self.db.query(Asset).filter(
                Asset.project_id == project_id,
                Asset.type == AssetType.CHARACTER,
            ).all()

            scenes = self.db.query(Asset).filter(
                Asset.project_id == project_id,
                Asset.type == AssetType.SCENE,
            ).all()

            response = f"""当前项目的资产：

👥 **角色** ({len(characters)}个):
{chr(10).join([f"- {c.name}" for c in characters]) if characters else "  暂无"}

🎬 **场景** ({len(scenes)}个):
{chr(10).join([f"- {s.name}" for s in scenes]) if scenes else "  暂无"}"""

            yield {
                "type": "message",
                "content": response,
            }

        except Exception as e:
            logger.error(f"Asset query failed: {e}", exc_info=True)
            yield {
                "type": "message",
                "content": f"抱歉，查询资产时出现错误：{str(e)}",
            }

    async def _chat_response(
        self,
        user_message: str,
        context: Dict[str, Any],
        streaming: bool,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """一般对话响应"""
        response = await self._call_llm(
            user_message=user_message,
            system_prompt=ASSET_AGENT_PROMPT,
            context=context,
        )
        yield {
            "type": "message",
            "content": response,
        }

    async def _extract_character_info(self, user_message: str) -> Dict[str, Any]:
        """提取角色信息"""
        # 使用 LLM 提取结构化信息
        prompt = f"""从以下用户消息中提取角色信息，返回JSON格式：
{{
  "name": "角色名称",
  "description": "角色描述",
  "appearance": "外貌特征"
}}

用户消息: {user_message}"""

        response = await self.llm._chat_completion(
            [{"role": "user", "content": prompt}],
            response_format="json",
        )

        import json
        return json.loads(response)

    async def _extract_scene_info(self, user_message: str) -> Dict[str, Any]:
        """提取场景信息"""
        # 使用 LLM 提取结构化信息
        prompt = f"""从以下用户消息中提取场景信息，返回JSON格式：
{{
  "name": "场景名称",
  "description": "场景描述"
}}

用户消息: {user_message}"""

        response = await self.llm._chat_completion(
            [{"role": "user", "content": prompt}],
            response_format="json",
        )

        import json
        return json.loads(response)
