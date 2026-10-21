# AI 图文生成系统（生产级）

基于 **Vue3 + FastAPI + Celery + Redis + SQLite** 的 AI 图文生成全栈系统，对接**火山方舟 Seedream** 文生图 / 图生图接口，**无需本地 GPU**。具备完整的用户鉴权、限流、熔断、任务可靠性保障与工程化能力，可作为内部正式使用的生产系统。

## 功能特性

- **文生图 / 图生图**：提示词生图；拖拽上传参考图（格式/大小/文件头三重校验）
- **异步任务队列**：Redis + Celery，提交接口毫秒级返回，不阻塞
- **实时进度推送**：WebSocket 推送「排队中 → 生成中 → 重试中 → 成功/失败」，断线自动重连 + 轮询兜底
- **用户体系**：注册/登录，JWT 鉴权，多用户数据隔离
- **安全防护**：IP + 用户双维度限流、上传文件头校验、密钥环境变量注入 + 脱敏
- **任务可靠性**：幂等提交、worker 宕机自动恢复、失败自动重试（≤2 次）、熔断降级
- **图片本地转存**：解决火山方舟 URL 24h 过期，支持一键下载与本地备份
- **作品画廊**：图片懒加载、滚动分页、大图预览、参数回看、一键下载
- **工程化**：分级日志、数据备份脚本、Locust 压测、Linux/Windows 一键启动、依赖版本锁定

## 技术栈

| 层 | 技术 |
| --- | --- |
| 前端 | Vue 3 + Vite + axios + WebSocket |
| 后端 | FastAPI + Uvicorn + JWT(PyJWT) |
| 异步任务 | Celery + Redis（broker/backend/Pub/Sub） |
| 存储 | SQLite |
| 生图模型 | 火山方舟 Seedream（OpenAI 兼容接口） |

## 目录结构

```
ai-image-generator/
├── backend/
│   ├── .env                  # 环境变量（密钥，不入库）
│   ├── main.py               # FastAPI：鉴权/限流/接口/图片服务/WebSocket
│   ├── celery_app.py         # Celery 配置（可靠性/并发/超时）
│   ├── tasks.py              # 异步任务：生图 + 转存 + 重试 + 熔断
│   ├── ark_client.py         # Seedream 封装（超时 + 熔断 + 脱敏）
│   ├── auth.py               # JWT 签发/校验 + PBKDF2 密码哈希
│   ├── rate_limit.py         # Redis 固定窗口限流（IP + 用户）
│   ├── circuit_breaker.py    # 三态熔断器
│   ├── security.py           # 上传文件格式/大小/文件头校验
│   ├── config.py             # 集中配置（环境变量）
│   ├── logging_config.py     # 分级日志 + 滚动文件
│   ├── db.py                 # SQLite：用户表 + 任务表 + 迁移 + 幂等
│   ├── backup.py             # 数据备份脚本
│   ├── requirements.txt      # 精确版本锁定
│   └── data/images/          # 本地图片转存目录（运行时生成）
├── frontend/
│   ├── .env.development      # 开发环境后端地址
│   ├── .env.production       # 生产环境后端地址
│   ├── vite.config.js        # 构建分包优化
│   └── src/
│       ├── App.vue           # 主组件（登录态/状态管理/预览下载）
│       ├── api/              # request.js + auth.js + generate.js
│       ├── store/auth.js     # 登录态 composable
│       ├── ws.js             # WebSocket 封装（自动重连 + 兜底）
│       └── components/       # LoginView / GeneratorForm / ProgressBar / Gallery
├── tests/
│   ├── locustfile.py         # Locust 并发压测脚本
│   ├── smoke_test.py         # 后端接口冒烟测试（鉴权/幂等/限流/隔离）
│   └── e2e_test.py           # 端到端测试（真实生图全链路）
├── scripts/start.sh          # Linux 一键启动
├── docs/                     # DEPLOY.md / ARCHITECTURE.md / LOAD_TEST_REPORT.md
├── start.bat                 # Windows 一键启动
└── README.md
```

## 快速开始

### Windows

```bash
# 1. 配置密钥
copy .env.example backend\.env   # 填入 ARK_API_KEY、JWT_SECRET

# 2. 安装后端依赖
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt

# 3. 安装前端依赖
cd ..\frontend
npm install

# 4. 一键启动（Redis + Celery + FastAPI + 前端）
cd ..
start.bat
```

浏览器打开 <http://localhost:5173>，**先注册账号再登录**。

### Linux

```bash
sudo apt install redis-server
bash scripts/start.sh        # 启动后端
cd frontend && npm install && npm run dev   # 另开终端启动前端
```

## 接口说明

| 方法 | 路径 | 鉴权 | 说明 |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | 否 | 注册 |
| POST | `/api/auth/login` | 否 | 登录，返回 JWT |
| POST | `/api/generate` | 是 | 提交生成任务（幂等） |
| GET | `/api/history?limit=&offset=` | 是 | 分页查询本人历史 |
| GET | `/api/task/{task_id}` | 是 | 查询任务状态（断线兜底） |
| GET | `/api/image/{task_id}` | 是 | 本地图片（`?download=1` 下载） |
| WS | `/ws/{task_id}?token=` | 是 | 实时进度推送 |

**提交任务请求体示例：**

```json
{
  "prompt": "一只坐在窗边的橘猫，柔和的午后阳光",
  "negative_prompt": "模糊、低质量、水印",
  "size": "1024x1024",
  "input_image": "data:image/jpeg;base64,/9j/...",
  "request_id": "客户端生成的 UUID（幂等键）"
}
```

## 文档索引

- 部署与启动：[docs/DEPLOY.md](docs/DEPLOY.md)
- 架构与选型：[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- 压测报告：[docs/LOAD_TEST_REPORT.md](docs/LOAD_TEST_REPORT.md)
