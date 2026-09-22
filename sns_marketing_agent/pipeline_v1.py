"""Orchestrates F1-F5 into one run — PRD v1.0 §4.2 핵심 플로우.

    [고객사 선택] → F1 스냅샷 생성 (co-mcp 읽기)
       → F2 월간 전략 생성 → STan 확인(수정 가능)
       → F3 주간 소재 후보 5건 랭킹 → 상위 3건 브리프
       → F4 브리프당 3안 생성 → 루브릭 자동점수
       → F5 승인/반려(사유코드) → 승인분 다운로드 (P1은 수동 게시)
       → 반려 사유는 다음 F3·F4 프롬프트에 주입

This module is the thing web/marketing_app.py calls; it holds no web
framework imports itself so it can be driven from a script or a future
non-web surface the same way.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sns_marketing_agent.brief_selector import BriefSelector
from sns_marketing_agent.carousel_renderer import CarouselAssetRenderer
from sns_marketing_agent.cofounder_client import ReadOnlyCofounderClient
from sns_marketing_agent.context_engine import ContextEngine
from sns_marketing_agent.context_models import ContextSnapshot
from sns_marketing_agent.creative_models import Creative
from sns_marketing_agent.creative_studio import CreativeStudio
from sns_marketing_agent.llm_client import LLMClient
from sns_marketing_agent.masking_filter import MaskingFilter
from sns_marketing_agent.review_models import REASON_LABELS, RubricScore
from sns_marketing_agent.review_queue import ReviewQueue
from sns_marketing_agent.rubric_scorer import RubricScorer
from sns_marketing_agent.strategy_models import Brief, MonthlyStrategy
from sns_marketing_agent.strategy_planner import StrategyPlanner


@dataclass
class PipelineRun:
    client_slug: str
    month: str
    snapshot: ContextSnapshot
    strategy: MonthlyStrategy
    briefs: list[Brief]
    creatives_by_brief: dict[str, list[Creative]] = field(default_factory=dict)
    brief_by_id: dict[str, Brief] = field(default_factory=dict)
    creative_by_id: dict[str, Creative] = field(default_factory=dict)


def run_pipeline(
    client_slug: str,
    month: str,
    co_client: ReadOnlyCofounderClient,
    llm: LLMClient,
    renderer: CarouselAssetRenderer,
    masking_filter: MaskingFilter,
    instagram_base_url: str,
    review_queue: ReviewQueue,
    n_briefs: int = 3,
) -> PipelineRun:
    snapshot = ContextEngine(co_client).build_snapshot(client_slug)
    strategy = StrategyPlanner(llm).build_strategy(snapshot, month=month)

    avoid_patterns = [
        REASON_LABELS[code] for code in review_queue.recent_rejection_patterns(client_slug)
    ]

    briefs = BriefSelector(llm).select_and_brief(
        snapshot, strategy, n=n_briefs, avoid_patterns=avoid_patterns
    )

    studio = CreativeStudio(llm, renderer, masking_filter, instagram_base_url)
    scorer = RubricScorer(llm)

    creatives_by_brief: dict[str, list[Creative]] = {}
    brief_by_id: dict[str, Brief] = {}
    creative_by_id: dict[str, Creative] = {}

    for brief in briefs:
        brief_by_id[brief.id] = brief
        creatives = studio.build_creatives(brief, campaign_month=month, avoid_patterns=avoid_patterns)
        creatives_by_brief[brief.id] = creatives
        for creative in creatives:
            creative_by_id[creative.id] = creative
            rubric: RubricScore = scorer.score(creative, brief)
            review_queue.submit(client_slug, creative.id, brief.id, rubric)

    return PipelineRun(
        client_slug=client_slug,
        month=month,
        snapshot=snapshot,
        strategy=strategy,
        briefs=briefs,
        creatives_by_brief=creatives_by_brief,
        brief_by_id=brief_by_id,
        creative_by_id=creative_by_id,
    )
