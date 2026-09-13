"""Stage 4: the mandatory human checkpoint before anything could go out.

The business plan is explicit that final approval of outward-facing content
stays with the client's founder — the automation removes the back-and-forth
before this point, not the approval itself. There is deliberately no
`publish()` here: turning an ApprovalRecord into an actual post on Naver
Blog / Instagram / Youtube is out of scope for this pipeline.
"""
from __future__ import annotations

from datetime import datetime, timezone

from .models import ApprovalRecord, ApprovalStatus, ContentDraft


class ApprovalGate:
    def __init__(self):
        self._records: list[ApprovalRecord] = []

    def submit(self, draft: ContentDraft) -> ApprovalRecord:
        record = ApprovalRecord(draft=draft)
        self._records.append(record)
        return record

    def approve(self, record: ApprovalRecord, reviewer: str) -> None:
        self._set_status(record, ApprovalStatus.APPROVED, reviewer, "")

    def reject(self, record: ApprovalRecord, reviewer: str, notes: str) -> None:
        self._set_status(record, ApprovalStatus.REJECTED, reviewer, notes)

    def pending(self) -> list[ApprovalRecord]:
        return [r for r in self._records if r.status == ApprovalStatus.PENDING]

    def _set_status(
        self,
        record: ApprovalRecord,
        status: ApprovalStatus,
        reviewer: str,
        notes: str,
    ) -> None:
        if record not in self._records:
            raise ValueError("record was not submitted through this gate")
        record.status = status
        record.reviewer = reviewer
        record.notes = notes
        record.reviewed_at = datetime.now(timezone.utc)
