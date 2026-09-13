import json

import pytest

from sns_marketing_agent.brief_generator import BriefGenerator
from sns_marketing_agent.models import Channel, ClientProfile


class FakeLLMClient:
    def __init__(self, response: str):
        self._response = response
        self.last_prompt = None

    def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._response


def make_profile():
    return ClientProfile(
        client_id="client-1",
        name="새벽빵집",
        business_summary="당일 발효 베이커리",
        business_plan_highlights=["당일 발효가 핵심 차별점"],
        recent_requests=["재고 소진 임박 상품 자동 노출 요청"],
        recent_complaints=["주말 조기 품절 사전 안내 부족 불만"],
        revenue_signals=["월요일 매출이 40% 낮음"],
        brand_tone="담백하게",
    )


def test_generate_parses_valid_json_into_briefs():
    response = json.dumps(
        [
            {
                "topic": "월요일 매출 낮은 이유",
                "angle": "월요일 한정 메뉴 소개",
                "source_evidence": ["월요일 매출이 40% 낮음"],
            }
        ],
        ensure_ascii=False,
    )
    generator = BriefGenerator(FakeLLMClient(response))
    briefs = generator.generate(make_profile(), Channel.NAVER_BLOG, n=1)

    assert len(briefs) == 1
    brief = briefs[0]
    assert brief.client_id == "client-1"
    assert brief.channel == Channel.NAVER_BLOG
    assert brief.topic == "월요일 매출 낮은 이유"
    assert brief.source_evidence == ["월요일 매출이 40% 낮음"]


def test_prompt_includes_history_and_channel_guidance():
    llm = FakeLLMClient("[]")
    generator = BriefGenerator(llm)
    generator.generate(make_profile(), Channel.INSTAGRAM, n=2)

    assert "당일 발효가 핵심 차별점" in llm.last_prompt
    assert Channel.INSTAGRAM.value in llm.last_prompt


def test_non_json_output_raises_value_error():
    generator = BriefGenerator(FakeLLMClient("이건 JSON이 아닙니다"))
    with pytest.raises(ValueError):
        generator.generate(make_profile(), Channel.YOUTUBE, n=1)
