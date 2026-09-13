"""Shared data types for the SNS marketing pipeline (stages 1-4)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class Channel(str, Enum):
    NAVER_BLOG = "naver_blog"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"


class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ClientProfile:
    """Normalized view of a client's history, sourced from Cofounder documents."""

    client_id: str
    name: str
    business_summary: str
    business_plan_highlights: list[str] = field(default_factory=list)
    recent_requests: list[str] = field(default_factory=list)
    recent_complaints: list[str] = field(default_factory=list)
    revenue_signals: list[str] = field(default_factory=list)
    brand_tone: str = ""


@dataclass
class ContentBrief:
    client_id: str
    channel: Channel
    topic: str
    angle: str
    source_evidence: list[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ImageAsset:
    """A rendered visual for the draft (card, cover, thumbnail).

    `file_path` is "" when the asset was only planned, not actually
    rendered (e.g. by NullImageGenerator in tests/offline demos).
    """

    channel: Channel
    file_path: str
    alt_text: str


@dataclass
class StoryboardScene:
    """One shot of a short-form video script — the unit stage 3 stops at.

    Turning this into an actual video file is out of scope: see
    image_generator.py's module docstring and README.md.
    """

    order: int
    on_screen_text: str
    narration: str
    duration_seconds: int


@dataclass
class ContentDraft:
    brief: ContentBrief
    title: str
    body: str
    hashtags: list[str] = field(default_factory=list)
    thumbnail_text: str | None = None
    images: list[ImageAsset] = field(default_factory=list)
    storyboard: list[StoryboardScene] = field(default_factory=list)


@dataclass
class ApprovalRecord:
    draft: ContentDraft
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewer: str | None = None
    reviewed_at: datetime | None = None
    notes: str = ""
