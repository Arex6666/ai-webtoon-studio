"""
清空项目资产的脚本
使用方法: python scripts/clear_project_assets.py <project_id>
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SessionLocal
from app.models.asset import Asset
from app.models.prop_asset import PropAsset
from app.models.outfit_variant import OutfitVariant
from app.models.asset_relation import AssetRelation


def clear_project_assets(project_id: str, keep_types: list = None):
    """
    清空项目的所有资产
    
    Args:
        project_id: 项目ID
        keep_types: 要保留的资产类型，如 ["style"]
    """
    db = SessionLocal()
    keep_types = keep_types or []
    
    try:
        # 1. 清空 PropAssets
        prop_count = db.query(PropAsset).filter(
            PropAsset.project_id == project_id
        ).delete()
        print(f"Deleted {prop_count} PropAssets")
        
        # 2. 清空 AssetRelations
        rel_count = db.query(AssetRelation).filter(
            AssetRelation.project_id == project_id
        ).delete()
        print(f"Deleted {rel_count} AssetRelations")
        
        # 3. 清空 OutfitVariants (通过 character assets)
        char_ids = [a.id for a in db.query(Asset).filter(
            Asset.project_id == project_id,
            Asset.type == "character"
        ).all()]
        if char_ids:
            outfit_count = db.query(OutfitVariant).filter(
                OutfitVariant.character_asset_id.in_(char_ids)
            ).delete(synchronize_session=False)
            print(f"Deleted {outfit_count} OutfitVariants")
        
        # 4. 清空 Assets (除了保留类型)
        query = db.query(Asset).filter(Asset.project_id == project_id)
        if keep_types:
            query = query.filter(Asset.type.notin_(keep_types))
        
        asset_count = query.delete(synchronize_session=False)
        print(f"Deleted {asset_count} Assets")
        
        db.commit()
        print(f"\n✅ Project {project_id} assets cleared successfully!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python clear_project_assets.py <project_id> [--keep-styles]")
        sys.exit(1)
    
    project_id = sys.argv[1]
    keep_types = []
    
    if "--keep-styles" in sys.argv:
        keep_types.append("style")
    
    print(f"Clearing assets for project: {project_id}")
    if keep_types:
        print(f"Keeping types: {keep_types}")
    
    confirm = input("Are you sure? (y/N): ")
    if confirm.lower() == 'y':
        clear_project_assets(project_id, keep_types)
    else:
        print("Cancelled")
