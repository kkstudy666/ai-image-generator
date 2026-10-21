"""Celery 应用配置：broker（任务队列）与 backend（结果存储）都使用 Redis。

可靠性配置说明（详见 docs/ARCHITECTURE.md）：
- task_acks_late=True：任务执行完才 ACK，worker 异常宕机后任务自动重入队恢复；
- worker_prefetch_multiplier=1：每个 worker 只预取 1 个任务，避免长任务堆积到单个 worker；
- task_reject_on_worker_lost=True：worker 进程被杀时拒绝任务而非静默丢失；
- visibility_timeout：Redis broker 下未被 ACK 的任务多久后重新可见（重入队）。
"""
from celery import Celery

from config import REDIS_URL

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
    # ===== 任务可靠性 =====
    task_acks_late=True,                 # 执行完才 ACK
    worker_prefetch_multiplier=1,        # 每 worker 只预取 1 个任务
    task_reject_on_worker_lost=True,     # worker 崩溃任务不丢失
    broker_transport_options={"visibility_timeout": 3600},  # 未 ACK 任务 1 小时后重入队
    # ===== 超时与并发 =====
    task_time_limit=600,                 # 硬超时 10 分钟
    task_soft_time_limit=540,            # 软超时 9 分钟（可捕获处理）
    worker_concurrency=2,                # Linux prefork 池生效；Windows solo 池固定为 1
    result_expires=3600,                 # 结果保留 1 小时
    # ===== 日志 =====
    worker_hijack_root_logger=False,     # 不接管 root logger，保留 logging_config 的文件 handler
)
