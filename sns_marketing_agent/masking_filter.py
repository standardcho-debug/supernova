"""C4 마스킹 필터 — PRD v1.0 §5.3.

"콘텐츠에 다른 고객사명·프로젝트명·금액이 노출되면 안 된다." This scans
plain text (captions, slide copy) for two things: any OTHER real client's
name/slug (never the client this creative is actually for), and Korean
currency-amount patterns (원/만원 등) — pricing specifics that shouldn't
leak into marketing copy regardless of whose they are.

OCR-based scanning of rendered slide images (the PRD's other half of C4 —
"스크린샷 OCR 결과에서 탐지") is not implemented here: this module only
covers text known before rendering. Since CreativeStudio's slide images
are rendered FROM the same caption/slide text this filter already scans
(image_generator.py-style HTML→PNG, not free-generation), catching it at
the text stage catches it before it ever reaches an image — OCR would be
a second, redundant check on the same content, not a first one. Flagged
here so it isn't silently assumed done.
"""
from __future__ import annotations

import re

_AMOUNT_PATTERN = re.compile(r"\d[\d,]*\s*(만원|원|만달러|달러)")


def extract_protected_terms(clients_resp: dict, exclude_slug: str) -> set[str]:
    """Every OTHER client's name and slug — never this creative's own client,
    since a client's own name in its own content isn't a leak."""
    terms = set()
    for client in clients_resp.get("results", []):
        if client["slug"] == exclude_slug:
            continue
        name = client.get("name", "").strip()
        slug = client.get("slug", "").strip()
        if name:
            terms.add(name)
        if slug:
            terms.add(slug)
    return terms


class MaskingFilter:
    def __init__(self, protected_terms: set[str]):
        # Longest-first so a match on "co·founder Inc" doesn't get pre-empted
        # by a shorter substring match first.
        self._terms = sorted((t for t in protected_terms if t), key=len, reverse=True)

    def scan(self, text: str) -> list[str]:
        hits = []
        for term in self._terms:
            if term in text:
                hits.append(term)
        for match in _AMOUNT_PATTERN.finditer(text):
            hits.append(match.group(0))
        return hits

    def mask(self, text: str) -> tuple[str, list[str]]:
        hits = self.scan(text)
        masked = text
        for term in self._terms:
            if term in masked:
                masked = masked.replace(term, "█" * len(term))
        masked = _AMOUNT_PATTERN.sub(lambda m: "█" * len(m.group(0)), masked)
        return masked, hits

    def status(self, *texts: str) -> tuple[str, list[str]]:
        """Combined mask_status ("clean"/"flagged") + all hits across every
        text a Creative carries (caption + every slide)."""
        all_hits: list[str] = []
        for text in texts:
            all_hits.extend(self.scan(text))
        status = "flagged" if all_hits else "clean"
        return status, all_hits
