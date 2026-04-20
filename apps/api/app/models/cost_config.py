"""
ProviderCostConfig Model - 提供商成本配置 (E4: Cost Metering)
"""
from sqlalchemy import Column, String, Float, Boolean, JSON
from app.models.base import Base, TimestampMixin
import uuid


class ProviderCostConfig(Base, TimestampMixin):
    """提供商成本配置"""
    __tablename__ = "provider_cost_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider = Column(String(50), unique=True, nullable=False)

    # Cost rates
    cost_per_image = Column(Float, default=0.0)
    cost_per_video_second = Column(Float, default=0.0)
    cost_per_1k_input_tokens = Column(Float, default=0.0)
    cost_per_1k_output_tokens = Column(Float, default=0.0)

    # Tier multipliers
    tier_multipliers = Column(JSON, default={"fast": 0.2, "normal": 1.0, "hero": 2.5})

    # Status
    active = Column(Boolean, default=True)

    def __repr__(self):
        return f"<ProviderCostConfig {self.provider}>"
