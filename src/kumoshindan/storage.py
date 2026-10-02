"""SQLite history for Kubernetes investigations."""

import json
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from kumoshindan.agent.graph import InvestigationResult
from kumoshindan.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS investigations (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    source TEXT NOT NULL,
    namespace TEXT NOT NULL,
    symptom TEXT NOT NULL,
    status TEXT NOT NULL,
    report_json TEXT,
    tool_calls_json TEXT,
    duration_s REAL,
    tokens_in INTEGER,
    tokens_out INTEGER,
    error TEXT
)
"""


@contextmanager
def _connection() -> Iterator[sqlite3.Connection]:
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, timeout=10)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_db() -> None:
    with _connection() as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute(SCHEMA)


def create(source: str, namespace: str, symptom: str) -> str:
    investigation_id = uuid.uuid4().hex[:12]
    with _connection() as connection:
        connection.execute(
            """
            INSERT INTO investigations
                (id, created_at, source, namespace, symptom, status)
            VALUES (?, ?, ?, ?, ?, 'queued')
            """,
            (
                investigation_id,
                datetime.now(timezone.utc).isoformat(),
                source,
                namespace,
                symptom,
            ),
        )
    return investigation_id


def mark_running(investigation_id: str) -> None:
    with _connection() as connection:
        connection.execute(
            "UPDATE investigations SET status='running' WHERE id=?",
            (investigation_id,),
        )


def finish(investigation_id: str, result: InvestigationResult) -> None:
    status = "done" if result.report else "failed"
    error = result.error or (None if result.report else "Investigation returned no report.")
    with _connection() as connection:
        connection.execute(
            """
            UPDATE investigations
            SET status=?, report_json=?, tool_calls_json=?, duration_s=?,
                tokens_in=?, tokens_out=?, error=?
            WHERE id=?
            """,
            (
                status,
                result.report.model_dump_json() if result.report else None,
                json.dumps(result.tool_calls),
                result.duration_s,
                result.tokens_in,
                result.tokens_out,
                error,
                investigation_id,
            ),
        )


def get(investigation_id: str) -> dict | None:
    with _connection() as connection:
        row = connection.execute(
            "SELECT * FROM investigations WHERE id=?",
            (investigation_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_recent(limit: int = 20) -> list[dict]:
    with _connection() as connection:
        rows = connection.execute(
            "SELECT * FROM investigations ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row: sqlite3.Row) -> dict:
    item = dict(row)
    report_json = item.pop("report_json")
    tool_calls_json = item.pop("tool_calls_json")
    item["report"] = json.loads(report_json) if report_json else None
    item["tool_calls"] = json.loads(tool_calls_json) if tool_calls_json else []
    return item
