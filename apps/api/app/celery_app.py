"""
Celery 应用配置
"""
from celery import Celery
from kombu import Queue
import os

# Redis URL
REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")

# 创建 Celery 应用
celery_app = Celery(
    "webtoon_studio",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=[
        "app.workers.image_worker",
        "app.workers.anchor_worker",
        "app.workers.video_worker",
        "app.workers.episode_video_worker",
        "app.workers.export_worker",
        "app.workers.advanced_worker",
        "app.workers.async_runner",
        "app.workers.bundle_worker",
    ]
)

# Celery 配置
celery_app.conf.update(
    # 任务序列化
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    
    # 时区
    timezone="Asia/Shanghai",
    enable_utc=True,
    
    # 任务跟踪
    task_track_started=True,
    task_time_limit=600,  # 10分钟超时
    
    # 队列定义
    task_queues=(
        Queue("default", routing_key="default"),
        Queue("image", routing_key="image"),
        Queue("anchor", routing_key="anchor"),
        Queue("video", routing_key="video"),
        Queue("export", routing_key="export"),
    ),
    
    # 默认队列
    task_default_queue="default",
    task_default_routing_key="default",
    
    # 路由规则
    task_routes={
        "app.workers.image_worker.*": {"queue": "image"},
        "app.workers.anchor_worker.*": {"queue": "anchor"},
        "app.workers.video_worker.*": {"queue": "video"},
        "app.workers.episode_video_worker.*": {"queue": "video"},
        "app.workers.export_worker.*": {"queue": "export"},
    },
    
    # 并发控制
    worker_prefetch_multiplier=1,  # 每次只获取一个任务
    worker_concurrency=2,  # 并发数
)
