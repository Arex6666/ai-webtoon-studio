"""Phase D: episode compose worker (stub, full impl in Task 3.1)."""
from celery import shared_task


@shared_task(bind=True, name="app.workers.episode_compose_worker.execute_episode_compose")
def execute_episode_compose(self, job_id: str):
    raise NotImplementedError("Filled in by Task 3.1")
