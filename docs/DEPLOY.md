# 部署与启动文档

## 一、环境要求

- Python 3.10+（开发环境 3.12）
- Node.js 18+（开发环境 24）
- Redis（Windows 便携版已内置在 `redis/`，Linux 用 `apt install redis-server`）

## 二、配置环境变量

复制模板并填写：

```bash
cp .env.example backend/.env
```

必填项（`backend/.env`）：

| 变量 | 说明 |
| --- | --- |
| `ARK_API_KEY` | 火山方舟 API Key（**必须轮换，勿硬编码、勿提交**） |
| `ARK_MODEL` | Seedream 模型 ID 或 `ep-xxx` 接入点 |
| `JWT_SECRET` | 随机长字符串（`python -c "import secrets;print(secrets.token_hex(32))"`） |

其余（Redis 地址、限流阈值、熔断阈值）有安全默认值，可选。

## 三、Windows 部署

```bash
# 1. 后端依赖
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 2. 一键启动（自动拉起 Redis + Celery + FastAPI + 前端）
cd ..
start.bat
```

手动分步启动（排查问题时）：

```bash
# 终端 1：Redis
redis\redis-server.exe

# 终端 2：Celery worker（Windows 必须 --pool=solo）
cd backend
venv\Scripts\python.exe -m celery -A celery_app worker --loglevel=info --pool=solo

# 终端 3：FastAPI
cd backend
venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000

# 终端 4：前端
cd frontend
npm install
npm run dev
```

浏览器打开 <http://localhost:5173>，**首次需注册账号再登录**。

## 四、Linux 部署

```bash
# 安装 Redis
sudo apt install redis-server

# 一键启动后端（Redis + Celery + FastAPI）
bash scripts/start.sh

# 前端（另开终端）
cd frontend
npm install
npm run dev
```

### 生产部署（systemd 托管，可选）

生产环境建议用 gunicorn/uvicorn 多 worker + supervisor/systemd 托管，示例：

```bash
# FastAPI（4 worker）
cd backend
venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# Celery worker（2 并发，Linux prefork 池）
venv/bin/celery -A celery_app worker --loglevel=info --concurrency=2
```

前端生产构建（产出静态文件，交给 Nginx）：

```bash
cd frontend
npm run build
# 将 dist/ 部署到 Nginx，并把 /api 与 /ws 反向代理到后端 8000 端口
```

## 五、数据备份

```bash
# 备份 SQLite + 本地图片目录（保留最近 30 份）
cd backend
venv\Scripts\python.exe backup.py        # Windows
venv/bin/python backup.py                # Linux
```

定时执行：

- Linux cron：`0 3 * * * cd /path/backend && venv/bin/python backup.py`
- Windows 计划任务：每天执行 `python backup.py`

## 六、压测与冒烟测试

```bash
# 安装开发依赖
pip install -r requirements-dev.txt

# 冒烟测试（需先启动 Redis + FastAPI）
python tests/smoke_test.py

# 压测（需先启动 Redis + FastAPI，压测时不要启动 worker）
locust -f tests/locustfile.py --host=http://localhost:8000
# 或命令行无头模式
locust -f tests/locustfile.py --host=http://localhost:8000 \
    --headless --users 100 --spawn-rate 20 --run-time 60s \
    --csv=report --html=report.html
```

## 七、常见问题

| 问题 | 解决 |
| --- | --- |
| `redis.exceptions.ConnectionError` | Redis 未启动，确认 6379 端口已监听 |
| Celery 启动卡住/报错 | Windows 必须加 `--pool=solo` |
| 图片一直排队 | 确认 Celery worker 已启动且日志无报错 |
| 登录后接口 401 | 令牌过期，重新登录；确认前后端时间基本一致 |
| 生成失败「AI 服务繁忙」 | 大模型连续失败触发熔断，冷却约 1 分钟后自动恢复 |
| 请求被 429 | 触发限流，稍等 1 分钟再试 |
