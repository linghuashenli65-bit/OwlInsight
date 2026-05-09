"""长期记忆 — SQLite 存储.

存储用户关注的公司、分析历史、高频关注指标、研究笔记、对话历史.
"""

import json
import threading
import uuid
from backend.logger import logger
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from backend.config import settings

class MemoryStore:
    """SQLite 长期记忆管理器."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or settings.MEMORY_DB_PATH
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()

    # ────────── 连接与初始化 ──────────

    def connect(self) -> "MemoryStore":
        """连接 SQLite 数据库，自动建表（已连接时跳过）. """
        if self._conn is not None:
            return self
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
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

            CREATE TABLE IF NOT EXISTS notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_code TEXT NOT NULL,
                company_name TEXT DEFAULT '',
                title TEXT DEFAULT '',
                content TEXT NOT NULL,
                metrics TEXT DEFAULT '[]',
                tags TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT DEFAULT '新对话',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT DEFAULT '',
                reasoning TEXT DEFAULT '[]',
                citations TEXT DEFAULT '[]',
                anomalies TEXT DEFAULT '[]',
                chart_data TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            );
        """)
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS alert_config (
                company_code TEXT PRIMARY KEY,
                price_up_pct REAL DEFAULT 5.0,
                price_down_pct REAL DEFAULT -5.0,
                fund_flow_threshold REAL DEFAULT 100000000.0,
                news_enabled INTEGER DEFAULT 1,
                intraday_enabled INTEGER DEFAULT 1,
                FOREIGN KEY (company_code) REFERENCES watched_companies(company_code)
            );

            CREATE TABLE IF NOT EXISTS alert_preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS alert_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_code TEXT NOT NULL,
                company_name TEXT DEFAULT '',
                event_type TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT DEFAULT '',
                severity TEXT DEFAULT 'info',
                data TEXT DEFAULT '{}',
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        # 迁移：旧表无 title 列时补充
        try:
            self.conn.execute("ALTER TABLE notes ADD COLUMN title TEXT DEFAULT ''")
        except Exception:
            pass  # 列已存在
        self.conn.commit()

    # ────────── 关注公司 ──────────

    def add_or_update_company(self, code: str, name: str) -> None:
        """新增或更新关注的公司（自动清洗代码）. """
        # 清洗：只取第一个代码（防止 "600519,000858" 之类的情况）
        import re as _re
        code = _re.split(r"[,，\s]+", code.strip())[0]
        # 去掉 .HK/.SH/.SZ 后缀
        code = _re.sub(r"\.(HK|SH|SZ|hk|sh|sz)$", "", code)
        # 补前导零（0700 → 00700）
        if code.isdigit() and len(code) == 4:
            code = "0" + code
        if not code:
            return
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

    def delete_company(self, company_code: str) -> None:
        """删除关注的公司及相关分析历史."""
        self.conn.execute("DELETE FROM analysis_history WHERE company_code = ?", (company_code,))
        self.conn.execute("DELETE FROM alert_config WHERE company_code = ?", (company_code,))
        self.conn.execute("DELETE FROM watched_companies WHERE company_code = ?", (company_code,))
        self.conn.commit()

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

    # ────────── 研究笔记 ──────────

    def upsert_note(
        self,
        company_code: str,
        company_name: str,
        content: str,
        title: str = "",
        metrics: Optional[list[str]] = None,
        tags: Optional[list[str]] = None,
    ) -> int:
        """保存或追加研究笔记（同一公司 + 同一天合并）. """
        today = date.today().isoformat()
        metrics_json = json.dumps(metrics or [], ensure_ascii=False)
        tags_json = json.dumps(tags or [], ensure_ascii=False)

        existing = self.conn.execute(
            "SELECT id, content, title FROM notes WHERE company_code = ? AND date(created_at) = ? ORDER BY created_at DESC LIMIT 1",
            (company_code, today),
        ).fetchone()

        if existing:
            new_content = existing["content"] + "\n\n---\n\n" + content
            new_title = existing["title"] or title  # 保留原标题
            self.conn.execute(
                "UPDATE notes SET title = ?, content = ?, metrics = ?, tags = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_title, new_content, metrics_json, tags_json, existing["id"]),
            )
            self.conn.commit()
            return existing["id"]

        cur = self.conn.execute(
            "INSERT INTO notes (company_code, company_name, title, content, metrics, tags) VALUES (?, ?, ?, ?, ?, ?)",
            (company_code, company_name, title, content, metrics_json, tags_json),
        )
        self.conn.commit()
        return cur.lastrowid

    def search_notes(self, keyword: str, limit: int = 20) -> list[dict[str, Any]]:
        """搜索笔记（模糊匹配 content / company_name / tags）. """
        pattern = f"%{keyword}%"
        rows = self.conn.execute(
            "SELECT * FROM notes WHERE content LIKE ? OR company_name LIKE ? OR tags LIKE ? "
            "ORDER BY updated_at DESC LIMIT ?",
            (pattern, pattern, pattern, limit),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["metrics"] = json.loads(d.get("metrics", "[]"))
            d["tags"] = json.loads(d.get("tags", "[]"))
            result.append(d)
        return result

    def get_notes_by_company(self, company_code: str, limit: int = 10) -> list[dict[str, Any]]:
        """获取某公司的研究笔记."""
        rows = self.conn.execute(
            "SELECT * FROM notes WHERE company_code = ? ORDER BY updated_at DESC LIMIT ?",
            (company_code, limit),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["metrics"] = json.loads(d.get("metrics", "[]"))
            d["tags"] = json.loads(d.get("tags", "[]"))
            result.append(d)
        return result

    def get_all_notes(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取所有笔记（带预览）. """
        rows = self.conn.execute(
            "SELECT id, company_code, company_name, title, substr(content, 1, 200) as preview, "
            "metrics, tags, created_at, updated_at FROM notes ORDER BY updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["metrics"] = json.loads(d.get("metrics", "[]"))
            d["tags"] = json.loads(d.get("tags", "[]"))
            result.append(d)
        return result

    def get_note_by_id(self, note_id: int) -> Optional[dict[str, Any]]:
        """按 ID 获取笔记完整内容."""
        row = self.conn.execute(
            "SELECT * FROM notes WHERE id = ?", (note_id,)
        ).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["metrics"] = json.loads(d.get("metrics", "[]"))
        d["tags"] = json.loads(d.get("tags", "[]"))
        return d

    def delete_note(self, note_id: int) -> None:
        """删除指定笔记."""
        self.conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        self.conn.commit()

    # ────────── 对话历史 ──────────

    def create_conversation(self, conv_id: Optional[str] = None, title: str = "新对话") -> str:
        """创建新对话，返回 id."""
        cid = conv_id or str(uuid.uuid4())
        self.conn.execute(
            "INSERT OR IGNORE INTO conversations (id, title) VALUES (?, ?)",
            (cid, title),
        )
        self.conn.commit()
        return cid

    def list_conversations(self, limit: int = 50) -> list[dict[str, Any]]:
        """获取对话列表（含消息数）. """
        rows = self.conn.execute(
            "SELECT c.id, c.title, c.created_at, c.updated_at, "
            "COUNT(m.id) as message_count "
            "FROM conversations c LEFT JOIN messages m ON c.id = m.conversation_id "
            "GROUP BY c.id ORDER BY c.updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_conversation(self, conv_id: str) -> Optional[dict[str, Any]]:
        """获取单个对话."""
        row = self.conn.execute(
            "SELECT * FROM conversations WHERE id = ?", (conv_id,)
        ).fetchone()
        return dict(row) if row else None

    def update_conversation_title(self, conv_id: str, title: str) -> None:
        """更新对话标题."""
        self.conn.execute(
            "UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (title, conv_id),
        )
        self.conn.commit()

    def delete_conversation(self, conv_id: str) -> None:
        """删除对话及其消息."""
        self.conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
        self.conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
        self.conn.commit()

    def add_message(
        self,
        conv_id: str,
        role: str,
        content: str,
        reasoning: Optional[list[str]] = None,
        citations: Optional[list[dict]] = None,
        anomalies: Optional[list[dict]] = None,
        chart_data: Optional[str] = None,
    ) -> int:
        """添加消息到对话，返回消息 id."""
        try:
            cur = self.conn.execute(
                "INSERT INTO messages (conversation_id, role, content, reasoning, citations, anomalies, chart_data) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    conv_id,
                    role,
                    content,
                    json.dumps(reasoning or [], ensure_ascii=False),
                    json.dumps(citations or [], ensure_ascii=False),
                    json.dumps(anomalies or [], ensure_ascii=False),
                    chart_data,
                ),
            )
            self.conn.execute(
                "UPDATE conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (conv_id,),
            )
            self.conn.commit()
            return cur.lastrowid
        except Exception as e:
            logger.warning("保存消息失败 (conv=%s role=%s): %s", conv_id, role, e)
            return -1

    def get_messages(self, conv_id: str) -> list[dict[str, Any]]:
        """获取对话的所有消息."""
        rows = self.conn.execute(
            "SELECT * FROM messages WHERE conversation_id = ? ORDER BY created_at ASC, id ASC",
            (conv_id,),
        ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            for field in ("reasoning", "citations", "anomalies"):
                try:
                    d[field] = json.loads(d.get(field, "[]"))
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
            result.append(d)
        return result

    # ────────── 告警配置 ──────────

    def get_alert_config(self, company_code: str) -> dict[str, Any]:
        """获取某公司的告警阈值配置，不存在则返回默认值."""
        row = self.conn.execute(
            "SELECT * FROM alert_config WHERE company_code = ?", (company_code,)
        ).fetchone()
        if row:
            return dict(row)
        return {
            "company_code": company_code,
            "price_up_pct": 5.0,
            "price_down_pct": -5.0,
            "fund_flow_threshold": 100000000.0,
            "news_enabled": 1,
            "intraday_enabled": 1,
        }

    def save_alert_config(self, config: dict[str, Any]) -> None:
        """保存某公司的告警阈值配置."""
        self.conn.execute("""
            INSERT INTO alert_config (company_code, price_up_pct, price_down_pct, fund_flow_threshold, news_enabled, intraday_enabled)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(company_code) DO UPDATE SET
                price_up_pct = excluded.price_up_pct,
                price_down_pct = excluded.price_down_pct,
                fund_flow_threshold = excluded.fund_flow_threshold,
                news_enabled = excluded.news_enabled,
                intraday_enabled = excluded.intraday_enabled
        """, (
            config["company_code"],
            config.get("price_up_pct", 5.0),
            config.get("price_down_pct", -5.0),
            config.get("fund_flow_threshold", 100000000.0),
            1 if config.get("news_enabled", True) else 0,
            1 if config.get("intraday_enabled", True) else 0,
        ))
        self.conn.commit()

    def get_all_alert_configs(self) -> list[dict[str, Any]]:
        """获取所有公司的告警配置."""
        rows = self.conn.execute(
            "SELECT ac.*, wc.company_name FROM alert_config ac "
            "LEFT JOIN watched_companies wc ON ac.company_code = wc.company_code"
        ).fetchall()
        return [dict(r) for r in rows]

    # ────────── 告警事件 ──────────

    def record_alert(self, event: dict[str, Any]) -> int:
        """记录一条告警事件，返回 id."""
        cur = self.conn.execute(
            "INSERT INTO alert_events (company_code, company_name, event_type, title, message, severity, data) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                event.get("company_code", ""),
                event.get("company_name", ""),
                event.get("event_type", "unknown"),
                event.get("title", ""),
                event.get("message", ""),
                event.get("severity", "info"),
                json.dumps(event.get("data", {}), ensure_ascii=False),
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_recent_alerts(self, limit: int = 50, unread_only: bool = False) -> list[dict[str, Any]]:
        """获取最近的告警事件."""
        if unread_only:
            rows = self.conn.execute(
                "SELECT * FROM alert_events WHERE is_read = 0 ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM alert_events ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            try:
                d["data"] = json.loads(d.get("data", "{}"))
            except (json.JSONDecodeError, TypeError):
                d["data"] = {}
            result.append(d)
        return result

    def mark_alert_read(self, alert_id: int) -> None:
        """标记告警为已读."""
        self.conn.execute("UPDATE alert_events SET is_read = 1 WHERE id = ?", (alert_id,))
        self.conn.commit()

    def mark_all_alerts_read(self) -> None:
        """标记所有告警为已读."""
        self.conn.execute("UPDATE alert_events SET is_read = 1 WHERE is_read = 0")
        self.conn.commit()

    def get_unread_alert_count(self) -> int:
        """获取未读告警数."""
        row = self.conn.execute(
            "SELECT COUNT(*) as cnt FROM alert_events WHERE is_read = 0"
        ).fetchone()
        return row["cnt"] if row else 0

    # ────────── 通用设置（key-value，替代 MySQL app_settings）──────────

    def get_all_settings(self) -> dict[str, str]:
        """读取所有设置."""
        rows = self.conn.execute("SELECT key, value FROM app_settings").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def get_setting(self, key: str, default: str = "") -> str:
        """读取单条设置."""
        row = self.conn.execute("SELECT value FROM app_settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def save_settings(self, data: dict[str, str]) -> None:
        """批量保存设置."""
        for key, value in data.items():
            self.conn.execute(
                "INSERT INTO app_settings (key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )
        self.conn.commit()

    # ────────── 告警偏好设置（key-value）──────────

    def set_preference(self, key: str, value: str) -> None:
        """设置一条偏好."""
        self.conn.execute(
            "INSERT INTO alert_preferences (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        self.conn.commit()

    def get_preference(self, key: str, default: str = "") -> str:
        """读取一条偏好."""
        row = self.conn.execute(
            "SELECT value FROM alert_preferences WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def get_all_preferences(self) -> dict[str, str]:
        """读取所有偏好."""
        rows = self.conn.execute("SELECT key, value FROM alert_preferences").fetchall()
        return {r["key"]: r["value"] for r in rows}

    def set_preferences_batch(self, data: dict[str, str]) -> None:
        """批量设置偏好（线程安全，逐条 UPSERT）. """
        with self._lock:
            for key, value in data.items():
                if not isinstance(key, str) or value is None:
                    continue
                self.conn.execute(
                    "INSERT INTO alert_preferences (key, value) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, str(value)),
                )
            self.conn.commit()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            logger.info("记忆库已关闭")

# 全局单例
memory_store = MemoryStore()
