"""
Panel Renderer Service - 分镜渲染服务
将 PanelRenderContext 转换为实际渲染请求

Production MVP: 真实渲染功能核心模块
"""
import asyncio
import time
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime

from app.services.layer_factory.render_protocol import (
    PanelRenderContext,
    LayerPackOutput,
    RenderResult,
    generate_trace_id,
    compute_inputs_hash,
    RenderProviderType,
)
from app.services.layer_factory.payload_builder import PayloadBuilder, AssetInjectionConfig
from app.services.layer_factory.comfyui_adapter import get_comfyui_adapter
from app.services.layer_factory.comfyui_client import get_comfyui_client
from app.services.storage import get_object_store

# New image providers
from app.services.layer_factory.tongyi_image_provider import (
    TongyiImageProvider,
    ImageGenerationRequest as TongyiImageRequest,
    get_tongyi_image_provider,
)
from app.services.layer_factory.doubao_image_provider import (
    DoubaoImageProvider,
    DoubaoImageRequest,
    get_doubao_image_provider,
)

logger = logging.getLogger(__name__)


class PanelRenderer:
    """
    分镜渲染器
    
    负责：
    1. 从 PanelRenderContext 构建 ComfyUI 工作流
    2. 提交到渲染 Provider
    3. 等待完成并获取结果
    4. 返回标准化的 LayerPackOutput
    """
    
    def __init__(self, provider: RenderProviderType = RenderProviderType.COMFYUI_LOCAL):
        self.provider = provider
        self.payload_builder = PayloadBuilder()
        self.storage = get_object_store()
    
    async def render(
        self,
        context: PanelRenderContext,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        timeout: int = 300,
    ) -> RenderResult:
        """
        执行分镜渲染
        
        Args:
            context: 渲染上下文
            progress_callback: 进度回调 callback(progress: float, message: str)
            timeout: 超时秒数
            
        Returns:
            RenderResult
        """
        trace_id = generate_trace_id()
        start_time = time.time()
        
        logger.info(f"[PanelRenderer] Starting render for panel {context.panel_id}, trace={trace_id}")
        
        try:
            # 1. 构建资产注入配置
            if progress_callback:
                progress_callback(0.1, "准备渲染参数...")
            
            asset_config = self._build_asset_config(context)
            
            # 2. 构建提示词
            positive_prompt = self._build_prompt(context)
            negative_prompt = context.negative_prompt
            
            logger.info(f"[PanelRenderer] Prompt: {positive_prompt[:100]}...")
            
            # 3. 根据 provider 选择渲染方式
            if self.provider == RenderProviderType.MOCK:
                result = await self._render_mock(context, trace_id)
            elif self.provider == RenderProviderType.TONGYI:
                result = await self._render_tongyi(
                    context=context,
                    positive_prompt=positive_prompt,
                    negative_prompt=negative_prompt,
                    trace_id=trace_id,
                    progress_callback=progress_callback,
                )
            elif self.provider == RenderProviderType.DOUBAO:
                result = await self._render_doubao(
                    context=context,
                    positive_prompt=positive_prompt,
                    negative_prompt=negative_prompt,
                    trace_id=trace_id,
                    progress_callback=progress_callback,
                )
            else:
                # Default to ComfyUI (LOCAL or CLOUD)
                result = await self._render_comfyui(
                    context=context,
                    positive_prompt=positive_prompt,
                    negative_prompt=negative_prompt,
                    asset_config=asset_config,
                    trace_id=trace_id,
                    progress_callback=progress_callback,
                    timeout=timeout,
                )
            
            duration_ms = int((time.time() - start_time) * 1000)
            if result.layerpack:
                result.layerpack.duration_ms = duration_ms
                result.layerpack.trace_id = trace_id
            
            logger.info(f"[PanelRenderer] Completed in {duration_ms}ms, success={result.success}")
            return result
            
        except TimeoutError as e:
            logger.error(f"[PanelRenderer] Timeout: {e}")
            return RenderResult(
                success=False,
                error=f"渲染超时: {timeout}秒",
                error_code="TIMEOUT",
            )
        except Exception as e:
            logger.error(f"[PanelRenderer] Error: {e}", exc_info=True)
            return RenderResult(
                success=False,
                error=str(e),
                error_code="RENDER_FAILED",
            )
    
    def _build_asset_config(self, context: PanelRenderContext) -> AssetInjectionConfig:
        """构建资产注入配置"""
        # 收集角色 embedding
        character_embeddings = {}
        if context.use_faceid:
            for char in context.characters:
                if char.embedding_status == "ready" and char.embedding_path:
                    character_embeddings[char.character_id] = char.embedding_path
        
        # 收集场景控制图
        scene_control_maps = {}
        scene_anchor_url = None
        if context.use_controlnet and context.scene:
            if context.scene.control_status == "ready":
                scene_control_maps = context.scene.control_maps
            if context.scene.anchor_status == "ready":
                scene_anchor_url = context.scene.anchor_image_url
        
        # 画风 LoRA
        style_lora = context.style.lora_path if context.style.lora_path else None
        
        return AssetInjectionConfig(
            character_embeddings=character_embeddings,
            scene_anchor_url=scene_anchor_url,
            scene_control_maps=scene_control_maps,
            style_lora=style_lora,
            style_strength=context.style.lora_strength,
            faceid_strength=context.faceid_strength,
            controlnet_strength=context.controlnet_strength,
        )
    
    def _build_prompt(self, context: PanelRenderContext) -> str:
        """构建渲染提示词"""
        # 如果有覆盖提示词，直接使用
        if context.positive_prompt_override:
            return context.positive_prompt_override
        
        parts = []
        
        # 1. 动作描述
        if context.action_description:
            parts.append(context.action_description)
        
        # 2. 角色一致性提示
        for char in context.characters:
            if char.consistency_prompt:
                parts.append(char.consistency_prompt)
            elif char.name:
                parts.append(f"{char.name}")
        
        # 3. 场景描述
        if context.scene and context.scene.description:
            parts.append(context.scene.description)
        elif context.scene_settings.location_description:
            parts.append(context.scene_settings.location_description)
        
        # 4. 物品描述
        for prop in context.props:
            if prop.prompt_tokens:
                parts.append(prop.prompt_tokens)
            elif prop.name:
                parts.append(prop.name)
        
        # 5. 时间和天气
        time_prompts = {
            "dawn": "dawn, golden hour, warm light",
            "morning": "morning, soft light",
            "noon": "noon, bright sunlight",
            "afternoon": "afternoon, warm light",
            "dusk": "dusk, sunset, orange sky",
            "night": "nighttime, moonlight, dark atmosphere",
            "day": "daytime, natural light",
        }
        parts.append(time_prompts.get(context.scene_settings.time_of_day, ""))
        
        weather_prompts = {
            "clear": "clear sky",
            "cloudy": "cloudy, overcast",
            "rainy": "rainy, wet ground",
            "snowy": "snowy, winter",
            "foggy": "foggy, misty",
            "stormy": "stormy, dramatic sky",
        }
        parts.append(weather_prompts.get(context.scene_settings.weather, ""))
        
        # 6. 镜头语言
        shot_prompts = {
            "extreme_close": "extreme close-up shot, face detail",
            "close": "close-up shot, portrait",
            "medium": "medium shot, upper body",
            "full": "full body shot",
            "wide": "wide shot, environment visible",
            "extreme_wide": "extreme wide shot, panorama",
        }
        parts.append(shot_prompts.get(context.camera.shot_type, ""))
        
        angle_prompts = {
            "eye_level": "eye level view",
            "high": "high angle, looking down",
            "low": "low angle, looking up",
            "bird": "bird's eye view",
            "worm": "worm's eye view",
            "dutch": "dutch angle, tilted",
        }
        parts.append(angle_prompts.get(context.camera.angle, ""))
        
        # 7. 画风
        style_prompts = {
            "korean_webtoon": "korean webtoon style, clean lines, vibrant colors",
            "manga": "manga style, black and white, screentone",
            "manhwa": "manhwa style, soft colors",
            "comic": "western comic style, bold lines",
            "realistic": "realistic, photorealistic",
        }
        parts.append(style_prompts.get(context.style.style_preset, ""))
        
        # 8. 质量标签
        parts.append("masterpiece, best quality, highly detailed")
        
        # 过滤空字符串并连接
        return ", ".join(p for p in parts if p)
    
    async def _render_mock(
        self,
        context: PanelRenderContext,
        trace_id: str,
    ) -> RenderResult:
        """Mock 渲染（用于测试）"""
        # 模拟延迟
        await asyncio.sleep(0.5)
        
        layerpack = LayerPackOutput(
            layerpack_id=f"lp-mock-{context.panel_id[:8]}",
            panel_id=context.panel_id,
            attempt=1,
            full_url="https://picsum.photos/1080/1920",
            provider="mock",
            trace_id=trace_id,
            seed=12345,
            prompt_hash=compute_inputs_hash(context),
        )
        
        return RenderResult(success=True, layerpack=layerpack)
    
    async def _render_comfyui(
        self,
        context: PanelRenderContext,
        positive_prompt: str,
        negative_prompt: str,
        asset_config: AssetInjectionConfig,
        trace_id: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        timeout: int = 300,
    ) -> RenderResult:
        """ComfyUI 真实渲染"""
        adapter = get_comfyui_adapter()
        
        if progress_callback:
            progress_callback(0.2, "提交渲染任务...")
        
        # 1. 提交任务
        seed = context.seed or int(time.time() * 1000) % 2147483647
        
        prompt_id = await adapter.submit(
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            width=context.width,
            height=context.height,
            seed=seed,
            steps=context.steps,
        )
        
        logger.info(f"[PanelRenderer] Submitted ComfyUI job: {prompt_id}")
        
        # 2. 等待完成
        def internal_progress_callback(progress: float):
            if progress_callback:
                # 映射进度: 0.2 -> 0.9
                mapped = 0.2 + progress * 0.7
                progress_callback(mapped, f"渲染中 {int(progress * 100)}%...")
        
        await adapter.wait_for_completion(
            prompt_id=prompt_id,
            timeout=timeout,
            progress_callback=internal_progress_callback,
        )
        
        if progress_callback:
            progress_callback(0.9, "上传结果...")
        
        # 3. 获取并上传结果
        result = await adapter.fetch_and_upload(
            prompt_id=prompt_id,
            project_id=context.project_id,
            chapter_id=context.chapter_id,
            panel_id=context.panel_id,
            attempt=1,
        )
        
        if progress_callback:
            progress_callback(1.0, "完成")
        
        # 4. 构建 LayerPackOutput
        layerpack = LayerPackOutput(
            layerpack_id=result.get("layerpack_id", f"lp-{prompt_id[:8]}"),
            panel_id=context.panel_id,
            attempt=1,
            full_url=result.get("full_url", ""),
            manifest_url=result.get("manifest_url"),
            provider="comfyui",
            trace_id=trace_id,
            seed=seed,
            prompt_hash=compute_inputs_hash(context),
            workflow_id=prompt_id,
        )
        
        return RenderResult(success=True, layerpack=layerpack)
    
    async def _render_tongyi(
        self,
        context: PanelRenderContext,
        positive_prompt: str,
        negative_prompt: str,
        trace_id: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> RenderResult:
        """通义万相渲染"""
        provider = get_tongyi_image_provider()
        
        if not provider:
            return RenderResult(
                success=False,
                error="Tongyi provider not configured (missing TONGYI_API_KEY)",
                error_code="PROVIDER_NOT_CONFIGURED",
            )
        
        if progress_callback:
            progress_callback(0.2, "提交到通义万相...")
        
        # 构建请求
        seed = context.seed or int(time.time() * 1000) % 2147483647
        
        request = TongyiImageRequest(
            panel_id=context.panel_id,
            project_id=context.project_id,
            chapter_id=context.chapter_id,
            prompt=positive_prompt,
            negative_prompt=negative_prompt,
            width=context.width,
            height=context.height,
            seed=seed,
            steps=context.steps,
        )
        
        # 调用生成
        def internal_callback(progress: float, message: str):
            if progress_callback:
                mapped = 0.2 + progress * 0.7
                progress_callback(mapped, message)
        
        result = await provider.generate(request, progress_callback=internal_callback)
        
        if not result.success:
            return RenderResult(
                success=False,
                error=result.error,
                error_code=result.error_code,
            )
        
        if progress_callback:
            progress_callback(0.95, "构建结果...")
        
        # 构建 LayerPackOutput
        layerpack = LayerPackOutput(
            layerpack_id=f"lp-tongyi-{trace_id[:8]}",
            panel_id=context.panel_id,
            attempt=1,
            full_url=result.image_url,
            provider="tongyi",
            trace_id=trace_id,
            seed=result.seed or seed,
            prompt_hash=compute_inputs_hash(context),
            duration_ms=result.generation_time_ms,
        )
        
        if progress_callback:
            progress_callback(1.0, "完成")
        
        return RenderResult(success=True, layerpack=layerpack)
    
    async def _render_doubao(
        self,
        context: PanelRenderContext,
        positive_prompt: str,
        negative_prompt: str,
        trace_id: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
    ) -> RenderResult:
        """豆包渲染"""
        provider = get_doubao_image_provider()
        
        if not provider:
            return RenderResult(
                success=False,
                error="Doubao provider not configured (missing DOUBAO_API_KEY)",
                error_code="PROVIDER_NOT_CONFIGURED",
            )
        
        if progress_callback:
            progress_callback(0.2, "提交到豆包...")
        
        # 构建请求
        seed = context.seed or int(time.time() * 1000) % 2147483647
        
        request = DoubaoImageRequest(
            prompt=positive_prompt,
            negative_prompt=negative_prompt,
            width=context.width,
            height=context.height,
            seed=seed,
            steps=context.steps,
        )
        
        # 调用生成
        def internal_callback(progress: float, message: str):
            if progress_callback:
                mapped = 0.2 + progress * 0.7
                progress_callback(mapped, message)
        
        result = await provider.generate(request, progress_callback=internal_callback)
        
        if not result.success:
            return RenderResult(
                success=False,
                error=result.error,
                error_code=result.error_code,
            )
        
        if progress_callback:
            progress_callback(0.95, "构建结果...")
        
        # 构建 LayerPackOutput
        layerpack = LayerPackOutput(
            layerpack_id=f"lp-doubao-{trace_id[:8]}",
            panel_id=context.panel_id,
            attempt=1,
            full_url=result.image_url,
            provider="doubao",
            trace_id=trace_id,
            seed=result.seed or seed,
            prompt_hash=compute_inputs_hash(context),
            duration_ms=result.generation_time_ms,
        )
        
        if progress_callback:
            progress_callback(1.0, "完成")
        
        return RenderResult(success=True, layerpack=layerpack)


# 全局实例
_renderer: Optional[PanelRenderer] = None


def get_panel_renderer(provider: RenderProviderType = None) -> PanelRenderer:
    """获取 PanelRenderer 实例"""
    global _renderer
    
    if provider is None:
        # 根据配置决定默认 provider
        from app.core.config import settings
        if settings.COMFYUI_URL:
            provider = RenderProviderType.COMFYUI_LOCAL
        else:
            provider = RenderProviderType.MOCK
    
    if _renderer is None or _renderer.provider != provider:
        _renderer = PanelRenderer(provider=provider)
    
    return _renderer


async def render_panel(
    panel_id: str,
    project_id: str,
    chapter_id: str,
    panel_spec: Dict[str, Any],
    assets_lock: Dict[str, Any],
    provider: RenderProviderType = None,
    progress_callback: Optional[Callable[[float, str], None]] = None,
) -> RenderResult:
    """
    便捷函数：渲染单个分镜
    
    Args:
        panel_id: 分镜 ID
        project_id: 项目 ID
        chapter_id: 章节 ID
        panel_spec: 分镜规格 JSON
        assets_lock: 资产锁定 JSON
        provider: 渲染提供商
        progress_callback: 进度回调
        
    Returns:
        RenderResult
    """
    # 构建渲染上下文
    context = PanelRenderContext.from_panel_spec_and_assets(
        panel_id=panel_id,
        project_id=project_id,
        chapter_id=chapter_id,
        panel_spec=panel_spec,
        assets_lock=assets_lock,
    )
    
    # 获取渲染器并执行
    renderer = get_panel_renderer(provider)
    return await renderer.render(context, progress_callback=progress_callback)


__all__ = [
    "PanelRenderer",
    "get_panel_renderer",
    "render_panel",
]
