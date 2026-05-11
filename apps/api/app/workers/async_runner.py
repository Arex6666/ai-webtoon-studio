"""
Async Task Runner Worker
为原本在 FastAPI BackgroundTasks 中执行的异步任务提供 Celery 包装，从而减轻 API 主进程的负载。
所有涉及数据库操作的任务会在内部自动创建和关闭 SessionLocal 实例。
"""
import asyncio
import logging
from celery import shared_task

logger = logging.getLogger(__name__)

def get_event_loop():
    """获取或创建当前线程的 Event Loop"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop

@shared_task(bind=True, name="app.workers.async_runner.run_portrait_generation")
def run_portrait_generation(
    self, character_id, project_id, character_name, character_description, appearance_traits, provider
):
    from app.services.portrait.retry_strategy import enqueue_portrait_generation
    loop = get_event_loop()
    return loop.run_until_complete(
        enqueue_portrait_generation(
            character_id=character_id,
            project_id=project_id,
            character_name=character_name,
            character_description=character_description,
            appearance_traits=appearance_traits,
            provider=provider,
            db_session=None
        )
    )

@shared_task(bind=True, name="app.workers.async_runner.run_scene_anchor_generation")
def run_scene_anchor_generation(
    self, scene_id, project_id, scene_name, location, time_of_day=None, mood=None
):
    from app.services.scene.retry_strategy import enqueue_scene_anchor_generation
    loop = get_event_loop()
    return loop.run_until_complete(
        enqueue_scene_anchor_generation(
            scene_id=scene_id,
            project_id=project_id,
            scene_name=scene_name,
            location=location,
            time_of_day=time_of_day,
            mood=mood,
            db_session=None,
        )
    )

@shared_task(bind=True, name="app.workers.async_runner.run_autobuild_characters_task")
def run_autobuild_characters_task(self, job_id, chapter_id, characters, config):
    from app.services.canonical.canonical_generator import run_autobuild_characters
    loop = get_event_loop()
    return loop.run_until_complete(
        run_autobuild_characters(
            job_id=job_id,
            chapter_id=chapter_id,
            characters=characters,
            config=config,
            db_session=None
        )
    )

@shared_task(bind=True, name="app.workers.async_runner.run_automation_task_celery")
def run_automation_task_celery(self, job_id, chapter_id, script_text, config_dict):
    from app.api.routes.automation import _run_automation_task
    from app.db.database import SessionLocal
    db = SessionLocal()
    try:
        loop = get_event_loop()
        return loop.run_until_complete(
            _run_automation_task(job_id, chapter_id, script_text, config_dict, db)
        )
    finally:
        db.close()

@shared_task(bind=True, name="app.workers.async_runner.run_batch_render_task_celery")
def run_batch_render_task_celery(self, job_ids, max_retries):
    from app.api.routes.batch_render import run_batch_render_task
    loop = get_event_loop()
    return loop.run_until_complete(
        run_batch_render_task(job_ids, max_retries)
    )

@shared_task(bind=True, name="app.workers.async_runner.run_storyboard_task_celery")
def run_storyboard_task_celery(self, job_id, chapter_id, script, style_hint, provider, auto_apply):
    from app.api.routes.chapters.storyboard import run_storyboard_task
    loop = get_event_loop()
    return loop.run_until_complete(
        run_storyboard_task(
            job_id=job_id, 
            chapter_id=chapter_id, 
            script=script, 
            style_hint=style_hint, 
            provider=provider, 
            auto_apply=auto_apply
        )
    )

@shared_task(bind=True, name="app.workers.async_runner.run_batch_render_celery")
def run_batch_render_celery(self, render_job_id, chapter_id):
    from app.api.routes.chapters.automation import run_batch_render
    loop = get_event_loop()
    return loop.run_until_complete(
        run_batch_render(render_job_id, chapter_id)
    )

@shared_task(bind=True, name="app.workers.async_runner.execute_compose_job_celery")
def execute_compose_job_celery(self, job_id, chapter_id):
    from app.api.routes.compose import execute_compose_job
    loop = get_event_loop()
    return loop.run_until_complete(
        execute_compose_job(job_id, chapter_id)
    )

@shared_task(bind=True, name="app.workers.async_runner.extract_faceid_task_celery")
def extract_faceid_task_celery(self, task_id, character_id, reference_image_path, project_id, force_regenerate):
    from app.api.routes.faceid import extract_task
    loop = get_event_loop()
    return loop.run_until_complete(
        extract_task(
            task_id=task_id, 
            character_id=character_id, 
            reference_image_path=reference_image_path, 
            project_id=project_id, 
            force_regenerate=force_regenerate
        )
    )

@shared_task(bind=True, name="app.workers.async_runner.generate_music_task_celery")
def generate_music_task_celery(self, music_id, prompt, style, duration):
    from app.api.routes.music import _generate_music_task
    loop = get_event_loop()
    return loop.run_until_complete(
        _generate_music_task(
            music_id=music_id,
            prompt=prompt,
            style=style,
            duration=duration
        )
    )

@shared_task(bind=True, name="app.workers.async_runner.execute_render_job_celery")
def execute_render_job_celery(self, job_id, panel_id):
    from app.api.routes.render import execute_render_job
    loop = get_event_loop()
    return loop.run_until_complete(
        execute_render_job(job_id, panel_id)
    )
