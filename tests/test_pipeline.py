import json
from pathlib import Path

from sns_marketing_agent.history_collector import StaticHistorySource
from sns_marketing_agent.llm_client import TemplateLLMClient
from sns_marketing_agent.models import ApprovalStatus, Channel
from sns_marketing_agent.pipeline import run_pipeline

FIXTURE = (
    Path(__file__).parent.parent
    / "sns_marketing_agent"
    / "fixtures"
    / "sample_client_history.json"
)


class ConfigurableLLMClient:
    """Same marker convention as TemplateLLMClient, but a settable brief count
    so pipeline wiring of `briefs_per_channel` can be tested independently of
    what a real model happens to return.
    """

    def __init__(self, brief_count: int):
        self._brief_count = brief_count

    def complete(self, prompt: str) -> str:
        if "JSON 배열" in prompt:
            items = [
                {"topic": f"topic-{i}", "angle": f"angle-{i}", "source_evidence": ["e"]}
                for i in range(self._brief_count)
            ]
            return json.dumps(items, ensure_ascii=False)
        return json.dumps({"title": "t", "body": "b", "hashtags": []}, ensure_ascii=False)


def test_run_pipeline_produces_one_pending_record_per_channel():
    records = run_pipeline(
        client_id="demo-bakery",
        channels=[Channel.NAVER_BLOG, Channel.INSTAGRAM, Channel.YOUTUBE],
        history_source=StaticHistorySource(FIXTURE),
        llm=TemplateLLMClient(),
        briefs_per_channel=1,
    )

    assert len(records) == 3
    assert {r.draft.brief.channel for r in records} == set(Channel)
    assert all(r.status == ApprovalStatus.PENDING for r in records)


def test_run_pipeline_produces_one_record_per_brief_returned():
    records = run_pipeline(
        client_id="demo-bakery",
        channels=[Channel.NAVER_BLOG],
        history_source=StaticHistorySource(FIXTURE),
        llm=ConfigurableLLMClient(brief_count=2),
        briefs_per_channel=2,
    )

    assert len(records) == 2
