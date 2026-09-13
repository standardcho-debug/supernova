"""Stage 2: turn a ClientProfile into channel-specific content briefs.

Each brief must cite which piece of the client's history it came from
(`source_evidence`) — that traceability is the whole point of grounding
content in Cofounder data instead of a generic prompt, and it's what lets a
human reviewer at stage 4 sanity-check "why this topic" at a glance.
"""
from __future__ import annotations

import json

from .llm_client import LLMClient
from .models import Channel, ClientProfile, ContentBrief

_CHANNEL_GUIDANCE = {
    Channel.NAVER_BLOG: "검색 유입을 노리는 정보성 롱폼 글감. SEO 키워드 후보 포함.",
    Channel.INSTAGRAM: "카드뉴스/캐러셀로 넘기기 좋은, 한 장면에 요약되는 소재.",
    Channel.YOUTUBE: "3-5분 안에 설명 가능한, 썸네일 한 줄로 승부할 수 있는 소재.",
}


def _build_prompt(profile: ClientProfile, channel: Channel, n: int) -> str:
    history_lines = "\n".join(
        [f"- 사업계획: {h}" for h in profile.business_plan_highlights]
        + [f"- 최근 요청: {r}" for r in profile.recent_requests]
        + [f"- 불만/이슈: {c}" for c in profile.recent_complaints]
        + [f"- 매출 시그널: {s}" for s in profile.revenue_signals]
    )
    return (
        f"고객사 '{profile.name}' 히스토리:\n{history_lines}\n\n"
        f"채널: {channel.value} ({_CHANNEL_GUIDANCE[channel]})\n"
        f"브랜드 톤: {profile.brand_tone or '미지정'}\n\n"
        f"위 히스토리에서 실제로 나온 항목에 근거해 콘텐츠 소재 {n}개를 제안하라. "
        "각 소재는 topic, angle, source_evidence(위 히스토리 문구 중 인용) 세 필드를 가진 "
        'JSON 배열로만 출력하라. 예: [{"topic": "...", "angle": "...", '
        '"source_evidence": ["..."]}]'
    )


class BriefGenerator:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def generate(
        self, profile: ClientProfile, channel: Channel, n: int = 3
    ) -> list[ContentBrief]:
        prompt = _build_prompt(profile, channel, n)
        raw = self._llm.complete(prompt)
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"brief generator got non-JSON output for {profile.client_id}/"
                f"{channel.value}: {raw[:200]!r}"
            ) from exc

        return [
            ContentBrief(
                client_id=profile.client_id,
                channel=channel,
                topic=item["topic"],
                angle=item["angle"],
                source_evidence=item["source_evidence"],
            )
            for item in items
        ]
