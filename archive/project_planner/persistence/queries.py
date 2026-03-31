"""
Layer 1 — Read queries for the project engine.

Pure data retrieval — no business logic, no computed fields.
Returns dicts from Cypher results; callers convert to domain models as needed.
"""

from __future__ import annotations

from typing import Any, Optional

from gqlalchemy import Memgraph


# ── Project ────────────────────────────────────────────────────────


def get_project(db: Memgraph, project_id: str) -> Optional[dict[str, Any]]:
    """Get a single project by id."""
    result = db.execute_and_fetch(
        """
        MATCH (p:Project {id: $id})
        RETURN p.id AS id, p.name AS name, p.status AS status,
               p.phase AS phase,
               p.created_at AS created_at, p.updated_at AS updated_at
        """,
        {"id": project_id},
    )
    return next(result, None)


def list_projects(db: Memgraph) -> list[dict[str, Any]]:
    """List all projects."""
    return list(db.execute_and_fetch(
        """
        MATCH (p:Project)
        RETURN p.id AS id, p.name AS name, p.status AS status,
               p.created_at AS created_at, p.updated_at AS updated_at
        ORDER BY p.name
        """
    ))


# ── WorkItem ───────────────────────────────────────────────────────


_WORK_ITEM_RETURN = """
    RETURN w.id AS id, w.project_id AS project_id, w.title AS title,
           w.description AS description, w.kind AS kind, w.state AS state,
           w.priority AS priority, w.due_at AS due_at,
           w.estimate_minutes AS estimate_minutes, w.acceptance AS acceptance,
           w.created_at AS created_at, w.updated_at AS updated_at
"""


def get_work_item(db: Memgraph, work_item_id: str) -> Optional[dict[str, Any]]:
    """Get a single work item by id."""
    result = db.execute_and_fetch(
        f"MATCH (w:WorkItem {{id: $id}}) {_WORK_ITEM_RETURN}",
        {"id": work_item_id},
    )
    return next(result, None)


def list_work_items(
    db: Memgraph,
    project_id: str,
    state: str | None = None,
    kind: str | None = None,
) -> list[dict[str, Any]]:
    """List work items for a project, optionally filtered by state and/or kind."""
    where_clauses = ["w.project_id = $project_id"]
    params: dict[str, Any] = {"project_id": project_id}

    if state is not None:
        where_clauses.append("w.state = $state")
        params["state"] = state
    if kind is not None:
        where_clauses.append("w.kind = $kind")
        params["kind"] = kind

    where_str = " AND ".join(where_clauses)
    return list(db.execute_and_fetch(
        f"MATCH (w:WorkItem) WHERE {where_str} {_WORK_ITEM_RETURN} ORDER BY w.priority DESC",
        params,
    ))


# ── Hierarchy ──────────────────────────────────────────────────────


def get_children(db: Memgraph, work_item_id: str) -> list[dict[str, Any]]:
    """Get direct children (PARENT_OF targets) of a work item."""
    return list(db.execute_and_fetch(
        f"""
        MATCH (parent:WorkItem {{id: $id}})-[:PARENT_OF]->(w:WorkItem)
        {_WORK_ITEM_RETURN}
        ORDER BY w.priority DESC
        """,
        {"id": work_item_id},
    ))


def get_parent(db: Memgraph, work_item_id: str) -> Optional[dict[str, Any]]:
    """Get the parent of a work item (if any)."""
    result = db.execute_and_fetch(
        f"""
        MATCH (w:WorkItem)-[:PARENT_OF]->(child:WorkItem {{id: $id}})
        RETURN w.id AS id, w.project_id AS project_id, w.title AS title,
               w.description AS description, w.kind AS kind, w.state AS state,
               w.priority AS priority, w.due_at AS due_at,
               w.estimate_minutes AS estimate_minutes, w.acceptance AS acceptance,
               w.created_at AS created_at, w.updated_at AS updated_at
        """,
        {"id": work_item_id},
    )
    return next(result, None)


def get_plan_tree(db: Memgraph, project_id: str) -> list[dict[str, Any]]:
    """
    Get the full plan tree for a project.

    Returns all work items reachable from the project root via PARENT_OF,
    with a 'depth' field indicating tree level (root = 0).
    """
    return list(db.execute_and_fetch(
        """
        MATCH (p:Project {id: $project_id})-[:HAS_ROOT]->(root:WorkItem)
        MATCH path = (root)-[:PARENT_OF*0..]->(n:WorkItem)
        WITH n, length(path) AS depth
        RETURN n.id AS id, n.project_id AS project_id, n.title AS title,
               n.description AS description, n.kind AS kind, n.state AS state,
               n.priority AS priority, n.due_at AS due_at,
               depth
        ORDER BY depth, n.priority DESC
        """,
        {"project_id": project_id},
    ))


# ── Contributions ──────────────────────────────────────────────────


def get_contributors(db: Memgraph, target_id: str) -> list[dict[str, Any]]:
    """Get work items that contribute to a target (WorkItem or Outcome)."""
    return list(db.execute_and_fetch(
        f"""
        MATCH (w:WorkItem)-[:CONTRIBUTES_TO]->(target {{id: $id}})
        {_WORK_ITEM_RETURN}
        ORDER BY w.priority DESC
        """,
        {"id": target_id},
    ))


def get_contributes_to(db: Memgraph, work_item_id: str) -> list[dict[str, Any]]:
    """Get targets that a work item contributes to (WorkItems or Outcomes)."""
    return list(db.execute_and_fetch(
        """
        MATCH (w:WorkItem {id: $id})-[:CONTRIBUTES_TO]->(target)
        RETURN target.id AS id, target.title AS title,
               labels(target) AS labels, target.state AS state
        """,
        {"id": work_item_id},
    ))


# ── Dependencies ───────────────────────────────────────────────────


def get_dependencies(db: Memgraph, work_item_id: str) -> list[dict[str, Any]]:
    """Get work items that this item depends on."""
    return list(db.execute_and_fetch(
        f"""
        MATCH (w:WorkItem {{id: $id}})-[:DEPENDS_ON]->(dep:WorkItem)
        RETURN dep.id AS id, dep.project_id AS project_id, dep.title AS title,
               dep.description AS description, dep.kind AS kind, dep.state AS state,
               dep.priority AS priority, dep.due_at AS due_at,
               dep.estimate_minutes AS estimate_minutes, dep.acceptance AS acceptance,
               dep.created_at AS created_at, dep.updated_at AS updated_at
        """,
        {"id": work_item_id},
    ))


def get_dependents(db: Memgraph, work_item_id: str) -> list[dict[str, Any]]:
    """Get work items that depend on this item."""
    return list(db.execute_and_fetch(
        f"""
        MATCH (dep:WorkItem)-[:DEPENDS_ON]->(w:WorkItem {{id: $id}})
        RETURN dep.id AS id, dep.project_id AS project_id, dep.title AS title,
               dep.description AS description, dep.kind AS kind, dep.state AS state,
               dep.priority AS priority, dep.due_at AS due_at,
               dep.estimate_minutes AS estimate_minutes, dep.acceptance AS acceptance,
               dep.created_at AS created_at, dep.updated_at AS updated_at
        """,
        {"id": work_item_id},
    ))


# ── Assignments ────────────────────────────────────────────────────


def get_assignments(db: Memgraph, work_item_id: str) -> list[dict[str, Any]]:
    """Get actors assigned to a work item."""
    return list(db.execute_and_fetch(
        """
        MATCH (w:WorkItem {id: $id})-[:ASSIGNED_TO]->(a:Actor)
        RETURN a.id AS id, a.kind AS kind, a.name AS name
        """,
        {"id": work_item_id},
    ))


def get_assigned_items(
    db: Memgraph,
    actor_id: str,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """Get work items assigned to an actor, optionally filtered by project."""
    if project_id:
        return list(db.execute_and_fetch(
            f"""
            MATCH (a:Actor {{id: $actor_id}})<-[:ASSIGNED_TO]-(w:WorkItem)
            WHERE w.project_id = $project_id
            {_WORK_ITEM_RETURN}
            ORDER BY w.priority DESC
            """,
            {"actor_id": actor_id, "project_id": project_id},
        ))
    return list(db.execute_and_fetch(
        f"""
        MATCH (a:Actor {{id: $actor_id}})<-[:ASSIGNED_TO]-(w:WorkItem)
        {_WORK_ITEM_RETURN}
        ORDER BY w.priority DESC
        """,
        {"actor_id": actor_id},
    ))


# ── Attachments ────────────────────────────────────────────────────


def get_notes(db: Memgraph, target_id: str) -> list[dict[str, Any]]:
    """Get notes attached to a work item or outcome."""
    return list(db.execute_and_fetch(
        """
        MATCH (target {id: $id})-[:HAS_NOTE]->(n:Note)
        RETURN n.id AS id, n.project_id AS project_id, n.body AS body,
               n.tags AS tags, n.created_at AS created_at
        ORDER BY n.created_at DESC
        """,
        {"id": target_id},
    ))


def get_artifacts(db: Memgraph, target_id: str) -> list[dict[str, Any]]:
    """Get artifacts attached to a work item or outcome."""
    return list(db.execute_and_fetch(
        """
        MATCH (target {id: $id})-[:HAS_ARTIFACT]->(a:Artifact)
        RETURN a.id AS id, a.project_id AS project_id, a.kind AS kind,
               a.ref AS ref, a.meta AS meta, a.created_at AS created_at
        ORDER BY a.created_at DESC
        """,
        {"id": target_id},
    ))


# ── Outcome ────────────────────────────────────────────────────────


def get_outcome(db: Memgraph, outcome_id: str) -> Optional[dict[str, Any]]:
    """Get a single outcome by id."""
    result = db.execute_and_fetch(
        """
        MATCH (o:Outcome {id: $id})
        RETURN o.id AS id, o.project_id AS project_id, o.title AS title,
               o.criteria AS criteria, o.state AS state,
               o.created_at AS created_at, o.updated_at AS updated_at
        """,
        {"id": outcome_id},
    )
    return next(result, None)


def list_outcomes(db: Memgraph, project_id: str) -> list[dict[str, Any]]:
    """List all outcomes for a project."""
    return list(db.execute_and_fetch(
        """
        MATCH (o:Outcome {project_id: $project_id})
        RETURN o.id AS id, o.project_id AS project_id, o.title AS title,
               o.criteria AS criteria, o.state AS state,
               o.created_at AS created_at, o.updated_at AS updated_at
        ORDER BY o.title
        """,
        {"project_id": project_id},
    ))


# ── Events ─────────────────────────────────────────────────────────


def get_events(
    db: Memgraph,
    target_id: str | None = None,
    actor_id: str | None = None,
    verb: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Query the event log with optional filters.

    At least one filter should be provided for reasonable performance.
    """
    match_parts = ["MATCH (e:Event)"]
    where_clauses: list[str] = []
    params: dict[str, Any] = {"limit": limit}

    if target_id:
        match_parts.append("MATCH (e)-[:ABOUT]->(target {id: $target_id})")
        params["target_id"] = target_id
    if actor_id:
        match_parts.append("MATCH (e)-[:BY]->(actor:Actor {id: $actor_id})")
        params["actor_id"] = actor_id
    if verb:
        where_clauses.append("e.verb = $verb")
        params["verb"] = verb

    query = "\n".join(match_parts)
    if where_clauses:
        query += "\nWHERE " + " AND ".join(where_clauses)

    query += """
    OPTIONAL MATCH (e)-[:BY]->(by:Actor)
    OPTIONAL MATCH (e)-[:ABOUT]->(about)
    RETURN e.id AS id, e.ts AS ts, e.verb AS verb, e.payload AS payload,
           by.id AS actor_id, about.id AS about_id
    ORDER BY e.ts DESC
    LIMIT $limit
    """

    return list(db.execute_and_fetch(query, params))
