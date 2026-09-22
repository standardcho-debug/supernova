"""F2 Monthly Strategy — PRD v1.0 §5.2.

Derives a month's goal + content pillars from the context snapshot (C2: no
separate profit-equation input). The LLM only writes the Korean sentences —
which changes/promises/gaps feed it is decided in code, so the output is
never grounded in anything the snapshot didn't already contain.
"""
from __future__ import annotations

import json

from sns_marketing_agent.context_models import ContextSnapshot
from sns_marketing_agent.llm_client import LLMClient
from sns_marketing_agent.strategy_models import MonthlyStrategy, Pillar

DEFAULT_CALENDAR_PER_WEEK = 3  # PRD §5.2 default, explicitly ⚠️미정 — not a settled decision
_CUSTOMER_FACING_LANE = "고객·외부"


def _build_prompt(client_slug: str, changes: list, promises: list, excluded: list[str]) -> str:
    change_lines = "\n".join(f"- {c.summary}" for c in changes) or "(없음)"
    promise_lines = "\n".join(f"- {p.rule_title}" for p in promises) or "(없음)"
    excluded_lines = "\n".join(f"- {e}" for e in excluded) or "(없음)"
    return (
        f"고객사 '{client_slug}'의 이번 달 콘텐츠 전략을 세운다.\n\n"
        f"최근 30일 고객 체감 변화:\n{change_lines}\n\n"
        f"차별화 약속(이미 지키고 있는 것):\n{promise_lines}\n\n"
        f"아직 측정·검증되지 않아 말하면 안 되는 것:\n{excluded_lines}\n\n"
        "위 사실만 근거로 월 목표 문장 1개와, 콘텐츠 필러 3종(예: 증거형/교육형/공감형 — "
        "이름은 자유롭게 붙이되 3개 합이 1.0이 되는 비율)을 JSON으로 출력하라. "
        '형식: {"goal": "...", "pillars": [{"name": "...", "ratio": 0.4}, ...]}. '
        "위에 없는 사실을 새로 만들지 말 것."
    )


class StrategyPlanner:
    def __init__(self, llm: LLMClient):
        self._llm = llm

    def build_strategy(
        self,
        snapshot: ContextSnapshot,
        month: str,
        calendar_per_week: int = DEFAULT_CALENDAR_PER_WEEK,
        max_promises: int = 3,
    ) -> MonthlyStrategy:
        facing_keys = {c.key for c in snapshot.customer_facing_cells}
        customer_changes = [c for c in snapshot.recent_changes if c.node_key in facing_keys]
        top_promises = snapshot.promises[:max_promises]
        excluded = sorted({g.label for g in snapshot.gaps if g.reason == "unmeasured"})

        prompt = _build_prompt(snapshot.client_slug, customer_changes, top_promises, excluded)
        raw = self._llm.complete(prompt)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"strategy planner got non-JSON output for {snapshot.client_slug}: {raw[:200]!r}"
            ) from exc

        return MonthlyStrategy(
            client_slug=snapshot.client_slug,
            month=month,
            goal=data["goal"],
            pillars=[Pillar(name=p["name"], ratio=p["ratio"]) for p in data["pillars"]],
            calendar_per_week=calendar_per_week,
            source_changes=[c.source for c in customer_changes],
            source_promises=[p.source for p in top_promises],
            excluded_claims=excluded,
        )
