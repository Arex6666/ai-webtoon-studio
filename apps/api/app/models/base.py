"""
SQLAlchemy Base Model
"""
from sqlalchemy import Column, DateTime, func
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class TimestampMixin:
    """时间戳 Mixin"""
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
