import json

import pytest

from sns_marketing_agent.creative_models import Creative, ResizedAsset, Slide
from sns_marketing_agent.rubric_scorer import RubricScorer
from sns_marketing_agent.strategy_models import Brief, EvidenceItem


class FakeLLMClient:
    def __init__(self, response: str):
        self._response = response
        self.last_prompt: str | None = None

    def complete(self, prompt: str) -> str:
        self.last_prompt = prompt
        return self._response


def make_brief():
    return Brief(
        client_slug="supernova-platform",
        channel="instagram",
        topic="t",
        angle="a",
        pillar="증거형",
        target_persona="운영팀",
        hook_125="훅",
        key_messages=["m1", "m2"],
        evidence=[EvidenceItem(source_tool="system_map_rules", ref="triage#rule71", excerpt="처분을 고른다")],
        cta="cta",
    )


def make_creative(mask_status="clean", hashtags=None, hook_text="짧은 훅"):
    slides = [Slide(order=i, text=t, image_path="") for i, t in enumerate(
        [hook_text, "메시지 1", "메시지 2", "메시지 3", "요약"]
    )]
    return Creative(
        brief_id="b1",
        variant=1,
        caption="캡션",
        hashtags=hashtags if hashtags is not None else ["a", "b", "c"],
        slides=slides,
        resized=[ResizedAsset(aspect="1:1", slides=[""] * 5), ResizedAsset(aspect="9:16", slides=[""] * 5)],
        utm_url="https://x?y=1",
        mask_status=mask_status,
    )


def llm_response(**overrides):
    data = {"evidence_fit": 20, "factual_accuracy": 15, "persona_resonance": 15, "hook_strength": 10}
    data.update(overrides)
    return json.dumps(data, ensure_ascii=False)


def test_masking_flagged_forces_zero_masking_score_regardless_of_llm():
    scorer = RubricScorer(FakeLLMClient(llm_response()))
    score = scorer.score(make_creative(mask_status="flagged"), make_brief())
    assert score.masking == 0


def test_masking_clean_gives_full_ten():
    scorer = RubricScorer(FakeLLMClient(llm_response()))
    score = scorer.score(make_creative(mask_status="clean"), make_brief())
    assert score.masking == 10


def test_format_compliance_full_when_all_checks_pass():
    scorer = RubricScorer(FakeLLMClient(llm_response()))
    score = scorer.score(make_creative(hashtags=["a", "b", "c"]), make_brief())
    assert score.format_compliance == 10


def test_format_compliance_penalized_when_hashtags_out_of_range():
    scorer = RubricScorer(FakeLLMClient(llm_response()))
    score = scorer.score(make_creative(hashtags=["only-one"]), make_brief())
    assert score.format_compliance < 10


def test_llm_scores_are_clamped_to_their_max_even_if_llm_overshoots():
    scorer = RubricScorer(FakeLLMClient(llm_response(evidence_fit=999, hook_strength=-5)))
    score = scorer.score(make_creative(), make_brief())
    assert score.evidence_fit == 25
    assert score.hook_strength == 0


def test_total_is_sum_of_all_six_components():
    scorer = RubricScorer(FakeLLMClient(llm_response()))
    score = scorer.score(make_creative(mask_status="clean"), make_brief())
    assert score.total == (
        score.evidence_fit
        + score.factual_accuracy
        + score.persona_resonance
        + score.hook_strength
        + score.format_compliance
        + score.masking
    )


def test_prompt_includes_real_evidence_and_slide_text():
    llm = FakeLLMClient(llm_response())
    RubricScorer(llm).score(make_creative(), make_brief())
    assert "처분을 고른다" in llm.last_prompt
    assert "메시지 1" in llm.last_prompt


def test_non_json_llm_output_raises_value_error():
    scorer = RubricScorer(FakeLLMClient("이건 JSON이 아닙니다"))
    with pytest.raises(ValueError):
        scorer.score(make_creative(), make_brief())
