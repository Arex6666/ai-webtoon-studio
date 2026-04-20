import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.core.database import SessionLocal
from app.models.job import Job

def check_jobs():
    db = SessionLocal()
    try:
        jobs = db.query(Job).filter(Job.type == "storyboard").order_by(Job.created_at.desc()).limit(3).all()
        for j in jobs:
            print(f"Job ID: {j.id} | Status: {j.status} | Created at: {j.created_at}")
            if j.error_json:
                print(f"Error: {j.error_json}")
            print("-" * 40)
    finally:
        db.close()

if __name__ == "__main__":
    check_jobs()
