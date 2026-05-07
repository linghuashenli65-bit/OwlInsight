"""长期记忆 — SQLite 存储.

存储用户关注的公司、分析历史、高频关注指标.
"""

import json
import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from src.config import settings

logger = logging.getLogger(__name__)


class MemoryStore:
    """SQLite 长期记忆管理器."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or settings.MEMORY_DB_PATH
        self._conn: Optional[sqlite3.Connection] = None

    # ────────── 连接与初始化 ──────────

    def connect(self) -> "MemoryStore":
        """连接 SQLite 数据库，自动建表."""
        self._conn = sqlite3.connect(self._db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_tables()
        logger.info("记忆库已连接: %s", self._db_path)
        return self

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("请先调用 connect() 连接数据库")
        return self._conn

    def _init_tables(self) -> None:
        cur = self.conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS watched_companies (
                company_code TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                first_analyzed DATE NOT NULL,
                last_analyzed DATE NOT NULL,
                analysis_count INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS analysis_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_code TEXT NOT NULL,
                question TEXT NOT NULL,
                summary TEXT DEFAULT '',
                key_metrics_mentioned TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (company_code) REFERENCES watched_companies(company_code)
            );

            CREATE TABLE IF NOT EXISTS user_interests (
                metric_name TEXT PRIMARY KEY,
                mention_count INTEGER DEFAULT 1,
                last_mentioned DATE NOT NULL,
                related_companies TEXT DEFAULT '[]'
            );
        """)
        self.conn.commit()

    # ────────── 关注公司 ──────────

    def add_or_update_company(self, code: str, name: str) -> None:
        """新增或更新关注的公司."""
        today = date.today().isoformat()
        self.conn.execute("""
            INSERT INTO watched_companies (company_code, company_name, first_analyzed, last_analyzed, analysis_count)
            VALUES (?, ?, ?, ?, 1)
            ON CONFLICT(company_code) DO UPDATE SET
                last_analyzed = excluded.last_analyzed,
                analysis_count = analysis_count + 1
        """, (code, name, today, today))
        self.conn.commit()

    def get_all_watched_companies(self) -> list[dict]:
        """获取所有关注的公司."""
        rows = self.conn.execute(
            "SELECT * FROM watched_companies ORDER BY last_analyzed DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_recently_analyzed(self, limit: int = 5) -> list[dict]:
        """最近分析过的公司."""
        rows = self.conn.execute(
            "SELECT * FROM watched_companies ORDER BY last_analyzed DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ────────── 分析历史 ──────────

    def add_analysis(self, company_code: str, question: str, summary: str = "",
                     metrics: Optional[list[str]] = None) -> int:
        """记录一次分析."""
        metrics_json = json.dumps(metrics or [], ensure_ascii=False)
        cur = self.conn.execute(
            "INSERT INTO analysis_history (company_code, question, summary, key_metrics_mentioned) "
            "VALUES (?, ?, ?, ?)",
            (company_code, question, summary, metrics_json),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_analysis_history(self, company_code: str, limit: int = 20) -> list[dict]:
        """获取某公司的分析历史."""
        rows = self.conn.execute(
            "SELECT * FROM analysis_history WHERE company_code = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (company_code, limit),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["key_metrics_mentioned"] = json.loads(d.get("key_metrics_mentioned", "[]"))
            except (json.JSONDecodeError, TypeError):
                d["key_metrics_mentioned"] = []
            result.append(d)
        return result

    def get_all_analysis(self, limit: int = 50) -> list[dict]:
        """获取所有分析记录."""
        rows = self.conn.execute(
            "SELECT * FROM analysis_history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ────────── 用户兴趣 ──────────

    def record_metric_mention(self, metric: str, company_code: str) -> None:
        """记录一次指标关注."""
        today = date.today().isoformat()
        existing = self.conn.execute(
            "SELECT * FROM user_interests WHERE metric_name = ?",
            (metric,),
        ).fetchone()

        if existing:
            related = json.loads(existing["related_companies"])
            if company_code not in related:
                related.append(company_code)
            self.conn.execute(
                "UPDATE user_interests SET mention_count = mention_count + 1, "
                "last_mentioned = ?, related_companies = ? WHERE metric_name = ?",
                (today, json.dumps(related, ensure_ascii=False), metric),
            )
        else:
            self.conn.execute(
                "INSERT INTO user_interests (metric_name, mention_count, last_mentioned, related_companies) "
                "VALUES (?, 1, ?, ?)",
                (metric, today, json.dumps([company_code], ensure_ascii=False)),
            )
        self.conn.commit()

    def get_top_interests(self, limit: int = 5) -> list[dict]:
        """获取用户最高频关注的指标."""
        rows = self.conn.execute(
            "SELECT * FROM user_interests ORDER BY mention_count DESC, last_mentioned DESC LIMIT ?",
            (limit,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["related_companies"] = json.loads(d.get("related_companies", "[]"))
            except (json.JSONDecodeError, TypeError):
                d["related_companies"] = []
            result.append(d)
        return result

    def get_matching_interests(self, metrics: list[str]) -> list[dict]:
        """批量查询指定指标的用户关注情况."""
        if not metrics:
            return []
        placeholders = ",".join("?" for _ in metrics)
        rows = self.conn.execute(
            f"SELECT * FROM user_interests WHERE metric_name IN ({placeholders})",
            metrics,
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["related_companies"] = json.loads(d.get("related_companies", "[]"))
            except (json.JSONDecodeError, TypeError):
                d["related_companies"] = []
            result.append(d)
        return result

    # ────────── 回顾功能 ──────────

    def search_analysis(self, keyword: str, limit: int = 5) -> list[dict]:
        """搜索分析历史（按公司名或问题内容模糊匹配）."""
        pattern = f"%{keyword}%"
        rows = self.conn.execute(
            "SELECT ah.*, wc.company_name FROM analysis_history ah "
            "LEFT JOIN watched_companies wc ON ah.company_code = wc.company_code "
            "WHERE wc.company_name LIKE ? OR ah.question LIKE ? OR ah.summary LIKE ? "
            "ORDER BY ah.created_at DESC LIMIT ?",
            (pattern, pattern, pattern, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            logger.info("记忆库已关闭")


# 全局单例
memory_store = MemoryStore()
