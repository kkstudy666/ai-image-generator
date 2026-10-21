"""Celery 异步任务：调用 Seedream 生成图片 -> 转存本地 -> 更新状态并推送。

状态流转：queued（入库时）-> generating -> retrying -> success / failed。

Celery worker 是独立进程，无法直接向 FastAPI 的 WebSocket 写数据，
这里通过 Redis Pub/Sub 发布状态，由 FastAPI 的 WebSocket 订阅并转发给浏览器。
"""
import json

import httpx
import redis as redis_sync

import db
from ark_client import generate_image
from celery_app import celery_app
from circuit_breaker import CircuitOpenError
from config import IMAGE_DIR, REDIS_URL
from logging_config import get_logger

logger = get_logger("tasks")

# 同步 Redis 客户端，用于发布状态更新（worker 是同步进程，无需异步客户端）
_redis = redis_sync.from_url(REDIS_URL, decode_responses=True)

# worker 进程启动时确保数据表存在
db.init_db()

# 云端 content-type 到本地文件扩展名的映射
_EXT_MAP = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def _push_status(task_id, status, image_url=None, local_path=None, error=None):
    """写数据库 + 发布 Redis 消息，通知 FastAPI WebSocket。"""
    db.update_task(task_id, status, image_url=image_url, local_path=local_path, error=error)

    message = {"task_id": task_id, "status": status}
    if image_url:
        message["image_url"] = image_url
    if local_path:
        message["local_path"] = local_path
    if error:
        message["error"] = error
    _redis.publish(f"task:{task_id}", json.dumps(message, ensure_ascii=False))
    logger.info("[task:%s] 状态更新为 %s", task_id, status)


def _download_to_local(task_id, image_url):
    """把云端图片下载到本地 data/images/，返回本地绝对路径。

    解决火山方舟返回的图片 URL 约 24 小时过期的问题，同时支撑本地备份。
    """
    logger.info("[task:%s] 开始转存图片到本地：%s", task_id, image_url)
    resp = httpx.get(image_url, timeout=30, follow_redirects=True)
    resp.raise_for_status()

    content_type = resp.headers.get("content-type", "").split(";")[0].strip()
    ext = _EXT_MAP.get(content_type, "jpg")
    path = IMAGE_DIR / f"{task_id}.{ext}"
    path.write_bytes(resp.content)
    logger.info("[task:%s] 图片已转存：%s（%s 字节）", task_id, path, len(resp.content))
    return str(path)


@celery_app.task(bind=True, name="tasks.generate_image_task", max_retries=2)
def generate_image_task(self, task_id, prompt, negative_prompt, size, task_type, input_image=None):
    """生成图片主任务：generating -> success / failed，失败自动重试最多 2 次。"""
    _push_status(task_id, "generating")
    logger.info("[task:%s] 任务开始（type=%s, size=%s）", task_id, task_type, size)

    try:
        image_url = generate_image(
            prompt=prompt,
            negative_prompt=negative_prompt,
            size=size,
            input_image=input_image,
        )
        # 生成成功后转存本地，解决火山方舟 URL 约 24 小时过期的问题
        local_path = _download_to_local(task_id, image_url)
        _push_status(task_id, "success", image_url=image_url, local_path=local_path)
        logger.info("[task:%s] 任务成功", task_id)
        return image_url

    except CircuitOpenError as exc:
        # 熔断打开：不重试，直接标记失败，返回友好提示
        _push_status(task_id, "failed", error=str(exc))
        logger.warning("[task:%s] 熔断打开，任务失败：%s", task_id, exc)
        return {"status": "failed", "error": str(exc)}

    except Exception as exc:
        # 其他异常按指数退避自动重试（最多 2 次）
        if self.request.retries < self.max_retries:
            delay = 2 ** self.request.retries * 10  # 10s -> 20s
            logger.warning(
                "[task:%s] 失败，第 %s 次重试（%s 秒后）：%s",
                task_id, self.request.retries + 1, delay, exc,
            )
            _push_status(task_id, "retrying", error=str(exc))
            raise self.retry(exc=exc, countdown=delay)

        _push_status(task_id, "failed", error=str(exc))
        logger.error("[task:%s] 重试耗尽，任务失败：%s", task_id, exc)
        return {"status": "failed", "error": str(exc)}
