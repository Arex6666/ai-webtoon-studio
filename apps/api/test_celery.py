from app.workers.episode_video_worker import generate_episode_video_task
import traceback

try:
    print("Attempting to call delay...")
    res = generate_episode_video_task.delay("test-job", "http://test.com/img.jpg", "test prompt", 5.0, "doubao")
    print("Success! Task ID:", res.id)
except Exception as e:
    print("FAILED!")
    traceback.print_exc()
