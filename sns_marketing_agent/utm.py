"""UTM builder — PRD v1.0 §5.3.

utm_source=instagram&utm_medium={organic|paid}&utm_campaign={yyyymm}_{pillar}&utm_content={creative_id}
"""
from __future__ import annotations

from urllib.parse import urlencode

_VALID_MEDIA = ("organic", "paid")


def build_utm_url(base_url: str, medium: str, yyyymm: str, pillar: str, creative_id: str) -> str:
    if medium not in _VALID_MEDIA:
        raise ValueError(f"medium must be one of {_VALID_MEDIA}, got {medium!r}")

    params = {
        "utm_source": "instagram",
        "utm_medium": medium,
        "utm_campaign": f"{yyyymm}_{pillar}",
        "utm_content": creative_id,
    }
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}{urlencode(params)}"
