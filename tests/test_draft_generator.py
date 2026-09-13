import json

import pytest

from sns_marketing_agent.draft_generator import DraftGenerator
from sns_marketing_agent.models import Channel, ClientProfile, ContentBrief


class FakeLLMClient:
    def __init__(self, response: str):
        self._response = response

    def complete(self, prompt: str) -> str:
        return self._response


def make_profile():
    return ClientProfile(client_id="client-1", name="새벽빵집", business_summary="")


def make_brief(channel=Channel.NAVER_BLOG):
    return ContentBrief(
        client_id="client-1",
        channel=channel,
        topic="월요일 매출 낮은 이유",
        angle="월요일 한정 메뉴 소개",
        source_evidence=["월요일 매출이 40% 낮음"],
    )


def test_generate_parses_valid_json_into_draft():
    response = json.dumps(
        {
            "title": "월요일에만 만나는 메뉴",
            "body": "본문 내용",
            "hashtags": ["동네빵집", "당일발효"],
        },
        ensure_ascii=False,
    )
    generator = DraftGenerator(FakeLLMClient(response))
    draft = generator.generate(make_profile(), make_brief())

    assert draft.title == "월요일에만 만나는 메뉴"
    assert draft.hashtags == ["동네빵집", "당일발효"]
    assert draft.thumbnail_text is None


def test_youtube_draft_parses_storyboard_and_derives_body():
    response = json.dumps(
        {
            "title": "월요일 한정 메뉴",
            "thumbnail_text": "월요일에만 파는 이유",
            "hashtags": ["동네빵집"],
            "storyboard": [
                {
                    "on_screen_text": "월요일에만?",
                    "narration": "저희는 월요일에만 이 메뉴를 굽습니다.",
                    "duration_seconds": 5,
                },
                {
                    "on_screen_text": "이유는 발효 시간",
                    "narration": "주말 동안 천천히 발효시키기 때문이에요.",
                    "duration_seconds": 8,
                },
            ],
        },
        ensure_ascii=False,
    )
    generator = DraftGenerator(FakeLLMClient(response))
    draft = generator.generate(make_profile(), make_brief(Channel.YOUTUBE))

    assert draft.thumbnail_text == "월요일에만 파는 이유"
    assert len(draft.storyboard) == 2
    assert draft.storyboard[0].order == 0
    assert draft.storyboard[1].duration_seconds == 8
    assert "천천히 발효" in draft.body


def test_non_youtube_draft_has_empty_storyboard():
    response = json.dumps(
        {"title": "t", "body": "b", "hashtags": []}, ensure_ascii=False
    )
    generator = DraftGenerator(FakeLLMClient(response))
    draft = generator.generate(make_profile(), make_brief(Channel.NAVER_BLOG))

    assert draft.storyboard == []


def test_non_json_output_raises_value_error():
    generator = DraftGenerator(FakeLLMClient("이건 JSON이 아닙니다"))
    with pytest.raises(ValueError):
        generator.generate(make_profile(), make_brief())
