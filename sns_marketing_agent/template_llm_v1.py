"""Deterministic offline stand-in for PRD v1.0's pipeline (strategy/brief/
copy/rubric) — same purpose as llm_client.TemplateLLMClient, but for this
pipeline's distinct JSON shapes (that older stub returns a single
title/body/hashtags shape that doesn't match any of these four calls).

Detects which stage is calling by a marker unique to that stage's own
prompt text, same technique as the old TemplateLLMClient. Lets
run_pipeline() execute end-to-end — and be demoed — with no API key.
"""
from __future__ import annotations

import json


class TemplateLLMClientV1:
    def complete(self, prompt: str) -> str:
        if "콘텐츠 필러 3종" in prompt:
            return json.dumps(
                {
                    "goal": "템플릿 목표 문장",
                    "pillars": [
                        {"name": "증거형", "ratio": 0.4},
                        {"name": "교육형", "ratio": 0.3},
                        {"name": "공감형", "ratio": 0.3},
                    ],
                },
                ensure_ascii=False,
            )
        if "hook_125(125자 이내 훅)" in prompt:
            return json.dumps(
                {
                    "topic": "템플릿 소재",
                    "angle": "템플릿 관점",
                    "pillar": "증거형",
                    "target_persona": "템플릿 타겟",
                    "hook_125": "템플릿 훅",
                    "key_messages": ["템플릿 메시지 1", "템플릿 메시지 2"],
                    "cta": "템플릿 CTA",
                },
                ensure_ascii=False,
            )
        if "캡션 3안" in prompt:
            return json.dumps(
                [
                    {"hook": f"템플릿 훅 {i}", "caption": f"템플릿 캡션 {i}", "hashtags": ["템플릿"]}
                    for i in range(1, 4)
                ],
                ensure_ascii=False,
            )
        if "evidence_fit" in prompt:
            return json.dumps(
                {"evidence_fit": 18, "factual_accuracy": 14, "persona_resonance": 14, "hook_strength": 10},
                ensure_ascii=False,
            )
        raise ValueError(f"TemplateLLMClientV1 doesn't recognize this prompt shape: {prompt[:120]!r}")
