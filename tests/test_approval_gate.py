import pytest

from sns_marketing_agent.approval_gate import ApprovalGate
from sns_marketing_agent.models import ApprovalStatus, Channel, ContentBrief, ContentDraft


def make_draft():
    brief = ContentBrief(
        client_id="client-1",
        channel=Channel.NAVER_BLOG,
        topic="topic",
        angle="angle",
        source_evidence=["evidence"],
    )
    return ContentDraft(brief=brief, title="title", body="body")


def test_submit_starts_pending():
    gate = ApprovalGate()
    record = gate.submit(make_draft())
    assert record.status == ApprovalStatus.PENDING
    assert gate.pending() == [record]


def test_approve_moves_out_of_pending():
    gate = ApprovalGate()
    record = gate.submit(make_draft())
    gate.approve(record, reviewer="대표")

    assert record.status == ApprovalStatus.APPROVED
    assert record.reviewer == "대표"
    assert record.reviewed_at is not None
    assert gate.pending() == []


def test_reject_records_notes():
    gate = ApprovalGate()
    record = gate.submit(make_draft())
    gate.reject(record, reviewer="대표", notes="톤이 너무 홍보성")

    assert record.status == ApprovalStatus.REJECTED
    assert record.notes == "톤이 너무 홍보성"


def test_approve_unknown_record_raises():
    gate = ApprovalGate()
    other_gate_record = ApprovalGate().submit(make_draft())
    with pytest.raises(ValueError):
        gate.approve(other_gate_record, reviewer="대표")
