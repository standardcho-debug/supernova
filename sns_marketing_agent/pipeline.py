"""Wires stages 1-4 together. Stage 5 (publishing) is intentionally absent."""
from __future__ import annotations

import argparse
from pathlib import Path

from .approval_gate import ApprovalGate
from .brief_generator import BriefGenerator
from .draft_generator import DraftGenerator
from .history_collector import HistorySource
from .llm_client import LLMClient
from .models import ApprovalRecord, Channel


def run_pipeline(
    client_id: str,
    channels: list[Channel],
    history_source: HistorySource,
    llm: LLMClient,
    briefs_per_channel: int = 1,
) -> list[ApprovalRecord]:
    profile = history_source.get_client_profile(client_id)
    brief_gen = BriefGenerator(llm)
    draft_gen = DraftGenerator(llm)
    gate = ApprovalGate()

    records = []
    for channel in channels:
        briefs = brief_gen.generate(profile, channel, n=briefs_per_channel)
        for brief in briefs:
            draft = draft_gen.generate(profile, brief)
            records.append(gate.submit(draft))
    return records


def _demo() -> None:
    from .history_collector import StaticHistorySource
    from .llm_client import TemplateLLMClient

    fixture = Path(__file__).parent / "fixtures" / "sample_client_history.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-id", default="demo-bakery")
    parser.add_argument(
        "--channels",
        nargs="+",
        default=[c.value for c in Channel],
        choices=[c.value for c in Channel],
    )
    args = parser.parse_args()

    records = run_pipeline(
        client_id=args.client_id,
        channels=[Channel(c) for c in args.channels],
        history_source=StaticHistorySource(fixture),
        llm=TemplateLLMClient(),
    )
    for record in records:
        print(f"[{record.status.value}] {record.draft.brief.channel.value}: {record.draft.title}")


if __name__ == "__main__":
    _demo()
