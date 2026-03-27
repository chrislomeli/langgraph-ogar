"""
Tests for ProjectSnapshot, snapshot facade, and knowledge_graph tool.

Covers:
- ProjectSnapshot model construction and validation
- snapshot_to_graph() — forward conversion with correct nodes, edges, IDs
- graph_to_snapshot() — reverse conversion preserving names and refs
- Round-trip: snapshot → graph → snapshot
- SnapshotConversionError on bad references
- make_knowledge_graph_tool() — CREATE, READ, DELETE via ToolSpec
"""
from __future__ import annotations

import pytest

from conversation_engine.models.base import BaseEdge
from conversation_engine.models.nodes import (
    Goal,
    Requirement,
    Capability,
    Component,
    Constraint,
    Dependency,
)
from conversation_engine.storage.graph import KnowledgeGraph
from conversation_engine.storage.project_store import InMemoryProjectStore
from conversation_engine.storage.project_specification import (
    ProjectSpecification,
    GoalSpec,
    RequirementSpec,
    CapabilitySpec,
    ComponentSpec,
    ConstraintSpec,
    DependencySpec,
)
from conversation_engine.storage.project_graph_facade import (
    snapshot_to_graph,
    graph_to_snapshot,
    SnapshotConversionError,
    _slugify,
)
from conversation_engine.infrastructure.tool_client.project_graph_tools import (
    ProjectGraphInput,
    ProjectGraphOutput,
    make_project_graph_tool,
)


# ── Helpers ────────────────────────────────────────────────────────

def _sample_snapshot() -> ProjectSpecification:
    """A realistic snapshot with all six entity types."""
    return ProjectSpecification(
        project_name="acme",
        goals=[
            GoalSpec(name="User Authentication", statement="Users can log in securely"),
        ],
        requirements=[
            RequirementSpec(
                name="OAuth Support",
                goal_ref="User Authentication",
                requirement_type="functional",
                description="Support OAuth 2.0 providers",
            ),
        ],
        capabilities=[
            CapabilitySpec(
                name="SSO Login",
                requirement_refs=["OAuth Support"],
                description="Single sign-on via OAuth",
            ),
        ],
        components=[
            ComponentSpec(
                name="Auth Service",
                capability_refs=["SSO Login"],
                dependency_refs=["Redis"],
                description="Handles authentication flows",
            ),
        ],
        constraints=[
            ConstraintSpec(name="GDPR", statement="Must comply with GDPR"),
        ],
        dependencies=[
            DependencySpec(name="Redis", description="Session cache"),
        ],
    )


# ── ProjectSnapshot model ─────────────────────────────────────────

class TestProjectSnapshot:

    def test_minimal_snapshot(self):
        snap = ProjectSpecification(project_name="empty")
        assert snap.project_name == "empty"
        assert snap.goals == []
        assert snap.requirements == []

    def test_full_snapshot(self):
        snap = _sample_snapshot()
        assert snap.project_name == "acme"
        assert len(snap.goals) == 1
        assert len(snap.requirements) == 1
        assert len(snap.capabilities) == 1
        assert len(snap.components) == 1
        assert len(snap.constraints) == 1
        assert len(snap.dependencies) == 1

    def test_snapshot_serialises_to_dict(self):
        snap = _sample_snapshot()
        d = snap.model_dump()
        assert d["project_name"] == "acme"
        assert d["goals"][0]["name"] == "User Authentication"

    def test_snapshot_round_trip_json(self):
        snap = _sample_snapshot()
        json_str = snap.model_dump_json()
        restored = ProjectSpecification.model_validate_json(json_str)
        assert restored == snap


# ── Slugify helper ─────────────────────────────────────────────────

class TestSlugify:

    def test_basic(self):
        assert _slugify("goal", "User Authentication") == "goal-user-authentication"

    def test_strips_whitespace(self):
        assert _slugify("req", "  foo bar  ") == "req-foo-bar"


# ── snapshot_to_graph ──────────────────────────────────────────────

class TestSnapshotToGraph:

    def test_creates_all_nodes(self):
        graph = snapshot_to_graph(_sample_snapshot())
        assert graph.node_count() == 6  # goal, req, cap, comp, cstr, dep

    def test_creates_correct_edges(self):
        graph = snapshot_to_graph(_sample_snapshot())
        # Goal --SATISFIED_BY--> Requirement
        # Requirement --REALIZED_BY--> Capability
        # Capability --REALIZED_BY--> Component
        # Component --DEPENDS_ON--> Dependency
        assert graph.edge_count() == 4

    def test_goal_node(self):
        graph = snapshot_to_graph(_sample_snapshot())
        node = graph.get_node("goal-user-authentication")
        assert node is not None
        assert isinstance(node, Goal)
        assert node.name == "User Authentication"
        assert node.statement == "Users can log in securely"

    def test_requirement_node(self):
        graph = snapshot_to_graph(_sample_snapshot())
        node = graph.get_node("req-oauth-support")
        assert node is not None
        assert isinstance(node, Requirement)
        assert node.requirement_type == "functional"

    def test_satisfied_by_edge(self):
        graph = snapshot_to_graph(_sample_snapshot())
        edge = graph.get_edge("goal-user-authentication", "SATISFIED_BY", "req-oauth-support")
        assert edge is not None

    def test_realized_by_req_to_cap(self):
        graph = snapshot_to_graph(_sample_snapshot())
        edge = graph.get_edge("req-oauth-support", "REALIZED_BY", "cap-sso-login")
        assert edge is not None

    def test_realized_by_cap_to_comp(self):
        graph = snapshot_to_graph(_sample_snapshot())
        edge = graph.get_edge("cap-sso-login", "REALIZED_BY", "comp-auth-service")
        assert edge is not None

    def test_depends_on_edge(self):
        graph = snapshot_to_graph(_sample_snapshot())
        edge = graph.get_edge("comp-auth-service", "DEPENDS_ON", "dep-redis")
        assert edge is not None

    def test_constraint_node(self):
        graph = snapshot_to_graph(_sample_snapshot())
        node = graph.get_node("cstr-gdpr")
        assert node is not None
        assert isinstance(node, Constraint)
        assert node.statement == "Must comply with GDPR"

    def test_component_has_no_dependencies_flag(self):
        snap = ProjectSpecification(
            project_name="test",
            components=[
                ComponentSpec(name="Standalone", has_no_dependencies=True),
            ],
        )
        graph = snapshot_to_graph(snap)
        node = graph.get_node_typed("comp-standalone", Component)
        assert node is not None
        assert node.has_no_dependencies is True

    def test_empty_snapshot_produces_empty_graph(self):
        graph = snapshot_to_graph(ProjectSpecification(project_name="empty"))
        assert graph.node_count() == 0
        assert graph.edge_count() == 0

    def test_bad_goal_ref_raises(self):
        snap = ProjectSpecification(
            project_name="test",
            requirements=[
                RequirementSpec(name="R1", goal_ref="NonexistentGoal"),
            ],
        )
        with pytest.raises(SnapshotConversionError, match="unknown goal"):
            snapshot_to_graph(snap)

    def test_bad_requirement_ref_raises(self):
        snap = ProjectSpecification(
            project_name="test",
            goals=[GoalSpec(name="G1", statement="g")],
            capabilities=[
                CapabilitySpec(name="C1", requirement_refs=["Nonexistent"]),
            ],
        )
        with pytest.raises(SnapshotConversionError, match="unknown requirement"):
            snapshot_to_graph(snap)

    def test_bad_capability_ref_raises(self):
        snap = ProjectSpecification(
            project_name="test",
            components=[
                ComponentSpec(name="X", capability_refs=["Nonexistent"]),
            ],
        )
        with pytest.raises(SnapshotConversionError, match="unknown capability"):
            snapshot_to_graph(snap)

    def test_bad_dependency_ref_raises(self):
        snap = ProjectSpecification(
            project_name="test",
            components=[
                ComponentSpec(name="X", dependency_refs=["Nonexistent"]),
            ],
        )
        with pytest.raises(SnapshotConversionError, match="unknown dependency"):
            snapshot_to_graph(snap)

    def test_multiple_requirements_per_goal(self):
        snap = ProjectSpecification(
            project_name="test",
            goals=[GoalSpec(name="G", statement="g")],
            requirements=[
                RequirementSpec(name="R1", goal_ref="G"),
                RequirementSpec(name="R2", goal_ref="G"),
            ],
        )
        graph = snapshot_to_graph(snap)
        edges = graph.get_outgoing_edges("goal-g", "SATISFIED_BY")
        assert len(edges) == 2

    def test_capability_with_multiple_requirement_refs(self):
        snap = ProjectSpecification(
            project_name="test",
            goals=[GoalSpec(name="G", statement="g")],
            requirements=[
                RequirementSpec(name="R1", goal_ref="G"),
                RequirementSpec(name="R2", goal_ref="G"),
            ],
            capabilities=[
                CapabilitySpec(name="C", requirement_refs=["R1", "R2"]),
            ],
        )
        graph = snapshot_to_graph(snap)
        # R1 --REALIZED_BY--> C  and  R2 --REALIZED_BY--> C
        assert graph.get_edge("req-r1", "REALIZED_BY", "cap-c") is not None
        assert graph.get_edge("req-r2", "REALIZED_BY", "cap-c") is not None


# ── graph_to_snapshot ──────────────────────────────────────────────

class TestGraphToSnapshot:

    def test_basic_reverse(self):
        """Build a graph manually and convert back to snapshot."""
        graph = KnowledgeGraph()
        graph.add_node(Goal(id="g1", name="G1", statement="Goal one"))
        graph.add_node(Requirement(id="r1", name="R1", requirement_type="functional"))
        graph.add_edge(BaseEdge(edge_type="SATISFIED_BY", source_id="g1", target_id="r1"))

        snap = graph_to_snapshot("test", graph)
        assert snap.project_name == "test"
        assert len(snap.goals) == 1
        assert snap.goals[0].name == "G1"
        assert len(snap.requirements) == 1
        assert snap.requirements[0].goal_ref == "G1"

    def test_empty_graph(self):
        snap = graph_to_snapshot("empty", KnowledgeGraph())
        assert snap.goals == []
        assert snap.requirements == []

    def test_component_depends_on(self):
        graph = KnowledgeGraph()
        graph.add_node(Component(id="c1", name="Comp1"))
        graph.add_node(Dependency(id="d1", name="Dep1"))
        graph.add_edge(BaseEdge(edge_type="DEPENDS_ON", source_id="c1", target_id="d1"))

        snap = graph_to_snapshot("test", graph)
        assert len(snap.components) == 1
        assert snap.components[0].dependency_refs == ["Dep1"]

    def test_unknown_node_types_silently_skipped(self):
        """Nodes the snapshot doesn't model (e.g. Feature) are skipped."""
        from conversation_engine.models.nodes import Feature
        graph = KnowledgeGraph()
        graph.add_node(Feature(id="f1", name="F1", description="A feature"))
        graph.add_node(Goal(id="g1", name="G1", statement="s"))

        snap = graph_to_snapshot("test", graph)
        assert len(snap.goals) == 1
        # Feature is silently skipped — no error


# ── Round-trip ─────────────────────────────────────────────────────

class TestRoundTrip:

    def test_snapshot_to_graph_and_back(self):
        """snapshot → graph → snapshot preserves all business data."""
        original = _sample_snapshot()
        graph = snapshot_to_graph(original)
        restored = graph_to_snapshot("acme", graph)

        assert restored.project_name == original.project_name
        assert len(restored.goals) == len(original.goals)
        assert len(restored.requirements) == len(original.requirements)
        assert len(restored.capabilities) == len(original.capabilities)
        assert len(restored.components) == len(original.components)
        assert len(restored.constraints) == len(original.constraints)
        assert len(restored.dependencies) == len(original.dependencies)

        # Check content
        assert restored.goals[0].name == "User Authentication"
        assert restored.requirements[0].goal_ref == "User Authentication"
        assert restored.capabilities[0].requirement_refs == ["OAuth Support"]
        assert restored.components[0].capability_refs == ["SSO Login"]
        assert restored.components[0].dependency_refs == ["Redis"]

    def test_empty_round_trip(self):
        original = ProjectSpecification(project_name="empty")
        graph = snapshot_to_graph(original)
        restored = graph_to_snapshot("empty", graph)
        assert restored.goals == []
        assert restored.requirements == []


# ── make_knowledge_graph_tool ──────────────────────────────────────

class TestKnowledgeGraphTool:

    def _make_tool(self):
        store = InMemoryProjectStore()
        spec = make_project_graph_tool(store)
        return spec, store

    def test_tool_spec_metadata(self):
        spec, _ = self._make_tool()
        assert spec.name == "knowledge_graph"
        assert "CREATE" in spec.description
        assert "READ" in spec.description
        assert "DELETE" in spec.description

    def test_create_success(self):
        spec, store = self._make_tool()
        inp = ProjectGraphInput(method="CREATE", payload=_sample_snapshot())
        out = spec.handler(inp)
        assert out.success is True
        assert "saved" in out.message.lower()
        assert store.exists("acme")

    def test_create_no_payload(self):
        spec, _ = self._make_tool()
        inp = ProjectGraphInput(method="CREATE")
        out = spec.handler(inp)
        assert out.success is False
        assert "payload" in out.message.lower()

    def test_create_duplicate_is_upsert(self):
        """Service does upsert — duplicate CREATE succeeds."""
        spec, _ = self._make_tool()
        inp = ProjectGraphInput(method="CREATE", payload=_sample_snapshot())
        spec.handler(inp)
        out = spec.handler(inp)
        assert out.success is True
        assert "saved" in out.message.lower()

    def test_create_bad_ref_fails(self):
        spec, _ = self._make_tool()
        bad_snap = ProjectSpecification(
            project_name="bad",
            requirements=[RequirementSpec(name="R", goal_ref="NoGoal")],
        )
        inp = ProjectGraphInput(method="CREATE", payload=bad_snap)
        out = spec.handler(inp)
        assert out.success is False
        assert "invalid spec" in out.message.lower()

    def test_read_success(self):
        spec, _ = self._make_tool()
        spec.handler(ProjectGraphInput(method="CREATE", payload=_sample_snapshot()))
        inp = ProjectGraphInput(method="READ", key="acme")
        out = spec.handler(inp)
        assert out.success is True
        assert out.payload is not None
        assert out.payload.project_name == "acme"
        assert len(out.payload.goals) == 1

    def test_read_not_found(self):
        spec, _ = self._make_tool()
        inp = ProjectGraphInput(method="READ", key="nope")
        out = spec.handler(inp)
        assert out.success is False
        assert "not found" in out.message.lower()

    def test_read_no_key(self):
        spec, _ = self._make_tool()
        inp = ProjectGraphInput(method="READ")
        out = spec.handler(inp)
        assert out.success is False
        assert "key" in out.message.lower()

    def test_delete_success(self):
        spec, store = self._make_tool()
        spec.handler(ProjectGraphInput(method="CREATE", payload=_sample_snapshot()))
        assert store.exists("acme")
        inp = ProjectGraphInput(method="DELETE", key="acme")
        out = spec.handler(inp)
        assert out.success is True
        assert not store.exists("acme")

    def test_delete_not_found(self):
        spec, _ = self._make_tool()
        inp = ProjectGraphInput(method="DELETE", key="nope")
        out = spec.handler(inp)
        assert out.success is False

    def test_delete_no_key(self):
        spec, _ = self._make_tool()
        inp = ProjectGraphInput(method="DELETE")
        out = spec.handler(inp)
        assert out.success is False

    def test_update_via_delete_then_create(self):
        """MVP update: delete + create."""
        spec, store = self._make_tool()
        spec.handler(ProjectGraphInput(method="CREATE", payload=_sample_snapshot()))

        # Delete
        spec.handler(ProjectGraphInput(method="DELETE", key="acme"))
        assert not store.exists("acme")

        # Create with modified data
        updated = _sample_snapshot()
        updated.goals.append(GoalSpec(name="New Goal", statement="Added later"))
        updated.requirements.append(
            RequirementSpec(name="New Req", goal_ref="New Goal")
        )
        out = spec.handler(ProjectGraphInput(method="CREATE", payload=updated))
        assert out.success is True

        # Verify
        read_out = spec.handler(ProjectGraphInput(method="READ", key="acme"))
        assert read_out.payload is not None
        assert len(read_out.payload.goals) == 2

    def test_create_read_round_trip_preserves_data(self):
        """CREATE then READ returns equivalent data."""
        spec, _ = self._make_tool()
        original = _sample_snapshot()
        spec.handler(ProjectGraphInput(method="CREATE", payload=original))
        out = spec.handler(ProjectGraphInput(method="READ", key="acme"))

        assert out.payload is not None
        restored = out.payload
        assert restored.goals[0].name == original.goals[0].name
        assert restored.requirements[0].goal_ref == original.requirements[0].goal_ref
        assert restored.capabilities[0].requirement_refs == original.capabilities[0].requirement_refs
        assert restored.components[0].capability_refs == original.components[0].capability_refs
        assert restored.components[0].dependency_refs == original.components[0].dependency_refs

    def test_tool_works_with_local_tool_client(self):
        """Integration: tool works through LocalToolClient envelope."""
        from conversation_engine.infrastructure.tool_client import (
            ToolRegistry,
            LocalToolClient,
        )
        store = InMemoryProjectStore()
        spec = make_project_graph_tool(store)
        reg = ToolRegistry()
        reg.register(spec)
        client = LocalToolClient(reg)

        # CREATE
        env = client.call("knowledge_graph", {
            "method": "CREATE",
            "payload": _sample_snapshot().model_dump(),
        })
        assert not env.is_error
        assert env.structured["success"] is True

        # READ
        env = client.call("knowledge_graph", {"method": "READ", "key": "acme"})
        assert not env.is_error
        assert env.structured["success"] is True
        assert env.structured["payload"]["project_name"] == "acme"
