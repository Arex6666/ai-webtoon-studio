# Database aliases - 重定向到 app.core.database
# 这个文件为了兼容性而存在，所有 from app.db.database import ... 的导入
# 都会被自动重定向到正确的位置

from app.core.database import get_db, SessionLocal, engine

__all__ = ["get_db", "SessionLocal", "engine"]
