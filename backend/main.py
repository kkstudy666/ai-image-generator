"""FastAPI 主应用：注册/登录、提交生成任务、查询历史、图片服务、WebSocket 推送。

所有业务接口均校验登录状态（JWT），并施加 IP + 用户双维度限流。
"""
import os
import sqlite3
import uuid
from contextlib import asynccontextmanager

import redis.asyncio as redis_asyncio
from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel, Field

import db
from auth import (
    create_access_token,
    get_current_user,
    get_current_user_flexible,
    get_user_from_token,
    hash_password,
    verify_password,
)
from celery_app import celery_app
from config import (
    ALLOWED_SIZES,
    RATE_LIMIT_API_IP,
    RATE_LIMIT_API_USER,
    RATE_LIMIT_AUTH,
    REDIS_URL,
)
from rate_limit import check_rate_limit, client_ip
from security import validate_and_decode_image
from tasks import generate_image_task


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用启动时初始化数据库。"""
    db.init_db()
    yield


app = FastAPI(title="AI 图文生成系统", lifespan=lifespan)

# 开发期跨域；鉴权用 Authorization 头（非 Cookie），生产可收紧 origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== 请求模型 =====

class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, description="用户名")
    password: str = Field(..., min_length=6, max_length=64, description="密码")


class LoginRequest(BaseModel):
    username: str
    password: str


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=2000, description="主提示词")
    negative_prompt: str = Field("", max_length=1000, description="负面提示词")
    size: str = Field("1024x1024", description="图片尺寸")
    input_image: str | None = Field(None, description="图生图参考图（base64 data URI，可选）")
    request_id: str | None = Field(None, description="客户端幂等键（UUID）")


# ===== 鉴权接口 =====

@app.post("/api/auth/register")
async def register(req: RegisterRequest, request: Request):
    """用户注册（IP 维度限流）。"""
    await check_rate_limit("auth", client_ip(request), RATE_LIMIT_AUTH)

    if db.get_user_by_username(req.username):
        raise HTTPException(status_code=409, detail="用户名已存在")
    try:
        db.create_user(req.username, hash_password(req.password))
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="用户名已存在")

    user = db.get_user_by_username(req.username)
    token = create_access_token(user["id"], user["username"])
    return {"code": 0, "token": token, "user": {"id": user["id"], "username": user["username"]}}


@app.post("/api/auth/login")
async def login(req: LoginRequest, request: Request):
    """用户登录（IP 维度限流）。"""
    await check_rate_limit("auth", client_ip(request), RATE_LIMIT_AUTH)

    user = db.get_user_by_username(req.username)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token(user["id"], user["username"])
    return {"code": 0, "token": token, "user": {"id": user["id"], "username": user["username"]}}


# ===== 限流依赖 =====

async def rate_limit_api(request: Request, user: dict = Depends(get_current_user)):
    """业务接口限流：IP + 用户双维度。"""
    await check_rate_limit("api_ip", client_ip(request), RATE_LIMIT_API_IP)
    await check_rate_limit("api_user", str(user["id"]), RATE_LIMIT_API_USER)


# ===== 业务接口 =====

@app.post("/api/generate")
def submit_generate(
    req: GenerateRequest,
    user: dict = Depends(get_current_user),
    _: None = Depends(rate_limit_api),
):
    """提交生成任务（幂等）：写入数据库 -> 投递 Celery -> 返回 task_id。

    幂等：以 request_id 为幂等键，重复提交（网络重试/双击）直接返回已有任务，
    不重复投递队列、不重复调用大模型。
    """
    if req.size not in ALLOWED_SIZES:
        raise HTTPException(status_code=400, detail=f"不支持的尺寸，可选：{ALLOWED_SIZES}")

    # 图生图参考图安全校验（格式 / 大小 / 文件头）
    if req.input_image:
        try:
            validate_and_decode_image(req.input_image)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    request_id = req.request_id or str(uuid.uuid4())
    task_id = str(uuid.uuid4())
    task_type = "img2img" if req.input_image else "text2img"

    existing = db.create_task_if_not_exists(
        user["id"], request_id, task_id, req.prompt, req.negative_prompt, req.size, task_type
    )
    if existing:
        # 幂等命中：直接返回已有任务，不重复投递
        return {
            "code": 0,
            "task_id": existing["task_id"],
            "status": existing["status"],
            "idempotent": True,
        }

    generate_image_task.apply_async(
        args=[task_id, req.prompt, req.negative_prompt, req.size, task_type, req.input_image],
        task_id=task_id,
    )
    return {"code": 0, "task_id": task_id, "status": "queued", "idempotent": False}


@app.get("/api/history")
def history(
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_current_user),
    _: None = Depends(rate_limit_api),
):
    """查询当前用户的历史记录（分页，多用户隔离）。"""
    limit = max(1, min(limit, 100))
    offset = max(0, offset)
    return {"code": 0, "data": db.list_tasks(user["id"], limit, offset)}


@app.get("/api/task/{task_id}")
def task_status(
    task_id: str,
    user: dict = Depends(get_current_user),
    _: None = Depends(rate_limit_api),
):
    """查询单个任务状态（多用户隔离），前端 WebSocket 断线时兜底。"""
    task = db.get_task(task_id)
    if not task or task["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {"code": 0, "data": task}


@app.get("/api/image/{task_id}")
def get_image(
    task_id: str,
    download: bool = False,
    user: dict = Depends(get_current_user_flexible),
):
    """返回本地转存图片（多用户隔离）；download=1 时作为附件下载。

    兜底：旧数据无本地文件时，重定向到云端 URL。
    """
    task = db.get_task(task_id)
    if not task or task["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="图片不存在")

    local_path = task.get("local_path")
    if local_path and os.path.isfile(local_path):
        return FileResponse(
            local_path,
            filename=os.path.basename(local_path),
            content_disposition_type="attachment" if download else "inline",
        )

    if task.get("image_url"):
        return RedirectResponse(task["image_url"])

    raise HTTPException(status_code=404, detail="图片尚未生成")


# ===== WebSocket =====

@app.websocket("/ws/{task_id}")
async def websocket_progress(websocket: WebSocket, task_id: str, token: str = Query("")):
    """WebSocket 实时推送：校验 token -> 订阅 Redis 频道 -> 转发状态。

    浏览器 WebSocket 无法自定义请求头，故 token 通过查询参数传递。
    """
    # 先校验身份与任务归属（在 accept 之前）
    user = get_user_from_token(token)
    if not user:
        await websocket.close(code=4401)
        return
    task = db.get_task(task_id)
    if not task or task["user_id"] != user["id"]:
        await websocket.close(code=4403)
        return

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
