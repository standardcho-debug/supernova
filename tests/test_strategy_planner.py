import json

import pytest

from sns_marketing_agent.cofounder_client import ReadOnlyCofounderClient
from sns_marketing_agent.cofounder_fixture_transport import FixtureMCPCaller
from sns_marketing_agent.context_engine import ContextEngine
from sns_marketing_agent.strategy_planner import StrategyPlanner


class FakeLLMClient:
    def __init__(self, response: str):
        self._response = response
        self.last_prompt: str | None = None

    def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._response


def real_snapshot():
    client = ReadOnlyCofounderClient(FixtureMCPCaller(client_slug="supernova-platform"))
    return ContextEngine(client).build_snapshot("supernova-platform")


def valid_llm_response():
    return json.dumps(
        {
            "goal": "이번 달은 요청 접수부터 완료까지의 속도를 보여준다",
            "pillars": [
                {"name": "증거형", "ratio": 0.5},
                {"name": "교육형", "ratio": 0.3},
                {"name": "공감형", "ratio": 0.2},
            ],
        },
        ensure_ascii=False,
    )


def test_build_strategy_parses_llm_output():
    planner = StrategyPlanner(FakeLLMClient(valid_llm_response()))
    strategy = planner.build_strategy(real_snapshot(), month="2026-09")

    assert strategy.client_slug == "supernova-platform"
    assert strategy.goal == "이번 달은 요청 접수부터 완료까지의 속도를 보여준다"
    assert len(strategy.pillars) == 3
    assert abs(sum(p.ratio for p in strategy.pillars) - 1.0) < 1e-6
    assert strategy.status == "draft"


def test_strategy_uses_default_calendar_unless_overridden():
    planner = StrategyPlanner(FakeLLMClient(valid_llm_response()))
    strategy = planner.build_strategy(real_snapshot(), month="2026-09")
    assert strategy.calendar_per_week == 3

    strategy2 = planner.build_strategy(real_snapshot(), month="2026-09", calendar_per_week=5)
    assert strategy2.calendar_per_week == 5


def test_excluded_claims_come_from_unmeasured_gaps_not_fabricated():
    snapshot = real_snapshot()
    planner = StrategyPlanner(FakeLLMClient(valid_llm_response()))
    strategy = planner.build_strategy(snapshot, month="2026-09")

    unmeasured_labels = {g.label for g in snapshot.gaps if g.reason == "unmeasured"}
    assert set(strategy.excluded_claims) <= unmeasured_labels
    assert len(strategy.excluded_claims) > 0  # the real fixture has unmeasured cells


def test_prompt_never_fabricates_facts_not_in_the_snapshot():
    snapshot = real_snapshot()
    llm = FakeLLMClient(valid_llm_response())
    StrategyPlanner(llm).build_strategy(snapshot, month="2026-09")

    # every promise fed into the prompt must be a real rule title from the snapshot
    real_titles = {p.rule_title for p in snapshot.promises}
    for line in llm.last_prompt.splitlines():
        if line.startswith("- ") and line[2:] in real_titles:
            assert line[2:] in real_titles


def test_non_json_llm_output_raises_value_error():
    planner = StrategyPlanner(FakeLLMClient("이건 JSON이 아닙니다"))
    with pytest.raises(ValueError):
        planner.build_strategy(real_snapshot(), month="2026-09")


def test_source_changes_only_includes_customer_facing_changes():
    snapshot = real_snapshot()
    planner = StrategyPlanner(FakeLLMClient(valid_llm_response()))
    strategy = planner.build_strategy(snapshot, month="2026-09")

    facing_keys = {c.key for c in snapshot.customer_facing_cells}
    for source in strategy.source_changes:
        assert source.ref in facing_keys
