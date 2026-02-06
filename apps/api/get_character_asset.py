
import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

from app.core.database import SessionLocal
from app.models.asset import Asset, AssetType

def get_character():
    print("Starting script...")
    db = SessionLocal()
    try:
        # Find first character asset
        assets = db.query(Asset).all()
        print(f"Total assets: {len(assets)}")
        for i, asset in enumerate(assets):
            print(f"[{i}] {asset.name} ({asset.type}) ID: {asset.id}")
            if asset.type == "character":
                 with open("asset_id.txt", "w") as f:
                     f.write(asset.id)
                 break
        else:
            print("No character found in list")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    get_character()
