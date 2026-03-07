"""
Layer 2 — Policy checks for the project engine.

Policies return warnings, not errors. They advise but don't block.
The caller decides whether to enforce or just log.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gqlalchemy import Memgraph


@dataclass
class Warning:
    """A policy warning — advisory, not blocking."""
    code: str
    message: str
    work_item_id: str | None = None


# ── Blocked check ──────────────────────────────────────────────────


def check_is_blocked(db: Memgraph, work_item_id: str) -> bool:
    """
    A work item is blocked if it has any DEPENDS_ON target with state ≠ done.

    This is the canonical "blocked" computation — not stored, always computed.
    """
    result = db.execute_and_fetch(
        """
        MATCH (w:WorkItem {id: $id})-[:DEPENDS_ON]->(b:WorkItem)
        WHERE b.state <> "done"
        RETURN count(b) AS cnt
        """,
        {"id": work_item_id},
    )
    row = next(result, None)
    return row is not None and row["cnt"] > 0


# ── Completion readiness ───────────────────────────────────────────


def check_can_complete(db: Memgraph, work_item_id: str) -> list[Warning]:
    """
    Check whether a work item is ready to be marked done.

    Returns a list of warnings (empty = safe to complete).
    """
    warnings: list[Warning] = []

    # 1. Check for undone children
    children = list(db.execute_and_fetch(
        """
        MATCH (w:WorkItem {id: $id})-[:PARENT_OF]->(child:WorkItem)
        WHERE child.state <> "done" AND child.state <> "canceled"
        RETURN child.id AS id, child.title AS title, child.state AS state
        """,
        {"id": work_item_id},
    ))
    for child in children:
        warnings.append(Warning(
            code="undone_child",
            message=f"Child '{child['title']}' is still {child['state']}",
            work_item_id=child["id"],
        ))

    # 2. Check acceptance criteria
    result = db.execute_and_fetch(
        "MATCH (w:WorkItem {id: $id}) RETURN w.acceptance AS acceptance",
        {"id": work_item_id},
    )
    row = next(result, None)
    if row and row["acceptance"]:
        import json
        try:
            acc = json.loads(row["acceptance"])
            if not acc.get("verified", False):
                warnings.append(Warning(
                    code="acceptance_not_verified",
                    message="Acceptance criteria not yet verified",
                    work_item_id=work_item_id,
                ))
        except (json.JSONDecodeError, TypeError):
            pass

    # 3. Check linked outcomes
    outcomes = list(db.execute_and_fetch(
        """
        MATCH (w:WorkItem {id: $id})-[:CONTRIBUTES_TO]->(o:Outcome)
        WHERE o.state = "pending"
        RETURN o.id AS id, o.title AS title
        """,
        {"id": work_item_id},
    ))
    for outcome in outcomes:
        warnings.append(Warning(
            code="outcome_pending",
            message=f"Linked outcome '{outcome['title']}' is still pending",
            work_item_id=outcome["id"],
        ))

    return warnings


# ── Orphan tasks ───────────────────────────────────────────────────


def check_orphan_tasks(db: Memgraph, project_id: str) -> list[Warning]:
    """
    Find tasks that don't contribute to any milestone or outcome.

    These are "orphans" — work that isn't connected to any goal.
    """
    orphans = list(db.execute_and_fetch(
        """
        MATCH (w:WorkItem {project_id: $project_id, kind: "task"})
        WHERE NOT (w)-[:CONTRIBUTES_TO]->()
        RETURN w.id AS id, w.title AS title
        """,
        {"project_id": project_id},
    ))
    return [
        Warning(
            code="orphan_task",
            message=f"Task '{row['title']}' doesn't contribute to any milestone or outcome",
            work_item_id=row["id"],
        )
        for row in orphans
    ]
