"""C1 enforcement tests: the read-only gate must block anything off the
allowlist, and every attempt — allowed or blocked — must be auditable."""
import pytest

from sns_marketing_agent.cofounder_client import (
    ALLOWED_TOOLS,
    InMemoryCallLog,
    ReadOnlyCofounderClient,
    ToolNotAllowedError,
)


class FakeCaller:
    def __init__(self):
        self.calls: list[tuple[str, dict]] = []

    def call(self, tool, **kwargs):
        self.calls.append((tool, kwargs))
        return {"tool": tool, "kwargs": kwargs}


@pytest.fixture
def caller():
    return FakeCaller()


@pytest.fixture
def client(caller):
    return ReadOnlyCofounderClient(caller)


def test_allowed_tool_passes_through(client, caller):
    result = client.call("list_domains", client="dodam")
    assert result == {"tool": "list_domains", "kwargs": {"client": "dodam"}}
    assert caller.calls == [("list_domains", {"client": "dodam"})]


@pytest.mark.parametrize(
    "write_tool",
    ["create_document", "triage_request", "update_feature", "upsert_system_map", "attach_node_rule"],
)
def test_write_tools_are_rejected(client, caller, write_tool):
    with pytest.raises(ToolNotAllowedError):
        client.call(write_tool, client="dodam")
    assert caller.calls == []  # never reached the transport


def test_blocked_call_is_still_logged():
    caller = FakeCaller()
    log = InMemoryCallLog()
    client = ReadOnlyCofounderClient(caller, call_log=log)

    with pytest.raises(ToolNotAllowedError):
        client.call("create_document", client="dodam")

    assert len(log.entries) == 1
    assert log.entries[0].tool == "create_document"
    assert log.entries[0].allowed is False


def test_allowed_call_is_logged_too():
    caller = FakeCaller()
    log = InMemoryCallLog()
    client = ReadOnlyCofounderClient(caller, call_log=log)

    client.call("list_clients")

    assert len(log.entries) == 1
    assert log.entries[0].allowed is True


def test_system_map_weight_always_forces_measure_false(client, caller):
    client.system_map_weight("dodam")
    assert caller.calls == [("system_map_weight", {"client": "dodam", "measure": False})]


def test_system_map_weight_forces_measure_false_even_if_caller_tries_true(client, caller):
    client.call("system_map_weight", client="dodam", measure=True)
    assert caller.calls == [("system_map_weight", {"client": "dodam", "measure": False})]


def test_convenience_wrappers_only_cover_allowed_tools():
    wrapper_names = {
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
    assert wrapper_names == ALLOWED_TOOLS
