import json

from sns_marketing_agent.carousel_renderer import NullCarouselRenderer
from sns_marketing_agent.creative_studio import CreativeStudio
from sns_marketing_agent.masking_filter import MaskingFilter
from sns_marketing_agent.strategy_models import Brief, EvidenceItem


class FakeLLMClient:
    def __init__(self, response: str):
        self._response = response

    def complete(self, prompt: str) -> str:
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
    )


def three_variants_response():
    return json.dumps(
        [
            {"hook": "훅 1", "caption": "캡션 1", "hashtags": ["코파운더", "자동화"]},
            {"hook": "훅 2", "caption": "캡션 2", "hashtags": ["코파운더"]},
            {"hook": "훅 3", "caption": "캡션 3", "hashtags": ["코파운더"]},
        ],
        ensure_ascii=False,
    )


def studio(protected_terms=frozenset()):
    return CreativeStudio(
        llm=FakeLLMClient(three_variants_response()),
        renderer=NullCarouselRenderer(),
        masking_filter=MaskingFilter(set(protected_terms)),
        instagram_base_url="https://dodamfood.kr",
    )


def test_build_creatives_produces_three_variants():
    creatives = studio().build_creatives(make_brief(), campaign_month="202609")
    assert len(creatives) == 3
    assert {c.variant for c in creatives} == {1, 2, 3}


def test_each_creative_has_utm_url_with_its_own_id():
    creatives = studio().build_creatives(make_brief(), campaign_month="202609")
    for c in creatives:
        assert f"utm_content={c.id}" in c.utm_url
        assert "utm_campaign=202609_" in c.utm_url


def test_each_creative_has_valid_slide_count_and_resized_assets():
    creatives = studio().build_creatives(make_brief(), campaign_month="202609")
    for c in creatives:
        assert 5 <= len(c.slides) <= 7
        assert {r.aspect for r in c.resized} == {"1:1", "9:16"}
        for r in c.resized:
            assert len(r.slides) == len(c.slides)


def test_clean_creative_when_no_protected_terms_present():
    creatives = studio(protected_terms=frozenset()).build_creatives(make_brief(), campaign_month="202609")
    assert all(c.mask_status == "clean" for c in creatives)


def test_flagged_creative_when_caption_leaks_another_client_name():
    llm_response = json.dumps(
        [{"hook": "훅", "caption": "celest 사례처럼요", "hashtags": ["코파운더"]}] * 1,
        ensure_ascii=False,
    )
    s = CreativeStudio(
        llm=FakeLLMClient(llm_response),
        renderer=NullCarouselRenderer(),
        masking_filter=MaskingFilter({"celest"}),
        instagram_base_url="https://dodamfood.kr",
    )
    creatives = s.build_creatives(make_brief(), campaign_month="202609")
    assert creatives[0].mask_status == "flagged"
    assert "celest" in creatives[0].mask_hits


def test_medium_paid_is_reflected_in_utm():
    creatives = studio().build_creatives(make_brief(), campaign_month="202609", medium="paid")
    assert all("utm_medium=paid" in c.utm_url for c in creatives)
