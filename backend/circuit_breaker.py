"""熔断器（Circuit Breaker）：保护后端对 Seedream 大模型的调用。

三态流转：
    closed（正常） --连续失败 N 次--> open（快速失败）
    open  --冷却期结束--> half-open（放行单个试探请求）
    half-open --成功--> closed / --失败--> open

状态与计数存 Redis，跨多个 Celery worker 进程共享，重启后依然生效。
"""
import time

import redis as redis_sync

from config import CB_FAILURE_THRESHOLD, CB_RECOVERY_SECONDS, REDIS_URL
from logging_config import get_logger

logger = get_logger("circuit_breaker")

_redis = redis_sync.from_url(REDIS_URL, decode_responses=True)

_STATE_KEY = "cb:ark:state"
_FAIL_COUNT_KEY = "cb:ark:fail_count"
_OPEN_AT_KEY = "cb:ark:open_at"
_HALF_OPEN_LOCK_KEY = "cb:ark:half_open_lock"


class CircuitOpenError(Exception):
    """熔断已打开，调用方应返回友好提示而非重试。"""


class CircuitBreaker:
    def __init__(self, failure_threshold: int = None, recovery_seconds: int = None):
        self.failure_threshold = failure_threshold or CB_FAILURE_THRESHOLD
        self.recovery_seconds = recovery_seconds or CB_RECOVERY_SECONDS

    def _state(self) -> str:
        return _redis.get(_STATE_KEY) or "closed"

    def _open_at(self) -> float:
        return float(_redis.get(_OPEN_AT_KEY) or 0)

    def before_call(self):
        """调用前检查熔断状态，允许则放行，否则抛 CircuitOpenError。"""
        state = self._state()
        if state == "open":
            if time.time() - self._open_at() < self.recovery_seconds:
                raise CircuitOpenError("AI 服务繁忙，请稍后重试")
            # 冷却期结束，进入 half-open
            _redis.set(_STATE_KEY, "half-open")
            state = "half-open"
            logger.info("熔断器冷却结束，进入 half-open")

        if state == "half-open":
            # 只允许一个试探请求（SETNX 分布式锁），其余快速失败
            got = _redis.set(_HALF_OPEN_LOCK_KEY, "1", nx=True, ex=self.recovery_seconds)
            if not got:
                raise CircuitOpenError("AI 服务繁忙，请稍后重试")

    def on_success(self):
        _redis.delete(_FAIL_COUNT_KEY)
        _redis.delete(_HALF_OPEN_LOCK_KEY)
        _redis.set(_STATE_KEY, "closed")
        logger.info("Seedream 调用成功，熔断器恢复 closed")

    def on_failure(self):
        count = _redis.incr(_FAIL_COUNT_KEY)
        if _redis.ttl(_FAIL_COUNT_KEY) < 0:
            _redis.expire(_FAIL_COUNT_KEY, self.recovery_seconds * 2)
        _redis.delete(_HALF_OPEN_LOCK_KEY)  # 释放试探锁，允许下一次试探
        if count >= self.failure_threshold:
            _redis.set(_STATE_KEY, "open")
            _redis.set(_OPEN_AT_KEY, time.time())
            logger.warning("连续失败 %s 次，熔断器打开", count)
