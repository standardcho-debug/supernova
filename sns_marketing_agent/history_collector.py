"""Stage 1: turn a client's raw Cofounder history into a ClientProfile.

The pipeline never talks to Cofounder directly. It depends on a small
`DocumentsFetcher` protocol instead, so the real integration (Cofounder's
`search_documents` / `list_documents`) can be wired in without this module
knowing about MCP, auth, or transport.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Protocol

from .models import ClientProfile


class RawDocument(Protocol):
    kind: str  # e.g. "business-plan", "feature-request", "decision"
    title: str
    body: str


class DocumentsFetcher(Protocol):
    """Adapter boundary: implement this against the real Cofounder client."""

    def fetch(self, client_id: str) -> list[RawDocument]:
        ...


class HistorySource(Protocol):
    def get_client_profile(self, client_id: str) -> ClientProfile:
        ...


class CofounderHistorySource:
    """Builds a ClientProfile from documents pulled via a DocumentsFetcher.

    Grouping by `kind` here is a first pass, not a real classifier: it
    covers the kinds Cofounder already uses (business-plan, feature-request,
    decision). Complaint/revenue signals will need a proper tagger once the
    document schema for those exists.
    """

    def __init__(self, fetcher: DocumentsFetcher, brand_tone: str = ""):
        self._fetcher = fetcher
        self._brand_tone = brand_tone

    def get_client_profile(self, client_id: str) -> ClientProfile:
        docs = self._fetcher.fetch(client_id)

        plan_docs = [d for d in docs if d.kind == "business-plan"]
        request_docs = [d for d in docs if d.kind == "feature-request"]
        complaint_docs = [
            d for d in docs if d.kind == "feature-request" and "bug" in d.title.lower()
        ]

        name = plan_docs[0].title if plan_docs else client_id

        return ClientProfile(
            client_id=client_id,
            name=name,
            business_summary=plan_docs[0].body if plan_docs else "",
            business_plan_highlights=[d.title for d in plan_docs],
            recent_requests=[d.title for d in request_docs],
            recent_complaints=[d.title for d in complaint_docs],
            revenue_signals=[],
            brand_tone=self._brand_tone,
        )


class StaticHistorySource:
    """Offline/demo source: reads a ClientProfile from a JSON fixture file."""

    def __init__(self, fixture_path: Path):
        self._fixture_path = fixture_path

    def get_client_profile(self, client_id: str) -> ClientProfile:
        data = json.loads(self._fixture_path.read_text(encoding="utf-8"))
        if data["client_id"] != client_id:
            raise ValueError(
                f"fixture {self._fixture_path} holds client_id={data['client_id']!r}, "
                f"requested {client_id!r}"
            )
        return ClientProfile(**data)
