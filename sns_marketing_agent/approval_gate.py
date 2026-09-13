"""Stage 4: the mandatory human checkpoint before anything could go out.

The business plan is explicit that final approval of outward-facing content
stays with the client's founder — the automation removes the back-and-forth
before this point, not the approval itself. There is deliberately no
`publish()` here: turning an ApprovalRecord into an actual post on Naver
Blog / Instagram / Youtube is out of scope for this pipeline.

Records are keyed by id (not object identity) because the web frontend only
has an id string from a form post, never the Python object.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol

from .models import ApprovalRecord, ApprovalStatus, ContentDraft


class ApprovalStore(Protocol):
    """What pipeline.py and the web frontend need from a records store.

    `ApprovalGate` below (in-memory) and `SqliteApprovalGate`
    (web/sqlite_store.py, persists across restarts) both satisfy this
    structurally — neither inherits from it.
    """

    def submit(self, draft: ContentDraft) -> ApprovalRecord: ...
    def get(self, record_id: str) -> ApprovalRecord: ...
    def approve(self, record_id: str, reviewer: str) -> ApprovalRecord: ...
    def reject(self, record_id: str, reviewer: str, notes: str) -> ApprovalRecord: ...
    def pending(self, client_id: str | None = None) -> list[ApprovalRecord]: ...
    def reviewed(self, client_id: str | None = None) -> list[ApprovalRecord]: ...
    def all(self, client_id: str | None = None) -> list[ApprovalRecord]: ...


class ApprovalGate:
    def __init__(self):
        self._records: dict[str, ApprovalRecord] = {}

    def submit(self, draft: ContentDraft) -> ApprovalRecord:
        record = ApprovalRecord(draft=draft)
        self._records[record.id] = record
        return record

    def get(self, record_id: str) -> ApprovalRecord:
        return self._records[record_id]

    def approve(self, record_id: str, reviewer: str) -> ApprovalRecord:
        return self._set_status(record_id, ApprovalStatus.APPROVED, reviewer, "")

    def reject(self, record_id: str, reviewer: str, notes: str) -> ApprovalRecord:
        return self._set_status(record_id, ApprovalStatus.REJECTED, reviewer, notes)

    def pending(self, client_id: str | None = None) -> list[ApprovalRecord]:
        return self._filter(ApprovalStatus.PENDING, client_id)

    def reviewed(self, client_id: str | None = None) -> list[ApprovalRecord]:
        return [
            r
            for r in self._records.values()
            if r.status != ApprovalStatus.PENDING
            and (client_id is None or r.draft.brief.client_id == client_id)
        ]

    def all(self, client_id: str | None = None) -> list[ApprovalRecord]:
        records = list(self._records.values())
        if client_id is not None:
            records = [r for r in records if r.draft.brief.client_id == client_id]
        return records

    def _filter(self, status: ApprovalStatus, client_id: str | None) -> list[ApprovalRecord]:
        return [
            r
            for r in self._records.values()
            if r.status == status and (client_id is None or r.draft.brief.client_id == client_id)
        ]

    def _set_status(
        self,
        record_id: str,
        status: ApprovalStatus,
        reviewer: str,
        notes: str,
    ) -> ApprovalRecord:
        record = self._records[record_id]
        record.status = status
        record.reviewer = reviewer
        record.notes = notes
        record.reviewed_at = datetime.now(timezone.utc)
        return record
