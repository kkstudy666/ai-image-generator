"""Locust 并发压测脚本：针对 FastAPI 接口层做并发压测。

⚠️ 重要说明：
- 生图任务本身耗时约 20 秒且消耗大模型 API 额度，因此压测只针对 HTTP 接口层
  （注册/登录/提交/历史/任务查询），不真实调用 Seedream。
- 压测时请【不要启动 Celery worker】，否则提交的任务会被真实消费、调用大模型。
- 压测前建议使用独立数据库，避免污染业务数据。

运行方式：
    pip install -r requirements-dev.txt
    locust -f tests/locustfile.py --host=http://localhost:8000
    然后浏览器打开 http://localhost:8089 配置并发数与爬升速率开始压测。

无头（命令行）方式示例：
    locust -f tests/locustfile.py --host=http://localhost:8000 \
        --headless --users 100 --spawn-rate 20 --run-time 60s \
        --csv=report --html=report.html
"""
import uuid

from locust import HttpUser, between, task

# 提示词池，模拟真实提交内容
PROMPTS = [
    "一只坐在窗边的橘猫，柔和的午后阳光",
    "未来城市的夜景，霓虹灯，赛博朋克风格",
    "山水画风格的古桥与垂柳，水墨丹青",
    "一杯拉花咖啡，木质桌面，浅景深",
]


class AIGCUser(HttpUser):
    """模拟一个已登录用户，按权重执行各接口。"""

    wait_time = between(1, 3)

    def on_start(self):
        """每个虚拟用户启动时：注册（不存在则忽略）并登录，保存 token。"""
        self.username = f"load_{uuid.uuid4().hex[:8]}"
        self.password = "loadtest123"

        # 注册（用户名已存在时后端返回 409，忽略即可）
        self.client.post(
            "/api/auth/register",
            json={"username": self.username, "password": self.password},
        )
        # 登录获取 token
        resp = self.client.post(
            "/api/auth/login",
            json={"username": self.username, "password": self.password},
        )
        self.token = resp.json().get("token", "")
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @task(5)
    def submit_generate(self):
        """提交生成任务（幂等，返回 task_id）。压测时请勿启动 worker。"""
        self.client.post(
            "/api/generate",
            json={
                "prompt": PROMPTS[uuid.uuid4().int % len(PROMPTS)],
                "negative_prompt": "",
                "size": "1024x1024",
                "request_id": str(uuid.uuid4()),
            },
            headers=self.headers,
        )

    @task(3)
    def fetch_history(self):
        """查询历史记录（分页）。"""
        self.client.get(
            "/api/history", params={"limit": 20, "offset": 0}, headers=self.headers
        )

    @task(1)
    def login_again(self):
        """重新登录（测鉴权接口吞吐）。"""
        self.client.post(
            "/api/auth/login",
            json={"username": self.username, "password": self.password},
        )
