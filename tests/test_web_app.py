"""Tests for the client-facing approval-queue frontend (web/app.py).

Every test gets a fresh in-memory ApprovalGate seeded with the demo fixture,
via NullImageGenerator so no browser/Playwright is required here — the real
PlaywrightCardRenderer path is covered separately in test_image_generator.py.
"""
import pytest
from fastapi.testclient import TestClient

from sns_marketing_agent.approval_gate import ApprovalGate
from sns_marketing_agent.image_generator import NullImageGenerator

import web.app as web_app


@pytest.fixture
def client(monkeypatch):
    fresh_gate = ApprovalGate()
    monkeypatch.setattr(web_app, "gate", fresh_gate)
    monkeypatch.setattr(web_app, "_build_image_generator", lambda: NullImageGenerator())
    web_app._seed_demo_content_sync()

    test_client = TestClient(web_app.app)
    test_client.gate = fresh_gate
    return test_client


def test_root_redirects_to_demo_client(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"].endswith("/clients/demo-bakery")


def test_client_queue_lists_seeded_pending_content(client):
    response = client.get("/clients/demo-bakery")
    assert response.status_code == 200
    assert "SNS 콘텐츠 승인함" in response.text
    assert len(client.gate.pending(client_id="demo-bakery")) == 3


def test_null_image_generator_renders_placeholder_not_broken_img(client):
    response = client.get("/clients/demo-bakery")
    assert "이미지 미리보기 없음" in response.text


def test_unknown_client_shows_empty_state_not_error(client):
    response = client.get("/clients/some-other-client")
    assert response.status_code == 200
    assert "대기 중인 콘텐츠가 없습니다" in response.text


def test_approve_moves_record_out_of_pending(client):
    record = client.gate.pending(client_id="demo-bakery")[0]

    response = client.post(
        f"/records/{record.id}/approve", data={"reviewer": "대표"}, follow_redirects=False
    )

    assert response.status_code == 303
    updated = client.gate.get(record.id)
    assert updated.status.value == "approved"
    assert updated.reviewer == "대표"
    assert record.id not in {r.id for r in client.gate.pending(client_id="demo-bakery")}


def test_reject_records_notes(client):
    record = client.gate.pending(client_id="demo-bakery")[0]

    response = client.post(
        f"/records/{record.id}/reject",
        data={"reviewer": "대표", "notes": "톤 재검토 필요"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    updated = client.gate.get(record.id)
    assert updated.status.value == "rejected"
    assert updated.notes == "톤 재검토 필요"


def test_approve_unknown_record_returns_404(client):
    response = client.post("/records/does-not-exist/approve", data={"reviewer": "대표"})
    assert response.status_code == 404


def test_blank_reviewer_falls_back_to_default(client):
    record = client.gate.pending(client_id="demo-bakery")[0]

    client.post(f"/records/{record.id}/approve", data={"reviewer": "  "})

    assert client.gate.get(record.id).reviewer == "대표"
