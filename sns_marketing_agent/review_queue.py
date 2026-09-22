"""F5 승인함 — PRD v1.0 §5.4, §5.2 반려 사유 환류.

Same boundary as the old prototype's ApprovalGate: there is no publish()
here either. A ReviewQueue only ever gets a Creative to `approved` or
`rejected` — turning that into an actual Instagram post is F6 (P2, not
built).

Rejecting requires at least one reason code (PRD §5.4: "반려 시 코드 1개
이상 필수") — enforced here, not left to the caller to remember.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol

from sns_marketing_agent.review_models import CreativeStatus, ReasonCode, ReviewRecord, RubricScore


class ReviewStore(Protocol):
    def save(self, record: ReviewRecord) -> None: ...
    def get(self, record_id: str) -> ReviewRecord: ...
    def pending(self, client_slug: str | None = None) -> list[ReviewRecord]: ...
    def reviewed(self, client_slug: str | None = None) -> list[ReviewRecord]: ...
    def all(self, client_slug: str | None = None) -> list[ReviewRecord]: ...


class InMemoryReviewStore:
    def __init__(self) -> None:
        self._records: dict[str, ReviewRecord] = {}

    def save(self, record: ReviewRecord) -> None:
        self._records[record.id] = record

    def get(self, record_id: str) -> ReviewRecord:
        return self._records[record_id]

    def pending(self, client_slug: str | None = None) -> list[ReviewRecord]:
        return self._filter(CreativeStatus.PENDING_REVIEW, client_slug)

    def reviewed(self, client_slug: str | None = None) -> list[ReviewRecord]:
        return [
            r
            for r in self._records.values()
            if r.status != CreativeStatus.PENDING_REVIEW
            and (client_slug is None or r.client_slug == client_slug)
        ]

    def all(self, client_slug: str | None = None) -> list[ReviewRecord]:
        records = list(self._records.values())
        if client_slug is not None:
            records = [r for r in records if r.client_slug == client_slug]
        return records

    def _filter(self, status: CreativeStatus, client_slug: str | None) -> list[ReviewRecord]:
        return [
            r
            for r in self._records.values()
            if r.status == status and (client_slug is None or r.client_slug == client_slug)
        ]


class ReviewQueue:
    def __init__(self, store: ReviewStore | None = None):
        self._store = store if store is not None else InMemoryReviewStore()

    def submit(self, client_slug: str, creative_id: str, brief_id: str, rubric: RubricScore) -> ReviewRecord:
        record = ReviewRecord(
            client_slug=client_slug, creative_id=creative_id, brief_id=brief_id, rubric=rubric
        )
        self._store.save(record)
        return record

    def approve(self, record_id: str, reviewer: str) -> ReviewRecord:
        record = self._store.get(record_id)
        record.status = CreativeStatus.APPROVED
        record.reviewer = reviewer
        record.reviewed_at = datetime.now(timezone.utc)
        self._store.save(record)
        return record

    def reject(
        self, record_id: str, reviewer: str, reason_codes: list[ReasonCode], note: str = ""
    ) -> ReviewRecord:
        if not reason_codes:
            raise ValueError("반려 시 반려 사유 코드가 1개 이상 필요합니다 (PRD §5.4)")
        record = self._store.get(record_id)
        record.status = CreativeStatus.REJECTED
        record.reviewer = reviewer
        record.reason_codes = list(reason_codes)
        record.note = note
        record.reviewed_at = datetime.now(timezone.utc)
        self._store.save(record)
        return record

    def pending(self, client_slug: str | None = None) -> list[ReviewRecord]:
        return self._store.pending(client_slug)

    def reviewed(self, client_slug: str | None = None) -> list[ReviewRecord]:
        return self._store.reviewed(client_slug)

    def recent_rejection_patterns(
        self, client_slug: str, days: int = 30, top_n: int = 3
    ) -> list[ReasonCode]:
        """최근 N일 반려 사유 상위 top_n개 — F3·F4 프롬프트에 '피해야 할 패턴'으로
        주입하기 위한 것 (PRD §5.4). Ties broken by ReasonCode's declaration
        order (R1 before R2, ...) for a deterministic result."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        counts: dict[ReasonCode, int] = {}
        for record in self._store.reviewed(client_slug):
            if record.status != CreativeStatus.REJECTED:
                continue
            if record.reviewed_at is None or record.reviewed_at < cutoff:
                continue
            for code in record.reason_codes:
                counts[code] = counts.get(code, 0) + 1

        ordered = sorted(counts.items(), key=lambda kv: (-kv[1], list(ReasonCode).index(kv[0])))
        return [code for code, _ in ordered[:top_n]]
