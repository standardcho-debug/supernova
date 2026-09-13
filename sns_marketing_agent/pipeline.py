"""Wires stages 1-4 together. Stage 5 (channel connect + upload automation)
and stage 6 (performance marketing automation) are separate, later work —
see README.md for the full roadmap this fits into.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .approval_gate import ApprovalGate
from .brief_generator import BriefGenerator
from .draft_generator import DraftGenerator
from .history_collector import HistorySource
from .image_generator import ImageAssetGenerator
from .llm_client import LLMClient
from .models import ApprovalRecord, Channel


def run_pipeline(
    client_id: str,
    channels: list[Channel],
    history_source: HistorySource,
    llm: LLMClient,
    image_generator: ImageAssetGenerator | None = None,
    briefs_per_channel: int = 1,
) -> list[ApprovalRecord]:
    profile = history_source.get_client_profile(client_id)
    brief_gen = BriefGenerator(llm)
    draft_gen = DraftGenerator(llm)
    gate = ApprovalGate()

    records = []
    for channel in channels:
        briefs = brief_gen.generate(profile, channel, n=briefs_per_channel)
        for brief in briefs:
            draft = draft_gen.generate(profile, brief)
            if image_generator is not None:
                draft.images = image_generator.generate(draft)
            records.append(gate.submit(draft))
    return records


def _demo() -> None:
    from .history_collector import StaticHistorySource
    from .image_generator import NullImageGenerator, PlaywrightCardRenderer
    from .llm_client import TemplateLLMClient

    fixture = Path(__file__).parent / "fixtures" / "sample_client_history.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-id", default="demo-bakery")
    parser.add_argument(
        "--channels",
        nargs="+",
        default=[c.value for c in Channel],
        choices=[c.value for c in Channel],
    )
    parser.add_argument(
        "--render-images",
        metavar="OUT_DIR",
        help="actually render card PNGs into OUT_DIR via Playwright "
        "(requires `pip install playwright && playwright install chromium`); "
        "omit to just plan card text without rendering",
    )
    args = parser.parse_args()

    image_generator = (
        PlaywrightCardRenderer(Path(args.render_images))
        if args.render_images
        else NullImageGenerator()
    )

    records = run_pipeline(
        client_id=args.client_id,
        channels=[Channel(c) for c in args.channels],
        history_source=StaticHistorySource(fixture),
        llm=TemplateLLMClient(),
        image_generator=image_generator,
    )
    for record in records:
        draft = record.draft
        print(f"[{record.status.value}] {draft.brief.channel.value}: {draft.title}")
        for image in draft.images:
            print(f"  image: {image.file_path or '(not rendered)'} — {image.alt_text!r}")
        for scene in draft.storyboard:
            print(f"  scene {scene.order}: {scene.on_screen_text!r} ({scene.duration_seconds}s)")


if __name__ == "__main__":
    _demo()
