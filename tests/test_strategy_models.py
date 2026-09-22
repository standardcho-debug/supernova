import pytest

from sns_marketing_agent.strategy_models import Brief, EvidenceItem


def _brief_kwargs(**overrides):
    kwargs = dict(
        client_slug="supernova-platform",
        channel="instagram",
        topic="t",
        angle="a",
        pillar="증거형",
        target_persona="p",
        hook_125="h",
        key_messages=["m1"],
        evidence=[EvidenceItem(source_tool="system_map_rules", ref="triage#rule71", excerpt="처분을 고른다")],
        cta="cta",
    )
    kwargs.update(overrides)
    return kwargs


def test_brief_requires_at_least_one_evidence_item():
    with pytest.raises(ValueError):
        Brief(**_brief_kwargs(evidence=[]))


def test_brief_rejects_more_than_three_key_messages():
    with pytest.raises(ValueError):
        Brief(**_brief_kwargs(key_messages=["a", "b", "c", "d"]))


def test_brief_constructs_with_valid_fields():
    brief = Brief(**_brief_kwargs())
    assert brief.evidence[0].excerpt == "처분을 고른다"
    assert brief.id
