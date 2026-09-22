"""Offline MCPToolCaller backed by recorded real co-mcp responses.

Every file under fixtures/cofounder_recorded/<client>/ is a REAL response
captured from co-mcp against supernova-platform (trimmed for size where
noted in each file's `_note`), not synthesized data. This is what PRD
§7 "Claude Code 작업 규칙" calls a 녹화 픽스처 — it lets ContextEngine and
its tests run deterministically, without network or the co-mcp auth this
prototype doesn't have yet (PRD §9 Q1).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DEFAULT_FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "cofounder_recorded"


class FixtureNotFoundError(Exception):
    pass


class FixtureMCPCaller:
    def __init__(self, client_slug: str, fixture_root: Path | None = None):
        root = fixture_root if fixture_root is not None else DEFAULT_FIXTURE_ROOT
        self._dir = Path(root) / client_slug

    def call(self, tool: str, **kwargs: Any) -> dict:
        if tool == "read_document":
            path = self._dir / "read_document" / f"{kwargs['id_or_path']}.json"
        else:
            path = self._dir / f"{tool}.json"

        if not path.exists():
            raise FixtureNotFoundError(
                f"no recorded fixture for tool={tool!r} kwargs={kwargs!r} at {path}"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        data.pop("_recorded_at", None)
        data.pop("_note", None)
        return data
