"""Static-source regression: Phase D real implementations are live (not stubbed)."""
import inspect

from app.workers import episode_compose_worker, episode_video_worker
from app.services.video import compose_dispatch
from app.api.routes import episode_video as episode_video_routes


def test_compose_worker_uses_ffmpeg():
    src = inspect.getsource(episode_compose_worker)
    assert "import subprocess" in src
    assert '"ffmpeg"' in src or "'ffmpeg'" in src
    assert "concat" in src
    assert "-c" in src and "copy" in src


def test_compose_dispatch_helper_exists():
    assert hasattr(compose_dispatch, "_maybe_enqueue_episode_compose")


def test_episode_video_worker_calls_dispatch_on_success():
    src = inspect.getsource(episode_video_worker.generate_episode_video_task)
    assert "_maybe_enqueue_episode_compose" in src, \
        "episode_video_worker no longer hooks into compose dispatch — Phase D regressed"


def test_retry_endpoint_route_exists():
    src = inspect.getsource(episode_video_routes)
    assert "/compose-video/retry" in src
    assert "ComposeRetryRequest" in src


def test_compose_status_route_exists():
    src = inspect.getsource(episode_video_routes)
    assert "/episode/compose-jobs/" in src
    assert "ComposeJobStatusResponse" in src
