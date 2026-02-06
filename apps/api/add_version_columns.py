"""
数据库迁移脚本 - 添加 S4-01 版本追溯列

运行方式: python add_version_columns.py
"""
import sys
sys.path.insert(0, '.')

from app.core.database import SessionLocal, engine
from sqlalchemy import text

def migrate():
    """添加 schema_version, prompt_version, script_digest, analysis_digest 列"""
    
    columns_to_add = [
        ("schema_version", "VARCHAR(50) DEFAULT 'storyboard_draft_v2'"),
        ("prompt_version", "VARCHAR(50) DEFAULT 'pc_v1'"),
        ("script_digest", "VARCHAR(64)"),
        ("analysis_digest", "VARCHAR(64)"),
    ]
    
    with engine.connect() as conn:
        for col_name, col_def in columns_to_add:
            try:
                # 检查列是否存在
                result = conn.execute(text(f"""
                    SELECT column_name FROM information_schema.columns 
                    WHERE table_name = 'storyboard_drafts' AND column_name = '{col_name}'
                """))
                exists = result.fetchone() is not None
                
                if not exists:
                    sql = f"ALTER TABLE storyboard_drafts ADD COLUMN {col_name} {col_def}"
                    conn.execute(text(sql))
                    print(f"✅ Added column: {col_name}")
                else:
                    print(f"⏭️ Column already exists: {col_name}")
                    
            except Exception as e:
                print(f"❌ Error adding {col_name}: {e}")
        
        conn.commit()
    
    print("\n✅ Migration completed!")

if __name__ == "__main__":
    migrate()
