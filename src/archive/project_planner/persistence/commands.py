"""
Layer 1 — Write commands for the project engine.

Every command:
  1. Executes the Cypher mutation
  2. Appends an :Event node with :ABOUT and :BY edges

Cycle detection for PARENT_OF, CONTRIBUTES_TO, DEPENDS_ON is enforced here.
Cross-project CONTRIBUTES_TO is rejected here.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from gqlalchemy import Memgraph


# ── Helpers ────────────────────────────────────────────────────────


def _new_id() -> str:
    return str(uuid.uuid4())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _append_event(
    db: Memgraph,
    actor_id: str,
    verb: str,
    target_id: str,
    target_label: str,
    payload: dict[str, Any] | None = None,
) -> str:
    """Append an Event node with ABOUT and BY edges. Returns event id."""
    event_id = _new_id()
    payload_json = json.dumps(payload or {})
    db.execute(
        """
        MATCH (target {id: $target_id}), (actor:Actor {id: $actor_id})
        CREATE (e:Event {
            id: $event_id,
            ts: datetime(),
            verb: $verb,
            payload: $payload
        })
        CREATE (e)-[:ABOUT]->(target)
        CREATE (e)-[:BY]->(actor)
        """,
        {
            "event_id": event_id,
            "actor_id": actor_id,
            "verb": verb,
            "target_id": target_id,
            "payload": payload_json,
        },
    )
    return event_id


def _would_create_cycle(
    db: Memgraph,
    from_id: str,
    to_id: str,
    rel_type: str,
) -> bool:
    """
    Check if adding from_id -> to_id with rel_type would create a cycle.

    A cycle exists if there is already a path from to_id back to from_id
    via the same relationship type.
    """
    result = db.execute_and_fetch(
        f"""
        MATCH path = (target {{id: $to_id}})-[:{rel_type}*1..]->(source {{id: $from_id}})
        RETURN count(path) AS cnt
        """,
        {"from_id": from_id, "to_id": to_id},
    )
    row = next(result, None)
    return row is not None and row["cnt"] > 0


def _get_project_id(db: Memgraph, node_id: str) -> Optional[str]:
    """Get project_id from a WorkItem or Outcome node."""
    result = db.execute_and_fetch(
        """
        MATCH (n {id: $node_id})
        WHERE n:WorkItem OR n:Outcome
        RETURN n.project_id AS project_id
        """,
        {"node_id": node_id},
    )
    row = next(result, None)
    return row["project_id"] if row else None


# ── Actor ──────────────────────────────────────────────────────────


def create_actor(
    db: Memgraph,
    *,
    id: str | None = None,
    kind: str,
    name: str,
) -> str:
    """Create an Actor node. Returns actor id."""
    actor_id = id or _new_id()
    db.execute(
        """
        MERGE (a:Actor {id: $id})
        ON CREATE SET a.kind = $kind, a.name = $name
        """,
        {"id": actor_id, "kind": kind, "name": name},
    )
    return actor_id


# ── Project ────────────────────────────────────────────────────────


def create_project(
    db: Memgraph,
    *,
    id: str | None = None,
    name: str,
    actor_id: str,
) -> str:
    """Create a Project node. Returns project id."""
    project_id = id or _new_id()
    db.execute(
        """
        CREATE (p:Project {
            id: $id,
            name: $name,
            status: "active",
            phase: "exploring",
            created_at: datetime(),
            updated_at: datetime()
        })
        """,
        {"id": project_id, "name": name},
    )
    _append_event(db, actor_id, "ProjectCreated", project_id, "Project",
                  {"name": name})
    return project_id


def set_project_phase(
    db: Memgraph,
    *,
    project_id: str,
    phase: str,
    actor_id: str,
) -> str:
    """Set the project phase. Returns the old phase."""
    result = db.execute_and_fetch(
        "MATCH (p:Project {id: $id}) RETURN p.phase AS old_phase",
        {"id": project_id},
    )
    row = next(result, None)
    if row is None:
        raise KeyError(f"Project '{project_id}' not found")
    old_phase = row["old_phase"] or "exploring"

    db.execute(
        """
        MATCH (p:Project {id: $id})
        SET p.phase = $phase, p.updated_at = datetime()
        """,
        {"id": project_id, "phase": phase},
    )
    _append_event(db, actor_id, "PhaseChanged", project_id, "Project",
                  {"from": old_phase, "to": phase})
    return old_phase


# ── WorkItem ───────────────────────────────────────────────────────


def create_work_item(
    db: Memgraph,
    *,
    id: str | None = None,
    project_id: str,
    title: str,
    kind: str,
    actor_id: str,
    description: str | None = None,
    state: str = "proposed",
    priority: int | None = None,
    due_at: str | None = None,
    estimate_minutes: int | None = None,
    acceptance: dict | None = None,
) -> str:
    """Create a WorkItem node. Returns work item id."""
    wi_id = id or _new_id()
    acceptance_json = json.dumps(acceptance) if acceptance else None
    db.execute(
        """
        CREATE (w:WorkItem {
            id: $id,
            project_id: $project_id,
            title: $title,
            kind: $kind,
            state: $state,
            created_at: datetime(),
            updated_at: datetime()
        })
        SET w.description = $description,
            w.priority = $priority,
            w.due_at = $due_at,
            w.estimate_minutes = $estimate_minutes,
            w.acceptance = $acceptance
        """,
        {
            "id": wi_id,
            "project_id": project_id,
            "title": title,
            "kind": kind,
            "state": state,
            "description": description,
            "priority": priority,
            "due_at": due_at,
            "estimate_minutes": estimate_minutes,
            "acceptance": acceptance_json,
        },
    )
    _append_event(db, actor_id, "WorkItemCreated", wi_id, "WorkItem",
                  {"title": title, "kind": kind, "project_id": project_id})
    return wi_id


def update_work_item(
    db: Memgraph,
    *,
    id: str,
    actor_id: str,
    **fields: Any,
) -> None:
    """Update arbitrary fields on a WorkItem."""
    if not fields:
        return
    set_clauses = []
    params: dict[str, Any] = {"id": id}
    for key, value in fields.items():
        param_name = f"val_{key}"
        if key == "acceptance" and isinstance(value, dict):
            value = json.dumps(value)
        set_clauses.append(f"w.{key} = ${param_name}")
        params[param_name] = value
    set_clauses.append("w.updated_at = datetime()")
    set_str = ", ".join(set_clauses)
    db.execute(
        f"MATCH (w:WorkItem {{id: $id}}) SET {set_str}",
        params,
    )
    _append_event(db, actor_id, "WorkItemUpdated", id, "WorkItem",
                  {"fields": list(fields.keys())})


def set_work_item_state(
    db: Memgraph,
    *,
    id: str,
    new_state: str,
    actor_id: str,
    reason: str | None = None,
) -> None:
    """Change a WorkItem's state."""
    result = db.execute_and_fetch(
        "MATCH (w:WorkItem {id: $id}) RETURN w.state AS old_state",
        {"id": id},
    )
    row = next(result, None)
    if row is None:
        raise KeyError(f"WorkItem '{id}' not found")
    old_state = row["old_state"]

    db.execute(
        """
        MATCH (w:WorkItem {id: $id})
        SET w.state = $new_state, w.updated_at = datetime()
        """,
        {"id": id, "new_state": new_state},
    )
    _append_event(db, actor_id, "WorkItemStateChanged", id, "WorkItem",
                  {"from": old_state, "to": new_state, "reason": reason})


# ── Linking: PARENT_OF ─────────────────────────────────────────────


def link_parent(
    db: Memgraph,
    *,
    child_id: str,
    parent_id: str,
    actor_id: str,
) -> None:
    """Add PARENT_OF edge. Rejects cycles and cross-project links."""
    # Same project check
    child_pid = _get_project_id(db, child_id)
    parent_pid = _get_project_id(db, parent_id)
    if child_pid != parent_pid:
        raise ValueError(
            f"Cannot link parent: child project '{child_pid}' != parent project '{parent_pid}'"
        )

    # Cycle check
    if child_id == parent_id:
        raise ValueError("Cannot link a WorkItem as its own parent")
    if _would_create_cycle(db, parent_id, child_id, "PARENT_OF"):
        raise ValueError(
            f"Cannot link parent: would create cycle ({parent_id} -> {child_id})"
        )

    db.execute(
        """
        MATCH (parent:WorkItem {id: $parent_id}), (child:WorkItem {id: $child_id})
        MERGE (parent)-[:PARENT_OF]->(child)
        """,
        {"parent_id": parent_id, "child_id": child_id},
    )
    _append_event(db, actor_id, "ParentLinked", child_id, "WorkItem",
                  {"parent_id": parent_id})


def unlink_parent(
    db: Memgraph,
    *,
    child_id: str,
    parent_id: str,
    actor_id: str,
) -> None:
    """Remove PARENT_OF edge."""
    db.execute(
        """
        MATCH (parent:WorkItem {id: $parent_id})-[r:PARENT_OF]->(child:WorkItem {id: $child_id})
        DELETE r
        """,
        {"parent_id": parent_id, "child_id": child_id},
    )
    _append_event(db, actor_id, "ParentUnlinked", child_id, "WorkItem",
                  {"parent_id": parent_id})


# ── Linking: CONTRIBUTES_TO ────────────────────────────────────────


def link_contributes(
    db: Memgraph,
    *,
    from_id: str,
    to_id: str,
    actor_id: str,
) -> None:
    """Add CONTRIBUTES_TO edge. Rejects cycles and cross-project links."""
    from_pid = _get_project_id(db, from_id)
    to_pid = _get_project_id(db, to_id)
    if from_pid != to_pid:
        raise ValueError(
            f"Cannot link contribution across projects: '{from_pid}' != '{to_pid}'"
        )

    if from_id == to_id:
        raise ValueError("Cannot contribute to self")
    if _would_create_cycle(db, from_id, to_id, "CONTRIBUTES_TO"):
        raise ValueError(
            f"Cannot link contribution: would create cycle ({from_id} -> {to_id})"
        )

    db.execute(
        """
        MATCH (a {id: $from_id}), (b {id: $to_id})
        WHERE (a:WorkItem) AND (b:WorkItem OR b:Outcome)
        MERGE (a)-[:CONTRIBUTES_TO]->(b)
        """,
        {"from_id": from_id, "to_id": to_id},
    )
    _append_event(db, actor_id, "ContributionLinked", from_id, "WorkItem",
                  {"to_id": to_id})


def unlink_contributes(
    db: Memgraph,
    *,
    from_id: str,
    to_id: str,
    actor_id: str,
) -> None:
    """Remove CONTRIBUTES_TO edge."""
    db.execute(
        """
        MATCH (a {id: $from_id})-[r:CONTRIBUTES_TO]->(b {id: $to_id})
        DELETE r
        """,
        {"from_id": from_id, "to_id": to_id},
    )
    _append_event(db, actor_id, "ContributionUnlinked", from_id, "WorkItem",
                  {"to_id": to_id})


# ── Linking: DEPENDS_ON ────────────────────────────────────────────


def link_depends_on(
    db: Memgraph,
    *,
    from_id: str,
    to_id: str,
    actor_id: str,
) -> None:
    """Add DEPENDS_ON edge. Rejects cycles. Cross-project allowed."""
    if from_id == to_id:
        raise ValueError("Cannot depend on self")
    if _would_create_cycle(db, from_id, to_id, "DEPENDS_ON"):
        raise ValueError(
            f"Cannot link dependency: would create cycle ({from_id} -> {to_id})"
        )

    db.execute(
        """
        MATCH (a:WorkItem {id: $from_id}), (b:WorkItem {id: $to_id})
        MERGE (a)-[:DEPENDS_ON]->(b)
        """,
        {"from_id": from_id, "to_id": to_id},
    )
    _append_event(db, actor_id, "DependencyAdded", from_id, "WorkItem",
                  {"depends_on": to_id})


def unlink_depends_on(
    db: Memgraph,
    *,
    from_id: str,
    to_id: str,
    actor_id: str,
) -> None:
    """Remove DEPENDS_ON edge."""
    db.execute(
        """
        MATCH (a:WorkItem {id: $from_id})-[r:DEPENDS_ON]->(b:WorkItem {id: $to_id})
        DELETE r
        """,
        {"from_id": from_id, "to_id": to_id},
    )
    _append_event(db, actor_id, "DependencyRemoved", from_id, "WorkItem",
                  {"depends_on": to_id})


# ── Assignment ─────────────────────────────────────────────────────


def assign(
    db: Memgraph,
    *,
    work_item_id: str,
    actor_id: str,
    assigned_by: str,
) -> None:
    """Assign an Actor to a WorkItem. Multiple assignments allowed."""
    db.execute(
        """
        MATCH (w:WorkItem {id: $work_item_id}), (a:Actor {id: $actor_id})
        MERGE (w)-[:ASSIGNED_TO]->(a)
        """,
        {"work_item_id": work_item_id, "actor_id": actor_id},
    )
    _append_event(db, assigned_by, "Assigned", work_item_id, "WorkItem",
                  {"actor_id": actor_id})


def unassign(
    db: Memgraph,
    *,
    work_item_id: str,
    actor_id: str,
    unassigned_by: str,
) -> None:
    """Remove assignment."""
    db.execute(
        """
        MATCH (w:WorkItem {id: $work_item_id})-[r:ASSIGNED_TO]->(a:Actor {id: $actor_id})
        DELETE r
        """,
        {"work_item_id": work_item_id, "actor_id": actor_id},
    )
    _append_event(db, unassigned_by, "Unassigned", work_item_id, "WorkItem",
                  {"actor_id": actor_id})


# ── Outcome ────────────────────────────────────────────────────────


def create_outcome(
    db: Memgraph,
    *,
    id: str | None = None,
    project_id: str,
    title: str,
    criteria: str,
    actor_id: str,
) -> str:
    """Create an Outcome node. Returns outcome id."""
    outcome_id = id or _new_id()
    db.execute(
        """
        CREATE (o:Outcome {
            id: $id,
            project_id: $project_id,
            title: $title,
            criteria: $criteria,
            state: "pending",
            created_at: datetime(),
            updated_at: datetime()
        })
        """,
        {
            "id": outcome_id,
            "project_id": project_id,
            "title": title,
            "criteria": criteria,
        },
    )
    _append_event(db, actor_id, "OutcomeCreated", outcome_id, "Outcome",
                  {"title": title, "project_id": project_id})
    return outcome_id


def set_outcome_state(
    db: Memgraph,
    *,
    id: str,
    new_state: str,
    actor_id: str,
) -> None:
    """Change an Outcome's state."""
    result = db.execute_and_fetch(
        "MATCH (o:Outcome {id: $id}) RETURN o.state AS old_state",
        {"id": id},
    )
    row = next(result, None)
    if row is None:
        raise KeyError(f"Outcome '{id}' not found")
    old_state = row["old_state"]

    db.execute(
        """
        MATCH (o:Outcome {id: $id})
        SET o.state = $new_state, o.updated_at = datetime()
        """,
        {"id": id, "new_state": new_state},
    )
    _append_event(db, actor_id, "OutcomeStateChanged", id, "Outcome",
                  {"from": old_state, "to": new_state})


# ── Attachments ────────────────────────────────────────────────────


def attach_artifact(
    db: Memgraph,
    *,
    target_id: str,
    project_id: str,
    kind: str,
    ref: str,
    actor_id: str,
    meta: str | None = None,
) -> str:
    """Create an Artifact and attach it to a WorkItem or Outcome."""
    artifact_id = _new_id()
    db.execute(
        """
        MATCH (target {id: $target_id})
        WHERE target:WorkItem OR target:Outcome
        CREATE (a:Artifact {
            id: $artifact_id,
            project_id: $project_id,
            kind: $kind,
            ref: $ref,
            meta: $meta,
            created_at: datetime()
        })
        CREATE (target)-[:HAS_ARTIFACT]->(a)
        """,
        {
            "target_id": target_id,
            "artifact_id": artifact_id,
            "project_id": project_id,
            "kind": kind,
            "ref": ref,
            "meta": meta,
        },
    )
    _append_event(db, actor_id, "ArtifactAttached", target_id, "WorkItem",
                  {"artifact_id": artifact_id, "kind": kind, "ref": ref})
    return artifact_id


def add_note(
    db: Memgraph,
    *,
    target_id: str,
    project_id: str,
    body: str,
    actor_id: str,
    tags: list[str] | None = None,
) -> str:
    """Create a Note and attach it to a WorkItem or Outcome."""
    note_id = _new_id()
    db.execute(
        """
        MATCH (target {id: $target_id})
        WHERE target:WorkItem OR target:Outcome
        CREATE (n:Note {
            id: $note_id,
            project_id: $project_id,
            body: $body,
            tags: $tags,
            created_at: datetime()
        })
        CREATE (target)-[:HAS_NOTE]->(n)
        """,
        {
            "target_id": target_id,
            "note_id": note_id,
            "project_id": project_id,
            "body": body,
            "tags": tags or [],
        },
    )
    _append_event(db, actor_id, "NoteAdded", target_id, "WorkItem",
                  {"note_id": note_id})
    return note_id


# ── Project root ───────────────────────────────────────────────────


def set_project_root(
    db: Memgraph,
    *,
    project_id: str,
    work_item_id: str,
    actor_id: str,
) -> None:
    """Set the HAS_ROOT edge from a Project to a WorkItem."""
    db.execute(
        """
        MATCH (p:Project {id: $project_id}), (w:WorkItem {id: $work_item_id})
        MERGE (p)-[:HAS_ROOT]->(w)
        """,
        {"project_id": project_id, "work_item_id": work_item_id},
    )
    _append_event(db, actor_id, "ProjectRootSet", project_id, "Project",
                  {"work_item_id": work_item_id})
