"""端到端测试：真实调用大模型，验证「提交 → worker 生图 → 本地转存 → 状态推送 → 图片下载」全链路。

⚠️ 会真实调用火山方舟 Seedream，消耗 API 额度（约 1 张图）。

运行前需启动 Redis + Celery worker + FastAPI。
用法：python tests/e2e_test.py
"""
import os
import time
import uuid

import httpx

BASE = "http://127.0.0.1:8000"
client = httpx.Client(base_url=BASE, timeout=30)

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


# 1. 注册 + 登录
username = f"e2e_{uuid.uuid4().hex[:6]}"
password = "e2etest123"
r = client.post("/api/auth/register", json={"username": username, "password": password})
print(f"注册状态码: {r.status_code}")
r = client.post("/api/auth/login", json={"username": username, "password": password})
check("登录成功", r.status_code == 200 and r.json().get("token"), r.text)
token = r.json().get("token", "")
headers = {"Authorization": f"Bearer {token}"}

# 2. 提交文生图任务（真实生图）
prompt = "一只坐在窗边的橘猫，柔和的午后阳光，摄影风格"
r = client.post(
    "/api/generate",
    json={
        "prompt": prompt,
        "negative_prompt": "模糊、低质量、水印",
        "size": "1024x1024",
        "request_id": str(uuid.uuid4()),
    },
    headers=headers,
)
check("提交任务成功", r.status_code == 200 and r.json().get("task_id"), r.text)
task_id = r.json().get("task_id", "")
print(f"  任务 ID: {task_id}")

# 3. 轮询任务状态（真实生图约 20-60 秒）
print("  等待真实生图完成（约 20-60 秒）...")
final = None
for i in range(60):  # 最多约 120 秒
    time.sleep(2)
    r = client.get(f"/api/task/{task_id}", headers=headers)
    data = r.json()["data"]
    status = data["status"]
    print(f"  [{i * 2:>3}s] 状态: {status}" + (f"  ({data.get('error', '')})" if data.get("error") else ""))
    if status in ("success", "failed"):
        final = data
        break

check("任务最终成功", final is not None and final["status"] == "success", str(final))

# 4. 验证本地转存
if final and final["status"] == "success":
    local_path = final.get("local_path", "")
    check("本地图片路径已记录", bool(local_path), local_path)
    check("本地图片文件存在", os.path.isfile(local_path or ""), local_path)

    # 5. 验证图片接口 + 下载
    r = client.get(f"/api/image/{task_id}", headers=headers)
    check("图片接口返回 200", r.status_code == 200, r.status_code)
    check("图片内容非空", r.status_code == 200 and len(r.content) > 1000, len(r.content))
    if r.status_code == 200:
        print(f"  图片大小: {len(r.content)} 字节")

    r2 = client.get(f"/api/image/{task_id}?download=1", headers=headers)
    check("下载接口返回 200", r2.status_code == 200, r2.status_code)

# 6. 验证历史记录包含该任务
r = client.get("/api/history", params={"limit": 10}, headers=headers)
items = r.json()["data"]
check("历史记录包含新任务", any(x["task_id"] == task_id for x in items), f"共 {len(items)} 条")

print(f"\n端到端测试结果：{passed} 通过，{failed} 失败")
raise SystemExit(1 if failed else 0)
