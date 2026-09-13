from dataclasses import dataclass
from pathlib import Path

import pytest

from sns_marketing_agent.history_collector import (
    CofounderHistorySource,
    StaticHistorySource,
)

FIXTURE = (
    Path(__file__).parent.parent
    / "sns_marketing_agent"
    / "fixtures"
    / "sample_client_history.json"
)


@dataclass
class FakeDoc:
    kind: str
    title: str
    body: str


class FakeFetcher:
    def __init__(self, docs):
        self._docs = docs

    def fetch(self, client_id):
        return self._docs


def test_static_history_source_loads_fixture():
    source = StaticHistorySource(FIXTURE)
    profile = source.get_client_profile("demo-bakery")
    assert profile.client_id == "demo-bakery"
    assert profile.business_plan_highlights
    assert profile.recent_complaints


def test_static_history_source_rejects_mismatched_client_id():
    source = StaticHistorySource(FIXTURE)
    with pytest.raises(ValueError):
        source.get_client_profile("some-other-client")


def test_cofounder_history_source_groups_docs_by_kind():
    docs = [
        FakeDoc(kind="business-plan", title="사업계획 초안", body="핵심 내용"),
        FakeDoc(kind="feature-request", title="신메뉴 알림 기능 요청", body="..."),
        FakeDoc(kind="feature-request", title="bug: 재고 표시 오류", body="..."),
    ]
    source = CofounderHistorySource(FakeFetcher(docs), brand_tone="담백하게")
    profile = source.get_client_profile("client-1")

    assert profile.name == "사업계획 초안"
    assert profile.business_summary == "핵심 내용"
    assert profile.recent_requests == ["신메뉴 알림 기능 요청", "bug: 재고 표시 오류"]
    assert profile.recent_complaints == ["bug: 재고 표시 오류"]
    assert profile.brand_tone == "담백하게"


def test_cofounder_history_source_handles_no_business_plan():
    source = CofounderHistorySource(FakeFetcher([]))
    profile = source.get_client_profile("client-2")
    assert profile.name == "client-2"
    assert profile.business_summary == ""
