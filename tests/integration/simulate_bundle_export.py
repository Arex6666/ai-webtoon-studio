"""
Bundle Export Simulation
"""
import sys
import os
import json
import uuid
import datetime
from unittest.mock import MagicMock, AsyncMock

# Add API to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../apps/api')))

# Mock database models BEFORE importing services to avoid SQLAlchemy connection issues
sys.modules['app.db.database'] = MagicMock()

from app.services.export.bundle_builder import BundleBuilder
from app.services.export.bundle_models import BundleBuildContext
from app.services.storage.object_store import ObjectStore 

# Mock ObjectStore
mock_store = MagicMock(spec=ObjectStore)
mock_store.download_to_file = AsyncMock()
mock_store.upload_file = AsyncMock(return_value="http://mock-storage/file.zip")
mock_store.upload_bytes = AsyncMock(return_value="http://mock-storage/file.json")

# Patch get_object_store
import app.services.export.bundle_builder
app.services.export.bundle_builder.get_object_store = lambda: mock_store

# Mock Models
class MockModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

def run_simulation():
    print("Starting BundleBuilder Simulation...")
    
    # Setup Mock Data
    chapter_id = str(uuid.uuid4())
    panel_id_1 = str(uuid.uuid4())
    lp_id_1 = str(uuid.uuid4())
    
    mock_chapter = MockModel(
        id=chapter_id,
        project_id="proj-123",
        title="Simulated Chapter",
        order_index=1,
        version=1,
        style_profile_json={"style": "anime"}
    )
    
    mock_panel_1 = MockModel(
        id=panel_id_1,
        chapter_id=chapter_id,
        order_index=1,
        spec_json={"shot": {"durationSec": 3.0}},
        params_json={"prompt": "test prompt"},
        active_layer_pack_id=lp_id_1,
        render_status="completed",
        qa_score=0.85,
        preview_url="http://mock/preview.png",
        typeset_image_url="http://mock/typeset.png",
        bubbles_json=[{"text": "Hello"}]
    )
    
    mock_lp_1 = MockModel(
        id=lp_id_1,
        panel_id=panel_id_1,
        version=1,  # Added missing attribute
        status="completed",
        manifest_url="http://mock/lp_manifest.json",
        full_url="http://mock/full.png",
        file_full="http://mock/full.png",
        file_char="http://mock/char.png",
        file_bg="http://mock/bg.png", 
        file_fg=None,
        file_mask=None,
        file_depth=None,  # Added missing attribute
        bbox_json={},     # Added missing attribute
        params_json={"model": "flux-dev", "seed": 123},
        generation_params={"model_name": "flux-dev", "seed": 123},
        width=1024,
        height=1024,
        qa_score=0.9,
        qa_passed="true",
        qa_json={},
        created_at=datetime.datetime.utcnow(),
        metadata_json={}
    )
    
    # Mock DB Session
    mock_db = MagicMock()
    
    # Query Side Effect
    def query_side_effect(model):
        query_mock = MagicMock()
        
        if model.__name__ == 'Chapter':
            query_mock.filter.return_value.first.return_value = mock_chapter
        elif model.__name__ == 'Panel':
            query_mock.filter.return_value.order_by.return_value.all.return_value = [mock_panel_1]
            query_mock.filter.return_value.first.return_value = mock_panel_1 # For single panel query
        elif model.__name__ == 'LayerPack':
            query_mock.filter.return_value.first.return_value = mock_lp_1
            query_mock.filter.return_value.order_by.return_value.first.return_value = mock_lp_1
        elif model.__name__ == 'Job':
             query_mock.filter.return_value.all.return_value = [] # No jobs for now
            
        return query_mock
            
    mock_db.query.side_effect = query_side_effect
    
    # Setup Context
    context = BundleBuildContext(
        export_id="export-sim-1",
        job_id="job-sim-1",
        chapter_id=chapter_id,
        progress_callback=lambda *args, **kwargs: print(f"Progress: {kwargs}")
    )
    
    # Initialize Builder
    builder = BundleBuilder(mock_db, context)
    
    # Run Build (using a wrapper to run async)
    import asyncio
    
    async def _run():
        result = await builder.build()
        
        print(f"\nBuild Result: Success={result.success}")
        if result.success:
            print(f"Bundle URL: {result.bundle_url}")
            print(f"Manifest URL: {result.manifest_url}")
            print(f"QA Summary: {json.dumps(result.qa_summary, indent=2)}")
        else:
            print(f"Error: {result.error_code} - {result.error_message}")
            if result.error_panel_index:
                print(f"Error Panel: {result.error_panel_index}")

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(_run())

if __name__ == "__main__":
    run_simulation()
