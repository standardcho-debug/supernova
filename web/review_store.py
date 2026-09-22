"""Sqlite persistence for F5 ReviewRecord — PRD v1.0 §6.3 `reviews`.

Same JSON-blob-per-row shape as sqlite_store.py's SqliteApprovalGate, for
the same reason: review_queue.ReviewStore only needs get-by-id and
list-filtered-by-status/client, never a join.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from sns_marketing_agent.review_models import CreativeStatus, ReasonCode, ReviewRecord, RubricScore


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"not JSON serializable: {type(obj)}")


def _record_to_dict(record: ReviewRecord) -> dict:
    data = asdict(record)
    data["status"] = record.status.value
    data["reason_codes"] = [c.value for c in record.reason_codes]
    return data


def _record_from_dict(data: dict) -> ReviewRecord:
    rubric = RubricScore(**data["rubric"])
    return ReviewRecord(
        client_slug=data["client_slug"],
        creative_id=data["creative_id"],
        brief_id=data["brief_id"],
        rubric=rubric,
        status=CreativeStatus(data["status"]),
        reviewer=data["reviewer"],
        reason_codes=[ReasonCode(c) for c in data["reason_codes"]],
        note=data["note"],
        reviewed_at=datetime.fromisoformat(data["reviewed_at"]) if data["reviewed_at"] else None,
        id=data["id"],
        created_at=datetime.fromisoformat(data["created_at"]),
    )


class SqliteReviewStore:
    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY,
                    client_slug TEXT NOT NULL,
                    status TEXT NOT NULL,
                    data TEXT NOT NULL
                )
                """
            )

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save(self, record: ReviewRecord) -> None:
        payload = json.dumps(_record_to_dict(record), default=_json_default, ensure_ascii=False)
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO reviews (id, client_slug, status, data) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET status = excluded.status, data = excluded.data",
                (record.id, record.client_slug, record.status.value, payload),
            )

    def get(self, record_id: str) -> ReviewRecord:
        with self._conn() as conn:
            row = conn.execute("SELECT data FROM reviews WHERE id = ?", (record_id,)).fetchone()
        if row is None:
            raise KeyError(record_id)
        return _record_from_dict(json.loads(row[0]))

    def pending(self, client_slug: str | None = None) -> list[ReviewRecord]:
        return self._select(CreativeStatus.PENDING_REVIEW.value, "=", client_slug)

    def reviewed(self, client_slug: str | None = None) -> list[ReviewRecord]:
        return self._select(CreativeStatus.PENDING_REVIEW.value, "!=", client_slug)

    def all(self, client_slug: str | None = None) -> list[ReviewRecord]:
        with self._conn() as conn:
            if client_slug is None:
                rows = conn.execute("SELECT data FROM reviews").fetchall()
            else:
                rows = conn.execute(
                    "SELECT data FROM reviews WHERE client_slug = ?", (client_slug,)
                ).fetchall()
        return [_record_from_dict(json.loads(r[0])) for r in rows]

    def _select(self, status_value: str, op: str, client_slug: str | None) -> list[ReviewRecord]:
        query = f"SELECT data FROM reviews WHERE status {op} ?"
        params: list = [status_value]
        if client_slug is not None:
            query += " AND client_slug = ?"
            params.append(client_slug)
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_record_from_dict(json.loads(r[0])) for r in rows]
