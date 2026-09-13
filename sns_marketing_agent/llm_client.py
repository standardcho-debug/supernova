"""LLM boundary shared by stage 2 (briefs) and stage 3 (drafts).

Kept as a one-method protocol so brief/draft generation can run in tests and
demos without an API key, and swap to a real model with one line at the call
site.
"""
from __future__ import annotations

import json
from typing import Protocol


class LLMClient(Protocol):
    def complete(self, prompt: str) -> str:
        ...


class AnthropicLLMClient:
    """Thin wrapper around the Anthropic SDK. Requires ANTHROPIC_API_KEY."""

    def __init__(self, model: str = "claude-sonnet-5"):
        import anthropic  # optional dependency, only needed for this client

        self._client = anthropic.Anthropic()
        self._model = model

    def complete(self, prompt: str) -> str:
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        )


class TemplateLLMClient:
    """Deterministic stand-in for demos and tests: no network, no API key.

    Not meant to produce publishable copy — it exists so the pipeline is
    runnable end-to-end before a real LLMClient is wired up. It returns
    minimal valid JSON matching whichever stage is calling: brief_generator
    asks for a JSON array (its prompt says "JSON 배열"), draft_generator
    asks for a single JSON object.
    """

    def complete(self, prompt: str) -> str:
        if "JSON 배열" in prompt:
            return json.dumps(
                [
                    {
                        "topic": "템플릿 소재",
                        "angle": "템플릿 관점",
                        "source_evidence": ["템플릿 근거"],
                    }
                ],
                ensure_ascii=False,
            )
        return json.dumps(
            {"title": "템플릿 제목", "body": "템플릿 본문", "hashtags": ["템플릿"]},
            ensure_ascii=False,
        )
