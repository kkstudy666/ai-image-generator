"""Celery 异步任务：调用 Seedream 生成图片，更新状态并通过 Redis 推送给前端。

状态流转：queued（入库时）-> generating（任务开始）-> success / failed。
Celery worker 是独立进程，无法直接向 FastAPI 的 WebSocket 写数据，
这里通过 Redis Pub/Sub 发布状态，由 FastAPI 的 WebSocket 订阅并转发给浏览器。
"""
import os
import json

from dotenv import load_dotenv
load_dotenv()

import redis as redis_sync

from celery_app import celery_app
import db
from ark_client import generate_image

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# 同步 Redis 客户端，用于发布状态更新（worker 是同步进程，无需异步客户端）
_redis = redis_sync.from_url(REDIS_URL, decode_responses=True)

# worker 进程启动时确保数据表存在
db.init_db()


def _push_status(task_id, status, image_url=None, error=None):
    """写数据库 + 发布 Redis 消息，通知 FastAPI WebSocket。"""
    db.update_task(task_id, status, image_url=image_url, error=error)

    message = {"task_id": task_id, "status": status}
    if image_url:
        message["image_url"] = image_url
    if error:
        message["error"] = error
    _redis.publish(f"task:{task_id}", json.dumps(message, ensure_ascii=False))


@celery_app.task(bind=True, name="tasks.generate_image_task")
def generate_image_task(self, task_id, prompt, negative_prompt, size, task_type, input_image=None):
    """生成图片主任务：generating -> success / failed。"""
    _push_status(task_id, "generating")
    try:
        image_url = generate_image(
            prompt=prompt,
            negative_prompt=negative_prompt,
            size=size,
            input_image=input_image,
        )
        _push_status(task_id, "success", image_url=image_url)
        return image_url
    except Exception as exc:
        # 失败时记录错误信息并推送，然后重新抛出以便 Celery 标记任务失败
        _push_status(task_id, "failed", error=str(exc))
        raise
