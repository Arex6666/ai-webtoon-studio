"""
RenderingAgent - 渲染智能体
处理分镜渲染和进度监控
"""
import logging
from typing import Dict, Any, AsyncGenerator
from sqlalchemy.orm import Session

from app.services.agents.base_agent import BaseAgent
from app.services.auto_storyboard_orchestrator import AutoStoryboardOrchestrator
from app.models.job import Job
from app.schemas.conversation import IntentAnalysisResult

logger = logging.getLogger(__name__)


RENDERING_AGENT_PROMPT = """你是一个渲染管理助手。你的职责是：
1. 处理分镜渲染请求
2. 监控渲染进度
3. 报告渲染状态和结果

当用户要渲染分镜时，你需要：
- 确定要渲染的分镜范围
- 选择渲染质量（草稿/最终）
- 启动渲染任务
- 实时报告进度

请用友好、专业的语气与用户交流。"""


class RenderingAgent(BaseAgent):
    """渲染智能体"""

    def __init__(self, db: Session):
        super().__init__(
            name="rendering_agent",
            description="处理分镜渲染和进度监控",
        )
        self.db = db
        self.orchestrator = AutoStoryboardOrchestrator(db)

    async def process(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
        streaming: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """处理渲染相关请求"""
        try:
            # 判断操作类型
            if self._should_render_panels(user_message):
                async for event in self._render_panels(user_message, intent, context):
                    yield event
            elif self._should_check_status(user_message):
                async for event in self._check_render_status(user_message, intent, context):
                    yield event
            else:
                # 一般对话
                async for event in self._chat_response(user_message, context, streaming):
                    yield event

        except Exception as e:
            logger.error(f"RenderingAgent error: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
            }

    def _should_render_panels(self, user_message: str) -> bool:
        """判断是否渲染分镜"""
        keywords = ["渲染", "生成图片", "画出来", "render", "生成", "制作"]
        message_lower = user_message.lower()
        return any(keyword in message_lower for keyword in keywords)

    def _should_check_status(self, user_message: str) -> bool:
        """判断是否查询状态"""
        keywords = ["进度", "状态", "完成了吗", "怎么样了", "status", "progress"]
        message_lower = user_message.lower()
        return any(keyword in message_lower for keyword in keywords)

    async def _render_panels(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """渲染分镜"""
        try:
            # 1. 提取渲染参数
            render_params = await self._extract_render_params(user_message, context)

            yield {
                "type": "message",
                "content": f"好的，我来渲染{render_params.get('description', '分镜')}...",
            }

            # 2. 调用工具
            yield {
                "type": "tool_call",
                "tool_call": {
                    "tool_name": "render_panels",
                    "parameters": render_params,
                },
            }

            # 3. 获取章节ID
            chapter_id = context.get("chapter_id") or render_params.get("chapter_id")
            if not chapter_id:
                yield {
                    "type": "message",
                    "content": "抱歉，无法确定要渲染的章节。请先创建分镜或指定章节ID。",
                }
                return

            # 4. 启动渲染任务
            yield {
                "type": "action_started",
                "action_id": f"render_{chapter_id}",
                "action_type": "render_panels",
                "description": "正在启动渲染任务...",
            }

            # 调用 AutoStoryboardOrchestrator
            job = await self.orchestrator.start_rendering(
                chapter_id=chapter_id,
                quality=render_params.get("quality", "draft"),
                panel_ids=render_params.get("panel_ids"),
            )

            yield {
                "type": "action_progress",
                "action_id": f"render_{chapter_id}",
                "action_type": "render_panels",
                "progress": 0.1,
                "description": f"渲染任务已启动 (Job ID: {job.id})",
            }

            # 5. 监控进度（简化版，实际应该通过WebSocket推送）
            # TODO: 实现真正的进度监控
            yield {
                "type": "action_completed",
                "action_id": f"render_{chapter_id}",
                "action_type": "render_panels",
                "result": {
                    "job_id": job.id,
                    "status": job.status,
                    "message": "渲染任务已提交，您可以在任务列表中查看进度",
                },
            }

            # 6. 响应
            response = f"""✓ 渲染任务已启动！

🎬 **任务ID**: {job.id}
📊 **状态**: {job.status}
⚙️ **质量**: {render_params.get('quality', 'draft')}

您可以：
- 说"查看渲染进度"来查看当前状态
- 说"取消渲染"来停止任务
- 在任务列表中查看详细进度"""

            yield {
                "type": "message",
                "content": response,
            }

        except Exception as e:
            logger.error(f"Panel rendering failed: {e}", exc_info=True)
            yield {
                "type": "message",
                "content": f"抱歉，渲染分镜时出现错误：{str(e)}",
            }

    async def _check_render_status(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """查询渲染状态"""
        try:
            # 获取最近的渲染任务
            chapter_id = context.get("chapter_id")
            if not chapter_id:
                yield {
                    "type": "message",
                    "content": "请先指定要查询的章节或任务ID。",
                }
                return

            # 查询任务
            jobs = self.db.query(Job).filter(
                Job.chapter_id == chapter_id,
                Job.type.in_(["render_panel", "render_chapter"]),
            ).order_by(Job.created_at.desc()).limit(5).all()

            if not jobs:
                yield {
                    "type": "message",
                    "content": "没有找到相关的渲染任务。",
                }
                return

            # 构建状态报告
            status_lines = []
            for job in jobs:
                status_emoji = {
                    "queued": "⏳",
                    "running": "🔄",
                    "succeeded": "✅",
                    "failed": "❌",
                    "canceled": "🚫",
                }.get(job.status, "❓")

                progress = job.progress or 0
                status_lines.append(
                    f"{status_emoji} **{job.id[:8]}...** - {job.status} ({progress:.0%})"
                )

            response = f"""当前渲染任务状态：

{chr(10).join(status_lines)}

最新任务详情：
- **ID**: {jobs[0].id}
- **状态**: {jobs[0].status}
- **进度**: {(jobs[0].progress or 0):.0%}
- **创建时间**: {jobs[0].created_at.strftime('%Y-%m-%d %H:%M:%S')}"""

            if jobs[0].error_message:
                response += f"\n- **错误**: {jobs[0].error_message}"

            yield {
                "type": "message",
                "content": response,
            }

        except Exception as e:
            logger.error(f"Status check failed: {e}", exc_info=True)
            yield {
                "type": "message",
                "content": f"抱歉，查询状态时出现错误：{str(e)}",
            }

    async def _chat_response(
        self,
        user_message: str,
        context: Dict[str, Any],
        streaming: bool,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """一般对话响应"""
        try:
            if streaming:
                # 流式响应
                async for chunk in self._stream_llm_response(
                    messages=[{"role": "user", "content": user_message}],
                    system_prompt=RENDERING_AGENT_PROMPT,
                ):
                    yield {
                        "type": "message_chunk",
                        "chunk": chunk,
                    }
            else:
                # 非流式响应
                response = await self._call_llm(
                    user_message=user_message,
                    system_prompt=RENDERING_AGENT_PROMPT,
                    context=context,
                )
                yield {
                    "type": "message",
                    "content": response,
                }

        except Exception as e:
            logger.error(f"Chat response failed: {e}", exc_info=True)
            yield {
                "type": "message",
                "content": "抱歉，我现在无法回答。请稍后再试。",
            }

    async def _extract_render_params(
        self,
        user_message: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """提取渲染参数"""
        # 使用 LLM 提取结构化信息
        prompt = f"""从以下用户消息中提取渲染参数，返回JSON格式：
{{
  "chapter_id": "章节ID（如果提到）",
  "panel_ids": ["分镜ID列表（如果指定了具体分镜）"],
  "quality": "draft 或 final（默认draft）",
  "description": "渲染描述（如'所有分镜'、'第1-3格'等）"
}}

当前上下文: {context}
用户消息: {user_message}"""

        response = await self.llm._chat_completion(
            [{"role": "user", "content": prompt}],
            response_format="json",
        )

        import json
        params = json.loads(response)

        # 从上下文补充缺失的信息
        if not params.get("chapter_id"):
            params["chapter_id"] = context.get("chapter_id")

        return params

    async def cancel_render(
        self,
        job_id: str,
    ) -> Dict[str, Any]:
        """取消渲染任务"""
        try:
            job = self.db.query(Job).filter(Job.id == job_id).first()
            if not job:
                return {
                    "success": False,
                    "message": "任务不存在",
                }

            if job.status in ["succeeded", "failed", "canceled"]:
                return {
                    "success": False,
                    "message": f"任务已经{job.status}，无法取消",
                }

            # 更新任务状态
            job.status = "canceled"
            self.db.commit()

            return {
                "success": True,
                "message": "任务已取消",
            }

        except Exception as e:
            logger.error(f"Cancel render failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
            }
