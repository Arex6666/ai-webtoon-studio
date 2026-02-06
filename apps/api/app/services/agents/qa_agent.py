"""
QAAgent - 质量分析智能体
处理质量检查和问题修复建议
"""
import logging
from typing import Dict, Any, AsyncGenerator, List
from sqlalchemy.orm import Session

from app.services.agents.base_agent import BaseAgent
from app.services.draft_qa import DraftQA
from app.models.panel import Panel
from app.schemas.conversation import IntentAnalysisResult

logger = logging.getLogger(__name__)


QA_AGENT_PROMPT = """你是一个专业的漫画质量分析助手。你的职责是：
1. 分析分镜的质量问题
2. 识别构图、角色一致性、视觉效果等问题
3. 提供具体的修复建议

当用户反馈质量问题时，你需要：
- 理解问题的具体描述
- 分析问题的根本原因
- 提供可行的修复方案
- 建议具体的参数调整

请用专业、建设性的语气与用户交流。"""


class QAAgent(BaseAgent):
    """质量分析智能体"""

    def __init__(self, db: Session):
        super().__init__(
            name="qa_agent",
            description="处理质量检查和问题修复",
        )
        self.db = db
        self.draft_qa = DraftQA()

    async def process(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
        streaming: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """处理质量分析相关请求"""
        try:
            # 判断操作类型
            if self._should_analyze_quality(user_message):
                async for event in self._analyze_quality(user_message, intent, context):
                    yield event
            elif self._should_suggest_fixes(user_message):
                async for event in self._suggest_fixes(user_message, intent, context):
                    yield event
            else:
                # 一般对话
                async for event in self._chat_response(user_message, context, streaming):
                    yield event

        except Exception as e:
            logger.error(f"QAAgent error: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
            }

    def _should_analyze_quality(self, user_message: str) -> bool:
        """判断是否分析质量"""
        keywords = ["检查", "分析", "质量", "问题", "不好", "有问题", "check", "analyze"]
        message_lower = user_message.lower()
        return any(keyword in message_lower for keyword in keywords)

    def _should_suggest_fixes(self, user_message: str) -> bool:
        """判断是否建议修复"""
        keywords = ["怎么改", "如何修复", "建议", "优化", "改进", "fix", "improve"]
        message_lower = user_message.lower()
        return any(keyword in message_lower for keyword in keywords)

    async def _analyze_quality(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """分析质量"""
        try:
            # 1. 提取要分析的分镜
            panel_info = await self._extract_panel_info(user_message, context)

            yield {
                "type": "message",
                "content": f"好的，我来分析{panel_info.get('description', '分镜')}的质量...",
            }

            # 2. 调用工具
            yield {
                "type": "tool_call",
                "tool_call": {
                    "tool_name": "analyze_quality",
                    "parameters": panel_info,
                },
            }

            # 3. 获取分镜
            panel_id = panel_info.get("panel_id")
            if not panel_id:
                # 如果没有指定分镜，分析最近的分镜
                chapter_id = context.get("chapter_id")
                if not chapter_id:
                    yield {
                        "type": "message",
                        "content": "请指定要分析的分镜或章节。",
                    }
                    return

                panels = self.db.query(Panel).filter(
                    Panel.chapter_id == chapter_id
                ).order_by(Panel.sequence_number).all()

                if not panels:
                    yield {
                        "type": "message",
                        "content": "没有找到可分析的分镜。",
                    }
                    return

                # 分析所有分镜
                panel_id = panels[0].id
            else:
                panels = [self.db.query(Panel).filter(Panel.id == panel_id).first()]

            # 4. 执行质量分析
            yield {
                "type": "action_started",
                "action_id": f"qa_{panel_id}",
                "action_type": "analyze_quality",
                "description": "正在分析质量...",
            }

            # 调用 DraftQA 服务
            issues = []
            for panel in panels:
                if panel and panel.draft_image_url:
                    panel_issues = await self.draft_qa.analyze_panel(
                        panel_id=panel.id,
                        image_url=panel.draft_image_url,
                        script_description=panel.description,
                    )
                    issues.extend(panel_issues)

            yield {
                "type": "action_completed",
                "action_id": f"qa_{panel_id}",
                "action_type": "analyze_quality",
                "result": {
                    "issues_found": len(issues),
                    "issues": issues,
                },
            }

            # 5. 生成报告
            if not issues:
                response = """✓ 质量分析完成！

未发现明显问题。分镜质量良好。

如果您有具体的改进需求，请告诉我。"""
            else:
                issue_lines = []
                for i, issue in enumerate(issues, 1):
                    severity_emoji = {
                        "critical": "🔴",
                        "major": "🟠",
                        "minor": "🟡",
                    }.get(issue.get("severity", "minor"), "⚪")

                    issue_lines.append(
                        f"{severity_emoji} **问题 {i}**: {issue.get('description')}\n"
                        f"   - **类型**: {issue.get('type')}\n"
                        f"   - **建议**: {issue.get('suggestion')}"
                    )

                response = f"""质量分析完成，发现 {len(issues)} 个问题：

{chr(10).join(issue_lines)}

您可以：
- 说"修复这些问题"来自动优化
- 说"重新渲染第X格"来手动调整
- 说"忽略这些问题"继续下一步"""

            yield {
                "type": "message",
                "content": response,
            }

        except Exception as e:
            logger.error(f"Quality analysis failed: {e}", exc_info=True)
            yield {
                "type": "message",
                "content": f"抱歉，分析质量时出现错误：{str(e)}",
            }

    async def _suggest_fixes(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """建议修复方案"""
        try:
            # 1. 理解问题描述
            problem_analysis = await self._analyze_problem(user_message, context)

            yield {
                "type": "message",
                "content": "让我分析一下这个问题...",
            }

            # 2. 生成修复建议
            suggestions = await self._generate_suggestions(problem_analysis)

            # 3. 构建响应
            suggestion_lines = []
            for i, suggestion in enumerate(suggestions, 1):
                suggestion_lines.append(
                    f"**方案 {i}**: {suggestion.get('title')}\n"
                    f"   - {suggestion.get('description')}\n"
                    f"   - 操作: {suggestion.get('action')}"
                )

            response = f"""针对您提到的问题，我有以下建议：

{chr(10).join(suggestion_lines)}

请告诉我您想尝试哪个方案，或者描述您的具体需求。"""

            yield {
                "type": "message",
                "content": response,
            }

        except Exception as e:
            logger.error(f"Suggestion generation failed: {e}", exc_info=True)
            yield {
                "type": "message",
                "content": f"抱歉，生成建议时出现错误：{str(e)}",
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
                    system_prompt=QA_AGENT_PROMPT,
                ):
                    yield {
                        "type": "message_chunk",
                        "chunk": chunk,
                    }
            else:
                # 非流式响应
                response = await self._call_llm(
                    user_message=user_message,
                    system_prompt=QA_AGENT_PROMPT,
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

    async def _extract_panel_info(
        self,
        user_message: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """提取分镜信息"""
        # 使用 LLM 提取结构化信息
        prompt = f"""从以下用户消息中提取要分析的分镜信息，返回JSON格式：
{{
  "panel_id": "分镜ID（如果明确指定）",
  "panel_number": "分镜序号（如'第2格'）",
  "description": "描述（如'所有分镜'、'第一格'等）",
  "specific_issue": "具体问题描述（如果提到）"
}}

当前上下文: {context}
用户消息: {user_message}"""

        response = await self.llm._chat_completion(
            [{"role": "user", "content": prompt}],
            response_format="json",
        )

        import json
        return json.loads(response)

    async def _analyze_problem(
        self,
        user_message: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """分析问题"""
        prompt = f"""分析用户描述的质量问题，返回JSON格式：
{{
  "problem_type": "问题类型（composition/character/lighting/style等）",
  "severity": "严重程度（critical/major/minor）",
  "affected_elements": ["受影响的元素列表"],
  "root_cause": "根本原因分析"
}}

当前上下文: {context}
用户消息: {user_message}"""

        response = await self.llm._chat_completion(
            [{"role": "user", "content": prompt}],
            response_format="json",
        )

        import json
        return json.loads(response)

    async def _generate_suggestions(
        self,
        problem_analysis: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """生成修复建议"""
        prompt = f"""根据问题分析生成修复建议，返回JSON数组格式：
[
  {{
    "title": "建议标题",
    "description": "详细描述",
    "action": "具体操作步骤",
    "priority": "优先级（high/medium/low）"
  }}
]

问题分析: {problem_analysis}

请生成2-3个可行的修复方案。"""

        response = await self.llm._chat_completion(
            [{"role": "user", "content": prompt}],
            response_format="json",
        )

        import json
        suggestions = json.loads(response)

        # 确保返回列表
        if isinstance(suggestions, dict):
            suggestions = [suggestions]

        return suggestions

    async def batch_analyze(
        self,
        chapter_id: str,
    ) -> Dict[str, Any]:
        """批量分析章节的所有分镜"""
        try:
            panels = self.db.query(Panel).filter(
                Panel.chapter_id == chapter_id
            ).order_by(Panel.sequence_number).all()

            if not panels:
                return {
                    "success": False,
                    "message": "没有找到分镜",
                }

            all_issues = []
            for panel in panels:
                if panel.draft_image_url:
                    issues = await self.draft_qa.analyze_panel(
                        panel_id=panel.id,
                        image_url=panel.draft_image_url,
                        script_description=panel.description,
                    )
                    all_issues.extend(issues)

            return {
                "success": True,
                "total_panels": len(panels),
                "total_issues": len(all_issues),
                "issues": all_issues,
            }

        except Exception as e:
            logger.error(f"Batch analysis failed: {e}", exc_info=True)
            return {
                "success": False,
                "message": str(e),
            }
