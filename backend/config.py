"""全局配置：集中从环境变量加载密钥与参数，禁止在代码中硬编码敏感信息。

所有可选值都提供安全默认值，生产环境请在 backend/.env 中覆盖。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

# 先确定目录，再加载 .env（确保无论启动目录在哪都能找到 backend/.env）
BACKEND_DIR = Path(__file__).resolve().parent
load_dotenv(BACKEND_DIR / ".env")

# ===== 目录 =====
DATA_DIR = BACKEND_DIR / "data"
IMAGE_DIR = DATA_DIR / "images"          # 本地图片转存目录
LOG_DIR = BACKEND_DIR / "logs"           # 日志目录
IMAGE_DIR.mkdir(parents=True, exist_ok=True)  # 启动即确保图片目录存在
LOG_DIR.mkdir(parents=True, exist_ok=True)

# ===== 火山方舟 Seedream =====
ARK_API_KEY = os.getenv("ARK_API_KEY", "")
ARK_BASE_URL = os.getenv("ARK_BASE_URL", "https://ark.cn-beijing.volces.com/api/v3")
ARK_MODEL = os.getenv("ARK_MODEL", "doubao-seedream-5-0-pro-260628")
SEEDREAM_TIMEOUT_SECONDS = float(os.getenv("SEEDREAM_TIMEOUT_SECONDS", "60"))  # 单次生图超时

# ===== Redis =====
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# ===== JWT 鉴权 =====
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "10080"))  # 默认 7 天

# ===== 生成参数 =====
ALLOWED_SIZES = {"1024x1024", "1280x720"}

# ===== 上传文件安全 =====
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 参考图最大 10MB

# ===== 限流（每分钟次数） =====
RATE_LIMIT_AUTH = int(os.getenv("RATE_LIMIT_AUTH", "10"))         # 登录/注册：IP 维度
RATE_LIMIT_API_IP = int(os.getenv("RATE_LIMIT_API_IP", "120"))    # 业务接口：IP 维度
RATE_LIMIT_API_USER = int(os.getenv("RATE_LIMIT_API_USER", "60"))  # 业务接口：用户维度

# ===== 熔断 =====
CB_FAILURE_THRESHOLD = int(os.getenv("CB_FAILURE_THRESHOLD", "5"))  # 连续失败 N 次打开
CB_RECOVERY_SECONDS = int(os.getenv("CB_RECOVERY_SECONDS", "60"))   # 冷却期（秒）


def mask_secret(secret: str, keep: int = 4) -> str:
    """脱敏展示密钥，仅保留末尾 keep 位，用于日志与调试输出。"""
    if not secret:
        return ""
    if len(secret) <= keep:
        return "*" * len(secret)
    return "*" * (len(secret) - keep) + secret[-keep:]
