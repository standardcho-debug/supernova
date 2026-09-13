import os
from pathlib import Path

import pytest

from sns_marketing_agent.image_generator import (
    NullImageGenerator,
    PlaywrightCardRenderer,
    plan_card_texts,
)
from sns_marketing_agent.models import Channel, ContentBrief, ContentDraft


def make_draft(channel):
    brief = ContentBrief(
        client_id="demo-bakery",
        channel=channel,
        topic="topic",
        angle="angle",
        source_evidence=["evidence"],
    )
    return ContentDraft(
        brief=brief,
        title="월요일에만 만나는 메뉴",
        body="이번 주 월요일, 딱 하루만 굽는 메뉴를 소개합니다.",
        hashtags=["동네빵집", "당일발효"],
        thumbnail_text="월요일에만 파는 이유",
    )


def test_plan_card_texts_instagram_is_hook_body_cta():
    texts = plan_card_texts(make_draft(Channel.INSTAGRAM))
    assert len(texts) == 3
    assert texts[0] == "월요일에만 만나는 메뉴"
    assert "동네빵집" in texts[2]


def test_plan_card_texts_blog_is_single_cover():
    texts = plan_card_texts(make_draft(Channel.NAVER_BLOG))
    assert texts == ["월요일에만 만나는 메뉴"]


def test_plan_card_texts_youtube_uses_thumbnail_text():
    texts = plan_card_texts(make_draft(Channel.YOUTUBE))
    assert texts == ["월요일에만 파는 이유"]


def test_null_image_generator_plans_without_writing_files():
    assets = NullImageGenerator().generate(make_draft(Channel.INSTAGRAM))
    assert len(assets) == 3
    assert all(asset.file_path == "" for asset in assets)
    assert all(asset.channel == Channel.INSTAGRAM for asset in assets)


def test_playwright_card_renderer_produces_real_png_files(tmp_path):
    pytest.importorskip("playwright")

    renderer = PlaywrightCardRenderer(
        out_dir=tmp_path,
        executable_path=os.environ.get("PLAYWRIGHT_CHROMIUM_PATH"),
    )
    try:
        assets = renderer.generate(make_draft(Channel.INSTAGRAM))
    except Exception as exc:  # pragma: no cover - depends on local browser install
        pytest.skip(f"chromium not available in this environment: {exc}")

    assert len(assets) == 3
    for asset in assets:
        path = Path(asset.file_path)
        assert path.exists()
        assert path.stat().st_size > 0
