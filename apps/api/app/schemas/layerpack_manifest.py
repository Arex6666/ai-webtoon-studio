"""
LayerPack Manifest Schema - 图层包清单规格 v1

可复现资产包的完整描述，包含来源追溯、输入依赖、产物清单、几何信息
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


class LayerPackModelRef(BaseModel):
    """模型引用"""
    name: str = Field(..., description="模型名称")
    hash: Optional[str] = Field(None, description="模型文件 hash")
    version_id: Optional[str] = Field(None, description="版本 ID")
    type: str = Field("checkpoint", description="类型: checkpoint/vae/clip/lora/embedding")


class LayerPackWorkflowRef(BaseModel):
    """工作流引用"""
    template_name: str = Field(..., description="模板名称")
    template_hash: Optional[str] = Field(None, description="模板 hash")
    injected_params: Dict[str, Any] = Field(default_factory=dict, description="注入的参数（扁平化）")


class LayerPackRunParams(BaseModel):
    """运行参数"""
    seed: Optional[int] = None
    steps: Optional[int] = None
    cfg: Optional[float] = None
    sampler: Optional[str] = None
    scheduler: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    dtype: Optional[str] = None
    denoise: Optional[float] = None


class LayerPackPromptPack(BaseModel):
    """Prompt 包"""
    positive: str = ""
    negative: str = ""
    style_profile_id: Optional[str] = None
    style_profile_snapshot: Optional[Dict[str, Any]] = None


class LayerPackProvenance(BaseModel):
    """
    LayerPack 来源追溯 - 复现核心
    
    包含足够信息以重建完全相同的生成参数
    """
    # 模型
    model: Optional[LayerPackModelRef] = None
    loras: List[LayerPackModelRef] = Field(default_factory=list)
    embeddings: List[LayerPackModelRef] = Field(default_factory=list)
    
    # 工作流
    workflow: Optional[LayerPackWorkflowRef] = None
    
    # 运行参数
    run: Optional[LayerPackRunParams] = None
    
    # Prompt
    prompt_pack: Optional[LayerPackPromptPack] = None
    prompt_hash: Optional[str] = Field(None, description="Prompt 内容 hash")
    
    # 确定性 key（用于幂等判断）
    deterministic_key: Optional[str] = Field(
        None, 
        description="hash(prompt+seed+model+workflow+size) 用于判断是否可复用"
    )


class LayerPackInputRef(BaseModel):
    """输入引用"""
    id: str
    type: str = Field(..., description="类型: face_embedding/scene_anchor/control_map/init_image/reference_image")
    hash: Optional[str] = None
    url: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LayerPackInputs(BaseModel):
    """
    LayerPack 输入依赖
    """
    # 角色一致性
    face_embedding_id: Optional[str] = None
    face_embedding_hash: Optional[str] = None
    character_id: Optional[str] = None
    
    # 场景控制
    scene_anchor_id: Optional[str] = None
    scene_anchor_hash: Optional[str] = None
    
    # 控制图
    control_maps: List[LayerPackInputRef] = Field(default_factory=list)
    
    # 初始图/参考图
    init_image_url: Optional[str] = None
    reference_images: List[str] = Field(default_factory=list)
    
    # IP-Adapter 参考
    ip_adapter_refs: List[LayerPackInputRef] = Field(default_factory=list)


class LayerPackFileEntry(BaseModel):
    """文件条目"""
    url: str = Field(..., description="文件 URL 或存储 key")
    width: int
    height: int
    format: str = Field("png", description="文件格式")
    size_bytes: Optional[int] = None
    hash: Optional[str] = None


class LayerPackFiles(BaseModel):
    """
    LayerPack 产物文件清单
    """
    # 必须
    full: LayerPackFileEntry = Field(..., description="完整合成图（必须）")
    
    # 可选分层
    char: Optional[LayerPackFileEntry] = Field(None, description="角色层")
    bg: Optional[LayerPackFileEntry] = Field(None, description="背景层")
    fg: Optional[LayerPackFileEntry] = Field(None, description="前景层")
    
    # 遮罩/辅助
    char_mask: Optional[LayerPackFileEntry] = Field(None, description="角色遮罩")
    alpha: Optional[LayerPackFileEntry] = Field(None, description="透明通道")
    depth: Optional[LayerPackFileEntry] = Field(None, description="深度图")
    lineart: Optional[LayerPackFileEntry] = Field(None, description="线稿")
    
    # 缩略图
    thumb: Optional[LayerPackFileEntry] = Field(None, description="缩略图")
    
    # 其他
    extras: Dict[str, LayerPackFileEntry] = Field(default_factory=dict)


class LayerPackBBox(BaseModel):
    """边界框"""
    x: int
    y: int
    width: int
    height: int
    label: Optional[str] = None
    confidence: Optional[float] = None


class LayerPackGeometry(BaseModel):
    """
    LayerPack 几何信息
    """
    width: int = Field(..., description="图片宽度")
    height: int = Field(..., description="图片高度")
    
    # 安全区域（上下左右边距）
    safe_area: Optional[Dict[str, int]] = Field(
        None, 
        description="安全区域 {top, bottom, left, right}"
    )
    
    # DPI（可选）
    dpi: Optional[int] = None
    
    # 边界框
    character_bboxes: List[LayerPackBBox] = Field(default_factory=list, description="角色边界框")
    face_bboxes: List[LayerPackBBox] = Field(default_factory=list, description="人脸边界框")


class LayerPackQuality(BaseModel):
    """
    LayerPack 质量信息
    """
    qa_score: Optional[float] = Field(None, description="总体评分 0-1")
    passed: bool = Field(True, description="是否通过")
    needs_fix: bool = Field(False, description="是否需要修复")
    
    # 细分评分
    face_similarity: Optional[float] = None
    artifact_score: Optional[float] = None
    composition_score: Optional[float] = None
    
    # 问题列表
    issues: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class LayerPackManifest(BaseModel):
    """
    LayerPack 完整清单 - layerpack/manifest.json
    
    这是一个生成产物的权威描述，包含足够信息以复现生成结果
    """
    # 版本与标识
    spec_version: str = Field("1.0.0", description="规格版本")
    layerpack_id: str = Field(..., description="LayerPack UUID")
    panel_id: str = Field(..., description="所属面板 ID")
    version: int = Field(1, description="版本号（同面板多次生成）")
    
    # 来源追溯（复现核心）
    provenance: LayerPackProvenance
    
    # 输入依赖
    inputs: LayerPackInputs = Field(default_factory=LayerPackInputs)
    
    # 产物文件
    files: LayerPackFiles
    
    # 几何信息
    geometry: LayerPackGeometry
    
    # 质量信息
    quality: LayerPackQuality = Field(default_factory=LayerPackQuality)
    
    # 时间戳
    created_at: str = Field(..., description="创建时间 ISO8601")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "spec_version": "1.0.0",
                "layerpack_id": "lp-001",
                "panel_id": "panel-001",
                "version": 1,
                "provenance": {
                    "model": {"name": "flux-dev", "type": "checkpoint"},
                    "workflow": {"template_name": "flux_basic"},
                    "run": {"seed": 12345, "steps": 20, "cfg": 7.5}
                },
                "files": {
                    "full": {"url": "/storage/full.png", "width": 1080, "height": 1920, "format": "png"}
                },
                "geometry": {"width": 1080, "height": 1920},
                "created_at": "2026-01-17T10:00:00Z"
            }
        }


def create_layerpack_manifest_from_db(
    layerpack,  # LayerPack model instance
    panel_spec: Optional[Dict] = None,
    job_data: Optional[Dict] = None
) -> LayerPackManifest:
    """
    从数据库 LayerPack 模型创建 Manifest
    
    Args:
        layerpack: LayerPack 数据库模型实例
        panel_spec: 可选的 PanelSpec 数据
        job_data: 可选的 Job 数据（用于提取 provenance）
    
    Returns:
        LayerPackManifest 实例
    """
    from datetime import datetime
    
    # 构建 files
    files_data = {
        "full": LayerPackFileEntry(
            url=layerpack.full_url or layerpack.file_full or "",
            width=layerpack.width or 1080,
            height=layerpack.height or 1920,
            format="png"
        )
    }
    
    if layerpack.file_char:
        files_data["char"] = LayerPackFileEntry(
            url=layerpack.file_char,
            width=layerpack.width or 1080,
            height=layerpack.height or 1920,
            format="png"
        )
    
    if layerpack.file_bg:
        files_data["bg"] = LayerPackFileEntry(
            url=layerpack.file_bg,
            width=layerpack.width or 1080,
            height=layerpack.height or 1920,
            format="png"
        )
    
    if layerpack.file_fg:
        files_data["fg"] = LayerPackFileEntry(
            url=layerpack.file_fg,
            width=layerpack.width or 1080,
            height=layerpack.height or 1920,
            format="png"
        )
    
    if layerpack.file_mask:
        files_data["char_mask"] = LayerPackFileEntry(
            url=layerpack.file_mask,
            width=layerpack.width or 1080,
            height=layerpack.height or 1920,
            format="png"
        )
    
    if layerpack.file_depth:
        files_data["depth"] = LayerPackFileEntry(
            url=layerpack.file_depth,
            width=layerpack.width or 1080,
            height=layerpack.height or 1920,
            format="png"
        )
    
    # 构建 provenance
    params = layerpack.params_json or {}
    gen_params = layerpack.generation_params or {}
    
    provenance = LayerPackProvenance(
        model=LayerPackModelRef(
            name=gen_params.get("model_name", params.get("model", "unknown")),
            type="checkpoint"
        ) if gen_params.get("model_name") or params.get("model") else None,
        run=LayerPackRunParams(
            seed=gen_params.get("seed") or params.get("seed"),
            steps=gen_params.get("steps") or params.get("steps"),
            cfg=gen_params.get("cfg") or params.get("cfg"),
            sampler=gen_params.get("sampler"),
            width=layerpack.width,
            height=layerpack.height
        ),
        prompt_pack=LayerPackPromptPack(
            positive=params.get("positive_prompt", ""),
            negative=params.get("negative_prompt", "")
        ) if params.get("positive_prompt") else None
    )
    
    # 构建 quality
    quality = LayerPackQuality(
        qa_score=layerpack.qa_score,
        passed=layerpack.qa_passed == "true",
        needs_fix=layerpack.qa_passed != "true" and layerpack.qa_score and layerpack.qa_score < 0.6,
        issues=(layerpack.qa_json or {}).get("issues", [])
    )
    
    # 构建 geometry
    geometry = LayerPackGeometry(
        width=layerpack.width or 1080,
        height=layerpack.height or 1920
    )
    
    # 添加 bbox
    if layerpack.bbox_json:
        for key, bbox in layerpack.bbox_json.items():
            if "face" in key.lower():
                geometry.face_bboxes.append(LayerPackBBox(**bbox))
            elif "char" in key.lower():
                geometry.character_bboxes.append(LayerPackBBox(**bbox))
    
    return LayerPackManifest(
        spec_version="1.0.0",
        layerpack_id=layerpack.id,
        panel_id=layerpack.panel_id,
        version=layerpack.version or 1,
        provenance=provenance,
        inputs=LayerPackInputs(),  # TODO: 从 job 数据填充
        files=LayerPackFiles(**files_data),
        geometry=geometry,
        quality=quality,
        created_at=layerpack.created_at.isoformat() if layerpack.created_at else datetime.utcnow().isoformat(),
        metadata=layerpack.metadata_json or {}
    )
