@echo off
chcp 936 >nul
cd /d %~dp0

echo ============================================
echo   AI 图文生成项目 一键启动（Windows）
echo ============================================
echo.
echo 首次使用：浏览器打开 http://localhost:5173 后先注册账号再登录。
echo 提示：请确认 backend\.env 中已配置 ARK_API_KEY 与 JWT_SECRET。
echo.

echo [1/4] 启动 Redis ...
start "Redis" cmd /k "cd /d %~dp0redis && redis-server.exe"

echo [2/4] 启动 Celery worker ...
start "Celery" cmd /k "cd /d %~dp0backend && venv\Scripts\python.exe -m celery -A celery_app worker --loglevel=info --pool=solo"

echo [3/4] 启动 FastAPI ...
start "FastAPI" cmd /k "cd /d %~dp0backend && venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000"

echo [4/4] 启动前端 ...
start "Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ============================================
echo   全部启动完成！
echo   浏览器打开 http://localhost:5173
echo   关闭项目：直接关掉这 4 个窗口即可
echo ============================================
echo.
pause
