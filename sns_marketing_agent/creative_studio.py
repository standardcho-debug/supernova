"""F4 CreativeStudio — PRD v1.0 §5.3. Ties copy, rendering, masking, and UTM
together into the 3 Creative variants a Brief becomes.

Masking runs on every text surface (caption + every slide) BEFORE a
Creative is returned — a flagged Creative still comes back (F5's approval
screen needs to show reviewers what was caught), but `mask_status` is
never left for a later stage to compute. There is no publish/schedule call
anywhere in this module, on purpose: see approval_gate.py's docstring for
why that boundary exists in this codebase.
"""
from __future__ import annotations

from sns_marketing_agent.carousel_renderer import CarouselAssetRenderer, plan_slide_texts
from sns_marketing_agent.copy_generator import CopyGenerator
from sns_marketing_agent.creative_models import Creative, ResizedAsset, Slide
from sns_marketing_agent.llm_client import LLMClient
from sns_marketing_agent.masking_filter import MaskingFilter
from sns_marketing_agent.strategy_models import Brief
from sns_marketing_agent.utm import build_utm_url

_RESIZED_ASPECTS = ("1:1", "9:16")


class CreativeStudio:
    def __init__(
        self,
        llm: LLMClient,
        renderer: CarouselAssetRenderer,
        masking_filter: MaskingFilter,
        instagram_base_url: str,
    ):
        self._copy_gen = CopyGenerator(llm)
        self._renderer = renderer
        self._masking = masking_filter
        self._base_url = instagram_base_url

    def build_creatives(
        self,
        brief: Brief,
        campaign_month: str,
        medium: str = "organic",
        avoid_patterns: list[str] | None = None,
    ) -> list[Creative]:
        variants = self._copy_gen.generate_variants(brief, avoid_patterns=avoid_patterns)
        creatives = []
        for copy_variant in variants:
            creatives.append(self._build_one(brief, copy_variant, campaign_month, medium))
        return creatives

    def _build_one(self, brief: Brief, copy_variant, campaign_month: str, medium: str) -> Creative:
        slide_texts = plan_slide_texts(copy_variant, brief)
        rendered = self._renderer.render(brief.id, copy_variant.variant, slide_texts)

        slides = [
            Slide(order=i, text=text, image_path=rendered["4:5"][i])
            for i, text in enumerate(slide_texts)
        ]
        resized = [
            ResizedAsset(aspect=aspect, slides=rendered[aspect]) for aspect in _RESIZED_ASPECTS
        ]

        mask_status, mask_hits = self._masking.status(copy_variant.caption, *slide_texts)

        creative = Creative(
            brief_id=brief.id,
            variant=copy_variant.variant,
            caption=copy_variant.caption,
            hashtags=copy_variant.hashtags,
            slides=slides,
            resized=resized,
            utm_url="",  # filled in below — needs creative.id, assigned at construction
            mask_status=mask_status,
            mask_hits=mask_hits,
        )
        creative.utm_url = build_utm_url(
            self._base_url, medium, campaign_month, brief.pillar, creative.id
        )
        return creative
