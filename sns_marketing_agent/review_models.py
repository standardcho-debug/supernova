"""F5 승인함 데이터 타입 — PRD v1.0 §5.4."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4


class CreativeStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    # P2 (out of scope here): scheduled, published, boosted


class ReasonCode(str, Enum):
    R1 = "R1"  # 근거부족
    R2 = "R2"  # 사실오류
    R3 = "R3"  # 톤불일치
    R4 = "R4"  # 훅약함
    R5 = "R5"  # 디자인
    R6 = "R6"  # 마스킹
    R7 = "R7"  # 타이밍
    R9 = "R9"  # 기타(자유기술)


REASON_LABELS: dict[ReasonCode, str] = {
    ReasonCode.R1: "근거부족",
    ReasonCode.R2: "사실오류",
    ReasonCode.R3: "톤불일치",
    ReasonCode.R4: "훅약함",
    ReasonCode.R5: "디자인",
    ReasonCode.R6: "마스킹",
    ReasonCode.R7: "타이밍",
    ReasonCode.R9: "기타",
}


@dataclass
class RubricScore:
    evidence_fit: int  # 0-25
    factual_accuracy: int  # 0-20
    persona_resonance: int  # 0-20
    hook_strength: int  # 0-15
    format_compliance: int  # 0-10
    masking: int  # 0-10 (0 whenever the creative is mask_status=flagged — never overridden)
    total: int


@dataclass
class ReviewRecord:
    client_slug: str
    creative_id: str
    brief_id: str
    rubric: RubricScore
    status: CreativeStatus = CreativeStatus.PENDING_REVIEW
    reviewer: str | None = None
    reason_codes: list[ReasonCode] = field(default_factory=list)
    note: str = ""
    reviewed_at: datetime | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
