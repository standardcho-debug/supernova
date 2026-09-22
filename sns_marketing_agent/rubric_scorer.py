"""F5 자동 루브릭 채점 — PRD v1.0 §5.4.

Split deliberately: masking and format_compliance are checked in code
(objective, already-known facts about the Creative — no reason to ask an
LLM whether a caption has 3-5 hashtags when `len()` answers it exactly).
evidence_fit/factual_accuracy/persona_resonance/hook_strength need
judgment, so those four go through one LLM call, grounded in the brief's
own evidence so the model is scoring against the same facts the brief was
built from, not guessing.

`masking` is never LLM-scored and never overridden: a flagged creative
gets 0 here regardless of what any prompt returns, because C4 is a
hard gate, not a rubric opinion.
"""
from __future__ import annotations

import json

from sns_marketing_agent.creative_models import Creative
from sns_marketing_agent.llm_client import LLMClient
from sns_marketing_agent.review_models import RubricScore
from sns_marketing_agent.strategy_models import Brief

_MAX = {"evidence_fit": 25, "factual_accuracy": 20, "persona_resonance": 20, "hook_strength": 15}


def _format_score(creative: Creative) -> int:
    checks = [
        3 <= len(creative.hashtags) <= 5,
        5 <= len(creative.slides) <= 7,
        len(creative.slides[0].text) <= 125,  # hook slide is always slides[0]
    ]
    return round(10 * sum(checks) / len(checks))


def _build_prompt(creative: Creative, brief: Brief) -> str:
    evidence_lines = "\n".join(f"- [{e.source_tool}:{e.ref}] {e.excerpt}" for e in brief.evidence)
    slide_lines = "\n".join(f"{i + 1}. {s.text}" for i, s in enumerate(creative.slides))
    return (
        f"타겟: {brief.target_persona}\n근거:\n{evidence_lines}\n\n"
        f"캡션: {creative.caption}\n\n슬라이드:\n{slide_lines}\n\n"
        "이 인스타그램 캐러셀을 아래 네 기준으로 채점하라(각 기준 배점 안에서 정수 점수):\n"
        "- evidence_fit(0-25): 주장마다 위 근거에 실제로 대응하는가\n"
        "- factual_accuracy(0-20): 숫자·고유명사가 근거 excerpt와 일치하는가\n"
        "- persona_resonance(0-20): 타겟이 쓸 법한 표현에 가까운가\n"
        "- hook_strength(0-15): 첫 슬라이드 훅이 강한가\n"
        '{"evidence_fit": N, "factual_accuracy": N, "persona_resonance": N, "hook_strength": N} '
        "JSON으로만 출력하라."
    )


class RubricScorer:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def score(self, creative: Creative, brief: Brief) -> RubricScore:
        masking_score = 10 if creative.mask_status == "clean" else 0
        format_score = _format_score(creative)

        raw = self._llm.complete(_build_prompt(creative, brief))
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"rubric scorer got non-JSON output for creative {creative.id}: {raw[:200]!r}"
            ) from exc

        clamped = {key: max(0, min(data[key], cap)) for key, cap in _MAX.items()}
        total = masking_score + format_score + sum(clamped.values())

        return RubricScore(
            evidence_fit=clamped["evidence_fit"],
            factual_accuracy=clamped["factual_accuracy"],
            persona_resonance=clamped["persona_resonance"],
            hook_strength=clamped["hook_strength"],
            format_compliance=format_score,
            masking=masking_score,
            total=total,
        )
