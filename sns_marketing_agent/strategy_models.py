"""F2/F3 data types — PRD v1.0 §5.2.

No profit-equation input anywhere here (C2): a MonthlyStrategy's goal and
pillars come from the context snapshot's cells/changes/promises, never from
a number a user types into a revenue formula.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from sns_marketing_agent.context_models import SourceRef


@dataclass
class Pillar:
    name: str  # e.g. "증거형" / "교육형" / "공감형" — PRD's example split, not fixed
    ratio: float  # 0..1; a strategy's pillars should sum to ~1


@dataclass
class MonthlyStrategy:
    client_slug: str
    month: str  # "2026-09"
    goal: str
    pillars: list[Pillar]
    calendar_per_week: int  # PRD §5.2 default 3, marked ⚠️미정 — not a settled product decision
    source_changes: list[SourceRef] = field(default_factory=list)
    source_promises: list[SourceRef] = field(default_factory=list)
    excluded_claims: list[str] = field(default_factory=list)  # gap labels — "아직 말하면 안 되는 것"
    status: str = "draft"  # draft | confirmed — STan's edit confirms it (PRD §5.2)
    edited_by: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ScoredCandidate:
    """One system-map change scored against §5.2's rubric, before it becomes
    a Brief. `disqualified` mirrors "근거 원문 없으면 후보 탈락" — a
    disqualified candidate is never promoted, regardless of its raw score."""

    node_key: str
    label: str
    total_score: int
    score_breakdown: dict[str, int]
    disqualified: bool
    evidence_excerpt: str | None
    source: SourceRef


@dataclass
class EvidenceItem:
    source_tool: str
    ref: str
    excerpt: str


@dataclass
class Brief:
    client_slug: str
    channel: str
    topic: str
    angle: str
    pillar: str
    target_persona: str
    hook_125: str
    key_messages: list[str]  # <=3
    evidence: list[EvidenceItem]  # >=1, enforced at construction
    cta: str
    excluded_claims: list[str] = field(default_factory=list)
    score: int = 0
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not self.evidence:
            raise ValueError("Brief requires at least one evidence item (PRD §5.2 schema)")
        if len(self.key_messages) > 3:
            raise ValueError("Brief allows at most 3 key_messages (PRD §5.2 schema)")
