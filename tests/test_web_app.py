"""Tests for the client-facing approval-queue frontend (web/app.py).

Every test gets a fresh SqliteApprovalGate + ClientAccessStore backed by
tmp_path (so tests never share state or touch web/data/), seeded with the
demo fixture via NullImageGenerator so no browser/Playwright is required
here — the real PlaywrightCardRenderer path is covered separately in
test_image_generator.py.
"""
import pytest
from fastapi.testclient import TestClient

from sns_marketing_agent.image_generator import NullImageGenerator

import web.app as web_app
from web.access import ClientAccessStore
from web.sqlite_store import SqliteApprovalGate


@pytest.fixture
def client(monkeypatch, tmp_path):
    fresh_gate = SqliteApprovalGate(tmp_path / "approvals.db")
    fresh_access = ClientAccessStore(tmp_path / "access.db")
    monkeypatch.setattr(web_app, "gate", fresh_gate)
    monkeypatch.setattr(web_app, "access_store", fresh_access)
    monkeypatch.setattr(web_app, "_build_image_generator", lambda: NullImageGenerator())
    web_app._seed_demo_content_sync()

    test_client = TestClient(web_app.app)
    test_client.gate = fresh_gate
    test_client.access_store = fresh_access
    test_client.token = fresh_access.token_for(web_app.DEMO_CLIENT_ID)
    return test_client


def test_root_redirects_to_admin(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code in (302, 307)
    assert response.headers["location"].endswith("/admin")


def test_admin_page_lists_client_link_with_token(client):
    response = client.get("/admin")
    assert response.status_code == 200
    assert f"/clients/demo-bakery?token={client.token}" in response.text


def test_client_queue_requires_valid_token(client):
    no_token = client.get("/clients/demo-bakery")
    wrong_token = client.get("/clients/demo-bakery?token=not-the-real-token")

    assert no_token.status_code == 403
    assert wrong_token.status_code == 403


def test_unregistered_client_returns_403_not_empty_page(client):
    response = client.get("/clients/some-other-client?token=anything")
    assert response.status_code == 403


def test_registered_client_with_no_content_shows_empty_state(client):
    other_token = client.access_store.token_for("other-client")
    response = client.get(f"/clients/other-client?token={other_token}")
    assert response.status_code == 200
    assert "대기 중인 콘텐츠가 없습니다" in response.text


def test_client_queue_lists_seeded_pending_content(client):
    response = client.get(f"/clients/demo-bakery?token={client.token}")
    assert response.status_code == 200
    assert "SNS 콘텐츠 승인함" in response.text
    assert len(client.gate.pending(client_id="demo-bakery")) == 3


def test_null_image_generator_renders_placeholder_not_broken_img(client):
    response = client.get(f"/clients/demo-bakery?token={client.token}")
    assert "이미지 미리보기 없음" in response.text


def test_approve_moves_record_out_of_pending(client):
    record = client.gate.pending(client_id="demo-bakery")[0]

    response = client.post(
        f"/records/{record.id}/approve",
        data={"reviewer": "대표", "token": client.token},
        follow_redirects=False,
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
        data={"reviewer": "대표", "notes": "톤 재검토 필요", "token": client.token},
        follow_redirects=False,
    )

    assert response.status_code == 303
    updated = client.gate.get(record.id)
    assert updated.status.value == "rejected"
    assert updated.notes == "톤 재검토 필요"


def test_approve_with_wrong_token_returns_403_and_stays_pending(client):
    record = client.gate.pending(client_id="demo-bakery")[0]

    response = client.post(
        f"/records/{record.id}/approve",
        data={"reviewer": "대표", "token": "not-the-real-token"},
    )

    assert response.status_code == 403
    assert client.gate.get(record.id).status.value == "pending"


def test_approve_unknown_record_returns_404(client):
    response = client.post(
        "/records/does-not-exist/approve", data={"reviewer": "대표", "token": client.token}
    )
    assert response.status_code == 404


def test_blank_reviewer_falls_back_to_default(client):
    record = client.gate.pending(client_id="demo-bakery")[0]

    client.post(f"/records/{record.id}/approve", data={"reviewer": "  ", "token": client.token})

    assert client.gate.get(record.id).reviewer == "대표"


def test_state_survives_a_fresh_store_instance_pointed_at_the_same_file(tmp_path):
    """The whole point of SqliteApprovalGate: unlike ApprovalGate, a new
    instance reading the same file sees prior writes — i.e. survives a
    process restart."""
    db_path = tmp_path / "approvals.db"
    first = SqliteApprovalGate(db_path)
    from sns_marketing_agent.models import ContentBrief, ContentDraft, Channel

    brief = ContentBrief(
        client_id="client-1", channel=Channel.NAVER_BLOG, topic="t", angle="a", source_evidence=["e"]
    )
    record = first.submit(ContentDraft(brief=brief, title="title", body="body"))
    first.approve(record.id, reviewer="대표")

    second = SqliteApprovalGate(db_path)
    reloaded = second.get(record.id)
    assert reloaded.status.value == "approved"
    assert reloaded.reviewer == "대표"
