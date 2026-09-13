"""Stage 3b: render a draft's text into card images (cover / carousel / thumbnail).

This renders real PNGs from HTML via a headless browser — the same approach
Cofounder's existing instagram-cards/blog-card skills already validated for
informational cards (freeform image-generation models distort text and
numbers; laying out known text does not). It does not do anything
photographic or illustrative — it is a text-on-background card renderer.

Video is handled the same way in spirit but stops one step earlier: stage 3
(draft_generator) produces a StoryboardScene breakdown, and this module does
not turn that into an actual video file. Actually cutting a video needs a
real video-generation or editing pipeline, which nothing in this repo
provides yet — that is separate, unstarted work, not an oversight.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import Channel, ContentDraft, ImageAsset

_CARD_SIZE = {
    Channel.INSTAGRAM: (1080, 1080),
    Channel.NAVER_BLOG: (1200, 630),
    Channel.YOUTUBE: (1280, 720),
}

_CARD_HTML = """<html><body style="margin:0;width:{width}px;height:{height}px;
display:flex;align-items:center;justify-content:center;background:#1c1c1e;
font-family:sans-serif;padding:60px;box-sizing:border-box;">
<div style="color:#fff;font-size:{font_size}px;line-height:1.4;
text-align:center;white-space:pre-wrap;">{text}</div></body></html>"""


def plan_card_texts(draft: ContentDraft) -> list[str]:
    """Rule-based split of a draft into one text block per card.

    This is layout, not content generation — which text goes on which card
    is a fixed convention per channel, so it stays deterministic instead of
    another LLM call. Instagram gets a small hook/body/CTA carousel; blog
    and youtube get a single cover/thumbnail card.
    """
    channel = draft.brief.channel
    if channel == Channel.INSTAGRAM:
        cta = draft.hashtags[0] if draft.hashtags else "더 알아보기"
        return [draft.title, draft.body, f"자세한 이야기는 댓글에서 · {cta}"]
    if channel == Channel.YOUTUBE:
        return [draft.thumbnail_text or draft.title]
    return [draft.title]


class ImageAssetGenerator(Protocol):
    def generate(self, draft: ContentDraft) -> list[ImageAsset]:
        ...


class PlaywrightCardRenderer:
    """Real renderer. Requires `pip install playwright` + `playwright install chromium`.

    `executable_path` only exists for environments where Playwright can't
    auto-detect its browser install (this sandbox is one); leave it unset
    on a normal dev machine.
    """

    def __init__(self, out_dir: Path, executable_path: str | None = None):
        self._out_dir = Path(out_dir)
        self._out_dir.mkdir(parents=True, exist_ok=True)
        self._executable_path = executable_path

    def generate(self, draft: ContentDraft) -> list[ImageAsset]:
        from playwright.sync_api import sync_playwright

        channel = draft.brief.channel
        width, height = _CARD_SIZE[channel]
        font_size = 48 if channel == Channel.NAVER_BLOG else 64
        texts = plan_card_texts(draft)
        assets: list[ImageAsset] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=self._executable_path)
            page = browser.new_page(viewport={"width": width, "height": height})
            try:
                for i, text in enumerate(texts):
                    page.set_content(
                        _CARD_HTML.format(
                            width=width, height=height, font_size=font_size, text=text
                        )
                    )
                    out_path = (
                        self._out_dir
                        / f"{draft.brief.client_id}_{channel.value}_{i}.png"
                    )
                    page.screenshot(path=str(out_path))
                    assets.append(
                        ImageAsset(channel=channel, file_path=str(out_path), alt_text=text)
                    )
            finally:
                browser.close()
        return assets


class NullImageGenerator:
    """No-op stand-in for demos/tests without a browser installed.

    Plans the same card texts a real renderer would, but leaves
    `file_path` empty instead of writing anything.
    """

    def generate(self, draft: ContentDraft) -> list[ImageAsset]:
        return [
            ImageAsset(channel=draft.brief.channel, file_path="", alt_text=text)
            for text in plan_card_texts(draft)
        ]
