from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING

import pandas as pd

if TYPE_CHECKING:
    from dot.checks.base import CheckResult


class ResultsStore:
    def __init__(self, db_path: str = "dot_results.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS results (
                    id              INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id          TEXT,
                    check_name      TEXT,
                    table_name      TEXT,
                    column_name     TEXT,
                    status          TEXT,
                    severity        TEXT,
                    observed_value  TEXT,
                    expected_value  TEXT,
                    message         TEXT,
                    run_at          TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_snapshots (
                    table_name    TEXT PRIMARY KEY,
                    snapshot_json TEXT,
                    saved_at      TIMESTAMP
                )
            """)
            conn.commit()

    def save(self, results: list[CheckResult], run_id: str) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT INTO results
                    (run_id, check_name, table_name, column_name, status, severity,
                     observed_value, expected_value, message, run_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        run_id,
                        r.check_name,
                        r.table,
                        r.column,
                        r.status,
                        r.severity,
                        str(r.observed_value) if r.observed_value is not None else None,
                        str(r.expected_value) if r.expected_value is not None else None,
                        r.message,
                        r.run_at.isoformat(),
                    )
                    for r in results
                ],
            )
            conn.commit()

    def get_history(self, table: str, check: str, days: int = 30) -> pd.DataFrame:
        """Returns past results for a given table + check type within the last N days."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(
                """
                SELECT * FROM results
                WHERE table_name = ? AND check_name = ? AND run_at >= ?
                ORDER BY run_at DESC
                """,
                conn,
                params=(table, check, cutoff),
            )

    def save_snapshot(self, table: str, columns: dict) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO schema_snapshots (table_name, snapshot_json, saved_at)
                VALUES (?, ?, ?)
                """,
                (table, json.dumps(columns), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()

    def reset_row_count_baseline(self, table: str) -> int:
        """Delete all row_count history for a table so the next run starts a fresh baseline."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "DELETE FROM results WHERE table_name = ? AND check_name = 'row_count'",
                (table,),
            )
            conn.commit()
            return cur.rowcount

    def get_snapshot(self, table: str) -> dict | None:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT snapshot_json FROM schema_snapshots WHERE table_name = ?",
                (table,),
            )
            row = cur.fetchone()
            return json.loads(row[0]) if row else None
