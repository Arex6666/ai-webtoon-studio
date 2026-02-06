"""
数据库连接配置
"""
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.models.base import Base  # 使用统一的 Base
import logging

logger = logging.getLogger(__name__)

# 创建数据库引擎
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    echo=False  # Disabled to avoid Windows console encoding issues
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """获取数据库会话（FastAPI 依赖注入）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def run_migrations():
    """执行简单的数据库迁移（无 Alembic 时的轻量方案）"""
    from sqlalchemy import text

    with engine.connect() as connection:
        inspector = inspect(connection)
        # 检查 projects 表是否存在 creation_method 列
        try:
            columns = [c['name'] for c in inspector.get_columns('projects')]
            if 'creation_method' not in columns:
                logger.info("Adding 'creation_method' to 'projects' table...")
                connection.execute(
                    text("ALTER TABLE projects ADD COLUMN creation_method VARCHAR(32) NOT NULL DEFAULT 'agent'")
                )
                connection.commit()
                logger.info("Column 'creation_method' added.")
        except Exception as e:
            logger.warning(f"Migration check failed (this may be normal if table doesn't exist yet): {e}")


def init_db():
    """初始化数据库表

    生产环境建议使用 Alembic 管理迁移，不在应用启动时执行 DDL。
    """
    # 导入所有模型确保它们被注册到 Base.metadata
    from app import models

    if settings.DB_AUTO_CREATE:
        Base.metadata.create_all(bind=engine, checkfirst=True)

    if settings.DB_RUN_LIGHT_MIGRATIONS:
        run_migrations()