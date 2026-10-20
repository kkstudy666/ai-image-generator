# AI 图文生成网站（API 版）

一个基于 **Vue3 + FastAPI + Redis + Celery + WebSocket** 的 AI 图文生成系统，对接**火山方舟 Seedream** 文生图 / 图生图接口，**无需本地 GPU**。

## 功能特性

- 文生图、图生图（上传图片转 base64 传入）
- Redis + Celery 异步任务队列，解决生图接口超时问题
- WebSocket 实时推送任务状态：排队中 / 生成中 / 成功 / 失败
- SQLite 存储：提示词、负面提示词、图片链接、task_id、状态、创建时间
- 作品画廊，支持图片预览、右键保存下载

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3 + Vite + axios |
| 后端 | FastAPI + Uvicorn |
| 异步任务 | Celery + Redis |
| 实时推送 | WebSocket + Redis Pub/Sub |
| 存储 | SQLite |
| 生图模型 | 火山方舟 Seedream 4.0（OpenAI 兼容接口） |

## 目录结构

```
clude_code_data/
├── backend/
│   ├── .env            # 环境变量（火山方舟密钥、Redis 地址）
│   ├── main.py         # FastAPI 主应用：接口 + WebSocket
│   ├── celery_app.py   # Celery 配置
│   ├── tasks.py        # Celery 异步任务（生图 + 状态推送）
│   ├── ark_client.py   # 火山方舟 Seedream 接口封装
│   ├── db.py           # SQLite 数据库操作
│   └── requirements.txt
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.js
│       ├── style.css
│       ├── api.js              # axios 封装
│       ├── App.vue             # 主组件
│       └── components/
│           ├── GeneratorForm.vue   # 生成表单
│           └── Gallery.vue         # 作品画廊
└── README.md
```

## 环境要求

- Python 3.10+
- Node.js 18+
- Redis（见下方 Windows 安装说明）

---

## 启动步骤

### 第 1 步：安装并启动 Redis（Windows）

官方 Redis 不支持 Windows 原生，任选其一：

**方案 A：Docker Desktop（推荐）**

```bash
docker run -d --name redis -p 6379:6379 redis
```

**方案 B：Memurai（Windows 原生 Redis 兼容版，免费 Developer 版）**

1. 到 <https://www.memurai.com/get-memurai> 下载安装
2. 安装后服务自动启动，默认端口 6379

**方案 C：tporadowski/redis（免安装便携版）**

1. 到 <https://github.com/tporadowski/redis/releases> 下载 `Redis-x64-5.0.14.1.zip`
2. 解压后双击 `redis-server.exe` 启动（默认端口 6379）

### 第 2 步：配置火山方舟密钥

1. 注册火山引擎账号，开通「火山方舟」大模型服务：<https://console.volcengine.com/ark>
2. 在控制台创建 **API Key**
3. 开通 Seedream 模型，推荐创建**推理接入点**（会得到一个 `ep-xxx` 的接入点 ID）
4. 打开 `backend/.env`，填入：

```env
ARK_API_KEY=你的API_Key
ARK_MODEL=doubao-seedream-4-0-250828   # 或填 ep-xxx 接入点 ID
```

> 使用 `ep-xxx` 接入点 ID 时，`ARK_MODEL` 直接填该 ID 即可，更稳定且便于控制成本。

### 第 3 步：启动后端（FastAPI）

```bash
cd backend

# 创建并激活虚拟环境
python -m venv venv
venv\Scripts\activate        # Windows；Mac/Linux 用 source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动 FastAPI
uvicorn main:app --reload --port 8000
```

### 第 4 步：启动 Celery worker（新开一个终端）

```bash
cd backend
venv\Scripts\activate

# Windows 必须加 --pool=solo（Celery 在 Windows 上不支持默认 prefork 池）
celery -A celery_app worker --loglevel=info --pool=solo
```

看到 `[tasks] ... tasks.generate_image_task` 和 `celery@... ready.` 即启动成功。

### 第 5 步：启动前端（再开一个终端）

```bash
cd frontend
npm install
npm run dev
```

浏览器打开 <http://localhost:5173>，输入提示词点击「生成图片」即可。

---

## 接口说明

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/generate` | 提交生成任务，返回 `task_id` |
| GET | `/api/history?limit=&offset=` | 分页查询历史记录 |
| GET | `/api/task/{task_id}` | 查询单个任务状态 |
| WS | `/ws/{task_id}` | WebSocket 实时推送任务进度 |

**提交任务请求体示例：**

```json
{
  "prompt": "一只坐在窗边的橘猫，柔和的午后阳光",
  "negative_prompt": "模糊、低质量、水印",
  "size": "1024x1024",
  "input_image": "data:image/jpeg;base64,/9j/..."   // 图生图时填，文生图省略
}
```

## 架构说明

1. 前端提交任务 → FastAPI 写入 SQLite（状态 `queued`）并投递到 Celery
2. Celery worker 异步调用火山方舟 Seedream（不阻塞接口）
3. worker 更新状态时写 SQLite，并通过 **Redis Pub/Sub** 发布到 `task:{task_id}` 频道
4. FastAPI 的 WebSocket 订阅该频道，把状态实时转发给浏览器
5. 前端根据状态实时提示，成功后刷新画廊

## 常见问题

**Q1：`celery -A celery_app worker` 报错 / 卡住？**
Windows 上必须加 `--pool=solo`。若提示缺少 eventlet，不要装，直接用 solo。

**Q2：提示 `redis.exceptions.ConnectionError`？**
Redis 未启动，回到第 1 步确认 6379 端口已监听。

**Q3：生图报错提示检查 ARK_API_KEY？**
确认 `.env` 中密钥已填且没有引号/多余空格；确认已开通 Seedream 模型并创建接入点。

**Q4：图片链接过一段时间打不开？**
火山方舟返回的图片 URL 有有效期（约 24 小时）。如需长期保存，右键另存到本地即可。

**Q5：负面提示词为什么不生效 / 效果一般？**
Seedream 官方接口没有独立的负面提示词参数，本项目是拼接到主提示词实现近似效果。可自行调整 `backend/ark_client.py` 中的拼接措辞。

## 依赖安装命令汇总

```bash
# 后端
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 前端
cd frontend
npm install
```
