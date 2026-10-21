"""后端接口冒烟测试：验证鉴权、文件校验、幂等、多用户隔离、限流等核心链路。

运行前需先启动 Redis 和 FastAPI（无需启动 Celery worker）。
用法：python tests/smoke_test.py
"""
import uuid

import httpx

BASE = "http://127.0.0.1:8000"
client = httpx.Client(base_url=BASE, timeout=10)

passed = 0
failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  [PASS] {name}")
    else:
        failed += 1
        print(f"  [FAIL] {name}  {detail}")


# 1. 注册 / 重复注册
r = client.post("/api/auth/register", json={"username": "smoke_user", "password": "smoke123"})
check("注册新用户返回 200", r.status_code == 200, r.text)

r = client.post("/api/auth/register", json={"username": "smoke_user", "password": "smoke123"})
check("重复注册返回 409", r.status_code == 409, r.text)

# 2. 登录 / 密码错误
r = client.post("/api/auth/login", json={"username": "smoke_user", "password": "smoke123"})
check("登录成功返回 token", r.status_code == 200 and r.json().get("token"), r.text)
token = r.json().get("token", "")
headers = {"Authorization": f"Bearer {token}"}

r = client.post("/api/auth/login", json={"username": "smoke_user", "password": "wrong"})
check("密码错误返回 401", r.status_code == 401, r.text)

# 3. 无 token 访问业务接口
r = client.get("/api/history")
check("无 token 访问历史返回 401", r.status_code == 401, r.text)

# 4. 非法尺寸
r = client.post("/api/generate", json={"prompt": "测试", "size": "999x999"}, headers=headers)
check("非法尺寸返回 400", r.status_code == 400, r.text)

# 5. 伪造文件格式（gif 伪装）被文件头校验拦截
r = client.post(
    "/api/generate",
    json={"prompt": "测试", "input_image": "data:image/gif;base64,R0lGODlhAQABAAAAACw="},
    headers=headers,
)
check("伪造 gif 文件头被拦截 400", r.status_code == 400, r.text)

# 6. 提交任务 + 幂等
rid = str(uuid.uuid4())
r = client.post("/api/generate", json={"prompt": "一只猫", "request_id": rid}, headers=headers)
check("提交任务成功", r.status_code == 200 and r.json().get("task_id"), r.text)
task_id = r.json().get("task_id", "")
check("首次提交非幂等命中", r.json().get("idempotent") is False, r.text)

r2 = client.post("/api/generate", json={"prompt": "一只猫", "request_id": rid}, headers=headers)
check(
    "相同 request_id 幂等命中且 task_id 一致",
    r2.json().get("idempotent") is True and r2.json().get("task_id") == task_id,
    r2.text,
)

# 7. 查询历史 / 任务状态
r = client.get("/api/history", params={"limit": 10}, headers=headers)
check("查询历史成功", r.status_code == 200 and r.json().get("code") == 0, r.text)

r = client.get(f"/api/task/{task_id}", headers=headers)
check("查询任务状态为 queued", r.status_code == 200 and r.json()["data"]["status"] == "queued", r.text)

# 8. 多用户隔离
r = client.post("/api/auth/register", json={"username": "smoke_user2", "password": "smoke123"})
token2 = r.json().get("token", "")
r = client.get(f"/api/task/{task_id}", headers={"Authorization": f"Bearer {token2}"})
check("跨用户查询任务返回 404", r.status_code == 404, r.text)

r = client.get("/api/history", headers={"Authorization": f"Bearer {token2}"})
check("其他用户历史为空", r.status_code == 200 and r.json()["data"] == [], r.text)

# 9. 登录接口限流（连续调用，应触发 429）
got_429 = False
for _ in range(20):
    r = client.post("/api/auth/login", json={"username": "smoke_user", "password": "wrong"})
    if r.status_code == 429:
        got_429 = True
        break
check("登录接口限流触发 429", got_429)

print(f"\n结果：{passed} 通过，{failed} 失败")
raise SystemExit(1 if failed else 0)
