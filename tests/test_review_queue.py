from datetime import datetime, timedelta, timezone

import pytest

from sns_marketing_agent.review_models import CreativeStatus, ReasonCode, RubricScore
from sns_marketing_agent.review_queue import ReviewQueue


def make_rubric(total=80):
    return RubricScore(
        evidence_fit=20, factual_accuracy=15, persona_resonance=15, hook_strength=10,
        format_compliance=10, masking=10, total=total,
    )


def test_submit_starts_pending_review():
    queue = ReviewQueue()
    record = queue.submit("supernova-platform", "creative-1", "brief-1", make_rubric())
    assert record.status == CreativeStatus.PENDING_REVIEW
    assert queue.pending("supernova-platform") == [record]


def test_approve_moves_out_of_pending():
    queue = ReviewQueue()
    record = queue.submit("supernova-platform", "creative-1", "brief-1", make_rubric())
    queue.approve(record.id, reviewer="STan")

    updated = queue.reviewed("supernova-platform")[0]
    assert updated.status == CreativeStatus.APPROVED
    assert updated.reviewer == "STan"
    assert updated.reviewed_at is not None
    assert queue.pending("supernova-platform") == []


def test_reject_requires_at_least_one_reason_code():
    queue = ReviewQueue()
    record = queue.submit("supernova-platform", "creative-1", "brief-1", make_rubric())
    with pytest.raises(ValueError):
        queue.reject(record.id, reviewer="STan", reason_codes=[])


def test_reject_records_codes_and_note():
    queue = ReviewQueue()
    record = queue.submit("supernova-platform", "creative-1", "brief-1", make_rubric())
    queue.reject(record.id, reviewer="STan", reason_codes=[ReasonCode.R1, ReasonCode.R4], note="근거가 약함")

    updated = queue.reviewed("supernova-platform")[0]
    assert updated.status == CreativeStatus.REJECTED
    assert updated.reason_codes == [ReasonCode.R1, ReasonCode.R4]
    assert updated.note == "근거가 약함"


def test_recent_rejection_patterns_ranks_by_frequency():
    queue = ReviewQueue()
    for _ in range(3):
        r = queue.submit("supernova-platform", "c", "b", make_rubric())
        queue.reject(r.id, reviewer="STan", reason_codes=[ReasonCode.R1])
    for _ in range(1):
        r = queue.submit("supernova-platform", "c", "b", make_rubric())
        queue.reject(r.id, reviewer="STan", reason_codes=[ReasonCode.R4])

    patterns = queue.recent_rejection_patterns("supernova-platform", days=30, top_n=3)
    assert patterns[0] == ReasonCode.R1  # most frequent first
    assert ReasonCode.R4 in patterns


def test_recent_rejection_patterns_ignores_old_rejections():
    queue = ReviewQueue()
    r = queue.submit("supernova-platform", "c", "b", make_rubric())
    queue.reject(r.id, reviewer="STan", reason_codes=[ReasonCode.R1])
    # backdate it past the 30-day window
    stored = queue.reviewed("supernova-platform")[0]
    stored.reviewed_at = datetime.now(timezone.utc) - timedelta(days=45)

    patterns = queue.recent_rejection_patterns("supernova-platform", days=30, top_n=3)
    assert patterns == []


def test_recent_rejection_patterns_ignores_approved_records():
    queue = ReviewQueue()
    r = queue.submit("supernova-platform", "c", "b", make_rubric())
    queue.approve(r.id, reviewer="STan")

    patterns = queue.recent_rejection_patterns("supernova-platform")
    assert patterns == []


def test_pending_and_reviewed_are_scoped_by_client():
    queue = ReviewQueue()
    a = queue.submit("client-a", "c1", "b1", make_rubric())
    b = queue.submit("client-b", "c2", "b2", make_rubric())
    queue.approve(b.id, reviewer="STan")

    assert queue.pending("client-a") == [a]
    assert queue.pending("client-b") == []
    assert len(queue.reviewed("client-b")) == 1
