import pytest

from sns_marketing_agent.approval_gate import ApprovalGate
from sns_marketing_agent.models import ApprovalStatus, Channel, ContentBrief, ContentDraft


def make_draft(client_id="client-1"):
    brief = ContentBrief(
        client_id=client_id,
        channel=Channel.NAVER_BLOG,
        topic="topic",
        angle="angle",
        source_evidence=["evidence"],
    )
    return ContentDraft(brief=brief, title="title", body="body")


def test_submit_starts_pending_and_has_stable_id():
    gate = ApprovalGate()
    record = gate.submit(make_draft())
    assert record.status == ApprovalStatus.PENDING
    assert gate.pending() == [record]
    assert gate.get(record.id) is record


def test_approve_moves_out_of_pending():
    gate = ApprovalGate()
    record = gate.submit(make_draft())
    gate.approve(record.id, reviewer="대표")

    updated = gate.get(record.id)
    assert updated.status == ApprovalStatus.APPROVED
    assert updated.reviewer == "대표"
    assert updated.reviewed_at is not None
    assert gate.pending() == []
    assert gate.reviewed() == [updated]


def test_reject_records_notes():
    gate = ApprovalGate()
    record = gate.submit(make_draft())
    gate.reject(record.id, reviewer="대표", notes="톤이 너무 홍보성")

    updated = gate.get(record.id)
    assert updated.status == ApprovalStatus.REJECTED
    assert updated.notes == "톤이 너무 홍보성"


def test_approve_unknown_id_raises_key_error():
    gate = ApprovalGate()
    with pytest.raises(KeyError):
        gate.approve("no-such-id", reviewer="대표")


def test_pending_and_reviewed_are_scoped_by_client_id():
    gate = ApprovalGate()
    a = gate.submit(make_draft(client_id="client-a"))
    b = gate.submit(make_draft(client_id="client-b"))
    gate.approve(b.id, reviewer="대표")

    assert gate.pending(client_id="client-a") == [a]
    assert gate.pending(client_id="client-b") == []
    assert gate.reviewed(client_id="client-b") == [gate.get(b.id)]
    assert gate.all(client_id="client-a") == [a]
