"""数据备份脚本：在线备份 SQLite 数据库 + 复制本地图片目录。

用法：
    python backup.py [备份目标目录，默认 backend/backups]

特性：
- 使用 sqlite3 的 backup API 在线备份（不阻塞业务读写）；
- 复制 data/images/ 图片目录；
- 保留最近 N 份（默认 30），自动清理更早的备份。

定时执行：
    Linux  cron：  0 3 * * * cd /path/backend && venv/bin/python backup.py
    Windows 计划任务： 任务计划程序 -> 新建任务 -> 每天执行 python backup.py
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
DB_PATH = BACKEND_DIR / "generations.db"
IMAGE_DIR = BACKEND_DIR / "data" / "images"
KEEP_COUNT = 30  # 保留最近多少份备份


def backup_database(target_dir: Path) -> Path:
    """在线备份 SQLite 数据库，返回备份文件路径。"""
    src = sqlite3.connect(DB_PATH)
    dst_path = target_dir / f"generations_{datetime.now():%Y%m%d_%H%M%S}.db"
    dst = sqlite3.connect(dst_path)
    with dst:
        src.backup(dst)  # 在线备份，不阻塞业务读写
    dst.close()
    src.close()
    return dst_path


def backup_images(target_dir: Path) -> Path | None:
    """复制图片目录到备份目录，返回备份目录路径；无图片时返回 None。"""
    if not IMAGE_DIR.exists():
        return None
    img_backup = target_dir / f"images_{datetime.now():%Y%m%d_%H%M%S}"
    shutil.copytree(IMAGE_DIR, img_backup)
    return img_backup


def cleanup_old(target_dir: Path, keep: int = KEEP_COUNT):
    """只保留最近 keep 份备份，删除更早的。"""
    db_backups = sorted(
        target_dir.glob("generations_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in db_backups[keep:]:
        old.unlink()

    img_backups = sorted(
        target_dir.glob("images_*"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in img_backups[keep:]:
        shutil.rmtree(old, ignore_errors=True)


def main():
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else BACKEND_DIR / "backups"
    target.mkdir(parents=True, exist_ok=True)

    db_file = backup_database(target)
    print(f"数据库已备份：{db_file}")

    img_dir = backup_images(target)
    if img_dir:
        print(f"图片已备份：{img_dir}")
    else:
        print("无本地图片，跳过图片备份")

    cleanup_old(target)
    print(f"旧备份清理完成（保留最近 {KEEP_COUNT} 份）")


if __name__ == "__main__":
    main()
