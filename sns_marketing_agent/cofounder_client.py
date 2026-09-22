"""Read-only gate onto co-mcp (Cofounder's MCP server) — PRD v1.0 §6.2, constraint C1.

`ReadOnlyCofounderClient` is the ONLY way any other module in this package may
reach co-mcp. It never touches the network itself — that's `MCPToolCaller`'s
job (a real transport in cofounder_mcp_transport.py, or a recorded fixture for
tests/offline runs) — it only decides whether a call is allowed and logs every
attempt, allowed or not. Nothing downstream of this gate needs to re-check C1;
they can't reach a disallowed tool at all.

`system_map_weight` is special-cased to always call with `measure=False`
regardless of what a caller passes — its default is `measure=True`, which
re-measures the map, and whether that re-measurement writes to the map is
unconfirmed (PRD §6.2, Q2). Fixing `measure=False` here is the safe side
until that's confirmed, not a caller-facing option.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

ALLOWED_TOOLS = frozenset(
    {
        "system_map_rules",
        "system_map_weight",
        "system_map_changes",
        "list_documents",
        "search_documents",
        "read_document",
        "list_document_versions",
        "get_roadmap",
        "get_feature_evidence",
        "list_clients",
        "list_ventures",
        "list_domains",
    }
)


class ToolNotAllowedError(Exception):
    def __init__(self, tool: str):
        super().__init__(f"{tool!r} is not on the read-only allowlist (PRD C1)")
        self.tool = tool


@dataclass
class McpCallRecord:
    tool: str
    args_hash: str
    allowed: bool
    at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class McpCallLog(Protocol):
    """Audit trail for C1: every call attempt, allowed or not."""

    def record(self, entry: McpCallRecord) -> None: ...


class InMemoryCallLog:
    def __init__(self) -> None:
        self.entries: list[McpCallRecord] = []

    def record(self, entry: McpCallRecord) -> None:
        self.entries.append(entry)


class MCPToolCaller(Protocol):
    """The transport boundary. A real network client and a recorded-fixture
    reader both satisfy this without either knowing about the other."""

    def call(self, tool: str, **kwargs: Any) -> dict: ...


def _args_hash(kwargs: dict) -> str:
    payload = json.dumps(kwargs, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


class ReadOnlyCofounderClient:
    def __init__(self, caller: MCPToolCaller, call_log: McpCallLog | None = None):
        self._caller = caller
        self._call_log = call_log if call_log is not None else InMemoryCallLog()

    @property
    def call_log(self) -> McpCallLog:
        return self._call_log

    def call(self, tool: str, **kwargs: Any) -> dict:
        if tool == "system_map_weight":
            kwargs["measure"] = False

        allowed = tool in ALLOWED_TOOLS
        self._call_log.record(McpCallRecord(tool=tool, args_hash=_args_hash(kwargs), allowed=allowed))
        if not allowed:
            raise ToolNotAllowedError(tool)
        return self._caller.call(tool, **kwargs)

    # -- Convenience wrappers, one per allowed tool -----------------------
    def system_map_rules(self, client: str) -> dict:
        return self.call("system_map_rules", client=client)

    def system_map_weight(self, client: str) -> dict:
        return self.call("system_map_weight", client=client)

    def system_map_changes(self, client: str, days: int = 30) -> dict:
        return self.call("system_map_changes", client=client, days=days)

    def list_documents(self, **kwargs: Any) -> dict:
        return self.call("list_documents", **kwargs)

    def search_documents(self, query: str, **kwargs: Any) -> dict:
        return self.call("search_documents", query=query, **kwargs)

    def read_document(self, id_or_path: str) -> dict:
        return self.call("read_document", id_or_path=id_or_path)

    def list_document_versions(self, id_or_path: str) -> dict:
        return self.call("list_document_versions", id_or_path=id_or_path)

    def get_roadmap(self, client: str, **kwargs: Any) -> dict:
        return self.call("get_roadmap", client=client, **kwargs)

    def get_feature_evidence(self, feature_id: int, client: str) -> dict:
        return self.call("get_feature_evidence", feature_id=feature_id, client=client)

    def list_clients(self, **kwargs: Any) -> dict:
        return self.call("list_clients", **kwargs)

    def list_ventures(self, **kwargs: Any) -> dict:
        return self.call("list_ventures", **kwargs)

    def list_domains(self, client: str) -> dict:
        return self.call("list_domains", client=client)
