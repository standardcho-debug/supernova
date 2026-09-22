from sns_marketing_agent.review_models import CreativeStatus, ReasonCode, RubricScore
from sns_marketing_agent.review_queue import ReviewQueue
from web.review_store import SqliteReviewStore


def make_rubric():
    return RubricScore(
        evidence_fit=20, factual_accuracy=15, persona_resonance=15, hook_strength=10,
        format_compliance=10, masking=10, total=80,
    )


def test_save_and_get_round_trips_through_sqlite(tmp_path):
    store = SqliteReviewStore(tmp_path / "reviews.db")
    queue = ReviewQueue(store)

    record = queue.submit("supernova-platform", "creative-1", "brief-1", make_rubric())
    reloaded = store.get(record.id)

    assert reloaded.creative_id == "creative-1"
    assert reloaded.rubric.total == 80
    assert reloaded.status == CreativeStatus.PENDING_REVIEW


def test_reject_persists_reason_codes_across_a_fresh_store_instance(tmp_path):
    db_path = tmp_path / "reviews.db"
    store1 = SqliteReviewStore(db_path)
    queue1 = ReviewQueue(store1)
    record = queue1.submit("supernova-platform", "creative-1", "brief-1", make_rubric())
    queue1.reject(record.id, reviewer="STan", reason_codes=[ReasonCode.R1, ReasonCode.R6], note="마스킹 문제")

    # simulate a process restart: fresh store instance, same file
    store2 = SqliteReviewStore(db_path)
    reloaded = store2.get(record.id)
    assert reloaded.status == CreativeStatus.REJECTED
    assert reloaded.reason_codes == [ReasonCode.R1, ReasonCode.R6]
    assert reloaded.note == "마스킹 문제"


def test_pending_and_reviewed_scoped_by_client_after_reload(tmp_path):
    store = SqliteReviewStore(tmp_path / "reviews.db")
    queue = ReviewQueue(store)
    a = queue.submit("client-a", "c1", "b1", make_rubric())
    queue.submit("client-b", "c2", "b2", make_rubric())
    queue.approve(a.id, reviewer="STan")

    fresh_store = SqliteReviewStore(tmp_path / "reviews.db")
    assert len(fresh_store.pending("client-b")) == 1
    assert len(fresh_store.reviewed("client-a")) == 1
    assert fresh_store.pending("client-a") == []
