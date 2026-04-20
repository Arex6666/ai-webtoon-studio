import sys
import os

# Set up path so we can import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import SessionLocal
from app.models.project import Project

def test_delete():
    db = SessionLocal()
    try:
        project_id = "9ec7d9c4-c324-4ead-9609-c56c7cdf3529"
        project = db.query(Project).filter(Project.id == project_id).first()
        if not project:
            print("Project not found")
            return
            
        print(f"Found project: {project.name}, attempting delete...")
        db.delete(project)
        db.commit()
        print("Success! Apparently?")
    except Exception as e:
        print("DELETE FAILED!")
        print("EXCEPTION TYPE:", type(e))
        print("EXCEPTION DETAILS:", str(e))
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    test_delete()
