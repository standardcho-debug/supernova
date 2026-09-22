"""F4 CreativeStudio data types — PRD v1.0 §5.3."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4


@dataclass
class CopyVariant:
    """One of a brief's 3 copy options — text only, before any rendering."""

    variant: int  # 1..3
    hook: str  # <=125 chars
    caption: str  # full caption: hook + body + cta
    hashtags: list[str]  # 3-5


@dataclass
class Slide:
    order: int
    text: str
    image_path: str  # "" if not actually rendered (offline/test runs)


@dataclass
class ResizedAsset:
    aspect: str  # "4:5" | "1:1" | "9:16"
    slides: list[str] = field(default_factory=list)  # file paths, in slide order


@dataclass
class Creative:
    brief_id: str
    variant: int
    caption: str
    hashtags: list[str]
    slides: list[Slide]
    resized: list[ResizedAsset]
    utm_url: str
    mask_status: str  # "clean" | "flagged" — F4's own gate; C4
    mask_hits: list[str] = field(default_factory=list)  # what was detected, for the review screen
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not (1 <= self.variant <= 3):
            raise ValueError("Creative.variant must be 1-3 (PRD §5.3: 브리프당 3안)")
        if not (5 <= len(self.slides) <= 7):
            raise ValueError(
                f"Creative must have 5-7 slides (PRD §5.3), got {len(self.slides)}"
            )
