"""Sqlite persistence for F1 output — PRD v1.0 §6.3 `context_snapshots`, `mcp_call_log`.

Same JSON-blob-per-row approach as web/sqlite_store.py's SqliteApprovalGate,
for the same reason: the only queries this needs are "latest snapshot for
client X" and "append a call-log row", neither of which needs a normalized
schema.

`mcp_call_log` is C1's audit trail made durable: SqliteMcpCallLog satisfies
cofounder_client.McpCallLog, so `ReadOnlyCofounderClient(caller, call_log=
SqliteMcpCallLog(db_path))` writes every allowed/blocked call attempt to
disk instead of losing it when the process exits.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sns_marketing_agent.cofounder_client import McpCallRecord
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


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"not JSON serializable: {type(obj)}")


def _snapshot_to_json(snapshot: ContextSnapshot) -> str:
    return json.dumps(asdict(snapshot), default=_json_default, ensure_ascii=False)


def _source(d: dict) -> SourceRef:
    return SourceRef(tool=d["tool"], ref=d["ref"])


def _snapshot_from_dict(data: dict) -> ContextSnapshot:
    return ContextSnapshot(
        client_slug=data["client_slug"],
        created_at=datetime.fromisoformat(data["created_at"]),
        lanes=[LaneSummary(**lane) for lane in data["lanes"]],
        customer_facing_cells=[
            ContextCell(**{**c, "source": _source(c["source"])}) for c in data["customer_facing_cells"]
        ],
        recent_changes=[
            ChangeEntry(**{**c, "at": datetime.fromisoformat(c["at"]), "source": _source(c["source"])})
            for c in data["recent_changes"]
        ],
        promises=[Promise(**{**p, "source": _source(p["source"])}) for p in data["promises"]],
        voice_of_customer=[
            VoiceEntry(**{**v, "source": _source(v["source"])}) for v in data["voice_of_customer"]
        ],
        internal_only=[
            Promise(**{**p, "source": _source(p["source"])}) for p in data["internal_only"]
        ],
        gaps=[Gap(**{**g, "source": _source(g["source"])}) for g in data["gaps"]],
    )


class SqliteContextStore:
    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS context_snapshots (
                    id TEXT PRIMARY KEY,
                    client_slug TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_context_snapshots_client "
                "ON context_snapshots(client_slug, created_at)"
            )

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def save(self, snapshot: ContextSnapshot) -> str:
        snapshot_id = str(uuid4())
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO context_snapshots (id, client_slug, created_at, payload_json) "
                "VALUES (?, ?, ?, ?)",
                (snapshot_id, snapshot.client_slug, snapshot.created_at.isoformat(), _snapshot_to_json(snapshot)),
            )
        return snapshot_id

    def latest(self, client_slug: str) -> ContextSnapshot | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT payload_json FROM context_snapshots WHERE client_slug = ? "
                "ORDER BY created_at DESC LIMIT 1",
                (client_slug,),
            ).fetchone()
        if row is None:
            return None
        return _snapshot_from_dict(json.loads(row[0]))


class SqliteMcpCallLog:
    """Durable McpCallLog (cofounder_client.McpCallLog) — the C1 audit trail."""

    def __init__(self, db_path: Path):
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mcp_call_log (
                    id TEXT PRIMARY KEY,
                    tool TEXT NOT NULL,
                    args_hash TEXT NOT NULL,
                    allowed INTEGER NOT NULL,
                    at TEXT NOT NULL
                )
                """
            )

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self._db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def record(self, entry: McpCallRecord) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO mcp_call_log (id, tool, args_hash, allowed, at) VALUES (?, ?, ?, ?, ?)",
                (str(uuid4()), entry.tool, entry.args_hash, int(entry.allowed), entry.at.isoformat()),
            )

    def blocked_calls(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT tool, args_hash, at FROM mcp_call_log WHERE allowed = 0 ORDER BY at"
            ).fetchall()
        return [{"tool": r[0], "args_hash": r[1], "at": r[2]} for r in rows]
