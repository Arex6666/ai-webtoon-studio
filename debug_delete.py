"""Debug script to test project listing"""
import sys
import os

os.chdir('apps/api')
sys.path.insert(0, '.')

from app.core.database import SessionLocal, init_db
from app.models.project import Project

# Initialize database
init_db()

db = SessionLocal()

try:
    project_id = '8f5f4097-0291-43d8-bd24-efbbdb258621'
    
    # Just query the project without eager loading
    print("Executing simple query...")
    project = db.query(Project).filter(Project.id == project_id).first()
    
    if not project:
        print(f"Project {project_id} not found")
    else:
        print(f"Found project: {project.name}")
        print("SUCCESS - Query works!")
        
except Exception as e:
    import traceback
    print(f"Error Type: {type(e).__name__}")
    print(f"Error: {e}")
    print("=" * 40)
    traceback.print_exc()
finally:
    db.close()
