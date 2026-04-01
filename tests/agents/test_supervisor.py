"""Tests for ogar.agents.supervisor — state reducers, node functions, routing."""

import pytest

from ogar.agents.supervisor.state import (
    aggregate_findings_reducer,
    SupervisorState,
)
from langchain_core.messages import AIMessage

from ogar.agents.supervisor.graph import (
    fan_out_to_clusters,
    run_cluster_agent,
    assess_situation,
    decide_actions,
    dispatch_commands,
    _make_route_after_decide,
    _parse_assessment,
    _parse_commands,
    route_after_assess_llm,
    route_after_decide_llm,
    build_supervisor_graph,
)
from ogar.agents.cluster.state import AnomalyFinding
from ogar.hitl.stub import ConsoleApprovalGate
from ogar.transport.schemas import SensorEvent


def _make_finding(finding_id: str = "f1", cluster_id: str = "c1") -> AnomalyFinding:
    return {
        "finding_id": finding_id,
        "cluster_id": cluster_id,
        "anomaly_type": "stub_placeholder",
        "affected_sensors": ["s1"],
        "confidence": 0.5,
        "summary": "test finding",
        "raw_context": {},
    }


def _make_supervisor_state(**overrides) -> dict:
    base = {
        "active_cluster_ids": ["cluster-north"],
        "cluster_findings": [],
        "messages": [],
        "pending_commands": [],
        "requires_approval": False,
        "approval_request_id": None,
        "approval_decision": None,
        "situation_summary": None,
        "status": "idle",
        "error_message": None,
    }
    base.update(overrides)
    return base


# ── Reducer tests ────────────────────────────────────────────────────────────

class TestAggregateFindingsReducer:
    def test_appends_new_findings(self):
        existing = [_make_finding("f1")]
        incoming = [_make_finding("f2")]
        result = aggregate_findings_reducer(existing, incoming)
        assert len(result) == 2

    def test_deduplicates_by_id(self):
        existing = [_make_finding("f1")]
        incoming = [_make_finding("f1"), _make_finding("f2")]
        result = aggregate_findings_reducer(existing, incoming)
        assert len(result) == 2
        ids = [f["finding_id"] for f in result]
        assert ids == ["f1", "f2"]

    def test_empty_lists(self):
        assert aggregate_findings_reducer([], []) == []


# ── Node function tests ─────────────────────────────────────────────────────

class TestFanOutToClusters:
    def test_returns_send_objects(self):
        state = _make_supervisor_state(
            active_cluster_ids=["cluster-north", "cluster-south"]
        )
        sends = fan_out_to_clusters(state)
        assert len(sends) == 2

    def test_empty_clusters(self):
        state = _make_supervisor_state(active_cluster_ids=[])
        sends = fan_out_to_clusters(state)
        assert len(sends) == 0


class TestRunClusterAgent:
    def test_returns_findings(self):
        cluster_state = {
            "cluster_id": "cluster-north",
            "workflow_id": "test",
            "sensor_events": [],
            "trigger_event": None,
            "messages": [],
            "anomalies": [],
            "status": "idle",
            "error_message": None,
        }
        result = run_cluster_agent(cluster_state)
        assert "cluster_findings" in result
        assert len(result["cluster_findings"]) >= 1


class TestAssessSituation:
    def test_produces_summary(self):
        state = _make_supervisor_state(
            cluster_findings=[_make_finding()],
            active_cluster_ids=["cluster-north"],
        )
        result = assess_situation(state)
        assert result["situation_summary"] is not None
        assert "[STUB]" in result["situation_summary"]
        assert result["status"] == "deciding"

    def test_adds_message(self):
        state = _make_supervisor_state(cluster_findings=[])
        result = assess_situation(state)
        assert len(result["messages"]) == 1


class TestDecideActions:
    def test_stub_returns_no_commands(self):
        state = _make_supervisor_state()
        result = decide_actions(state)
        assert result["pending_commands"] == []
        assert result["requires_approval"] is False
        assert result["status"] == "dispatching"


class TestDispatchCommands:
    def test_dispatch_without_approval(self):
        state = _make_supervisor_state(
            pending_commands=[],
            approval_decision=None,
        )
        result = dispatch_commands(state)
        assert result["status"] == "complete"

    def test_dispatch_with_rejection(self):
        state = _make_supervisor_state(
            pending_commands=[{"cmd": "test"}],
            approval_decision={"approved": False, "reason": "nope"},
        )
        result = dispatch_commands(state)
        assert result["status"] == "complete"
        assert result["pending_commands"] == []

    def test_dispatch_with_approval(self):
        state = _make_supervisor_state(
            pending_commands=[{"cmd": "test"}],
            approval_decision={"approved": True},
        )
        result = dispatch_commands(state)
        assert result["status"] == "complete"


class TestRouteAfterDecide:
    def test_routes_to_dispatch_no_approval_with_gate(self):
        route_fn = _make_route_after_decide(has_gate=True)
        state = _make_supervisor_state(
            requires_approval=False, status="dispatching"
        )
        assert route_fn(state) == "dispatch_commands"

    def test_routes_to_hitl_when_approval_needed(self):
        route_fn = _make_route_after_decide(has_gate=True)
        state = _make_supervisor_state(
            requires_approval=True, status="dispatching"
        )
        assert route_fn(state) == "hitl_pause"

    def test_routes_to_end_on_error(self):
        route_fn = _make_route_after_decide(has_gate=True)
        state = _make_supervisor_state(status="error")
        assert route_fn(state) == "__end__"

    def test_routes_to_dispatch_without_gate(self):
        route_fn = _make_route_after_decide(has_gate=False)
        state = _make_supervisor_state(
            requires_approval=True, status="dispatching"
        )
        # Without a gate, always goes to dispatch regardless of requires_approval
        assert route_fn(state) == "dispatch_commands"

    def test_no_gate_routes_to_end_on_error(self):
        route_fn = _make_route_after_decide(has_gate=False)
        state = _make_supervisor_state(status="error")
        assert route_fn(state) == "__end__"


# ── Graph build test ─────────────────────────────────────────────────────────

class TestSupervisorGraph:
    def test_build_stub_no_gate(self):
        graph = build_supervisor_graph()
        assert graph is not None
        assert hasattr(graph, "invoke")
        node_names = set(graph.get_graph().nodes.keys())
        assert "fan_out_to_clusters" in node_names
        assert "run_cluster_agent" in node_names
        assert "assess_situation" in node_names
        assert "decide_actions" in node_names
        assert "dispatch_commands" in node_names
        # No HITL node when gate is not provided
        assert "hitl_pause" not in node_names

    def test_build_stub_with_gate(self):
        gate = ConsoleApprovalGate()
        graph = build_supervisor_graph(gate=gate)
        node_names = set(graph.get_graph().nodes.keys())
        assert "hitl_pause" in node_names
        assert "assess_situation" in node_names
        assert "decide_actions" in node_names


class TestLLMRouters:
    def test_route_after_assess_no_tool_calls(self):
        state = _make_supervisor_state(
            messages=[AIMessage(content="some assessment")]
        )
        assert route_after_assess_llm(state) == "parse_assessment"

    def test_route_after_assess_with_tool_calls(self):
        msg = AIMessage(content="", tool_calls=[{"name": "get_all_findings", "args": {}, "id": "1"}])
        state = _make_supervisor_state(messages=[msg])
        assert route_after_assess_llm(state) == "assess_tool_node"

    def test_route_after_assess_error(self):
        state = _make_supervisor_state(status="error")
        assert route_after_assess_llm(state) == "__end__"

    def test_route_after_decide_no_tool_calls(self):
        state = _make_supervisor_state(
            messages=[AIMessage(content="some decision")]
        )
        assert route_after_decide_llm(state) == "parse_commands"

    def test_route_after_decide_with_tool_calls(self):
        msg = AIMessage(content="", tool_calls=[{"name": "get_finding_summary", "args": {}, "id": "2"}])
        state = _make_supervisor_state(messages=[msg])
        assert route_after_decide_llm(state) == "decide_tool_node"


class TestParseAssessment:
    def test_valid_json(self):
        content = '{"severity": "high", "situation_summary": "Fire detected"}'
        state = _make_supervisor_state(
            messages=[AIMessage(content=content)]
        )
        result = _parse_assessment(state)
        assert result["situation_summary"] == "Fire detected"
        assert result["status"] == "deciding"

    def test_invalid_json_uses_raw_content(self):
        state = _make_supervisor_state(
            messages=[AIMessage(content="Not JSON at all")]
        )
        result = _parse_assessment(state)
        assert "Not JSON at all" in result["situation_summary"]

    def test_no_messages(self):
        state = _make_supervisor_state(messages=[])
        result = _parse_assessment(state)
        assert result["situation_summary"] == "[No assessment produced]"

    def test_markdown_fenced_json(self):
        content = '```json\n{"severity": "low", "situation_summary": "All clear"}\n```'
        state = _make_supervisor_state(
            messages=[AIMessage(content=content)]
        )
        result = _parse_assessment(state)
        assert result["situation_summary"] == "All clear"


class TestParseCommands:
    def test_valid_commands(self):
        content = '{"commands": [{"command_type": "alert", "cluster_id": "c1", "priority": 3, "payload": {"message": "fire"}}], "reasoning": "test"}'
        state = _make_supervisor_state(
            messages=[AIMessage(content=content)]
        )
        result = _parse_commands(state)
        assert len(result["pending_commands"]) == 1
        cmd = result["pending_commands"][0]
        assert cmd.command_type == "alert"
        assert cmd.cluster_id == "c1"
        assert result["requires_approval"] is False

    def test_high_priority_requires_approval(self):
        content = '{"commands": [{"command_type": "escalate", "cluster_id": "c1", "priority": 5, "payload": {}}], "reasoning": "urgent"}'
        state = _make_supervisor_state(
            messages=[AIMessage(content=content)]
        )
        result = _parse_commands(state)
        assert result["requires_approval"] is True

    def test_no_commands(self):
        content = '{"commands": [], "reasoning": "all clear"}'
        state = _make_supervisor_state(
            messages=[AIMessage(content=content)]
        )
        result = _parse_commands(state)
        assert result["pending_commands"] == []
        assert result["requires_approval"] is False

    def test_invalid_json(self):
        state = _make_supervisor_state(
            messages=[AIMessage(content="not json")]
        )
        result = _parse_commands(state)
        assert result["pending_commands"] == []
        assert result["status"] == "dispatching"

    def test_empty_messages(self):
        state = _make_supervisor_state(messages=[])
        result = _parse_commands(state)
        assert result["pending_commands"] == []
