"""SQLite 数据库操作：建表、写入任务、更新状态、查询历史。

说明：
- 使用标准库 sqlite3，无需额外依赖。
- Celery worker 与 FastAPI 是两个独立进程，都会访问同一个 SQLite 文件，
  因此每次操作都新建连接（用 _conn 上下文管理器保证 commit/close），
  并设置 timeout 以减少并发写时的锁冲突。
"""
import os
import sqlite3
from contextlib import contextmanager

# 数据库文件与 db.py 放在同一目录
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generations.db")


def get_conn():
    """新建数据库连接。check_same_thread=False 允许跨线程使用。"""
    conn = sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # 让查询结果支持按列名取值
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
    """初始化数据表（幂等，可重复调用）。"""
    with _conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS generations (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id         TEXT UNIQUE NOT NULL,
                prompt          TEXT NOT NULL,
                negative_prompt TEXT DEFAULT '',
                size            TEXT DEFAULT '1024x1024',
                task_type       TEXT DEFAULT 'text2img',
                status          TEXT DEFAULT 'queued',
                image_url       TEXT DEFAULT '',
                error           TEXT DEFAULT '',
                created_at      TEXT DEFAULT (datetime('now', 'localtime'))
            )
            """
        )


def create_task(task_id, prompt, negative_prompt, size, task_type):
    """插入新任务记录，初始状态为 queued。"""
    with _conn() as conn:
        conn.execute(
            "INSERT INTO generations (task_id, prompt, negative_prompt, size, task_type, status) "
            "VALUES (?, ?, ?, ?, ?, 'queued')",
            (task_id, prompt, negative_prompt, size, task_type),
        )


def update_task(task_id, status, image_url=None, error=None):
    """更新任务状态，可同时更新图片链接与错误信息。"""
    sets, params = ["status = ?"], [status]
    if image_url is not None:
        sets.append("image_url = ?")
        params.append(image_url)
    if error is not None:
        sets.append("error = ?")
        params.append(error)
    params.append(task_id)
    with _conn() as conn:
        conn.execute(f"UPDATE generations SET {', '.join(sets)} WHERE task_id = ?", params)


def get_task(task_id):
    """按 task_id 查询单条记录，不存在时返回 None。"""
    with _conn() as conn:
        row = conn.execute("SELECT * FROM generations WHERE task_id = ?", (task_id,)).fetchone()
        return dict(row) if row else None


def list_tasks(limit=50, offset=0):
    """分页查询历史记录，按创建时间倒序（最新在前）。"""
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM generations ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)
        ).fetchall()
        return [dict(r) for r in rows]
