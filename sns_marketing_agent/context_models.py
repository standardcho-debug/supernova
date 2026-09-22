"""F1 Context Engine data types — PRD v1.0 §5.1.

Every extracted item carries a `SourceRef` (tool + node key or document id).
That's not decoration: PRD §5.1's acceptance criterion is "스냅샷의 모든
항목이 원천(tool, key/doc id)을 보유" — a snapshot item with no source is a
bug, not an edge case, so the field is required (not Optional) on each type.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class SourceRef:
    tool: str
    ref: str  # node key, or document id/path


@dataclass
class ContextCell:
    key: str
    label: str
    lane: str
    guarantee: str
    per_month: float | None  # None = unmeasured, not zero (system_map_weight semantics)
    open_to_client: bool  # false -> internal_only (C5), never used as brief evidence
    source: SourceRef


@dataclass
class LaneSummary:
    lane: str
    cell_count: int
    monthly_frequency: float | None  # sum of per_month across the lane's measured cells; None if none measured


@dataclass
class ChangeEntry:
    node_key: str
    label: str | None
    at: datetime
    kind: str  # "drawn" | "changed"
    summary: str
    source: SourceRef


@dataclass
class Promise:
    """One rule at a cell, tagged by its `open_to_client` flag.

    Used for both `promises` (open_to_client=true — candidate evidence for
    brand/trust messaging) and `internal_only` (open_to_client=false — C5:
    never usable as brief evidence). Same shape both ways; a rule is one or
    the other by construction, so the two lists never overlap — unlike
    `customer_facing_cells`, which is a *cell*-level, lane-based concept
    that can legitimately include a cell with an internal_only rule (e.g.
    "고객 직접 등록" is lane=고객·외부 even though its own rule body cites
    internal source file paths, not customer-safe copy)."""

    node_key: str
    rule_title: str
    source: SourceRef


@dataclass
class VoiceEntry:
    excerpt: str
    source: SourceRef


@dataclass
class Gap:
    """A cell the context engine could not ground: unmeasured frequency, or
    a node with no rule at all. Surfaced so strategy/brief generation can
    exclude it rather than silently guessing (PRD §5.2 excluded_claims)."""

    node_key: str
    label: str
    reason: str  # "unmeasured" | "no_rule"
    source: SourceRef


@dataclass
class ContextSnapshot:
    client_slug: str
    lanes: list[LaneSummary] = field(default_factory=list)
    customer_facing_cells: list[ContextCell] = field(default_factory=list)
    recent_changes: list[ChangeEntry] = field(default_factory=list)
    promises: list[Promise] = field(default_factory=list)
    voice_of_customer: list[VoiceEntry] = field(default_factory=list)
    internal_only: list[Promise] = field(default_factory=list)
    gaps: list[Gap] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
