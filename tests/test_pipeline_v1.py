"""End-to-end F1->F5 smoke test, entirely against real recorded
supernova-platform data + the deterministic offline LLM stub — same
"can run with no network/API key" guarantee the old prototype's pipeline
test gave, now for PRD v1.0's flow."""
from sns_marketing_agent.carousel_renderer import NullCarouselRenderer
from sns_marketing_agent.cofounder_client import ReadOnlyCofounderClient
from sns_marketing_agent.cofounder_fixture_transport import FixtureMCPCaller
from sns_marketing_agent.masking_filter import MaskingFilter, extract_protected_terms
from sns_marketing_agent.pipeline_v1 import run_pipeline
from sns_marketing_agent.review_models import ReasonCode
from sns_marketing_agent.review_queue import ReviewQueue
from sns_marketing_agent.template_llm_v1 import TemplateLLMClientV1

CLIENT_SLUG = "supernova-platform"


def build_dependencies():
    co_client = ReadOnlyCofounderClient(FixtureMCPCaller(client_slug=CLIENT_SLUG))
    clients_resp = co_client.list_clients()
    terms = extract_protected_terms(clients_resp, exclude_slug=CLIENT_SLUG)
    masking_filter = MaskingFilter(terms)
    review_queue = ReviewQueue()
    return co_client, masking_filter, review_queue


def test_run_pipeline_end_to_end_produces_pending_reviews():
    co_client, masking_filter, review_queue = build_dependencies()

    run = run_pipeline(
        client_slug=CLIENT_SLUG,
        month="2026-09",
        co_client=co_client,
        llm=TemplateLLMClientV1(),
        renderer=NullCarouselRenderer(),
        masking_filter=masking_filter,
        instagram_base_url="https://spnv.jengablock.com",
        review_queue=review_queue,
    )

    assert run.snapshot.client_slug == CLIENT_SLUG
    assert run.strategy.client_slug == CLIENT_SLUG
    assert 1 <= len(run.briefs) <= 3
    for brief in run.briefs:
        assert brief.evidence  # every brief carries real evidence (F3 disqualifies otherwise)
        creatives = run.creatives_by_brief[brief.id]
        assert len(creatives) == 3

    pending = review_queue.pending(CLIENT_SLUG)
    assert len(pending) == sum(len(c) for c in run.creatives_by_brief.values())


def test_run_pipeline_only_calls_allowed_co_mcp_tools():
    co_client, masking_filter, review_queue = build_dependencies()
    run_pipeline(
        client_slug=CLIENT_SLUG,
        month="2026-09",
        co_client=co_client,
        llm=TemplateLLMClientV1(),
        renderer=NullCarouselRenderer(),
        masking_filter=masking_filter,
        instagram_base_url="https://spnv.jengablock.com",
        review_queue=review_queue,
    )
    called = {e.tool for e in co_client.call_log.entries}
    assert called <= {
        "system_map_rules",
        "system_map_weight",
        "system_map_changes",
        "list_documents",
        "list_clients",
    }
    assert all(e.allowed for e in co_client.call_log.entries)


def test_approving_and_rejecting_reviews_moves_them_out_of_pending():
    co_client, masking_filter, review_queue = build_dependencies()
    run = run_pipeline(
        client_slug=CLIENT_SLUG,
        month="2026-09",
        co_client=co_client,
        llm=TemplateLLMClientV1(),
        renderer=NullCarouselRenderer(),
        masking_filter=masking_filter,
        instagram_base_url="https://spnv.jengablock.com",
        review_queue=review_queue,
    )
    pending = review_queue.pending(CLIENT_SLUG)
    review_queue.approve(pending[0].id, reviewer="STan")
    review_queue.reject(pending[1].id, reviewer="STan", reason_codes=[ReasonCode.R4])

    still_pending = review_queue.pending(CLIENT_SLUG)
    assert pending[0].id not in {r.id for r in still_pending}
    assert pending[1].id not in {r.id for r in still_pending}
    assert len(still_pending) == len(pending) - 2
    assert run.client_slug == CLIENT_SLUG  # run object still usable after review actions


def test_rejection_patterns_feed_back_into_the_next_run():
    co_client, masking_filter, review_queue = build_dependencies()
    run1 = run_pipeline(
        client_slug=CLIENT_SLUG, month="2026-09", co_client=co_client, llm=TemplateLLMClientV1(),
        renderer=NullCarouselRenderer(), masking_filter=masking_filter,
        instagram_base_url="https://spnv.jengablock.com", review_queue=review_queue,
    )
    for record in review_queue.pending(CLIENT_SLUG):
        review_queue.reject(record.id, reviewer="STan", reason_codes=[ReasonCode.R4])

    patterns = review_queue.recent_rejection_patterns(CLIENT_SLUG)
    assert ReasonCode.R4 in patterns

    # a second run should succeed with those patterns fed into the prompts
    # (TemplateLLMClientV1 ignores the extra text but a real LLM would see it)
    run2 = run_pipeline(
        client_slug=CLIENT_SLUG, month="2026-09", co_client=co_client, llm=TemplateLLMClientV1(),
        renderer=NullCarouselRenderer(), masking_filter=masking_filter,
        instagram_base_url="https://spnv.jengablock.com", review_queue=review_queue,
    )
    assert len(run2.briefs) >= 1
