"""
DAG operations for PlanGraph.

Pure functions over the plan's dependency graph:
topological sort, cycle detection, parallel groups,
invalidation propagation, and traversal helpers.

No side effects — these functions read the graph but never mutate it
(except ``invalidate_downstream`` which updates sub-plan statuses).
"""

from __future__ import annotations

from collections import deque
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ogar.planning.models import PlanGraph


# ── Errors ──────────────────────────────────────────────────────────


class CycleError(Exception):
    """Raised when the dependency graph contains a cycle."""


# ── Core algorithms ─────────────────────────────────────────────────


def topological_sort(plan: PlanGraph) -> list[str]:
    """
    Return scope_ids in dependency order (Kahn's algorithm).

    Raises ``CycleError`` if the graph contains a cycle.
    """
    in_degree: dict[str, int] = {sid: 0 for sid in plan.sub_plans}
    adjacency: dict[str, list[str]] = {sid: [] for sid in plan.sub_plans}

    for sid, deps in plan.dependencies.items():
        for dep in deps:
            adjacency[dep].append(sid)
            in_degree[sid] += 1

    queue: deque[str] = deque(sid for sid, deg in in_degree.items() if deg == 0)
    order: list[str] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for neighbor in adjacency[node]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(plan.sub_plans):
        visited = set(order)
        cycle_members = [sid for sid in plan.sub_plans if sid not in visited]
        raise CycleError(
            f"Dependency cycle detected involving: {', '.join(sorted(cycle_members))}"
        )

    return order


def roots(plan: PlanGraph) -> list[str]:
    """Sub-plans with no dependencies (can start immediately)."""
    return sorted(
        sid
        for sid in plan.sub_plans
        if not plan.dependencies.get(sid)
    )


def leaves(plan: PlanGraph) -> list[str]:
    """Sub-plans that no other sub-plan depends on (terminal outputs)."""
    depended_on: set[str] = set()
    for deps in plan.dependencies.values():
        depended_on.update(deps)
    return sorted(sid for sid in plan.sub_plans if sid not in depended_on)


def downstream(plan: PlanGraph, scope_id: str) -> set[str]:
    """All transitive dependents of a sub-plan (BFS forward)."""
    # Build forward adjacency: dep → list of dependents
    forward: dict[str, list[str]] = {sid: [] for sid in plan.sub_plans}
    for sid, deps in plan.dependencies.items():
        for dep in deps:
            forward[dep].append(sid)

    visited: set[str] = set()
    queue: deque[str] = deque(forward.get(scope_id, []))
    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        queue.extend(forward.get(node, []))
    return visited


def upstream(plan: PlanGraph, scope_id: str) -> set[str]:
    """All transitive dependencies of a sub-plan (BFS backward)."""
    visited: set[str] = set()
    queue: deque[str] = deque(plan.dependencies.get(scope_id, set()))
    while queue:
        node = queue.popleft()
        if node in visited:
            continue
        visited.add(node)
        queue.extend(plan.dependencies.get(node, set()))
    return visited


def parallel_groups(plan: PlanGraph) -> list[set[str]]:
    """
    Group sub-plans by topological level.

    Each group contains sub-plans that can execute concurrently
    (all their dependencies are in earlier groups).
    Returns groups in execution order.
    """
    if not plan.sub_plans:
        return []

    # Compute the level of each node (longest path from a root)
    levels: dict[str, int] = {}
    order = topological_sort(plan)

    for sid in order:
        deps = plan.dependencies.get(sid, set())
        if not deps:
            levels[sid] = 0
        else:
            levels[sid] = max(levels[dep] for dep in deps) + 1

    # Group by level
    max_level = max(levels.values()) if levels else 0
    groups: list[set[str]] = [set() for _ in range(max_level + 1)]
    for sid, level in levels.items():
        groups[level].add(sid)

    return groups


def ready_to_execute(plan: PlanGraph) -> list[str]:
    """
    Sub-plans that are approved and whose dependencies are all done/locked.

    These can be dispatched to executors immediately.
    """
    from ogar.planning.models import SubPlanStatus

    ready = []
    for sid, sp in plan.sub_plans.items():
        if sp.status != SubPlanStatus.approved:
            continue
        deps = plan.dependencies.get(sid, set())
        all_deps_done = all(
            plan.sub_plans[dep].status in (SubPlanStatus.done, SubPlanStatus.locked)
            for dep in deps
        )
        if all_deps_done:
            ready.append(sid)
    return sorted(ready)


# ── Invalidation ────────────────────────────────────────────────────


def invalidate_downstream(plan: PlanGraph, changed_scope_id: str) -> set[str]:
    """
    Mark all downstream sub-plans as stale (unless locked).

    This is the key mechanism for plan consistency: when an upstream
    sub-plan is re-planned, all dependents are invalidated so they
    can be re-approved and re-executed.

    Returns the set of scope_ids that were invalidated.
    """
    from ogar.planning.models import SubPlanStatus

    invalidated: set[str] = set()
    for ds_id in downstream(plan, changed_scope_id):
        sp = plan.sub_plans[ds_id]
        if sp.status == SubPlanStatus.locked:
            continue
        if sp.status in (
            SubPlanStatus.done,
            SubPlanStatus.approved,
            SubPlanStatus.executing,
        ):
            sp.status = SubPlanStatus.stale
            sp.touch()
            invalidated.add(ds_id)
    return invalidated
