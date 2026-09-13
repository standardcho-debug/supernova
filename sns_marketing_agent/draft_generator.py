"""Stage 3: turn a ContentBrief into a channel-specific draft.

Output still isn't publishable on its own — it stops at stage 4 (approval).
Actually posting to Naver Blog / Instagram / Youtube is a separate,
not-yet-built integration; see README.md.
"""
from __future__ import annotations

import json

from .llm_client import LLMClient
from .models import Channel, ClientProfile, ContentBrief, ContentDraft

_CHANNEL_INSTRUCTIONS = {
    Channel.NAVER_BLOG: (
        "네이버 블로그 글을 작성하라. title, body(마크다운, 800-1200자), "
        "hashtags(5-8개) 필드를 가진 JSON으로 출력하라."
    ),
    Channel.INSTAGRAM: (
        "인스타그램 캐러셀 캡션을 작성하라. title(카드 1장 헤드라인), "
        "body(캡션 본문, 3-5문장), hashtags(8-15개) 필드를 가진 JSON으로 출력하라."
    ),
    Channel.YOUTUBE: (
        "유튜브 숏폼 스크립트를 작성하라. title(영상 제목), "
        "body(3-5분 분량 스크립트), hashtags(3-5개), "
        "thumbnail_text(썸네일에 넣을 한 줄) 필드를 가진 JSON으로 출력하라."
    ),
}


def _build_prompt(profile: ClientProfile, brief: ContentBrief) -> str:
    return (
        f"고객사: {profile.name} (브랜드 톤: {profile.brand_tone or '미지정'})\n"
        f"소재: {brief.topic}\n"
        f"관점: {brief.angle}\n"
        f"근거: {', '.join(brief.source_evidence)}\n\n"
        f"{_CHANNEL_INSTRUCTIONS[brief.channel]}"
    )


class DraftGenerator:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def generate(self, profile: ClientProfile, brief: ContentBrief) -> ContentDraft:
        prompt = _build_prompt(profile, brief)
        raw = self._llm.complete(prompt)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"draft generator got non-JSON output for {brief.client_id}/"
                f"{brief.channel.value}: {raw[:200]!r}"
            ) from exc

        return ContentDraft(
            brief=brief,
            title=data["title"],
            body=data["body"],
            hashtags=data.get("hashtags", []),
            thumbnail_text=data.get("thumbnail_text"),
        )
