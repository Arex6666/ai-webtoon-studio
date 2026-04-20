"""
StoryAgent - 故事创作智能体
实现 story-genesis 技能的对话式故事生成流程
支持三阶段状态机: INTAKE → BUILD → STORYBOARD
"""
import json
import logging
import uuid
from typing import Dict, Any, AsyncGenerator, List, Optional
from sqlalchemy.orm import Session

from app.services.agents.base_agent import BaseAgent
from app.schemas.conversation import IntentAnalysisResult
from app.schemas.story_artifacts import (
    StoryGenesisPhase,
    StoryGenesisState,
    CreativeBrief,
    ToneGuardrails,
    CharacterProfile,
    Screenplay,
    ScreenplayScene,
    SceneBeat,
    IntakeProgress,
)

logger = logging.getLogger(__name__)


# ============ System Prompts ============

INTAKE_SYSTEM_PROMPT = """You are a master story architect. Your job is to extract creative inspiration from a user through natural, engaging conversation.

You have 8 key areas to explore. Do NOT ask them like a form — weave them into natural conversation. If the user provides rich detail, extract what you can and only ask about what's missing.

The 8 areas:
1. Genre + 2 comparison works + 1 anti-comparison
2. Protagonist: what they're great at / what flaw ruins their relationships
3. Core relationship: who they need most, why they push them away
4. Story engine: what creates new problems each episode/chapter
5. Theme question (one sentence)
6. Tone guardrails: rating, comedy level (1-5), violence level (1-5)
7. Setting + 5-10 visual/aesthetic keywords
8. Ending stakes: what must be irrevocably different by the end

RULES:
- Match the user's language (Chinese or English)
- Be warm and enthusiastic, not clinical
- After each user response, acknowledge what's great about their idea
- Ask 1-2 questions at a time, never all 8 at once
- If user gives a detailed pitch, extract everything you can and confirm

When you have enough information on all 8 areas, respond with a JSON block wrapped in ```json``` containing the creative brief. The JSON must have this structure:
{
  "status": "brief_complete",
  "brief": {
    "title": "working title",
    "genre": "genre",
    "comparisons": ["comp1", "comp2"],
    "anti_comparison": "anti-comp",
    "logline": "one-line summary",
    "theme_question": "core question",
    "story_engine": "what generates new problems",
    "tone": {"rating": "teen", "comedy_level": 3, "violence_level": 2},
    "setting": "location and period",
    "visual_keywords": ["kw1", "kw2", "..."],
    "ending_stakes": "irreversible change"
  }
}

If you still need more info, just respond conversationally (no JSON).
"""

BUILD_SYSTEM_PROMPT = """You are a master screenwriter and character designer. Given a creative brief, autonomously generate a complete story package.

You will generate content in this order:
1. CHARACTER SHEETS — Each character with full profile
2. SCREENPLAY — Complete scene-by-scene script

CRITICAL RULES:
- appearance_keywords: provide a LIST of visual keywords for AI image generation
  Example: ["black hair", "shoulder length", "brown eyes", "slim build", "school uniform"]
- personality_keywords: provide a LIST of personality traits
  Example: ["内向", "温柔", "专一"] or ["introverted", "gentle"]
- Every scene beat MUST include source_quote: the exact narrative text for this beat (30-100 chars)
- Every scene beat MUST include emotion_shift: "starting_emotion → ending_emotion"
- Dialogue must use character-specific voice
- Every scene must have Goal/Obstacle/Turn/Cost
- Anti-exposition: characters don't explain what they both already know
- Match the user's language (Chinese or English)
- Aim for 4-8 scenes, 12-24 estimated panels
- suggested_shot_types must use pipeline enum: ECU/CU/MCU/MS/MLS/LS/WS/EWS/OTS/POV
- emotion_label per scene: tense/calm/joyful/sad/angry/fearful/hopeful/melancholic/dramatic/neutral
- pacing per scene: slow/moderate/fast/climax

Respond with a JSON block wrapped in ```json``` containing:
{
  "status": "story_complete",
  "characters": [
    {
      "name": "",
      "age": "",
      "age_range": "20s",
      "gender": "male/female/other",
      "role": "protagonist/antagonist/supporting/minor",
      "importance": "protagonist/supporting/minor",
      "face_description": "",
      "hair_description": "",
      "build": "",
      "distinguishing_features": "",
      "default_outfit": "",
      "outfit_variants": [],
      "visual_tags": ["tag1", "tag2"],
      "appearance_keywords": ["keyword1", "keyword2", "keyword3"],
      "personality_keywords": ["trait1", "trait2"],
      "core_traits": ["trait1", "trait2"],
      "strength": "",
      "flaw": "",
      "speech_pattern": "",
      "want": "",
      "need": "",
      "lie": "",
      "ghost": "",
      "backstory": ""
    }
  ],
  "screenplay": {
    "title": "",
    "episode_number": 1,
    "genre": "",
    "estimated_panels": 16,
    "scenes": [
      {
        "scene_index": 1,
        "scene_name": "",
        "location": "",
        "time_of_day": "afternoon",
        "weather_mood": "rainy",
        "characters_present": ["name1", "name2"],
        "visual_atmosphere": "",
        "emotion_label": "calm",
        "pacing": "slow",
        "beats": [
          {
            "beat_index": 1,
            "title": "",
            "goal": "",
            "obstacle": "",
            "turn": "",
            "cost": "",
            "action": "",
            "dialogue": [{"speaker": "", "text": "", "direction": ""}],
            "source_quote": "The exact narrative text for this beat (30-100 chars)",
            "emotion_shift": "平静 → 心动",
            "tension_level": 3
          }
        ],
        "suggested_shot_types": ["WS", "MS", "CU"],
        "lighting": "soft",
        "key_visual": ""
      }
    ]
  }
}
"""


class StoryAgent(BaseAgent):
    """故事创作智能体 — 对话式故事生成 + 自动分镜"""

    def __init__(self, db: Session):
        super().__init__(
            name="story_agent",
            description="对话式故事创作与智能分镜生成",
        )
        self.db = db

    async def process(
        self,
        user_message: str,
        intent: IntentAnalysisResult,
        context: Dict[str, Any],
        streaming: bool = True,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """处理故事创作相关请求"""
        try:
            # 从上下文获取或初始化故事状态
            state = self._get_or_create_state(context)

            if state.phase == StoryGenesisPhase.INTAKE:
                async for event in self._handle_intake(user_message, state, context, streaming):
                    yield event

            elif state.phase == StoryGenesisPhase.BUILD:
                async for event in self._handle_build(state, context, streaming):
                    yield event

            elif state.phase == StoryGenesisPhase.STORYBOARD:
                async for event in self._handle_storyboard(state, context, streaming):
                    yield event

            elif state.phase == StoryGenesisPhase.COMPLETED:
                async for event in self._handle_completed(user_message, state, context, streaming):
                    yield event

            # 保存更新后的状态到上下文
            self._save_state(context, state)

        except Exception as e:
            logger.error(f"StoryAgent error: {e}", exc_info=True)
            yield {
                "type": "error",
                "error": str(e),
            }

    # ============ Phase Handlers ============

    async def _handle_intake(
        self,
        user_message: str,
        state: StoryGenesisState,
        context: Dict[str, Any],
        streaming: bool,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """处理 INTAKE 阶段 — 对话式灵感采集"""

        # 检测语言
        if state.language == "auto":
            state.language = self._detect_language(user_message)

        # 构建对话历史
        messages = self._build_context_messages(context, max_messages=10)
        messages.append({"role": "user", "content": user_message})

        # 调用 LLM 进行对话
        if streaming:
            full_response = ""
            async for chunk in self._stream_llm_response(
                messages=messages,
                system_prompt=INTAKE_SYSTEM_PROMPT,
            ):
                full_response += chunk
                yield {
                    "type": "message_chunk",
                    "chunk": chunk,
                }
        else:
            full_response = await self._call_llm(
                user_message=user_message,
                system_prompt=INTAKE_SYSTEM_PROMPT,
                context=context,
            )
            yield {
                "type": "message",
                "content": full_response,
            }

        # 检查是否 LLM 返回了完整的 brief JSON
        brief = self._extract_brief_from_response(full_response)
        if brief:
            state.creative_brief = brief
            state.phase = StoryGenesisPhase.BUILD
            state.intake_progress.questions_asked = state.intake_progress.questions_total

            yield {
                "type": "action_completed",
                "action_id": "intake_complete",
                "action_type": "story_intake",
                "result": {
                    "title": brief.title,
                    "genre": brief.genre,
                    "phase": "BUILD",
                },
            }

            # 自动进入 BUILD 阶段
            async for event in self._handle_build(state, context, streaming):
                yield event
        else:
            # 更新进度
            state.intake_progress.questions_asked += 1

    async def _handle_build(
        self,
        state: StoryGenesisState,
        context: Dict[str, Any],
        streaming: bool,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """处理 BUILD 阶段 — 自主生成角色和剧本"""

        if not state.creative_brief:
            yield {
                "type": "message",
                "content": "⚠️ 缺少创意简报，请先完成灵感采集。",
            }
            state.phase = StoryGenesisPhase.INTAKE
            return

        # 通知用户开始生成
        lang = state.language
        building_msg = (
            "🎬 灵感采集完成！现在开始自动生成故事...\n\n"
            "📝 正在创建角色档案和剧本，请稍候..."
        ) if lang == "zh" else (
            "🎬 Inspiration collected! Now auto-generating the story...\n\n"
            "📝 Creating character profiles and screenplay, please wait..."
        )

        yield {
            "type": "message",
            "content": building_msg,
        }

        yield {
            "type": "action_started",
            "action_id": "story_build",
            "action_type": "story_build",
            "description": "生成角色和剧本" if lang == "zh" else "Generating characters and screenplay",
        }

        # 构建 BUILD 请求
        brief_json = state.creative_brief.model_dump()
        build_prompt = f"Based on this creative brief, generate complete character sheets and screenplay:\n\n```json\n{json.dumps(brief_json, ensure_ascii=False, indent=2)}\n```"

        messages = [{"role": "user", "content": build_prompt}]

        # 调用 LLM 生成（非流式，因为需要完整 JSON）
        try:
            full_response = await self._call_llm(
                user_message=build_prompt,
                system_prompt=BUILD_SYSTEM_PROMPT,
            )

            # 解析生成结果
            story_data = self._extract_json_from_response(full_response)

            if story_data and story_data.get("status") == "story_complete":
                # 解析角色
                for char_data in story_data.get("characters", []):
                    char = CharacterProfile(**char_data)
                    state.characters.append(char)

                # 解析剧本
                sp_data = story_data.get("screenplay", {})
                if sp_data:
                    state.screenplay = Screenplay(**sp_data)

                # 构建结果摘要
                char_names = [c.name for c in state.characters]
                scene_count = len(state.screenplay.scenes) if state.screenplay else 0
                panel_count = state.screenplay.estimated_panels if state.screenplay else 0

                summary = (
                    f"✅ **故事生成完成！**\n\n"
                    f"👥 **角色** ({len(state.characters)})：{', '.join(char_names)}\n"
                    f"🎬 **场景数**：{scene_count}\n"
                    f"📐 **预估分镜**：{panel_count} 格\n\n"
                ) if lang == "zh" else (
                    f"✅ **Story generation complete!**\n\n"
                    f"👥 **Characters** ({len(state.characters)}): {', '.join(char_names)}\n"
                    f"🎬 **Scenes**: {scene_count}\n"
                    f"📐 **Estimated Panels**: {panel_count}\n\n"
                )

                yield {
                    "type": "action_completed",
                    "action_id": "story_build",
                    "action_type": "story_build",
                    "result": {
                        "characters": char_names,
                        "scene_count": scene_count,
                        "estimated_panels": panel_count,
                    },
                }

                yield {
                    "type": "message",
                    "content": summary,
                }

                # ============ 持久化资产 + 生成图片 ============
                project_id = context.get("project_id") or context.get("context_data", {}).get("project_id")
                async for event in self._persist_assets_and_generate_images(
                    state=state,
                    project_id=project_id,
                    lang=lang,
                ):
                    yield event

                # 补充最终提示
                tail_msg = (
                    "是否要继续生成智能分镜？回复「生成分镜」或「generate storyboard」"
                ) if lang == "zh" else (
                    "Ready to generate storyboard? Reply 'generate storyboard'"
                )
                yield {"type": "message", "content": tail_msg}

                # 进入等待分镜确认状态（仍然在 BUILD 阶段，等用户确认再转 STORYBOARD）
                state.phase = StoryGenesisPhase.STORYBOARD

            else:
                # 生成失败，返回原始响应
                yield {
                    "type": "action_failed",
                    "action_id": "story_build",
                    "action_type": "story_build",
                    "result": {"error": "Failed to parse generated story"},
                }

                yield {
                    "type": "message",
                    "content": full_response,
                }

        except Exception as e:
            logger.error(f"Story build failed: {e}", exc_info=True)
            yield {
                "type": "action_failed",
                "action_id": "story_build",
                "action_type": "story_build",
                "result": {"error": str(e)},
            }
            yield {
                "type": "message",
                "content": f"⚠️ 故事生成时遇到问题: {str(e)}\n请重试或调整创意方向。",
            }

    async def _handle_storyboard(
        self,
        state: StoryGenesisState,
        context: Dict[str, Any],
        streaming: bool,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """处理 STORYBOARD 阶段 — 直接调用 ScriptPipelineService"""

        if not state.screenplay:
            yield {
                "type": "message",
                "content": "⚠️ 缺少剧本，无法生成分镜。",
            }
            return

        lang = state.language

        yield {
            "type": "action_started",
            "action_id": "storyboard_gen",
            "action_type": "generate_storyboard",
            "description": "正在将故事转化为分镜..." if lang == "zh" else "Converting story to storyboard...",
        }

        try:
            # 1. 构建剧本文本
            script_text = self._build_script_text(state)

            # 2. 选择导演风格
            director = self._select_director(state)
            director_name = director.name

            # 3. 构建已有资产上下文（优先使用本次生成的资产）
            assets_index = self._build_assets_context(state)

            # 4. 直接调用 ScriptPipelineService
            from app.services.script_pipeline import ScriptPipelineService
            pipeline = ScriptPipelineService()

            yield {
                "type": "action_progress",
                "action_id": "storyboard_gen",
                "progress": 20,
                "description": f"使用 {director_name} 风格解析剧本..." if lang == "zh" else f"Parsing script with {director_name} style...",
            }

            parse_result, plan_result, bind_result = await pipeline.run_full_pipeline(
                script_text=script_text,
                director=director,
                assets_index=assets_index,
            )

            # 5. 收集结果
            if parse_result.success:
                panel_count = len(plan_result.plan.panels) if plan_result.success and plan_result.plan else 0
                char_count = parse_result.character_count
                scene_count = parse_result.scene_count
                beat_count = parse_result.beat_count
                validation_score = plan_result.plan.validation_score if plan_result.success and plan_result.plan else 0
                missing_assets = bind_result.proposal.pending_count if bind_result.success and bind_result.proposal else 0

                yield {
                    "type": "action_completed",
                    "action_id": "storyboard_gen",
                    "action_type": "generate_storyboard",
                    "result": {
                        "panels": panel_count,
                        "characters": char_count,
                        "scenes": scene_count,
                        "beats": beat_count,
                        "validation_score": validation_score,
                        "missing_assets": missing_assets,
                        "director": director_name,
                    },
                }

                done_msg = (
                    f"🖼️ **分镜计划生成完成！**\n\n"
                    f"🎬 **导演风格**：{director_name}\n"
                    f"📐 **分镜数**：{panel_count} 格\n"
                    f"👥 **角色**：{char_count} | 🏠 **场景**：{scene_count} | 🎭 **节拍**：{beat_count}\n"
                    f"✅ **质量评分**：{validation_score}/100\n"
                ) if lang == "zh" else (
                    f"🖼️ **Storyboard plan generated!**\n\n"
                    f"🎬 **Director style**: {director_name}\n"
                    f"📐 **Panels**: {panel_count}\n"
                    f"👥 **Characters**: {char_count} | 🏠 **Scenes**: {scene_count} | 🎭 **Beats**: {beat_count}\n"
                    f"✅ **Quality score**: {validation_score}/100\n"
                )

                if missing_assets > 0:
                    done_msg += (
                        f"\n⚠️ 还有 {missing_assets} 个资产需要创建。您可以在工作台中管理资产。"
                    ) if lang == "zh" else (
                        f"\n⚠️ {missing_assets} assets still need to be created. Manage them in the Workbench."
                    )

                if plan_result.warnings:
                    done_msg += f"\n\n📝 注意事项：{len(plan_result.warnings)} 条" if lang == "zh" else f"\n\n📝 Warnings: {len(plan_result.warnings)}"

                yield {"type": "message", "content": done_msg}

            else:
                errors = parse_result.errors
                yield {
                    "type": "action_failed",
                    "action_id": "storyboard_gen",
                    "action_type": "generate_storyboard",
                    "result": {"errors": errors},
                }
                error_msg = "\n".join(errors) if errors else "Unknown error"
                yield {
                    "type": "message",
                    "content": f"⚠️ 分镜解析失败:\n{error_msg}" if lang == "zh" else f"⚠️ Storyboard parse failed:\n{error_msg}",
                }

            state.phase = StoryGenesisPhase.COMPLETED

        except Exception as e:
            logger.error(f"Storyboard generation failed: {e}", exc_info=True)
            yield {
                "type": "action_failed",
                "action_id": "storyboard_gen",
                "action_type": "generate_storyboard",
                "result": {"error": str(e)},
            }
            yield {
                "type": "message",
                "content": f"⚠️ 分镜生成失败: {str(e)}",
            }

    async def _handle_completed(
        self,
        user_message: str,
        state: StoryGenesisState,
        context: Dict[str, Any],
        streaming: bool,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """处理 COMPLETED 阶段 — 后续对话（修改、重新生成等）"""

        # 检查是否想重新开始
        restart_keywords = ["重新开始", "新故事", "another story", "start over", "restart"]
        if any(kw in user_message.lower() for kw in restart_keywords):
            # 重置状态
            new_state = StoryGenesisState()
            state.phase = new_state.phase
            state.creative_brief = None
            state.characters = []
            state.screenplay = None
            state.intake_progress = IntakeProgress()

            msg = "🔄 好的，让我们开始一个新故事！\n\n你想创作什么样的故事？" if state.language == "zh" else \
                  "🔄 Let's start a new story!\n\nWhat kind of story would you like to create?"
            yield {"type": "message", "content": msg}
            return

        # 一般后续对话
        messages = self._build_context_messages(context, max_messages=5)
        messages.append({"role": "user", "content": user_message})

        system = (
            "You are a helpful story assistant. The user has completed story generation. "
            "Help them with follow-up questions about their story, characters, or storyboard. "
            "If they want to generate storyboard, remind them the storyboard has been submitted. "
            "If they want to start a new story, tell them to say 'start over' or '重新开始'."
        )

        if streaming:
            async for chunk in self._stream_llm_response(messages=messages, system_prompt=system):
                yield {"type": "message_chunk", "chunk": chunk}
        else:
            response = await self._call_llm(user_message=user_message, system_prompt=system, context=context)
            yield {"type": "message", "content": response}

    # ============ Helpers ============

    def _get_or_create_state(self, context: Dict[str, Any]) -> StoryGenesisState:
        """从对话上下文获取或创建故事状态"""
        context_data = context.get("context_data", {})
        state_data = context_data.get("story_genesis_state")

        if state_data:
            try:
                return StoryGenesisState.model_validate(state_data)
            except Exception:
                logger.warning("Failed to parse stored story state, creating new")

        return StoryGenesisState()

    def _save_state(self, context: Dict[str, Any], state: StoryGenesisState):
        """将状态保存到上下文"""
        if "context_data" not in context:
            context["context_data"] = {}
        context["context_data"]["story_genesis_state"] = state.model_dump()

    def _detect_language(self, text: str) -> str:
        """简单语言检测"""
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        return "zh" if chinese_chars > len(text) * 0.1 else "en"

    def _extract_brief_from_response(self, response: str) -> CreativeBrief | None:
        """从 LLM 响应中提取创意简报 JSON"""
        data = self._extract_json_from_response(response)
        if data and data.get("status") == "brief_complete":
            brief_data = data.get("brief", {})
            try:
                # Parse tone if present
                tone_data = brief_data.pop("tone", {})
                if tone_data:
                    brief_data["tone"] = ToneGuardrails(**tone_data)
                return CreativeBrief(**brief_data)
            except Exception as e:
                logger.warning(f"Failed to parse brief: {e}")
        return None

    def _extract_json_from_response(self, response: str) -> dict | None:
        """从 LLM 响应中提取 JSON 块"""
        import re

        # 尝试 ```json ... ``` 块
        json_match = re.search(r'```json\s*\n(.*?)\n```', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试 { ... } 块
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    def _select_director(self, state: StoryGenesisState):
        """根据 genre 和 tone 自动选择 DirectorProfile"""
        from app.schemas.director_profile import (
            get_default_director,
            get_romance_director,
            get_thriller_director,
            get_contemplative_director,
        )

        # Use stored preset if already selected
        preset = state.director_preset
        if preset == "romance":
            return get_romance_director()
        elif preset == "thriller":
            return get_thriller_director()
        elif preset == "contemplative":
            return get_contemplative_director()
        elif preset != "default" and preset != "auto":
            return get_default_director()

        # Auto-select from genre
        genre = (state.creative_brief.genre if state.creative_brief else "").lower()
        romance_keywords = ["romance", "love", "浪漫", "爱情", "恋爱", "甜宠", "校园"]
        thriller_keywords = ["thriller", "horror", "mystery", "悬疑", "惊悚", "恐怖", "推理", "犯罪"]
        literary_keywords = ["literary", "art", "文艺", "诗意", "哲学", "indie", "实验"]

        if any(kw in genre for kw in romance_keywords):
            state.director_preset = "romance"
            return get_romance_director()
        elif any(kw in genre for kw in thriller_keywords):
            state.director_preset = "thriller"
            return get_thriller_director()
        elif any(kw in genre for kw in literary_keywords):
            state.director_preset = "contemplative"
            return get_contemplative_director()
        else:
            state.director_preset = "default"
            return get_default_director()

    # ============ Asset Persistence + Image Generation ============

    async def _persist_assets_and_generate_images(
        self,
        state: StoryGenesisState,
        project_id: Optional[str],
        lang: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        将生成的角色/场景持久化为 Asset DB 记录，并自动调用
        DoubaoAssetGenerator 生成定妆照和场景空镜图。
        """
        from app.models.asset import Asset

        if not project_id:
            logger.warning("No project_id available, skipping asset persistence")
            yield {
                "type": "message",
                "content": "⚠️ 未找到项目ID，资产入库已跳过。" if lang == "zh"
                           else "⚠️ No project_id found, asset persistence skipped.",
            }
            return

        yield {
            "type": "action_started",
            "action_id": "asset_persist",
            "action_type": "asset_persist",
            "description": "正在入库角色和场景资产..." if lang == "zh"
                           else "Persisting character and scene assets...",
        }

        created_chars: List[Dict[str, Any]] = []
        created_scenes: List[Dict[str, Any]] = []

        # ---- 1. 持久化角色 ----
        for char in state.characters:
            try:
                # 去重检查
                existing = self.db.query(Asset).filter(
                    Asset.project_id == project_id,
                    Asset.name == char.name,
                    Asset.type == "character",
                ).first()

                if existing:
                    state.asset_ids[f"char:{char.name}"] = existing.id
                    created_chars.append({"id": existing.id, "name": char.name, "existed": True})
                    continue

                asset_id = str(uuid.uuid4())
                asset = Asset(
                    id=asset_id,
                    project_id=project_id,
                    name=char.name,
                    type="character",
                    description=char.backstory or f"{char.name} - {char.role}",
                    tags=char.appearance_keywords + char.personality_keywords,
                    status="active",
                    data_json={
                        "source": "story_genesis",
                        "appearance_keywords": char.appearance_keywords,
                        "personality_keywords": char.personality_keywords,
                        "gender": char.gender,
                        "age": char.age,
                        "age_range": char.age_range,
                        "role": char.role,
                        "importance": char.importance,
                        "face_description": char.face_description,
                        "hair_description": char.hair_description,
                        "build": char.build,
                        "distinguishing_features": char.distinguishing_features,
                        "default_outfit": char.default_outfit,
                        "outfit_variants": char.outfit_variants,
                        "visual_tags": char.visual_tags,
                        "core_traits": char.core_traits,
                        "strength": char.strength,
                        "flaw": char.flaw,
                        "speech_pattern": char.speech_pattern,
                        "want": char.want,
                        "need": char.need,
                        "lie": char.lie,
                        "ghost": char.ghost,
                        "backstory": char.backstory,
                    },
                )
                self.db.add(asset)
                state.asset_ids[f"char:{char.name}"] = asset_id
                created_chars.append({"id": asset_id, "name": char.name, "existed": False})

            except Exception as e:
                logger.error(f"Failed to persist character {char.name}: {e}")

        # ---- 2. 持久化场景 ----
        scenes = state.screenplay.scenes if state.screenplay else []
        for scene in scenes:
            try:
                existing = self.db.query(Asset).filter(
                    Asset.project_id == project_id,
                    Asset.name == scene.scene_name,
                    Asset.type == "scene",
                ).first()

                if existing:
                    state.asset_ids[f"scene:{scene.scene_name}"] = existing.id
                    created_scenes.append({"id": existing.id, "name": scene.scene_name, "existed": True})
                    continue

                asset_id = str(uuid.uuid4())
                asset = Asset(
                    id=asset_id,
                    project_id=project_id,
                    name=scene.scene_name,
                    type="scene",
                    description=scene.visual_atmosphere or scene.scene_name,
                    tags=scene.suggested_shot_types,
                    status="active",
                    data_json={
                        "source": "story_genesis",
                        "location": scene.location,
                        "time_of_day": scene.time_of_day,
                        "weather_mood": scene.weather_mood,
                        "characters_present": scene.characters_present,
                        "visual_atmosphere": scene.visual_atmosphere,
                        "lighting": scene.lighting,
                        "key_visual": scene.key_visual,
                        "emotion_label": scene.emotion_label,
                        "pacing": scene.pacing,
                    },
                )
                self.db.add(asset)
                state.asset_ids[f"scene:{scene.scene_name}"] = asset_id
                created_scenes.append({"id": asset_id, "name": scene.scene_name, "existed": False})

            except Exception as e:
                logger.error(f"Failed to persist scene {scene.scene_name}: {e}")

        try:
            self.db.commit()
        except Exception as e:
            logger.error(f"DB commit failed: {e}")
            self.db.rollback()

        new_char_count = sum(1 for c in created_chars if not c.get("existed"))
        new_scene_count = sum(1 for s in created_scenes if not s.get("existed"))
        logger.info(
            f"Persisted assets: {new_char_count} characters, {new_scene_count} scenes"
        )

        # ---- 3. 生成图片 (Doubao Seedream) ----
        try:
            from app.services.doubao_asset_generator import (
                DoubaoAssetGenerator,
                CharacterInfo,
                SceneInfo,
                get_doubao_asset_generator,
            )
            generator = get_doubao_asset_generator()
        except Exception:
            generator = None

        if not generator:
            yield {
                "type": "action_completed",
                "action_id": "asset_persist",
                "action_type": "asset_persist",
                "result": {
                    "characters_created": new_char_count,
                    "scenes_created": new_scene_count,
                    "images_generated": 0,
                },
            }
            yield {
                "type": "message",
                "content": (
                    f"📦 已入库 {new_char_count} 个角色、{new_scene_count} 个场景资产。\n"
                    f"⚠️ 图片生成服务未配置（缺少 ARK_API_KEY），跳过定妆照/空镜图生成。"
                ) if lang == "zh" else (
                    f"📦 Persisted {new_char_count} characters, {new_scene_count} scenes.\n"
                    f"⚠️ Image generation service not configured (missing ARK_API_KEY), skipping portraits/backgrounds."
                ),
            }
            return

        # ---- 3a. 角色定妆照 ----
        portrait_count = 0
        total_chars = len(created_chars)
        for i, char_info in enumerate(created_chars):
            if char_info.get("existed"):
                continue
            char = next((c for c in state.characters if c.name == char_info["name"]), None)
            if not char:
                continue

            yield {
                "type": "action_progress",
                "action_id": "asset_persist",
                "progress": int(30 + 40 * (i + 1) / max(total_chars, 1)),
                "description": (
                    f"🎨 生成角色定妆照: {char.name} ({i + 1}/{total_chars})"
                ) if lang == "zh" else (
                    f"🎨 Generating portrait: {char.name} ({i + 1}/{total_chars})"
                ),
            }

            try:
                char_input = CharacterInfo(
                    name=char.name,
                    gender=char.gender or None,
                    age_range=char.age_range or None,
                    appearance_keywords=char.appearance_keywords or [],
                    personality_keywords=char.personality_keywords or [],
                )
                gen_result = await generator.generate_character_portrait(
                    character=char_input,
                    project_id=project_id,
                    asset_id=char_info["id"],
                    style_hint="韩漫风格" if lang == "zh" else "Korean webtoon style",
                )
                if gen_result.get("success"):
                    portrait_count += 1
                    # 更新 Asset 记录
                    asset = self.db.query(Asset).filter(Asset.id == char_info["id"]).first()
                    if asset:
                        asset.reference_image_path = gen_result.get("image_url")
                        asset.reference_image_status = "ready"
                        asset.thumbnail_url = gen_result.get("thumbnail_url") or gen_result.get("image_url")
                        asset.reference_image_meta = {
                            "provider": "doubao",
                            "embedding_path": gen_result.get("embedding_path"),
                        }
                else:
                    logger.warning(f"Portrait failed for {char.name}: {gen_result.get('error')}")
            except Exception as e:
                logger.error(f"Portrait generation error for {char.name}: {e}")

        # ---- 3b. 场景空镜图 ----
        bg_count = 0
        total_scenes = len(created_scenes)
        for i, scene_info in enumerate(created_scenes):
            if scene_info.get("existed"):
                continue
            scene = next(
                (s for s in scenes if s.scene_name == scene_info["name"]),
                None,
            )
            if not scene:
                continue

            yield {
                "type": "action_progress",
                "action_id": "asset_persist",
                "progress": int(70 + 25 * (i + 1) / max(total_scenes, 1)),
                "description": (
                    f"🏞️ 生成场景空镜图: {scene.scene_name} ({i + 1}/{total_scenes})"
                ) if lang == "zh" else (
                    f"🏞️ Generating background: {scene.scene_name} ({i + 1}/{total_scenes})"
                ),
            }

            try:
                scene_input = SceneInfo(
                    name=scene.scene_name,
                    description=scene.visual_atmosphere or scene.location or scene.scene_name,
                    time_of_day=scene.time_of_day or None,
                    lighting=scene.lighting or None,
                    mood=scene.emotion_label or None,
                )
                gen_result = await generator.generate_scene_background(
                    scene=scene_input,
                    project_id=project_id,
                    asset_id=scene_info["id"],
                    style_hint="韩漫风格" if lang == "zh" else "Korean webtoon style",
                )
                if gen_result.get("success"):
                    bg_count += 1
                    asset = self.db.query(Asset).filter(Asset.id == scene_info["id"]).first()
                    if asset:
                        asset.reference_image_path = gen_result.get("image_url")
                        asset.reference_image_status = "ready"
                        asset.thumbnail_url = gen_result.get("thumbnail_url") or gen_result.get("image_url")
                else:
                    logger.warning(f"Background failed for {scene.scene_name}: {gen_result.get('error')}")
            except Exception as e:
                logger.error(f"Background generation error for {scene.scene_name}: {e}")

        # Commit image URLs
        try:
            self.db.commit()
        except Exception as e:
            logger.error(f"DB commit after image gen failed: {e}")
            self.db.rollback()

        yield {
            "type": "action_completed",
            "action_id": "asset_persist",
            "action_type": "asset_persist",
            "result": {
                "characters_created": new_char_count,
                "scenes_created": new_scene_count,
                "portraits_generated": portrait_count,
                "backgrounds_generated": bg_count,
            },
        }

        img_summary = (
            f"📦 已入库 {new_char_count} 个角色、{new_scene_count} 个场景资产。\n"
            f"🎨 已生成 {portrait_count} 张定妆照、{bg_count} 张场景空镜图。\n"
        ) if lang == "zh" else (
            f"📦 Persisted {new_char_count} characters, {new_scene_count} scenes.\n"
            f"🎨 Generated {portrait_count} portraits, {bg_count} backgrounds.\n"
        )
        yield {"type": "message", "content": img_summary}

    def _build_assets_context(self, state: StoryGenesisState = None) -> Dict[str, list]:
        """从数据库查询已有资产，供 Bind 阶段使用"""
        try:
            from app.models.asset import Asset

            # 优先使用本次生成的资产 ID
            tracked_ids = list(state.asset_ids.values()) if state and state.asset_ids else []

            if tracked_ids:
                assets = self.db.query(Asset).filter(Asset.id.in_(tracked_ids)).all()
            else:
                assets = self.db.query(Asset).filter(Asset.type.in_(["character", "scene"])).all()

            characters = []
            scenes = []
            for a in assets:
                item = {
                    "id": a.id,
                    "name": a.name,
                    "reference_image": a.reference_image_path,
                }
                if a.type == "character":
                    characters.append(item)
                elif a.type == "scene":
                    scenes.append(item)

            return {"characters": characters, "scenes": scenes}
        except Exception as e:
            logger.warning(f"Failed to load assets context: {e}")
            return {"characters": [], "scenes": []}

    def _build_script_text(self, state: StoryGenesisState) -> str:
        """将故事产物转化为管线友好的剧本文本"""
        if not state.screenplay:
            return ""

        parts = []
        sp = state.screenplay
        parts.append(f"# {sp.title}")
        parts.append(f"Genre: {sp.genre}")
        parts.append("")

        # 角色介绍：使用 appearance_keywords（管线优先）或 visual_tags 回退
        if state.characters:
            parts.append("## Characters")
            for char in state.characters:
                visual = ", ".join(char.appearance_keywords) if char.appearance_keywords else \
                         ", ".join(char.visual_tags) if char.visual_tags else char.face_description
                gender_age = f"{char.gender or ''}, {char.age_range or char.age or ''}".strip(", ")
                parts.append(f"**{char.name}**（{gender_age}，{char.role}）")
                parts.append(f"  外观: {visual}")
                if char.default_outfit:
                    parts.append(f"  服装: {char.default_outfit}")
                if char.personality_keywords:
                    parts.append(f"  性格: {', '.join(char.personality_keywords)}")
                elif char.core_traits:
                    parts.append(f"  性格: {', '.join(char.core_traits)}")
                parts.append("")

        # 剧本场景
        for scene in sp.scenes:
            parts.append(f"## Scene {scene.scene_index}: {scene.scene_name}")
            parts.append(f"Location: {scene.location} | Time: {scene.time_of_day} | Weather: {scene.weather_mood}")
            if scene.characters_present:
                parts.append(f"Characters: {', '.join(scene.characters_present)}")
            if scene.visual_atmosphere:
                parts.append(f"Atmosphere: {scene.visual_atmosphere}")
            if scene.emotion_label:
                parts.append(f"Emotion: {scene.emotion_label} | Pacing: {scene.pacing}")
            parts.append("")

            for beat in scene.beats:
                # 使用 source_quote 作为原文（管线溯源关键）
                if beat.source_quote:
                    parts.append(beat.source_quote)
                elif beat.action:
                    parts.append(beat.action)

                for d in beat.dialogue:
                    speaker = d.get("speaker", "")
                    text = d.get("text", "")
                    direction = d.get("direction", "")
                    if direction:
                        parts.append(f"**{speaker}** ({direction}): \"{text}\"")
                    else:
                        parts.append(f"**{speaker}**: \"{text}\"")
                parts.append("")

            if scene.suggested_shot_types:
                parts.append(f"[Camera: {', '.join(scene.suggested_shot_types)}]")
            parts.append("")  # scene separator

        return "\n".join(parts)
