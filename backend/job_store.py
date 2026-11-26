"""Persistent task/job store supporting PostgreSQL (production) and SQLite (local)."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import threading
from typing import Any, Optional


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStore:
    """Thread-safe persistent storage for scraping jobs and live progress."""

    def __init__(
        self,
        database_url: Optional[str] = None,
        sqlite_path: str | Path = "data/jobs.db",
    ) -> None:
        self.database_url = (database_url or os.getenv("DATABASE_URL") or "").strip()
        self.sqlite_path = Path(sqlite_path)
        self._lock = threading.Lock()
        self._use_postgres = self.database_url.startswith(("postgres://", "postgresql://"))

        if not self._use_postgres:
            self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self):
        if self._use_postgres:
            import psycopg
            from psycopg.rows import dict_row

            return psycopg.connect(self.database_url, row_factory=dict_row)
        conn = sqlite3.connect(str(self.sqlite_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _ph(self) -> str:
        return "%s" if self._use_postgres else "?"

    def _init_schema(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS automation_jobs (
            task_id TEXT PRIMARY KEY,
            raw_message TEXT NOT NULL,
            category TEXT NOT NULL,
            discount_percent TEXT NOT NULL,
            status TEXT NOT NULL,
            stage TEXT NOT NULL,
            stage_index INTEGER NOT NULL DEFAULT 1,
            total_stages INTEGER NOT NULL DEFAULT 11,
            progress_percent INTEGER NOT NULL DEFAULT 0,
            products_discovered INTEGER NOT NULL DEFAULT 0,
            products_extracted INTEGER NOT NULL DEFAULT 0,
            failed_products INTEGER NOT NULL DEFAULT 0,
            current_subcategory TEXT NOT NULL DEFAULT '',
            subcategories_json TEXT NOT NULL DEFAULT '[]',
            failures_json TEXT NOT NULL DEFAULT '[]',
            warnings_json TEXT NOT NULL DEFAULT '[]',
            excel_filename TEXT NOT NULL DEFAULT '',
            excel_storage_key TEXT NOT NULL DEFAULT '',
            pdf_filename TEXT NOT NULL DEFAULT '',
            pdf_storage_key TEXT NOT NULL DEFAULT '',
            error_message TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            started_at TEXT NOT NULL DEFAULT '',
            completed_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );
        """
        with self._lock, self._connect() as conn:
            conn.execute(ddl)
            conn.commit()

    def _row_to_dict(self, row: Any) -> dict[str, Any]:
        d = dict(row)
        d["subcategories"] = json.loads(d.pop("subcategories_json", "[]") or "[]")
        d["failures"] = json.loads(d.pop("failures_json", "[]") or "[]")
        d["warnings"] = json.loads(d.pop("warnings_json", "[]") or "[]")
        return d

    def create_job(
        self,
        task_id: str,
        raw_message: str,
        category: str,
        discount_percent: str,
    ) -> dict[str, Any]:
        now = _utc_now_iso()
        ph = self._ph()
        sql = f"""
        INSERT INTO automation_jobs (
            task_id, raw_message, category, discount_percent,
            status, stage, stage_index, total_stages, progress_percent,
            created_at, updated_at
        ) VALUES ({ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph}, {ph})
        """
        params = (
            task_id,
            raw_message,
            category,
            discount_percent,
            "queued",
            "Validating task",
            1,
            11,
            5,
            now,
            now,
        )
        with self._lock, self._connect() as conn:
            conn.execute(sql, params)
            conn.commit()
        return self.get_job(task_id)  # type: ignore[return-value]

    def get_job(self, task_id: str) -> Optional[dict[str, Any]]:
        ph = self._ph()
        sql = f"SELECT * FROM automation_jobs WHERE task_id = {ph}"
        with self._lock, self._connect() as conn:
            cur = conn.execute(sql, (task_id,))
            row = cur.fetchone()
            return self._row_to_dict(row) if row else None

    def find_active_duplicate(self, category: str, discount_percent: str) -> Optional[dict[str, Any]]:
        """Prevent duplicate concurrent submissions for the exact same category and discount."""
        ph = self._ph()
        sql = f"""
        SELECT * FROM automation_jobs
        WHERE LOWER(category) = LOWER({ph})
          AND discount_percent = {ph}
          AND status IN ('queued', 'running')
        ORDER BY created_at DESC
        LIMIT 1
        """
        with self._lock, self._connect() as conn:
            cur = conn.execute(sql, (category, discount_percent))
            row = cur.fetchone()
            return self._row_to_dict(row) if row else None

    def update_job(self, task_id: str, **fields: Any) -> Optional[dict[str, Any]]:
        if not fields:
            return self.get_job(task_id)

        mapped: dict[str, Any] = {}
        for k, v in fields.items():
            if k == "subcategories":
                mapped["subcategories_json"] = json.dumps(v)
            elif k == "failures":
                mapped["failures_json"] = json.dumps(v)
            elif k == "warnings":
                mapped["warnings_json"] = json.dumps(v)
            else:
                mapped[k] = v
        mapped["updated_at"] = _utc_now_iso()

        ph = self._ph()
        assignments = ", ".join(f"{col} = {ph}" for col in mapped)
        sql = f"UPDATE automation_jobs SET {assignments} WHERE task_id = {ph}"
        params = tuple(mapped.values()) + (task_id,)
        with self._lock, self._connect() as conn:
            conn.execute(sql, params)
            conn.commit()
        return self.get_job(task_id)

    def delete_job(self, task_id: str) -> bool:
        ph = self._ph()
        sql = f"DELETE FROM automation_jobs WHERE task_id = {ph}"
        with self._lock, self._connect() as conn:
            cur = conn.execute(sql, (task_id,))
            conn.commit()
            return (cur.rowcount or 0) > 0
