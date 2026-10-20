"""Celery 应用配置：broker（任务队列）与 backend（结果存储）都使用 Redis。"""
import os

from dotenv import load_dotenv
load_dotenv()

from celery import Celery

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "aigc_tasks",
    broker=REDIS_URL,   # 任务队列
    backend=REDIS_URL,  # 任务结果存储
    include=["tasks"],  # 显式注册任务模块，确保 worker 能发现 tasks.py 中的任务
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
)
