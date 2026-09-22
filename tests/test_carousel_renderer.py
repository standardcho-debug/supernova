import os
from pathlib import Path

import pytest

from sns_marketing_agent.carousel_renderer import (
    ASPECTS,
    MAX_SLIDES,
    MIN_SLIDES,
    NullCarouselRenderer,
    PlaywrightCarouselRenderer,
    plan_slide_texts,
)
from sns_marketing_agent.creative_models import CopyVariant
from sns_marketing_agent.strategy_models import Brief, EvidenceItem


def make_brief(key_messages=None, evidence_excerpt="처분을 고른다"):
    return Brief(
        client_slug="supernova-platform",
        channel="instagram",
        topic="요청이 도착하면 바로 분류된다",
        angle="속도를 체감 지표로 보여준다",
        pillar="증거형",
        target_persona="이미 코파운더를 쓰는 운영팀",
        hook_125="요청 하나가 도착하는 순간, 무슨 일이 벌어질까요?",
        key_messages=key_messages if key_messages is not None else ["제보 즉시 분류", "코드가 판정"],
        evidence=[EvidenceItem(source_tool="system_map_rules", ref="triage#rule71", excerpt=evidence_excerpt)],
        cta="지금 요청을 남겨보세요",
    )


def make_variant():
    return CopyVariant(
        variant=1,
        hook="요청 하나가 도착하는 순간, 무슨 일이 벌어질까요?",
        caption="요청 하나가 도착하는 순간... 지금 요청을 남겨보세요",
        hashtags=["코파운더", "자동화"],
    )


def test_plan_slide_texts_within_bounds():
    slides = plan_slide_texts(make_variant(), make_brief())
    assert MIN_SLIDES <= len(slides) <= MAX_SLIDES


def test_plan_slide_texts_starts_with_hook_and_ends_with_summary():
    brief = make_brief()
    variant = make_variant()
    slides = plan_slide_texts(variant, brief)
    assert slides[0] == variant.hook
    assert brief.topic in slides[-1]


def test_plan_slide_texts_pads_when_few_key_messages():
    # only 1 key message; must still reach the 5-slide floor via evidence/angle/persona/topic
    brief = make_brief(key_messages=["딱 하나뿐인 메시지"])
    slides = plan_slide_texts(make_variant(), brief)
    assert len(slides) >= MIN_SLIDES


def test_plan_slide_texts_caps_at_max_slides_with_plenty_of_material():
    # Brief caps key_messages at 3 (its own §5.2 schema invariant); pile on
    # extra evidence items instead to prove the MAX_SLIDES cap independently.
    brief = make_brief(key_messages=["메시지 1", "메시지 2", "메시지 3"])
    brief.evidence.extend(
        EvidenceItem(source_tool="system_map_rules", ref=f"node{i}", excerpt=f"근거 {i}")
        for i in range(5)
    )
    slides = plan_slide_texts(make_variant(), brief)
    assert len(slides) <= MAX_SLIDES


def test_null_renderer_plans_without_writing_files():
    slides = plan_slide_texts(make_variant(), make_brief())
    result = NullCarouselRenderer().render("brief-1", 1, slides)
    assert set(result.keys()) == set(ASPECTS.keys())
    for aspect, paths in result.items():
        assert len(paths) == len(slides)
        assert all(p == "" for p in paths)


def test_playwright_carousel_renderer_produces_real_files(tmp_path):
    pytest.importorskip("playwright")
    slides = plan_slide_texts(make_variant(), make_brief())
    renderer = PlaywrightCarouselRenderer(
        out_dir=tmp_path, executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_PATH")
    )
    try:
        result = renderer.render("brief-1", 1, slides)
    except Exception as exc:  # pragma: no cover - depends on local browser install
        pytest.skip(f"chromium not available in this environment: {exc}")

    for aspect, paths in result.items():
        assert len(paths) == len(slides)
        for path in paths:
            assert Path(path).exists()
            assert Path(path).stat().st_size > 0
