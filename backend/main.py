"""FastAPI 主应用：提交生成任务、查询历史记录、WebSocket 实时推送进度。

接口一览：
- POST /api/generate        提交生成任务（文生图 / 图生图）
- GET  /api/history         查询历史记录（分页）
- GET  /api/task/{task_id}  查询单个任务状态（WebSocket 断线时兜底）
- WS   /ws/{task_id}        WebSocket 实时推送任务进度
"""
import os
import uuid
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

import redis.asyncio as redis_asyncio
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import db
from celery_app import celery_app
from tasks import generate_image_task

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
ALLOWED_SIZES = {"1024x1024", "1280x720"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化数据库。"""
    db.init_db()
    yield


app = FastAPI(title="AI 图文生成系统", lifespan=lifespan)

# 开启 CORS 跨域，允许前端开发服务器（如 http://localhost:5173）直接访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    """提交生成任务的请求体。"""
    prompt: str = Field(..., min_length=1, description="主提示词")
    negative_prompt: str = Field("", description="负面提示词")
    size: str = Field("1024x1024", description="图片尺寸")
    input_image: str | None = Field(None, description="图生图参考图（base64 data URI，可选）")


@app.post("/api/generate")
def submit_generate(req: GenerateRequest):
    """提交生成任务：写入数据库 -> 投递 Celery -> 返回 task_id。"""
    if req.size not in ALLOWED_SIZES:
        raise HTTPException(status_code=400, detail=f"不支持的尺寸，可选：{ALLOWED_SIZES}")

    task_id = str(uuid.uuid4())
    task_type = "img2img" if req.input_image else "text2img"

    # 先入库（状态 queued），再投递任务，避免 worker 执行过快导致更新不到记录
    db.create_task(task_id, req.prompt, req.negative_prompt, req.size, task_type)
    generate_image_task.apply_async(
        args=[task_id, req.prompt, req.negative_prompt, req.size, task_type, req.input_image],
        task_id=task_id,
    )
    return {"code": 0, "task_id": task_id, "status": "queued"}


@app.get("/api/history")
def history(limit: int = 50, offset: int = 0):
    """查询历史生成记录（按时间倒序分页）。"""
    limit = max(1, min(limit, 200))
    return {"code": 0, "data": db.list_tasks(limit, offset)}


@app.get("/api/task/{task_id}")
def task_status(task_id: str):
    """查询单个任务当前状态，前端 WebSocket 断线时可用它兜底。"""
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"code": 0, "data": task}


@app.websocket("/ws/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str):
    """WebSocket 实时推送：订阅 Redis 频道，转发 Celery 发布的状态更新。"""
    await websocket.accept()

    r = redis_asyncio.from_url(REDIS_URL, decode_responses=True)
    pubsub = r.pubsub()
    await pubsub.subscribe(f"task:{task_id}")
    try:
        while True:
            # 每秒轮询一次 Redis 频道，收到消息就转发给浏览器
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if message and message.get("type") == "message":
                await websocket.send_text(message["data"])
    except WebSocketDisconnect:
        # 客户端断开连接，正常退出
        pass
    finally:
        await pubsub.unsubscribe(f"task:{task_id}")
        await pubsub.close()
        await r.aclose()
