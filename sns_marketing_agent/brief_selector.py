"""F3 소재 선정 + 브리프 — PRD v1.0 §5.2.

Two passes: `score_candidates` ranks every recent change against the
§5.2 rubric in plain code (auditable, no LLM judgment call in the ranking
itself); `expand_to_brief` then asks the LLM to write the actual copy
scaffolding (hook/messages/cta) for whichever candidates the caller
promotes — never the other way around, so the ranking a reviewer sees is
never a black box the LLM produced.

Known simplification (documented, not hidden): "월간전략 필러 적합"(30) and
"고객 체감 변화인가"(25) both currently key off the same signal — whether
the change's node is customer-facing — because there's no per-pillar
classifier yet. A real classifier is a later iteration, not this one; see
README. "시각자료 존재"(10) is always 0 for the same reason: ContextEngine
doesn't call get_feature_evidence yet.
"""
from __future__ import annotations

import json

from sns_marketing_agent.context_models import ContextSnapshot
from sns_marketing_agent.llm_client import LLMClient
from sns_marketing_agent.strategy_models import Brief, EvidenceItem, MonthlyStrategy, ScoredCandidate

_PILLAR_FIT_FACING = 30
_PILLAR_FIT_INTERNAL = 10
_CUSTOMER_FELT_FACING = 25
_EVIDENCE_EXISTS = 25
_NOT_DUPLICATE = 10
_VISUAL_EVIDENCE = 0  # not implemented — see module docstring


def score_candidates(
    snapshot: ContextSnapshot,
    recent_topics: frozenset[str] = frozenset(),
) -> list[ScoredCandidate]:
    facing_keys = {c.key for c in snapshot.customer_facing_cells}
    promise_text_by_node: dict[str, str] = {}
    for promise in snapshot.promises:
        promise_text_by_node.setdefault(promise.node_key, promise.rule_title)

    scored = []
    for change in snapshot.recent_changes:
        is_facing = change.node_key in facing_keys
        evidence_excerpt = promise_text_by_node.get(change.node_key)
        is_duplicate = change.node_key in recent_topics

        breakdown = {
            "pillar_fit": _PILLAR_FIT_FACING if is_facing else _PILLAR_FIT_INTERNAL,
            "customer_felt": _CUSTOMER_FELT_FACING if is_facing else 0,
            "evidence_exists": _EVIDENCE_EXISTS if evidence_excerpt else 0,
            "not_duplicate": 0 if is_duplicate else _NOT_DUPLICATE,
            "visual_evidence": _VISUAL_EVIDENCE,
        }
        scored.append(
            ScoredCandidate(
                node_key=change.node_key,
                label=change.label or change.node_key,
                total_score=sum(breakdown.values()),
                score_breakdown=breakdown,
                disqualified=evidence_excerpt is None,
                evidence_excerpt=evidence_excerpt,
                source=change.source,
            )
        )
    return scored


def top_candidates(scored: list[ScoredCandidate], n: int = 3) -> list[ScoredCandidate]:
    eligible = [c for c in scored if not c.disqualified]
    return sorted(eligible, key=lambda c: c.total_score, reverse=True)[:n]


def _build_prompt(candidate: ScoredCandidate, strategy: MonthlyStrategy) -> str:
    pillar_names = ", ".join(p.name for p in strategy.pillars)
    excluded = ", ".join(strategy.excluded_claims) or "(없음)"
    return (
        f"소재: {candidate.label}\n"
        f"근거(citable): {candidate.evidence_excerpt}\n"
        f"이번 달 전략 목표: {strategy.goal}\n"
        f"콘텐츠 필러: {pillar_names}\n"
        f"말하면 안 되는 것(측정 미확정): {excluded}\n\n"
        "위 소재로 인스타그램 브리프를 작성하라. 위 '근거' 문장을 실제로 인용해서 "
        "topic, angle, pillar(필러 중 하나), target_persona, hook_125(125자 이내 훅), "
        "key_messages(핵심 메시지, 최대 3개 배열), cta 필드를 가진 JSON으로 출력하라. "
        "'말하면 안 되는 것'에 있는 내용은 절대 포함하지 말 것."
    )


class BriefSelector:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def expand_to_brief(self, candidate: ScoredCandidate, strategy: MonthlyStrategy) -> Brief:
        if candidate.disqualified:
            raise ValueError(
                f"candidate {candidate.node_key!r} has no evidence excerpt — cannot brief it (PRD §5.2)"
            )

        prompt = _build_prompt(candidate, strategy)
        raw = self._llm.complete(prompt)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"brief expansion got non-JSON output for {candidate.node_key!r}: {raw[:200]!r}"
            ) from exc

        return Brief(
            client_slug=strategy.client_slug,
            channel="instagram",  # PRD v1.0 §0 scope — Instagram only for this MVP
            topic=data["topic"],
            angle=data["angle"],
            pillar=data["pillar"],
            target_persona=data["target_persona"],
            hook_125=data["hook_125"],
            key_messages=data.get("key_messages", [])[:3],
            evidence=[
                EvidenceItem(
                    source_tool=candidate.source.tool,
                    ref=candidate.source.ref,
                    excerpt=candidate.evidence_excerpt or "",
                )
            ],
            cta=data["cta"],
            excluded_claims=list(strategy.excluded_claims),
            score=candidate.total_score,
        )

    def select_and_brief(
        self,
        snapshot: ContextSnapshot,
        strategy: MonthlyStrategy,
        n: int = 3,
        recent_topics: frozenset[str] = frozenset(),
    ) -> list[Brief]:
        scored = score_candidates(snapshot, recent_topics=recent_topics)
        chosen = top_candidates(scored, n=n)
        return [self.expand_to_brief(c, strategy) for c in chosen]
