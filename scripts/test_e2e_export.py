
"""
End-to-End Test for Bundle Export
=================================
This script verifies the entire bundle export pipeline using:
- Real Database
- Real MinIO Object Storage
- Real BundleBuilder Service

It bypasses the Celery worker to run synchronously for easier debugging.
"""
import sys
import os
import asyncio
import logging
from datetime import datetime, timedelta
import uuid

# Add apps/api to path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from app.db.session import SessionLocal
from app.services.storage.object_store import get_object_store
from app.services.export.bundle_builder import BundleBuilder
from app.services.export.bundle_models import BundleBuildContext
from app.models import Chapter, Panel, LayerPack, Project

# Configure Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_e2e")

async def setup_test_data(db, object_store):
    """Setup test chapter, panels, and assets"""
    logger.info("Setting up test data...")
    
    # 1. Project
    project = db.query(Project).filter(Project.title == "E2E Test Project").first()
    if not project:
        project = Project(id=str(uuid.uuid4()), title="E2E Test Project")
        db.add(project)
        db.commit()
    
    # 2. Chapter
    chapter = db.query(Chapter).filter(Chapter.title == "E2E Export Test").first()
    if not chapter:
        chapter = Chapter(
            id=str(uuid.uuid4()),
            project_id=project.id,
            title="E2E Export Test",
            order_index=999
        )
        db.add(chapter)
        db.commit()
    logger.info(f"Using Chapter: {chapter.id}")
    
    # 3. Create dummy image
    dummy_img_content = b"fake_png_content" * 100
    dummy_key = f"test/assets/{uuid.uuid4()}.png"
    await object_store.upload_data(dummy_img_content, dummy_key, "image/png")
    
    # 4. Panels & LayerPacks
    # Create 3 panels
    panel_ids = []
    for i in range(3):
        # Panel
        panel = db.query(Panel).filter(
            Panel.chapter_id == chapter.id,
            Panel.order_index == i
        ).first()
        
        if not panel:
            panel = Panel(
                id=str(uuid.uuid4()),
                chapter_id=chapter.id,
                order_index=i,
                spec_json={"shot": {"durationSec": 2.0}},
                qa_score=0.8
            )
            db.add(panel)
            db.flush()
        
        panel_ids.append(panel.id)
        
        # LayerPack
        lp = db.query(LayerPack).filter(LayerPack.panel_id == panel.id).first()
        if not lp:
            lp = LayerPack(
                id=str(uuid.uuid4()),
                panel_id=panel.id,
                status="completed",
                file_full=dummy_key, # Use the S3 key directly
                gallery_images=[dummy_key],
                created_at=datetime.utcnow()
            )
            db.add(lp)
            db.flush()
            
            # Update panel to point to this LP
            panel.active_layer_pack_id = lp.id
            panel.preview_url = dummy_key # For fallback
            
    db.commit()
    return chapter.id

async def run_test():
    db = SessionLocal()
    object_store = get_object_store()
    
    try:
        # 1. Setup Data
        chapter_id = await setup_test_data(db, object_store)
        
        # 2. Prepare Context
        export_id = str(uuid.uuid4())
        job_id = str(uuid.uuid4())
        
        context = BundleBuildContext(
            export_id=export_id,
            job_id=job_id,
            chapter_id=chapter_id,
            progress_callback=lambda **kwargs: logger.info(f"Progress: {kwargs.get('stage')} {int(kwargs.get('progress',0)*100)}%")
        )
        
        # 3. Run Builder
        logger.info(f"Starting Bundle Build (Export ID: {export_id})")
        builder = BundleBuilder(db, context)
        result = await builder.build()
        
        # 4. Verify Result
        if result.success:
            logger.info("✅ Build SUCCESS")
            logger.info(f"Bundle URL: {result.bundle_url}")
            logger.info(f"Manifest URL: {result.manifest_url}")
            logger.info(f"Total Bytes: {result.total_bytes}")
            logger.info(f"Panel Count: {result.panel_count}")
            
            # Verify URLs exist
            if await object_store.exists(result.bundle_url):
                 logger.info("✅ Verified: Bundle object exists in MinIO")
            else:
                 logger.error("❌ Bundle object NOT found in MinIO")
                 
            if await object_store.exists(result.manifest_url):
                 logger.info("✅ Verified: Manifest object exists in MinIO")
            else:
                 logger.error("❌ Manifest object NOT found in MinIO")
                 
        else:
            logger.error(f"❌ Build FAILED: {result.error_message}")
            if result.error_panel_index:
                logger.error(f"Error at Panel: {result.error_panel_index}")
                
    except Exception as e:
        logger.exception("Test failed with exception")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_test())
