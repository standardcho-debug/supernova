import json

import pytest

from sns_marketing_agent.brief_selector import BriefSelector, score_candidates, top_candidates
from sns_marketing_agent.cofounder_client import ReadOnlyCofounderClient
from sns_marketing_agent.cofounder_fixture_transport import FixtureMCPCaller
from sns_marketing_agent.context_engine import ContextEngine
from sns_marketing_agent.strategy_models import MonthlyStrategy, Pillar


class FakeLLMClient:
    def __init__(self, response: str):
        self._response = response

    def complete(self, prompt: str) -> str:
        return self._response


def real_snapshot():
    client = ReadOnlyCofounderClient(FixtureMCPCaller(client_slug="supernova-platform"))
    return ContextEngine(client).build_snapshot("supernova-platform")


def make_strategy(snapshot):
    return MonthlyStrategy(
        client_slug=snapshot.client_slug,
        month="2026-09",
        goal="이번 달은 요청 접수 속도를 보여준다",
        pillars=[Pillar(name="증거형", ratio=1.0)],
        calendar_per_week=3,
        excluded_claims=[g.label for g in snapshot.gaps if g.reason == "unmeasured"][:2],
    )


def valid_brief_response():
    return json.dumps(
        {
            "topic": "요청이 도착하면 바로 분류된다",
            "angle": "속도를 체감 지표로 보여준다",
            "pillar": "증거형",
            "target_persona": "이미 코파운더를 쓰는 운영팀",
            "hook_125": "요청 하나가 도착하는 순간, 무슨 일이 벌어질까요?",
            "key_messages": ["제보 즉시 분류", "코드가 판정"],
            "cta": "지금 코파운더에 요청을 남겨보세요",
        },
        ensure_ascii=False,
    )


def test_score_candidates_covers_every_recent_change():
    snapshot = real_snapshot()
    scored = score_candidates(snapshot)
    assert len(scored) == len(snapshot.recent_changes)


def test_candidates_with_no_evidence_are_disqualified():
    snapshot = real_snapshot()
    scored = score_candidates(snapshot)
    disqualified = [c for c in scored if c.disqualified]
    qualified = [c for c in scored if not c.disqualified]
    assert disqualified  # real fixture has some changes with no promise-backed evidence
    assert qualified
    for c in disqualified:
        assert c.evidence_excerpt is None
    for c in qualified:
        assert c.evidence_excerpt is not None


def test_top_candidates_excludes_disqualified_even_if_high_scoring():
    snapshot = real_snapshot()
    scored = score_candidates(snapshot)
    top = top_candidates(scored, n=len(scored))  # take everyone eligible
    assert all(not c.disqualified for c in top)


def test_top_candidates_respects_n():
    snapshot = real_snapshot()
    scored = score_candidates(snapshot)
    top3 = top_candidates(scored, n=3)
    assert len(top3) <= 3
    # sorted descending
    assert all(top3[i].total_score >= top3[i + 1].total_score for i in range(len(top3) - 1))


def test_customer_facing_duplicate_topic_scores_lower_than_fresh_one():
    snapshot = real_snapshot()
    facing_key = next(iter({c.node_key for c in score_candidates(snapshot) if not c.disqualified}))

    fresh = score_candidates(snapshot, recent_topics=frozenset())
    stale = score_candidates(snapshot, recent_topics=frozenset({facing_key}))

    fresh_score = next(c for c in fresh if c.node_key == facing_key).total_score
    stale_score = next(c for c in stale if c.node_key == facing_key).total_score
    assert stale_score < fresh_score


def test_expand_to_brief_requires_evidence():
    snapshot = real_snapshot()
    strategy = make_strategy(snapshot)
    scored = score_candidates(snapshot)
    disqualified = next(c for c in scored if c.disqualified)

    selector = BriefSelector(FakeLLMClient(valid_brief_response()))
    with pytest.raises(ValueError):
        selector.expand_to_brief(disqualified, strategy)


def test_expand_to_brief_builds_valid_brief_with_real_evidence():
    snapshot = real_snapshot()
    strategy = make_strategy(snapshot)
    scored = score_candidates(snapshot)
    qualified = next(c for c in scored if not c.disqualified)

    selector = BriefSelector(FakeLLMClient(valid_brief_response()))
    brief = selector.expand_to_brief(qualified, strategy)

    assert brief.channel == "instagram"
    assert len(brief.evidence) == 1
    assert brief.evidence[0].excerpt == qualified.evidence_excerpt
    assert brief.excluded_claims == strategy.excluded_claims


def test_select_and_brief_end_to_end():
    snapshot = real_snapshot()
    strategy = make_strategy(snapshot)
    selector = BriefSelector(FakeLLMClient(valid_brief_response()))

    briefs = selector.select_and_brief(snapshot, strategy, n=3)

    assert 1 <= len(briefs) <= 3
    for brief in briefs:
        assert brief.evidence
        assert len(brief.key_messages) <= 3


def test_avoid_patterns_are_injected_into_expand_prompt():
    snapshot = real_snapshot()
    strategy = make_strategy(snapshot)
    scored = score_candidates(snapshot)
    qualified = next(c for c in scored if not c.disqualified)

    class RecordingLLM:
        def __init__(self, response):
            self._response = response
            self.last_prompt = None

        def complete(self, prompt):
            self.last_prompt = prompt
            return self._response

    llm = RecordingLLM(valid_brief_response())
    BriefSelector(llm).expand_to_brief(qualified, strategy, avoid_patterns=["훅약함"])
    assert "훅약함" in llm.last_prompt


def test_non_json_brief_response_raises_value_error():
    snapshot = real_snapshot()
    strategy = make_strategy(snapshot)
    scored = score_candidates(snapshot)
    qualified = next(c for c in scored if not c.disqualified)

    selector = BriefSelector(FakeLLMClient("이건 JSON이 아닙니다"))
    with pytest.raises(ValueError):
        selector.expand_to_brief(qualified, strategy)
