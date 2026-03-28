"""
ProjectSnapshot ↔ KnowledgeGraph facade.

Converts the flat, business-level ``ProjectSnapshot`` to/from the internal
``KnowledgeGraph`` representation.  This is the only place that knows about
node IDs, edge types, and edge directions.

The LLM never calls this directly — it is used inside the knowledge-graph
tool handler and by the ``ProjectStore`` pipeline.

Edge wiring rules (source --EDGE_TYPE--> target):
    Goal        --SATISFIED_BY-->  Requirement
    Requirement --REALIZED_BY-->   Capability
    Capability  --REALIZED_BY-->   Component
    Component   --DEPENDS_ON-->    Dependency
    Constraint  --CONSTRAINS-->    (any node, not wired automatically)
"""
from __future__ import annotations

from typing import Dict, List, Optional

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
from conversation_engine.models.project_spec import (
    ProjectSpecification,
    ProjectSnapshot,  # backwards-compatible alias
    GoalSpec,
    RequirementSpec,
    CapabilitySpec,
    ComponentSpec,
    ConstraintSpec,
    DependencySpec,
)


def _slugify(prefix: str, name: str) -> str:
    """Deterministic ID from a prefix and a human-readable name."""
    slug = name.strip().lower().replace(" ", "-")
    return f"{prefix}-{slug}"


# ── Snapshot → KnowledgeGraph ──────────────────────────────────────

class SnapshotConversionError(Exception):
    """Raised when a snapshot contains invalid references."""


def snapshot_to_graph(snapshot: ProjectSnapshot) -> KnowledgeGraph:
    """
    Convert a ``ProjectSnapshot`` to a ``KnowledgeGraph``.

    Generates deterministic node IDs from names, creates typed nodes,
    and wires edges with the correct types and directions.

    Raises:
        SnapshotConversionError: If a name-based reference cannot be resolved.
    """
    graph = KnowledgeGraph()

    # ── Name → ID registries (built as nodes are added) ────────────
    goal_ids: Dict[str, str] = {}
    req_ids: Dict[str, str] = {}
    cap_ids: Dict[str, str] = {}
    comp_ids: Dict[str, str] = {}
    dep_ids: Dict[str, str] = {}

    # ── Goals ──────────────────────────────────────────────────────
    for spec in snapshot.goals:
        nid = _slugify("goal", spec.name)
        goal_ids[spec.name] = nid
        graph.add_node(Goal(id=nid, name=spec.name, statement=spec.statement))

    # ── Requirements (→ Goal via SATISFIED_BY) ─────────────────────
    for spec in snapshot.requirements:
        nid = _slugify("req", spec.name)
        req_ids[spec.name] = nid
        graph.add_node(Requirement(
            id=nid,
            name=spec.name,
            requirement_type=spec.requirement_type,
            description=spec.description,
        ))
        # Wire: Goal --SATISFIED_BY--> Requirement
        if spec.goal_ref:
            goal_id = goal_ids.get(spec.goal_ref)
            if goal_id is None:
                raise SnapshotConversionError(
                    f"Requirement '{spec.name}' references unknown goal '{spec.goal_ref}'. "
                    f"Known goals: {sorted(goal_ids)}"
                )
            graph.add_edge(BaseEdge(
                edge_type="SATISFIED_BY",
                source_id=goal_id,
                target_id=nid,
            ))

    # ── Capabilities (→ Requirement via REALIZED_BY) ───────────────
    for spec in snapshot.capabilities:
        nid = _slugify("cap", spec.name)
        cap_ids[spec.name] = nid
        graph.add_node(Capability(
            id=nid,
            name=spec.name,
            description=spec.description,
        ))
        for ref in spec.requirement_refs:
            req_id = req_ids.get(ref)
            if req_id is None:
                raise SnapshotConversionError(
                    f"Capability '{spec.name}' references unknown requirement '{ref}'. "
                    f"Known requirements: {sorted(req_ids)}"
                )
            graph.add_edge(BaseEdge(
                edge_type="REALIZED_BY",
                source_id=req_id,
                target_id=nid,
            ))

    # ── Dependencies (added before components so refs resolve) ─────
    for spec in snapshot.dependencies:
        nid = _slugify("dep", spec.name)
        dep_ids[spec.name] = nid
        graph.add_node(Dependency(
            id=nid,
            name=spec.name,
            description=spec.description,
        ))

    # ── Components (→ Capability via REALIZED_BY, → Dependency via DEPENDS_ON)
    for spec in snapshot.components:
        nid = _slugify("comp", spec.name)
        comp_ids[spec.name] = nid
        graph.add_node(Component(
            id=nid,
            name=spec.name,
            description=spec.description,
            has_no_dependencies=spec.has_no_dependencies,
        ))
        for ref in spec.capability_refs:
            cap_id = cap_ids.get(ref)
            if cap_id is None:
                raise SnapshotConversionError(
                    f"Component '{spec.name}' references unknown capability '{ref}'. "
                    f"Known capabilities: {sorted(cap_ids)}"
                )
            graph.add_edge(BaseEdge(
                edge_type="REALIZED_BY",
                source_id=cap_id,
                target_id=nid,
            ))
        for ref in spec.dependency_refs:
            dep_id = dep_ids.get(ref)
            if dep_id is None:
                raise SnapshotConversionError(
                    f"Component '{spec.name}' references unknown dependency '{ref}'. "
                    f"Known dependencies: {sorted(dep_ids)}"
                )
            graph.add_edge(BaseEdge(
                edge_type="DEPENDS_ON",
                source_id=nid,
                target_id=dep_id,
            ))

    # ── Constraints (standalone — no automatic edges) ──────────────
    for spec in snapshot.constraints:
        nid = _slugify("cstr", spec.name)
        graph.add_node(Constraint(id=nid, name=spec.name, statement=spec.statement))

    return graph


# ── KnowledgeGraph → Snapshot ──────────────────────────────────────

def graph_to_snapshot(project_name: str, graph: KnowledgeGraph) -> ProjectSnapshot:
    """
    Convert a ``KnowledgeGraph`` back to a ``ProjectSnapshot``.

    Reconstructs name-based references by following edges in reverse.
    Nodes without matching types are silently skipped (forward-compatible
    with future node types the snapshot doesn't yet model).
    """
    # ── Collect nodes by type ──────────────────────────────────────
    goals_by_id: Dict[str, Goal] = {}
    reqs_by_id: Dict[str, Requirement] = {}
    caps_by_id: Dict[str, Capability] = {}
    comps_by_id: Dict[str, Component] = {}
    deps_by_id: Dict[str, Dependency] = {}
    constraints_by_id: Dict[str, Constraint] = {}

    for node in graph.get_all_nodes():
        if isinstance(node, Goal):
            goals_by_id[node.id] = node
        elif isinstance(node, Requirement):
            reqs_by_id[node.id] = node
        elif isinstance(node, Capability):
            caps_by_id[node.id] = node
        elif isinstance(node, Component):
            comps_by_id[node.id] = node
        elif isinstance(node, Dependency):
            deps_by_id[node.id] = node
        elif isinstance(node, Constraint):
            constraints_by_id[node.id] = node

    # ── Build reverse lookups from edges ───────────────────────────
    # Requirement → goal name  (Goal --SATISFIED_BY--> Req)
    req_to_goal: Dict[str, str] = {}
    for edge in graph.get_edges_by_type("SATISFIED_BY"):
        if edge.target_id in reqs_by_id and edge.source_id in goals_by_id:
            req_to_goal[edge.target_id] = goals_by_id[edge.source_id].name

    # Capability → requirement names  (Req --REALIZED_BY--> Cap)
    cap_to_reqs: Dict[str, List[str]] = {}
    for edge in graph.get_edges_by_type("REALIZED_BY"):
        if edge.target_id in caps_by_id and edge.source_id in reqs_by_id:
            cap_to_reqs.setdefault(edge.target_id, []).append(
                reqs_by_id[edge.source_id].name
            )
        elif edge.target_id in comps_by_id and edge.source_id in caps_by_id:
            pass  # handled below in comp_to_caps

    # Component → capability names  (Cap --REALIZED_BY--> Comp)
    comp_to_caps: Dict[str, List[str]] = {}
    for edge in graph.get_edges_by_type("REALIZED_BY"):
        if edge.target_id in comps_by_id and edge.source_id in caps_by_id:
            comp_to_caps.setdefault(edge.target_id, []).append(
                caps_by_id[edge.source_id].name
            )

    # Component → dependency names  (Comp --DEPENDS_ON--> Dep)
    comp_to_deps: Dict[str, List[str]] = {}
    for edge in graph.get_edges_by_type("DEPENDS_ON"):
        if edge.source_id in comps_by_id and edge.target_id in deps_by_id:
            comp_to_deps.setdefault(edge.source_id, []).append(
                deps_by_id[edge.target_id].name
            )

    # ── Assemble specs ─────────────────────────────────────────────
    goal_specs = [
        GoalSpec(name=g.name, statement=g.statement)
        for g in goals_by_id.values()
    ]

    req_specs = [
        RequirementSpec(
            name=r.name,
            goal_ref=req_to_goal.get(r.id, ""),
            requirement_type=r.requirement_type,
            description=r.description,
        )
        for r in reqs_by_id.values()
    ]

    cap_specs = [
        CapabilitySpec(
            name=c.name,
            requirement_refs=cap_to_reqs.get(c.id, []),
            description=c.description,
        )
        for c in caps_by_id.values()
    ]

    comp_specs = [
        ComponentSpec(
            name=c.name,
            capability_refs=comp_to_caps.get(c.id, []),
            dependency_refs=comp_to_deps.get(c.id, []),
            has_no_dependencies=c.has_no_dependencies,
            description=c.description,
        )
        for c in comps_by_id.values()
    ]

    constraint_specs = [
        ConstraintSpec(name=c.name, statement=c.statement)
        for c in constraints_by_id.values()
    ]

    dep_specs = [
        DependencySpec(name=d.name, description=d.description)
        for d in deps_by_id.values()
    ]

    return ProjectSnapshot(
        project_name=project_name,
        goals=goal_specs,
        requirements=req_specs,
        capabilities=cap_specs,
        components=comp_specs,
        constraints=constraint_specs,
        dependencies=dep_specs,
    )
