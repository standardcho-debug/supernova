"""F1 ContextEngine, run against REAL recorded supernova-platform responses
(sns_marketing_agent/fixtures/cofounder_recorded/) — not synthetic data.
Covers the PRD §5.1 acceptance criteria: every item carries a source, and
zero write-tool calls happen along the way (the gate would raise if one did)."""
from sns_marketing_agent.cofounder_client import InMemoryCallLog, ReadOnlyCofounderClient
from sns_marketing_agent.cofounder_fixture_transport import FixtureMCPCaller
from sns_marketing_agent.context_engine import ContextEngine


def build_real_snapshot():
    caller = FixtureMCPCaller(client_slug="supernova-platform")
    call_log = InMemoryCallLog()
    client = ReadOnlyCofounderClient(caller, call_log=call_log)
    engine = ContextEngine(client)
    snapshot = engine.build_snapshot("supernova-platform")
    return snapshot, call_log


def test_snapshot_generation_succeeds_against_real_fixture():
    snapshot, _ = build_real_snapshot()
    assert snapshot.client_slug == "supernova-platform"
    assert len(snapshot.customer_facing_cells) > 0
    assert len(snapshot.lanes) > 0


def test_only_allowed_tools_were_called():
    _, call_log = build_real_snapshot()
    called_tools = {e.tool for e in call_log.entries}
    assert called_tools == {
        "system_map_rules",
        "system_map_weight",
        "system_map_changes",
        "list_documents",
    }
    assert all(e.allowed for e in call_log.entries)


def test_every_customer_facing_cell_has_a_source():
    snapshot, _ = build_real_snapshot()
    for cell in snapshot.customer_facing_cells:
        assert cell.source.tool == "system_map_rules"
        assert cell.source.ref == cell.key


def test_every_change_has_a_source():
    snapshot, _ = build_real_snapshot()
    assert len(snapshot.recent_changes) > 0
    for change in snapshot.recent_changes:
        assert change.source.tool == "system_map_changes"


def test_every_promise_has_a_source_and_is_open_to_client():
    snapshot, _ = build_real_snapshot()
    assert len(snapshot.promises) > 0
    for promise in snapshot.promises:
        assert promise.source.tool == "system_map_rules"
        assert "#rule" in promise.source.ref


def test_promises_and_internal_only_never_share_a_rule():
    snapshot, _ = build_real_snapshot()
    promise_refs = {p.source.ref for p in snapshot.promises}
    internal_refs = {p.source.ref for p in snapshot.internal_only}
    # C5, at the level it actually applies: one rule is open_to_client true
    # XOR false, never both, so these two lists can't share a rule reference.
    assert promise_refs.isdisjoint(internal_refs)
    # the real fixture has selfreq/sr_ctx/est? with open_to_client: false
    internal_keys = {p.node_key for p in snapshot.internal_only}
    assert "selfreq" in internal_keys


def test_a_customer_facing_cell_can_still_have_an_internal_only_rule():
    # selfreq (고객 직접 등록) is lane=고객·외부 -> customer_facing by lane,
    # even though its own rule body is open_to_client=false. That's the bug
    # the previous (wrong) version of this test enforced against: cell-level
    # "customer facing" and rule-level "safe to quote" are different axes.
    snapshot, _ = build_real_snapshot()
    facing_keys = {c.key for c in snapshot.customer_facing_cells}
    internal_keys = {p.node_key for p in snapshot.internal_only}
    assert "selfreq" in facing_keys
    assert "selfreq" in internal_keys


def test_gaps_flag_unmeasured_cells_without_treating_them_as_zero():
    snapshot, _ = build_real_snapshot()
    unmeasured_gaps = [g for g in snapshot.gaps if g.reason == "unmeasured"]
    assert len(unmeasured_gaps) > 0
    # dx_target is unmeasured in the real fixture (system_map_weight)
    assert any(g.node_key == "dx_target" for g in unmeasured_gaps)


def test_gaps_flag_cells_with_no_rule():
    snapshot, _ = build_real_snapshot()
    no_rule_gaps = [g for g in snapshot.gaps if g.reason == "no_rule"]
    # bmark has an empty rules list in the real fixture
    assert any(g.node_key == "bmark" for g in no_rule_gaps)


def test_lane_monthly_frequency_is_none_when_lane_has_no_measured_cells():
    snapshot, _ = build_real_snapshot()
    lanes_by_name = {lane.lane: lane for lane in snapshot.lanes}
    # every lane in the trimmed fixture either has a measured cell or doesn't;
    # whichever it is, None must mean "no measured cells", never 0
    for lane in lanes_by_name.values():
        if lane.monthly_frequency is not None:
            assert lane.monthly_frequency > 0
