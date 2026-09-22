"""C4 DoD: masking test must catch 100% of other-client-name insertions.
Uses the REAL recorded list_clients() response, not synthetic names."""
import json
from pathlib import Path

from sns_marketing_agent.masking_filter import MaskingFilter, extract_protected_terms

FIXTURE = (
    Path(__file__).parent.parent
    / "sns_marketing_agent"
    / "fixtures"
    / "cofounder_recorded"
    / "supernova-platform"
    / "list_clients.json"
)


def real_clients_resp():
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    data.pop("_recorded_at", None)
    data.pop("_note", None)
    return data


def test_extract_protected_terms_excludes_the_creative_owner_client():
    terms = extract_protected_terms(real_clients_resp(), exclude_slug="dodam")
    assert "dodam" not in terms
    # dodam's display name in the fixture is also "dodam" (slug==name), still excluded
    assert "celest" in terms
    assert "Celeste" in terms


def test_all_other_real_client_names_are_detected_100_percent():
    clients_resp = real_clients_resp()
    terms = extract_protected_terms(clients_resp, exclude_slug="dodam")
    other_names = [c["name"] for c in clients_resp["results"] if c["slug"] != "dodam"]

    filt = MaskingFilter(terms)
    caught = 0
    for name in other_names:
        text = f"이번 캠페인은 {name} 사례를 참고했습니다."
        hits = filt.scan(text)
        if name in hits:
            caught += 1

    assert caught == len(other_names)  # 100% detection — the C4 DoD


def test_own_client_name_is_never_flagged():
    terms = extract_protected_terms(real_clients_resp(), exclude_slug="dodam")
    filt = MaskingFilter(terms)
    hits = filt.scan("dodam 고객님께 안내드립니다.")
    assert hits == []


def test_amount_patterns_are_detected():
    filt = MaskingFilter(set())
    hits = filt.scan("월 250만원 계약으로 진행했습니다.")
    assert any("250만원" in h for h in hits)


def test_clean_text_has_no_hits_and_clean_status():
    terms = extract_protected_terms(real_clients_resp(), exclude_slug="dodam")
    filt = MaskingFilter(terms)
    status, hits = filt.status("제보가 도착하면 자동으로 분류됩니다.")
    assert status == "clean"
    assert hits == []


def test_flagged_status_when_any_text_has_a_hit():
    terms = extract_protected_terms(real_clients_resp(), exclude_slug="dodam")
    filt = MaskingFilter(terms)
    status, hits = filt.status("caption 안전함", "slide 1", "celest 사례처럼요")
    assert status == "flagged"
    assert "celest" in hits


def test_mask_replaces_every_hit_with_block_characters():
    terms = extract_protected_terms(real_clients_resp(), exclude_slug="dodam")
    filt = MaskingFilter(terms)
    masked, hits = filt.mask("celest 사례를 참고했고 월 250만원 계약이었습니다.")
    assert "celest" not in masked
    assert "250만원" not in masked
    assert hits  # non-empty
