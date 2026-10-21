# 架构设计与关键技术选型说明

本文档说明系统架构、Celery+Redis 选型依据，以及任务可靠性、熔断、限流、幂等的设计原理。

## 一、整体架构

```
浏览器 Vue3
   │ ① 登录/注册（JWT）
   │ ② 提交任务（幂等）
   │ ③ WebSocket 订阅进度
   ▼
FastAPI（JWT 鉴权 + IP/用户双维度限流 + 文件校验）
   │ 写入 SQLite（queued）
   │ 投递任务队列
   ▼
Redis（broker 任务队列 + backend 结果 + Pub/Sub 消息总线 + 限流/熔断状态）
   │
   ▼
Celery Worker（acks_late + 自动重试 + 熔断保护）
   │ 调用火山方舟 Seedream（超时控制）
   │ 生成成功后下载图片到本地 data/images/
   │ 更新 SQLite + 发布 Redis Pub/Sub
   ▼
前端画廊（本地图片 + 懒加载 + 分页）
```

## 二、Celery + Redis vs RabbitMQ 选型依据

| 维度 | Redis（本项目选用） | RabbitMQ |
| --- | --- | --- |
| 部署运维 | 轻量，单机即可，项目已依赖 | 需额外部署 Erlang + 服务，运维重 |
| 可靠性 | 靠 `visibility_timeout` 重投递，极端情况可能重复/延迟 | ACK 机制成熟，投递可靠性更强 |
| 消息路由 | 简单队列，支持基础优先级 | 支持复杂路由、优先级、死信队列 |
| 吞吐 | 内存型，快 | 稍低，但稳定 |
| 适用规模 | 单机/小团队、任务量适中 | 大规模、需强可靠投递（如计费） |

**结论**：本项目是单机/小团队内部系统，生图任务为低频长耗时（约 20s/张），Redis 作为 broker + backend + Pub/Sub 三合一，完全满足需求且零额外部署成本。若未来任务量激增或需要「消息绝不丢失」的强可靠投递，仅需修改 `celery_app.py` 的 broker 配置即可无缝迁移 RabbitMQ（Celery 抽象了 broker）。

## 三、Celery Worker 并发与预取优化

- **`worker_prefetch_multiplier=1`**：每个 worker 一次只预取 1 个任务。生图任务耗时长（约 20s），若按默认值 4 预取，单个 worker 会同时堆积 4 个长任务，而其他 worker 空闲，导致负载不均。设为 1 让任务在多个 worker 间均匀分配。
- **`worker_concurrency=2`**：生图是 **IO 密集型**（等待大模型 API 返回），可设 2~4 个并发；若是 CPU 密集型则应等于 CPU 核数。Windows 下 `--pool=solo` 固定并发为 1（Celery 平台限制），Linux 下 `prefork` 池生效。
- **`task_time_limit` / `soft_time_limit`**：硬超时兜底，防止单个任务无限卡死占用 worker。

## 四、任务可靠性设计

| 机制 | 实现 | 作用 |
| --- | --- | --- |
| 幂等提交 | `request_id` 唯一键 + 先查后插 + 唯一约束冲突回读 | 网络重试/双击不重复生成 |
| worker 宕机恢复 | `task_acks_late=True` + `visibility_timeout` | worker 崩溃后未完成任务自动重入队 |
| 自动重试 | `max_retries=2` + 指数退避（10s→20s） | 瞬时错误自动恢复 |
| 熔断降级 | 三态熔断器（closed/open/half-open） | 大模型连续失败时快速失败，避免雪崩 |

## 五、熔断器（Circuit Breaker）

状态流转与存储（存 Redis，跨 worker 共享、重启生效）：

```
closed --连续失败 N 次--> open（快速失败，返回「服务繁忙」）
open   --冷却期结束--> half-open（放行单个试探请求）
half-open --成功--> closed / --失败--> open
```

熔断打开时，`ark_client.generate_image` 抛 `CircuitOpenError`，任务层捕获后**不重试**、直接标记失败并返回友好提示，避免在大模型不可用时继续堆积请求。

## 六、限流设计

- **固定窗口计数器**（Redis `INCR` + `EXPIRE`），以秒级窗口为粒度。
- **双维度**：登录/注册按 IP（防暴力破解）；业务接口按 IP + 用户 ID（防单用户刷接口）。
- 超阈值返回 HTTP 429，前端统一提示「请求过于频繁」。

## 七、多用户隔离与图片本地转存

- 每张任务记录关联 `user_id`，查询时强制 `WHERE user_id = ?`，WebSocket/图片接口同样校验归属。
- 图片生成后 worker 用 httpx 下载到 `backend/data/images/`，DB 记录 `local_path`，前端经 `/api/image/{task_id}` 读取。解决火山方舟 URL 约 24 小时过期的问题，同时支撑本地备份与一键下载。
