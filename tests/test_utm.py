import pytest

from sns_marketing_agent.utm import build_utm_url


def test_builds_expected_query_params():
    url = build_utm_url("https://dodamfood.kr", "organic", "202609", "증거형", "creative-1")
    assert url.startswith("https://dodamfood.kr?")
    assert "utm_source=instagram" in url
    assert "utm_medium=organic" in url
    assert "utm_content=creative-1" in url
    assert "utm_campaign=202609_" in url  # pillar is URL-encoded (Korean)


def test_appends_with_ampersand_when_base_url_already_has_query():
    url = build_utm_url("https://dodamfood.kr?ref=ig", "paid", "202609", "pillar", "c1")
    assert url.startswith("https://dodamfood.kr?ref=ig&")


def test_rejects_invalid_medium():
    with pytest.raises(ValueError):
        build_utm_url("https://dodamfood.kr", "email", "202609", "pillar", "c1")
