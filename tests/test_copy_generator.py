import json

import pytest

from sns_marketing_agent.copy_generator import CopyGenerator
from sns_marketing_agent.strategy_models import Brief, EvidenceItem


class FakeLLMClient:
    def __init__(self, response: str):
        self._response = response
        self.last_prompt: str | None = None

    def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._response


def make_brief():
    return Brief(
        client_slug="supernova-platform",
        channel="instagram",
        topic="요청이 도착하면 바로 분류된다",
        angle="속도를 체감 지표로 보여준다",
        pillar="증거형",
        target_persona="이미 코파운더를 쓰는 운영팀",
        hook_125="요청 하나가 도착하는 순간, 무슨 일이 벌어질까요?",
        key_messages=["제보 즉시 분류", "코드가 판정"],
        evidence=[EvidenceItem(source_tool="system_map_rules", ref="triage#rule71", excerpt="처분을 고른다")],
        cta="지금 요청을 남겨보세요",
        excluded_claims=["칸 단위 판정"],
    )


def three_variants_response():
    return json.dumps(
        [
            {"hook": "훅 1", "caption": "캡션 1", "hashtags": ["코파운더", "자동화", "운영"]},
            {"hook": "훅 2", "caption": "캡션 2", "hashtags": ["코파운더", "속도"]},
            {"hook": "훅 3", "caption": "캡션 3", "hashtags": ["코파운더"]},
        ],
        ensure_ascii=False,
    )


def test_generates_three_variants():
    gen = CopyGenerator(FakeLLMClient(three_variants_response()))
    variants = gen.generate_variants(make_brief())
    assert len(variants) == 3
    assert [v.variant for v in variants] == [1, 2, 3]


def test_prompt_includes_evidence_and_excluded_claims():
    llm = FakeLLMClient(three_variants_response())
    CopyGenerator(llm).generate_variants(make_brief())
    assert "처분을 고른다" in llm.last_prompt
    assert "칸 단위 판정" in llm.last_prompt


def test_hashtags_capped_at_five():
    response = json.dumps(
        [{"hook": "h", "caption": "c", "hashtags": [f"tag{i}" for i in range(10)]}],
        ensure_ascii=False,
    )
    variants = CopyGenerator(FakeLLMClient(response)).generate_variants(make_brief())
    assert len(variants[0].hashtags) == 5


def test_non_json_output_raises_value_error():
    gen = CopyGenerator(FakeLLMClient("이건 JSON이 아닙니다"))
    with pytest.raises(ValueError):
        gen.generate_variants(make_brief())
