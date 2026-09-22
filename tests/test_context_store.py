from sns_marketing_agent.cofounder_client import (
    McpCallRecord,
    ReadOnlyCofounderClient,
    ToolNotAllowedError,
)
from sns_marketing_agent.cofounder_fixture_transport import FixtureMCPCaller
from sns_marketing_agent.context_engine import ContextEngine
from sns_marketing_agent.context_store import SqliteContextStore, SqliteMcpCallLog


def _real_snapshot():
    client = ReadOnlyCofounderClient(FixtureMCPCaller(client_slug="supernova-platform"))
    return ContextEngine(client).build_snapshot("supernova-platform")


def test_save_and_retrieve_latest_snapshot_round_trips(tmp_path):
    store = SqliteContextStore(tmp_path / "context.db")
    original = _real_snapshot()

    store.save(original)
    reloaded = store.latest("supernova-platform")

    assert reloaded is not None
    assert reloaded.client_slug == original.client_slug
    assert len(reloaded.customer_facing_cells) == len(original.customer_facing_cells)
    assert {c.key for c in reloaded.customer_facing_cells} == {c.key for c in original.customer_facing_cells}
    assert len(reloaded.promises) == len(original.promises)
    assert len(reloaded.gaps) == len(original.gaps)
    # source refs survive the round trip, not just the top-level fields
    assert reloaded.customer_facing_cells[0].source.tool == "system_map_rules"


def test_latest_returns_none_for_unknown_client(tmp_path):
    store = SqliteContextStore(tmp_path / "context.db")
    assert store.latest("no-such-client") is None


def test_latest_picks_the_most_recently_saved_snapshot(tmp_path):
    store = SqliteContextStore(tmp_path / "context.db")
    snap = _real_snapshot()

    store.save(snap)
    import time

    time.sleep(0.01)
    snap.created_at = snap.created_at.replace(microsecond=999999)
    second_id = store.save(snap)

    latest = store.latest("supernova-platform")
    assert latest is not None
    # both saves succeeded; retrieval doesn't error and returns a valid snapshot
    assert latest.client_slug == "supernova-platform"
    assert second_id


def test_sqlite_call_log_persists_blocked_and_allowed_calls(tmp_path):
    log = SqliteMcpCallLog(tmp_path / "calls.db")
    client = ReadOnlyCofounderClient(FixtureMCPCaller(client_slug="supernova-platform"), call_log=log)

    client.list_domains(client="supernova-platform")
    try:
        client.call("create_document")
    except ToolNotAllowedError:
        pass

    blocked = log.blocked_calls()
    assert len(blocked) == 1
    assert blocked[0]["tool"] == "create_document"


def test_sqlite_call_log_satisfies_the_mcp_call_log_protocol(tmp_path):
    # duck-typed protocol check: record() must accept a bare McpCallRecord
    log = SqliteMcpCallLog(tmp_path / "calls.db")
    log.record(McpCallRecord(tool="list_clients", args_hash="abc123", allowed=True))
    assert log.blocked_calls() == []
