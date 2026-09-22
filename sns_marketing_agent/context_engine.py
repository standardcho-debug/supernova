"""F1 Context Engine — PRD v1.0 §5.1.

Turns a client's system map + recent documents into a ContextSnapshot: the
one normalized "what's actually going on at this company right now" object
that stages 2+ (strategy, briefs) build on. Read-only end to end — every
co-mcp call goes through ReadOnlyCofounderClient, so this module never sees
a write tool even by accident (C1).
"""
from __future__ import annotations

from datetime import datetime

from sns_marketing_agent.cofounder_client import ReadOnlyCofounderClient
from sns_marketing_agent.context_models import (
    ChangeEntry,
    ContextCell,
    ContextSnapshot,
    Gap,
    LaneSummary,
    Promise,
    SourceRef,
    VoiceEntry,
)

_CUSTOMER_FACING_LANE = "고객·외부"


def _weight_lookup(weight_resp: dict) -> dict[str, float | None]:
    lookup: dict[str, float | None] = {}
    for row in weight_resp.get("ranked", []):
        lookup[row["key"]] = row.get("per_month")
    for row in weight_resp.get("unmeasured", []):
        lookup.setdefault(row["key"], None)
    return lookup


def _build_cells(rules_resp: dict, weight_by_key: dict[str, float | None]) -> list[ContextCell]:
    cells = []
    for cell in rules_resp.get("cells", []):
        key = cell["key"]
        rules = cell.get("rules", [])
        open_to_client = any(r.get("open_to_client") for r in rules)
        cells.append(
            ContextCell(
                key=key,
                label=cell.get("label", key),
                lane=cell.get("lane", ""),
                guarantee=cell.get("guarantee", ""),
                per_month=weight_by_key.get(key),
                open_to_client=open_to_client,
                source=SourceRef(tool="system_map_rules", ref=key),
            )
        )
    return cells


def _summarize_lanes(cells: list[ContextCell]) -> list[LaneSummary]:
    by_lane: dict[str, list[ContextCell]] = {}
    for cell in cells:
        by_lane.setdefault(cell.lane, []).append(cell)

    summaries = []
    for lane, lane_cells in by_lane.items():
        measured = [c.per_month for c in lane_cells if c.per_month is not None]
        summaries.append(
            LaneSummary(
                lane=lane,
                cell_count=len(lane_cells),
                monthly_frequency=sum(measured) if measured else None,
            )
        )
    return summaries


def _summarize_change(row: dict) -> str:
    after = row.get("after", {})
    label = after.get("label") or row.get("node") or "(지도 전체)"
    if row["kind"] == "drawn":
        return f"'{label}' 칸이 새로 그려짐 (lane={after.get('lane', '?')}, guarantee={after.get('guarantee', '?')})"
    fields = ", ".join(row.get("fields", []))
    return f"'{label}' 칸의 {fields} 변경"


def _extract_rule_promises(rules_resp: dict) -> tuple[list[Promise], list[Promise]]:
    """Splits every rule into (open_to_client=true, open_to_client=false) —
    `promises` and `internal_only` respectively. Rule-level, not cell-level
    (see Promise's docstring): a cell can hold both kinds of rule, and one
    cell's lane-based customer_facing_cells membership is a separate concern
    from any single rule's open_to_client flag."""
    promises: list[Promise] = []
    internal_only: list[Promise] = []
    for cell in rules_resp.get("cells", []):
        for rule in cell.get("rules", []):
            item = Promise(
                node_key=cell["key"],
                rule_title=rule["title"],
                source=SourceRef(tool="system_map_rules", ref=f"{cell['key']}#rule{rule['id']}"),
            )
            (promises if rule.get("open_to_client") else internal_only).append(item)
    return promises, internal_only


def _extract_voice_of_customer(docs_resp: dict) -> list[VoiceEntry]:
    # For supernova-platform (Cofounder itself), most requests are internally
    # authored (created_by=None) — a self-dev backlog, not client inquiries.
    # An empty or short result here is the correct read of that, not a bug:
    # see PRD §9 Q3-adjacent note in README about this client being atypical.
    entries = []
    for doc in docs_resp.get("results", []):
        if doc.get("created_by"):
            entries.append(
                VoiceEntry(
                    excerpt=doc.get("snippet", ""),
                    source=SourceRef(tool="list_documents", ref=doc["id"]),
                )
            )
    return entries


def _extract_gaps(cells: list[ContextCell], rules_resp: dict) -> list[Gap]:
    rules_by_key = {c["key"]: c.get("rules", []) for c in rules_resp.get("cells", [])}
    gaps = []
    for cell in cells:
        if cell.per_month is None:
            gaps.append(
                Gap(
                    node_key=cell.key,
                    label=cell.label,
                    reason="unmeasured",
                    source=SourceRef(tool="system_map_weight", ref=cell.key),
                )
            )
        if not rules_by_key.get(cell.key):
            gaps.append(
                Gap(
                    node_key=cell.key,
                    label=cell.label,
                    reason="no_rule",
                    source=SourceRef(tool="system_map_rules", ref=cell.key),
                )
            )
    return gaps


class ContextEngine:
    def __init__(self, client: ReadOnlyCofounderClient):
        self._client = client

    def build_snapshot(self, client_slug: str) -> ContextSnapshot:
        rules_resp = self._client.system_map_rules(client_slug)
        weight_resp = self._client.system_map_weight(client_slug)
        changes_resp = self._client.system_map_changes(client_slug, days=30)
        docs_resp = self._client.list_documents(client=client_slug, limit=20)

        weight_by_key = _weight_lookup(weight_resp)
        cells = _build_cells(rules_resp, weight_by_key)

        customer_facing = [c for c in cells if c.lane == _CUSTOMER_FACING_LANE or c.open_to_client]
        promises, internal_only = _extract_rule_promises(rules_resp)

        recent_changes = [
            ChangeEntry(
                node_key=row["node"] or "(지도 전체)",
                label=row.get("after", {}).get("label"),
                at=datetime.fromisoformat(row["at"]),
                kind=row["kind"],
                summary=_summarize_change(row),
                source=SourceRef(tool="system_map_changes", ref=row["node"] or "(지도 전체)"),
            )
            for row in changes_resp.get("rows", [])
        ]

        return ContextSnapshot(
            client_slug=client_slug,
            lanes=_summarize_lanes(cells),
            customer_facing_cells=customer_facing,
            recent_changes=recent_changes,
            promises=promises,
            voice_of_customer=_extract_voice_of_customer(docs_resp),
            internal_only=internal_only,
            gaps=_extract_gaps(cells, rules_resp),
        )
