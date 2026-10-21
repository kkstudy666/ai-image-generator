"""SQLite 数据库操作：用户表 + 任务表，含轻量迁移与幂等写入。

说明：
- 使用标准库 sqlite3，每次操作新建连接（_conn 上下文管理器），
  设置 timeout 减少 Celery worker 与 FastAPI 并发写时的锁冲突。
- init_db 幂等：旧库缺少新列时自动 ALTER TABLE 补齐，兼容既有 generations.db。
"""
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generations.db")


def get_conn():
    """新建数据库连接。check_same_thread=False 允许跨线程使用。"""
    conn = sqlite3.connect(DB_PATH, timeout=15, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def _conn():
    """连接上下文管理器：自动 commit / rollback / close。"""
    conn = get_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    """初始化数据表 + 轻量迁移（幂等，可重复调用）。"""
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at    TEXT DEFAULT (datetime('now', 'localtime'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS generations (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id         TEXT UNIQUE NOT NULL,
                request_id      TEXT,
                user_id         INTEGER NOT NULL DEFAULT 0,
                prompt          TEXT NOT NULL,
                negative_prompt TEXT DEFAULT '',
                size            TEXT DEFAULT '1024x1024',
                task_type       TEXT DEFAULT 'text2img',
                status          TEXT DEFAULT 'queued',
                image_url       TEXT DEFAULT '',
                local_path      TEXT DEFAULT '',
                error           TEXT DEFAULT '',
                created_at      TEXT DEFAULT (datetime('now', 'localtime'))
            )
            """
        )

        # 轻量迁移：为旧版本数据库补齐新增列
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(generations)").fetchall()}
        if "user_id" not in existing:
            conn.execute("ALTER TABLE generations ADD COLUMN user_id INTEGER NOT NULL DEFAULT 0")
        if "request_id" not in existing:
            conn.execute("ALTER TABLE generations ADD COLUMN request_id TEXT")
        if "local_path" not in existing:
            conn.execute("ALTER TABLE generations ADD COLUMN local_path TEXT DEFAULT ''")

        # 索引：按用户倒序查询 + request_id 幂等唯一
        conn.execute("CREATE INDEX IF NOT EXISTS idx_generations_user ON generations(user_id, id DESC)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_generations_request_id ON generations(request_id)")


# ===== 用户 =====

def create_user(username, password_hash):
    """注册新用户，用户名重复时抛 sqlite3.IntegrityError。"""
    with _conn() as conn:
        conn.execute(
            "INSERT INTO users (username, password_hash) VALUES (?, ?)",
            (username, password_hash),
        )


def get_user_by_username(username):
    """按用户名查询，不存在返回 None。"""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id):
    """按用户 ID 查询，不存在返回 None。"""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row else None


# ===== 任务 =====

def create_task_if_not_exists(user_id, request_id, task_id, prompt, negative_prompt, size, task_type):
    """幂等插入：request_id 已存在则返回已有记录，否则新建并返回 None。

    返回：
        dict —— 命中已有任务（调用方应直接返回，不再投递队列）
        None —— 新建成功（调用方投递 Celery）
    """
    conn = get_conn()
    try:
        # 先查：命中则直接返回，避免重复生成
        row = conn.execute(
            "SELECT * FROM generations WHERE request_id = ?", (request_id,)
        ).fetchone()
        if row:
            return dict(row)

        conn.execute(
            "INSERT INTO generations "
            "(task_id, request_id, user_id, prompt, negative_prompt, size, task_type, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'queued')",
            (task_id, request_id, user_id, prompt, negative_prompt, size, task_type),
        )
        conn.commit()
        return None
    except sqlite3.IntegrityError:
        # 并发下 request_id 唯一约束冲突：说明已有相同请求，回读返回
        conn.rollback()
        row = conn.execute(
            "SELECT * FROM generations WHERE request_id = ?", (request_id,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_task(task_id, status, image_url=None, local_path=None, error=None):
    """更新任务状态，可同时更新图片链接、本地路径与错误信息。"""
    sets, params = ["status = ?"], [status]
    if image_url is not None:
        sets.append("image_url = ?")
        params.append(image_url)
    if local_path is not None:
        sets.append("local_path = ?")
        params.append(local_path)
    if error is not None:
        sets.append("error = ?")
        params.append(error)
    params.append(task_id)
    with _conn() as conn:
        conn.execute(f"UPDATE generations SET {', '.join(sets)} WHERE task_id = ?", params)


def get_task(task_id):
    """按 task_id 查询单条记录，不存在返回 None。"""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM generations WHERE task_id = ?", (task_id,)).fetchone()
        return dict(row) if row else None


def list_tasks(user_id, limit=50, offset=0):
    """分页查询当前用户的任务，按 id 倒序（最新在前）。"""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM generations WHERE user_id = ? ORDER BY id DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
