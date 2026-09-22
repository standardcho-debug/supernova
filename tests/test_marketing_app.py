"""Smoke tests for the Split-View marketing app (web/marketing_app.py) —
PRD v1.0 §6.4 / P1-d DoD: "STan이 로컬에서 1개월치 전략->승인까지 수행
가능." Runs entirely against the real recorded supernova-platform fixture +
the offline TemplateLLMClientV1 stub, same as tests/test_pipeline_v1.py, so
it needs no network or API key.

Every test gets a fresh review_queue/context_store/_state (module globals
monkeypatched to tmp_path-backed instances), same isolation pattern as
tests/test_web_app.py.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import web.marketing_app as marketing_app
from sns_marketing_agent.carousel_renderer import NullCarouselRenderer
from sns_marketing_agent.context_store import SqliteContextStore
from sns_marketing_agent.review_queue import ReviewQueue
from web.review_store import SqliteReviewStore

CLIENT_SLUG = "supernova-platform"
MONTH = "2026-09"


@pytest.fixture
def client(monkeypatch, tmp_path):
    fresh_queue = ReviewQueue(SqliteReviewStore(tmp_path / "reviews.db"))
    fresh_context_store = SqliteContextStore(tmp_path / "context.db")
    monkeypatch.setattr(marketing_app, "review_queue", fresh_queue)
    monkeypatch.setattr(marketing_app, "context_store", fresh_context_store)
    monkeypatch.setattr(marketing_app, "_state", {})
    monkeypatch.setattr(marketing_app, "_build_renderer", lambda: NullCarouselRenderer())
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    test_client = TestClient(marketing_app.app)
    test_client.review_queue = fresh_queue
    return test_client


def test_root_redirects_to_default_client(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert f"/clients/{CLIENT_SLUG}" in response.headers["location"]


def test_client_page_shows_draft_strategy_before_confirmation(client):
    response = client.get(f"/clients/{CLIENT_SLUG}?month={MONTH}")
    assert response.status_code == 200
    assert "초안 — 확인 전" in response.text
    assert "아직 생성된 브리프가 없습니다" in response.text


def test_generate_before_strategy_confirmed_is_rejected(client):
    client.get(f"/clients/{CLIENT_SLUG}?month={MONTH}")  # seeds F1/F2 state
    response = client.post(f"/clients/{CLIENT_SLUG}/generate", data={"month": MONTH})
    assert response.status_code == 400


def test_confirm_strategy_then_generate_produces_pending_reviews(client):
    client.get(f"/clients/{CLIENT_SLUG}?month={MONTH}")
    confirm = client.post(
        f"/clients/{CLIENT_SLUG}/strategy",
        data={"month": MONTH, "goal": "이번 달은 요청 접수 속도를 보여준다", "reviewer": "STan"},
        follow_redirects=False,
    )
    assert confirm.status_code == 303

    page_after_confirm = client.get(f"/clients/{CLIENT_SLUG}?month={MONTH}")
    assert "확인됨" in page_after_confirm.text
    assert "이번 달은 요청 접수 속도를 보여준다" in page_after_confirm.text

    generate = client.post(f"/clients/{CLIENT_SLUG}/generate", data={"month": MONTH}, follow_redirects=False)
    assert generate.status_code == 303

    pending = client.review_queue.pending(CLIENT_SLUG)
    assert pending  # at least one brief's worth of creatives
    assert len(pending) % 3 == 0  # 브리프당 3안

    page_after_generate = client.get(f"/clients/{CLIENT_SLUG}?month={MONTH}")
    assert "승인" in page_after_generate.text
    assert "반려" in page_after_generate.text


def test_approve_moves_record_out_of_pending(client):
    client.get(f"/clients/{CLIENT_SLUG}?month={MONTH}")
    client.post(
        f"/clients/{CLIENT_SLUG}/strategy",
        data={"month": MONTH, "goal": "g", "reviewer": "STan"},
    )
    client.post(f"/clients/{CLIENT_SLUG}/generate", data={"month": MONTH})
    record = client.review_queue.pending(CLIENT_SLUG)[0]

    response = client.post(
        f"/records/{record.id}/approve",
        data={"client_slug": CLIENT_SLUG, "month": MONTH, "reviewer": "STan"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert record.id not in {r.id for r in client.review_queue.pending(CLIENT_SLUG)}


def test_reject_without_reason_code_is_rejected(client):
    client.get(f"/clients/{CLIENT_SLUG}?month={MONTH}")
    client.post(f"/clients/{CLIENT_SLUG}/strategy", data={"month": MONTH, "goal": "g", "reviewer": "STan"})
    client.post(f"/clients/{CLIENT_SLUG}/generate", data={"month": MONTH})
    record = client.review_queue.pending(CLIENT_SLUG)[0]

    response = client.post(
        f"/records/{record.id}/reject",
        data={"client_slug": CLIENT_SLUG, "month": MONTH, "reviewer": "STan"},
    )
    assert response.status_code == 400


def test_reject_with_reason_code_records_it(client):
    client.get(f"/clients/{CLIENT_SLUG}?month={MONTH}")
    client.post(f"/clients/{CLIENT_SLUG}/strategy", data={"month": MONTH, "goal": "g", "reviewer": "STan"})
    client.post(f"/clients/{CLIENT_SLUG}/generate", data={"month": MONTH})
    record = client.review_queue.pending(CLIENT_SLUG)[0]

    response = client.post(
        f"/records/{record.id}/reject",
        data={
            "client_slug": CLIENT_SLUG,
            "month": MONTH,
            "reviewer": "STan",
            "reason_codes": ["R4"],
            "note": "훅이 약함",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303
    reviewed = {r.id: r for r in client.review_queue.reviewed(CLIENT_SLUG)}
    assert reviewed[record.id].status.value == "rejected"
    assert reviewed[record.id].note == "훅이 약함"


def test_regenerate_after_rejection_injects_avoid_patterns(client):
    client.get(f"/clients/{CLIENT_SLUG}?month={MONTH}")
    client.post(f"/clients/{CLIENT_SLUG}/strategy", data={"month": MONTH, "goal": "g", "reviewer": "STan"})
    client.post(f"/clients/{CLIENT_SLUG}/generate", data={"month": MONTH})
    for record in client.review_queue.pending(CLIENT_SLUG):
        client.post(
            f"/records/{record.id}/reject",
            data={"client_slug": CLIENT_SLUG, "month": MONTH, "reviewer": "STan", "reason_codes": ["R4"]},
        )

    assert not client.review_queue.pending(CLIENT_SLUG)

    regenerate = client.post(f"/clients/{CLIENT_SLUG}/generate", data={"month": MONTH}, follow_redirects=False)
    assert regenerate.status_code == 303
    assert client.review_queue.pending(CLIENT_SLUG)  # a fresh round was submitted
