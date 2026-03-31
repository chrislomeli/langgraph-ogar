"""
Tests for the intake subgraph.

Black-box: invoke the compiled graph, assert on output state.
All tests use deterministic stubs (no LLM calls).
"""
import pytest

from ogar.runtime.graph.intake import build_intake_graph


def _invoke_intake(pid="test_proj", **overrides):
    """Helper: build + invoke the intake graph with default inputs."""
    graph = build_intake_graph()
    inputs = {
        "pid": pid,
        "project": None,
        "stage": "",
        "questions": [],
        "human_reply": None,
        "patch": None,
        "validation_errors": [],
        "node_result": None,
        **overrides,
    }
    return graph.invoke(inputs)


class TestIntakeHappyPath:
    """Intake should collect goals, requirements, and reach 'done'."""

    def test_reaches_done(self):
        out = _invoke_intake()
        assert out["stage"] == "done"

    def test_project_has_title(self):
        out = _invoke_intake()
        assert out["project"] is not None
        assert out["project"].title.strip() != ""

    def test_project_has_goals(self):
        out = _invoke_intake()
        assert len(out["project"].goals) >= 1

    def test_project_has_requirements(self):
        out = _invoke_intake()
        assert len(out["project"].requirements) >= 1

    def test_requirements_link_to_goals(self):
        out = _invoke_intake()
        project = out["project"]
        goal_ids = set(project.goals.keys())
        for rid, req in project.requirements.items():
            assert len(req.source_goal_ids) >= 1, f"Requirement {rid} has no linked goals"
            for gid in req.source_goal_ids:
                assert gid in goal_ids, f"Requirement {rid} links to unknown goal {gid}"

    def test_no_validation_errors_at_end(self):
        out = _invoke_intake()
        assert out.get("validation_errors", []) == []


class TestIntakeEdgeCases:
    """Edge cases for the intake subgraph."""

    def test_different_pid_creates_different_project(self):
        out1 = _invoke_intake(pid="proj_a")
        out2 = _invoke_intake(pid="proj_b")
        assert out1["project"].pid == "proj_a"
        assert out2["project"].pid == "proj_b"

    def test_output_contains_all_state_keys(self):
        out = _invoke_intake()
        expected_keys = {"pid", "project", "stage", "questions",
                         "human_reply", "patch", "validation_errors",
                         "node_result"}
        assert expected_keys.issubset(set(out.keys()))
