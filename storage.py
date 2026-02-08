# -*- coding: utf-8 -*-
"""将 文件路径/文件名 与 领域 对应关系写入 SQLite 与 CSV。"""

import csv
import sqlite3
from pathlib import Path
from typing import List, Tuple, Optional


def ensure_db(db_path: str) -> sqlite3.Connection:
    """创建或连接数据库，并确保表存在。"""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS literature_domains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL UNIQUE,
            file_name TEXT,
            domain TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        )
    """)
    conn.commit()
    return conn


def upsert_domain(conn: sqlite3.Connection, file_path: str, domain: str) -> None:
    """插入或更新一条记录：路径 + 领域。"""
    name = Path(file_path).name
    conn.execute(
        """
        INSERT INTO literature_domains (file_path, file_name, domain)
        VALUES (?, ?, ?)
        ON CONFLICT(file_path) DO UPDATE SET
            domain = excluded.domain,
            file_name = excluded.file_name,
            updated_at = datetime('now','localtime')
        """,
        (str(Path(file_path).resolve()), name, domain),
    )
    conn.commit()


def export_csv(db_path: str, csv_path: str) -> None:
    """从数据库导出到 CSV。"""
    Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT file_path, file_name, domain, updated_at FROM literature_domains ORDER BY domain, file_name"
    ).fetchall()
    conn.close()
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file_path", "file_name", "domain", "updated_at"])
        w.writerows(rows)


def query_by_domain(db_path: str, domain: str) -> List[Tuple[str, str, str]]:
    """按领域筛选，返回 (file_path, file_name, domain) 列表。"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT file_path, file_name, domain FROM literature_domains WHERE domain = ? ORDER BY file_name",
        (domain,),
    ).fetchall()
    conn.close()
    return rows


def list_domains(db_path: str) -> List[str]:
    """返回所有出现过的领域列表（去重）。"""
    conn = sqlite3.connect(db_path)
    rows = conn.execute("SELECT DISTINCT domain FROM literature_domains ORDER BY domain").fetchall()
    conn.close()
    return [r[0] for r in rows]
