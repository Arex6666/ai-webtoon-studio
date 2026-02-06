"""
数据库迁移脚本：添加 S3-04 ~ S3-06 的新字段
运行方式：python -m app.scripts.fix_db_columns
"""
import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.core.database import engine

def add_missing_columns():
    """添加数据库中缺失的列"""
    with engine.connect() as conn:
        # Chapter 表新增字段
        chapter_columns = [
            ("script_version", "INTEGER DEFAULT 0"),
            ("storyboard_version", "INTEGER DEFAULT 0"),
            ("assets_lock_json", "JSON"),
            ("timeline_json", "JSON"),  # P0-TL-01: Timeline clips
        ]
        
        for col_name, col_type in chapter_columns:
            try:
                conn.execute(text(f"ALTER TABLE chapters ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                print(f"✓ chapters.{col_name} added/exists")
            except Exception as e:
                print(f"✗ chapters.{col_name}: {e}")
        
        # StoryboardDraft 表新增字段
        draft_columns = [
            ("script_version_on_create", "INTEGER"),
            ("applied_as_storyboard_version", "INTEGER"),
        ]
        
        for col_name, col_type in draft_columns:
            try:
                conn.execute(text(f"ALTER TABLE storyboard_drafts ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                print(f"✓ storyboard_drafts.{col_name} added/exists")
            except Exception as e:
                print(f"✗ storyboard_drafts.{col_name}: {e}")
        
        conn.commit()
        print("\n✓ Migration complete!")

if __name__ == "__main__":
    add_missing_columns()
