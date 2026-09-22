"""F4 카피 생성 — PRD v1.0 §5.3: 브리프당 3안, 캡션(훅<=125자+본문+CTA)+해시태그 3-5개.

Grounded the same way stage 2/3 always have been in this codebase: the
prompt states the brief's evidence and excluded_claims explicitly and asks
the model to stay inside them, rather than trusting it to remember not to
invent anything.
"""
from __future__ import annotations

import json

from sns_marketing_agent.creative_models import CopyVariant
from sns_marketing_agent.llm_client import LLMClient
from sns_marketing_agent.strategy_models import Brief


def _build_prompt(brief: Brief, avoid_patterns: list[str]) -> str:
    evidence_lines = "\n".join(f"- [{e.source_tool}:{e.ref}] {e.excerpt}" for e in brief.evidence)
    excluded = ", ".join(brief.excluded_claims) or "(없음)"
    messages = "\n".join(f"- {m}" for m in brief.key_messages)
    avoid = (
        f"\n\n최근 반려에서 반복된 문제(피할 것): {', '.join(avoid_patterns)}"
        if avoid_patterns
        else ""
    )
    return (
        f"소재: {brief.topic}\n관점: {brief.angle}\n타겟: {brief.target_persona}\n"
        f"훅 초안: {brief.hook_125}\n핵심 메시지:\n{messages}\nCTA: {brief.cta}\n\n"
        f"근거(반드시 이 안에서만 인용):\n{evidence_lines}\n\n"
        f"말하면 안 되는 것(측정 미확정): {excluded}{avoid}\n\n"
        "위 브리프로 인스타그램 캡션 3안을 작성하라. 각 안은 hook(125자 이내), "
        "caption(hook+본문+CTA를 포함한 전체 캡션), hashtags(3-5개) 필드를 가진다. "
        '전체를 [{"hook": "...", "caption": "...", "hashtags": ["..."]}, ...] '
        "JSON 배열 3개 원소로 출력하라. 근거에 없는 숫자·사실을 새로 만들지 말 것."
    )


class CopyGenerator:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def generate_variants(self, brief: Brief, avoid_patterns: list[str] | None = None) -> list[CopyVariant]:
        """`avoid_patterns` is PRD §5.4's rejection-reason feedback loop:
        the queue's recent_rejection_patterns() labels, passed straight
        through as plain strings — this module doesn't know they're reason
        codes, just text to avoid repeating."""
        prompt = _build_prompt(brief, avoid_patterns or [])
        raw = self._llm.complete(prompt)
        try:
            items = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"copy generator got non-JSON output for brief {brief.id}: {raw[:200]!r}"
            ) from exc

        return [
            CopyVariant(
                variant=i + 1,
                hook=item["hook"],
                caption=item["caption"],
                hashtags=item.get("hashtags", [])[:5],
            )
            for i, item in enumerate(items)
        ]
