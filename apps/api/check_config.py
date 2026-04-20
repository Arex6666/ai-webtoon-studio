import sys
sys.path.insert(0, ".")
from app.core.config import settings
print(f"DATABASE_URL = {settings.DATABASE_URL}")
print(f"DB_AUTO_CREATE = {settings.DB_AUTO_CREATE}")
print(f"env_file = {settings.model_config.get('env_file')}")
