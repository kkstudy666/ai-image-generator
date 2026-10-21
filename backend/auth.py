"""用户鉴权：密码哈希（PBKDF2）与 JWT 签发/校验，提供 get_current_user 依赖。

说明：密码哈希使用标准库 hashlib.pbkdf2_hmac（零额外依赖，兼容稳定），
JWT 使用 PyJWT。
"""
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

import db
from config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET

# 供业务接口注入 Authorization: Bearer <token>
_bearer = HTTPBearer(auto_error=False)

_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    """PBKDF2-HMAC-SHA256 加盐哈希，存储格式：pbkdf2_sha256$iterations$salt$hex。"""
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), _PBKDF2_ITERATIONS)
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """校验明文密码与存储哈希，恒定时间比较防时序攻击。"""
    try:
        algo, iterations, salt, expected = stored.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(iterations))
        return secrets.compare_digest(dk.hex(), expected)
    except Exception:
        return False


def create_access_token(user_id: int, username: str) -> str:
    """签发 JWT，sub 存用户 ID。"""
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "username": username,
        "iat": now,
        "exp": now + timedelta(minutes=JWT_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """校验并解析 JWT，失败返回 None。"""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def get_user_from_token(token: str) -> dict | None:
    """由 token 解析用户（供 WebSocket 使用）。"""
    payload = decode_token(token)
    if not payload:
        return None
    return db.get_user_by_id(int(payload.get("sub", 0)))


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> dict:
    """FastAPI 依赖：校验 Authorization 头，返回用户记录。"""
    if not credentials:
        raise HTTPException(status_code=401, detail="未登录或令牌缺失")
    user = get_user_from_token(credentials.credentials)
    if not user:
        raise HTTPException(status_code=401, detail="令牌无效或已过期")
    return user


def get_current_user_flexible(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    token: str = Query(""),
) -> dict:
    """FastAPI 依赖：支持 Authorization 头或 ?token= 查询参数两种鉴权方式。

    图片 <img> 标签无法携带自定义请求头，故图片服务接口额外支持 token 查询参数。
    """
    if credentials:
        user = get_user_from_token(credentials.credentials)
        if user:
            return user
    if token:
        user = get_user_from_token(token)
        if user:
            return user
    raise HTTPException(status_code=401, detail="未登录或令牌缺失")
