"""基于 Redis 的固定窗口限流（IP 维度 + 用户维度）。

原理：以「秒级时间窗口」为粒度，对每个 key 用 INCR 计数，首次访问设置过期，
超过阈值即拒绝。相比令牌桶/滑动窗口更简单，足够内部系统使用。
"""
import time

import redis.asyncio as redis_asyncio
from fastapi import HTTPException, Request

from config import REDIS_URL

_pool = None


def get_redis():
    """懒加载异步 Redis 连接（复用连接池）。"""
    global _pool
    if _pool is None:
        _pool = redis_asyncio.from_url(REDIS_URL, decode_responses=True)
    return _pool


def client_ip(request: Request) -> str:
    """提取客户端 IP，兼容反向代理的 X-Forwarded-For。"""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def check_rate_limit(scope: str, key: str, limit: int, window_seconds: int = 60) -> None:
    """固定窗口限流，超阈值抛 HTTPException(429)。"""
    r = get_redis()
    redis_key = f"rl:{scope}:{key}:{int(time.time() // window_seconds)}"
    count = await r.incr(redis_key)
    if count == 1:
        await r.expire(redis_key, window_seconds)
    if count > limit:
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")
