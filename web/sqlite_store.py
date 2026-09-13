"""Stage 4 persistence: survives process restarts, unlike ApprovalGate.

Serializes each ApprovalRecord (draft, brief, images, storyboard — the
works) as one JSON blob per row, alongside `client_id`/`status` columns for
filtering. This is not a normalized schema — the only queries this app
needs are "pending for client X" / "reviewed for client X" / "get by id",
none of which need a join. If real reporting/analytics on this data
becomes a need, that's the point to design a proper schema, not before.

A fresh sqlite3 connection is opened per call rather than held open, so
this is safe to use from FastAPI's request thread pool without any
cross-thread connection sharing.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from sns_marketing_agent.models import (
    ApprovalRecord,
    ApprovalStatus,
    Channel,
    ContentBrief,
    ContentDraft,
    ImageAsset,
    StoryboardScene,
)


def _record_to_dict(record: ApprovalRecord) -> dict:
    draft = record.draft
    brief = draft.brief
    return {
        "id": record.id,
        "status": record.status.value,
        "reviewer": record.reviewer,
        "reviewed_at": record.reviewed_at.isoformat() if record.reviewed_at else None,
        "notes": record.notes,
        "draft": {
            "title": draft.title,
            "body": draft.body,
            "hashtags": draft.hashtags,
            "thumbnail_text": draft.thumbnail_text,
            "images": [
                {"channel": i.channel.value, "file_path": i.file_path, "alt_text": i.alt_text}
                for i in draft.images
            ],
            "storyboard": [
                {
                    "order": s.order,
                    "on_screen_text": s.on_screen_text,
                    "narration": s.narration,
                    "duration_seconds": s.duration_seconds,
                }
                for s in draft.storyboard
            ],
            "brief": {
                "client_id": brief.client_id,
                "channel": brief.channel.value,
                "topic": brief.topic,
                "angle": brief.angle,
                "source_evidence": brief.source_evidence,
                "created_at": brief.created_at.isoformat(),
            },
        },
    }


def _record_from_dict(data: dict) -> ApprovalRecord:
    brief_data = data["draft"]["brief"]
    brief = ContentBrief(
        client_id=brief_data["client_id"],
        channel=Channel(brief_data["channel"]),
        topic=brief_data["topic"],
        angle=brief_data["angle"],
        source_evidence=brief_data["source_evidence"],
        created_at=datetime.fromisoformat(brief_data["created_at"]),
    )
    draft_data = data["draft"]
    draft = ContentDraft(
        brief=brief,
        title=draft_data["title"],
        body=draft_data["body"],
        hashtags=draft_data["hashtags"],
        thumbnail_text=draft_data["thumbnail_text"],
        images=[
            ImageAsset(channel=Channel(i["channel"]), file_path=i["file_path"], alt_text=i["alt_text"])
            for i in draft_data["images"]
        ],
        storyboard=[
            StoryboardScene(
                order=s["order"],
                on_screen_text=s["on_screen_text"],
                narration=s["narration"],
                duration_seconds=s["duration_seconds"],
            )
            for s in draft_data["storyboard"]
        ],
    )
    return ApprovalRecord(
        id=data["id"],
        draft=draft,
        status=ApprovalStatus(data["status"]),
        reviewer=data["reviewer"],
        reviewed_at=datetime.fromisoformat(data["reviewed_at"]) if data["reviewed_at"] else None,
        notes=data["notes"],
    )


class SqliteApprovalGate:
    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approval_records (
                    id TEXT PRIMARY KEY,
                    client_id TEXT NOT NULL,
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

    def submit(self, draft: ContentDraft) -> ApprovalRecord:
        record = ApprovalRecord(draft=draft)
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO approval_records (id, client_id, status, data) VALUES (?, ?, ?, ?)",
                (
                    record.id,
                    record.draft.brief.client_id,
                    record.status.value,
                    json.dumps(_record_to_dict(record), ensure_ascii=False),
                ),
            )
        return record

    def get(self, record_id: str) -> ApprovalRecord:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT data FROM approval_records WHERE id = ?", (record_id,)
            ).fetchone()
        if row is None:
            raise KeyError(record_id)
        return _record_from_dict(json.loads(row[0]))

    def approve(self, record_id: str, reviewer: str) -> ApprovalRecord:
        return self._update_status(record_id, ApprovalStatus.APPROVED, reviewer, "")

    def reject(self, record_id: str, reviewer: str, notes: str) -> ApprovalRecord:
        return self._update_status(record_id, ApprovalStatus.REJECTED, reviewer, notes)

    def _update_status(
        self, record_id: str, status: ApprovalStatus, reviewer: str, notes: str
    ) -> ApprovalRecord:
        record = self.get(record_id)  # raises KeyError if missing
        record.status = status
        record.reviewer = reviewer
        record.notes = notes
        record.reviewed_at = datetime.now(timezone.utc)
        with self._conn() as conn:
            conn.execute(
                "UPDATE approval_records SET status = ?, data = ? WHERE id = ?",
                (status.value, json.dumps(_record_to_dict(record), ensure_ascii=False), record_id),
            )
        return record

    def pending(self, client_id: str | None = None) -> list[ApprovalRecord]:
        return self._select(ApprovalStatus.PENDING.value, "=", client_id)

    def reviewed(self, client_id: str | None = None) -> list[ApprovalRecord]:
        return self._select(ApprovalStatus.PENDING.value, "!=", client_id)

    def all(self, client_id: str | None = None) -> list[ApprovalRecord]:
        with self._conn() as conn:
            if client_id is None:
                rows = conn.execute("SELECT data FROM approval_records").fetchall()
            else:
                rows = conn.execute(
                    "SELECT data FROM approval_records WHERE client_id = ?", (client_id,)
                ).fetchall()
        return [_record_from_dict(json.loads(r[0])) for r in rows]

    def _select(self, status_value: str, op: str, client_id: str | None) -> list[ApprovalRecord]:
        query = f"SELECT data FROM approval_records WHERE status {op} ?"
        params: list = [status_value]
        if client_id is not None:
            query += " AND client_id = ?"
            params.append(client_id)
        with self._conn() as conn:
            rows = conn.execute(query, params).fetchall()
        return [_record_from_dict(json.loads(r[0])) for r in rows]
