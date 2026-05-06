"""
应用配置 - 使用 Pydantic Settings 管理环境变量
"""
from pydantic_settings import BaseSettings
from typing import Optional, List, Union, Any
from pydantic import field_validator
from functools import lru_cache
from pathlib import Path


def find_env_file() -> Optional[str]:
    """查找 .env 文件，支持多个可能的位置"""
    current = Path(__file__).resolve().parent  # app/core
    
    # 向上查找 .env 文件
    for _ in range(5):  # 最多向上查找5层
        env_path = current / ".env"
        if env_path.exists():
            return str(env_path)
        current = current.parent
    
    return None


class Settings(BaseSettings):
    """应用配置"""
    
    # App
    APP_NAME: str = "AI Webtoon Studio"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    
    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/webtoon_studio"
    
    # Redis
    REDIS_URL: str = "redis://127.0.0.1:6379/0"
    
    # MinIO S3
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "webtoon-assets"
    MINIO_SECURE: bool = False
    
    # ComfyUI (empty = use mock)
    COMFYUI_URL: Optional[str] = None
    
    # LLM Provider
    # options: openai, deepseek, tongyi, doubao
    LLM_PROVIDER: str = "openai"
    LLM_BASE_URL: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gpt-4o-mini"
    
    # Provider-specific configurations
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-chat"
    
    TONGYI_API_KEY: Optional[str] = None
    TONGYI_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    TONGYI_MODEL: str = "qwen-max"
    
    DOUBAO_API_KEY: Optional[str] = None
    DOUBAO_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"
    DOUBAO_MODEL: str = "doubao-pro-32k"
    
    # 火山引擎方舟 API Key (用于 Seedream 图片生成)
    ARK_API_KEY: Optional[str] = None
    DOUBAO_IMAGE_MODEL: str = "doubao-seedream-4.5"  # 默认图片生成模型

    # B-1 Agent Runner — model routing
    LLM_MODEL_FLAGSHIP: str = "doubao-pro-32k"
    LLM_MODEL_MID: str = "doubao-pro"
    LLM_MODEL_FAST: str = "doubao-lite-32k"
    LLM_MAX_RETRIES: int = 3
    LLM_TIMEOUT_SECONDS: int = 60
    LLM_PROMPT_CACHE_ENABLED: bool = True

    # B-1 Anthropic provider (no existing key)
    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_BASE_URL: Optional[str] = None    # None = SDK default

    # B-1 Skill loader
    SKILL_GUIDANCE_TOKEN_CAP: int = 10000
    WEBTOON_DATA_DIR: str = "~/.webtoon"
    
    # Video Generation Providers (optional, falls back to LLM keys if not set)
    TONGYI_VIDEO_MODEL: str = "wanx2.1-i2v-plus"  # 图生视频
    DOUBAO_VIDEO_API_KEY: Optional[str] = None  # 视频生成独立 Key
    DOUBAO_VIDEO_ENDPOINT: str = "https://open.volcengineapi.com"
    
    # Volcengine/Jimeng Image Generation (已弃用，改用 ARK_API_KEY)
    VOLCENGINE_ACCESS_KEY_ID: Optional[str] = None
    VOLCENGINE_SECRET_ACCESS_KEY: Optional[str] = None
    
    @property
    def effective_llm_api_key(self) -> Optional[str]:
        """根据 LLM_PROVIDER 获取对应的 API Key"""
        if self.LLM_API_KEY:
            return self.LLM_API_KEY
        provider_map = {
            "openai": self.OPENAI_API_KEY,
            "deepseek": self.DEEPSEEK_API_KEY,
            "tongyi": self.TONGYI_API_KEY,
            "doubao": self.DOUBAO_API_KEY,
        }
        return provider_map.get(self.LLM_PROVIDER)
    
    @property
    def effective_llm_base_url(self) -> str:
        """根据 LLM_PROVIDER 获取对应的 Base URL"""
        if self.LLM_BASE_URL:
            return self.LLM_BASE_URL
        provider_map = {
            "openai": self.OPENAI_BASE_URL,
            "deepseek": self.DEEPSEEK_BASE_URL,
            "tongyi": self.TONGYI_BASE_URL,
            "doubao": self.DOUBAO_BASE_URL,
        }
        return provider_map.get(self.LLM_PROVIDER, "https://api.openai.com/v1")
    
    @property
    def effective_llm_model(self) -> str:
        """根据 LLM_PROVIDER 获取对应的模型名"""
        if self.LLM_MODEL != "gpt-4o-mini":  # 非默认值说明用户显式设置了
            return self.LLM_MODEL
        provider_map = {
            "openai": self.OPENAI_MODEL,
            "deepseek": self.DEEPSEEK_MODEL,
            "tongyi": self.TONGYI_MODEL,
            "doubao": self.DOUBAO_MODEL,
        }
        return provider_map.get(self.LLM_PROVIDER, self.LLM_MODEL)
    
    # JWT
    JWT_SECRET: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    # Auth / Users
    # 当 ENABLE_AUTH=true 时，所有受保护路由都需要 Bearer JWT。
    ENABLE_AUTH: bool = True

    # DB init strategy
    # 生产环境建议禁用自动建表/运行时迁移，改用 Alembic。
    DB_AUTO_CREATE: bool = False
    DB_RUN_LIGHT_MIGRATIONS: bool = False
    # 首次启动时可用该账户初始化管理员用户（仅在 users 表为空时生效）
    INITIAL_ADMIN_USERNAME: str = "admin"
    INITIAL_ADMIN_PASSWORD: str = "admin"
    INITIAL_ADMIN_EMAIL: str = "admin@example.com"
    INITIAL_ADMIN_NAME: str = "Administrator"
    
    # CORS
    # 支持 JSON 字符串或列表 (e.g. '["http://localhost:3000"]' or "http://localhost:3000,http://example.com")
    CORS_ORIGINS: Any = [
        "http://localhost:3000", 
        "http://127.0.0.1:3000",
        "http://localhost:3001", 
        "http://127.0.0.1:3001"
    ]
    
    @field_validator("CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)
    
    
    model_config = {
        "env_file": find_env_file(),
        "case_sensitive": True,
        "extra": "ignore"
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
