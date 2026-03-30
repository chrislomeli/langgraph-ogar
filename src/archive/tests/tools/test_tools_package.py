"""
Tests for the centralized src/tools/ package.

These tests verify:
  - Package structure and imports
  - Backward compatibility of the old project_planner.graph.tools re-export
  - project_tools.build_project_tools produces the expected tool list (requires Memgraph)
"""

from __future__ import annotations

import pytest


# ── Import / structure tests (no Memgraph needed) ─────────────────────


class TestToolsPackageImports:
    """Verify all tool modules are importable."""

    def test_import_tools_package(self):
        import tools
        assert hasattr(tools, "__doc__")

    def test_import_project_tools(self):
        from tools.project_tools import build_project_tools
        assert callable(build_project_tools)

    def test_import_intent_tools_stub(self):
        import tools.intent_tools
        assert tools.intent_tools.__doc__ is not None

    def test_import_music_tools_stub(self):
        import tools.music_tools
        assert tools.music_tools.__doc__ is not None

    def test_import_persistence_tools_stub(self):
        import tools.persistence_tools
        assert tools.persistence_tools.__doc__ is not None


class TestBackwardCompatibility:
    """The old import path should still work via re-export."""

    def test_old_import_path_works(self):
        from project_planner.graph.tools import build_tools
        assert callable(build_tools)

    def test_old_and_new_are_same_function(self):
        from project_planner.graph.tools import build_tools
        from tools.project_tools import build_project_tools
        assert build_tools is build_project_tools


# ── Integration tests (require Memgraph) ──────────────────────────────


def _memgraph_available() -> bool:
    try:
        from project_planner.persistence.connection import get_memgraph
        db = get_memgraph()
        db.execute("RETURN 1")
        return True
    except Exception:
        return False


requires_memgraph = pytest.mark.skipif(
    not _memgraph_available(),
    reason="Memgraph not available",
)


@requires_memgraph
class TestBuildProjectTools:
    """Verify build_project_tools produces the expected LangGraph tools."""

    @pytest.fixture
    def db(self):
        from project_planner.persistence.connection import get_memgraph, ensure_schema
        mg = get_memgraph()
        mg.execute("MATCH (n) DETACH DELETE n")
        ensure_schema(mg)
        yield mg
        mg.execute("MATCH (n) DETACH DELETE n")

    def test_returns_eight_tools(self, db):
        from tools.project_tools import build_project_tools
        tools = build_project_tools(db, project_id="p1", actor_id="a1")
        assert len(tools) == 8

    def test_tool_names(self, db):
        from tools.project_tools import build_project_tools
        tools = build_project_tools(db, project_id="p1", actor_id="a1")
        names = sorted(t.name for t in tools)
        expected = sorted([
            "plan_task_tool",
            "update_status_tool",
            "get_context_tool",
            "get_next_actions_tool",
            "add_finding_tool",
            "set_phase_tool",
            "propose_plan_tool",
            "approve_plan_tool",
        ])
        assert names == expected

    def test_tools_are_callable(self, db):
        from tools.project_tools import build_project_tools
        tools = build_project_tools(db, project_id="p1", actor_id="a1")
        for t in tools:
            assert callable(t)
