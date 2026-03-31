"""
Layer 2 — Semantic views for the project engine.

These are computed projections over the graph — they never mutate data.
They combine multiple Layer 1 queries to produce meaningful reports.
"""

from __future__ import annotations

from typing import Any

from gqlalchemy import Memgraph


# ── Milestone Rollup ───────────────────────────────────────────────


def milestone_rollup(db: Memgraph, milestone_id: str) -> dict[str, Any]:
    """
    Compute completion ratio for a milestone based on its direct contributors.

    Returns:
        {"milestone_id", "title", "total", "done", "completion_ratio"}
    """
    result = db.execute_and_fetch(
        """
        MATCH (m:WorkItem {id: $milestone_id})
        OPTIONAL MATCH (w:WorkItem)-[:CONTRIBUTES_TO]->(m)
        WITH m,
             count(w) AS total,
             sum(CASE WHEN w.state = "done" THEN 1 ELSE 0 END) AS done
        RETURN m.id AS milestone_id,
               m.title AS title,
               total,
               done,
               CASE WHEN total = 0 THEN 0.0
                    ELSE (1.0 * done / total)
               END AS completion_ratio
        """,
        {"milestone_id": milestone_id},
    )
    row = next(result, None)
    if row is None:
        raise KeyError(f"Milestone '{milestone_id}' not found")
    return dict(row)


# ── Project Status ─────────────────────────────────────────────────


def project_status(db: Memgraph, project_id: str) -> dict[str, Any]:
    """
    High-level project health report.

    Returns:
        {
            "project_id", "project_name",
            "milestones": [{"id", "title", "total", "done", "completion_ratio"}],
            "outcomes": [{"id", "title", "state"}]
        }
    """
    # Project info
    proj = next(db.execute_and_fetch(
        "MATCH (p:Project {id: $id}) RETURN p.name AS name",
        {"id": project_id},
    ), None)
    if proj is None:
        raise KeyError(f"Project '{project_id}' not found")

    # Milestones with rollup
    milestones = list(db.execute_and_fetch(
        """
        MATCH (w:WorkItem {project_id: $project_id, kind: "milestone"})
        OPTIONAL MATCH (c:WorkItem)-[:CONTRIBUTES_TO]->(w)
        WITH w,
             count(c) AS total,
             sum(CASE WHEN c.state = "done" THEN 1 ELSE 0 END) AS done
        RETURN w.id AS id, w.title AS title, w.state AS state,
               total, done,
               CASE WHEN total = 0 THEN 0.0
                    ELSE (1.0 * done / total)
               END AS completion_ratio
        ORDER BY w.priority DESC
        """,
        {"project_id": project_id},
    ))

    # Outcomes
    outcomes = list(db.execute_and_fetch(
        """
        MATCH (o:Outcome {project_id: $project_id})
        RETURN o.id AS id, o.title AS title, o.state AS state
        ORDER BY o.title
        """,
        {"project_id": project_id},
    ))

    return {
        "project_id": project_id,
        "project_name": proj["name"],
        "milestones": [dict(m) for m in milestones],
        "outcomes": [dict(o) for o in outcomes],
    }


# ── Week View ──────────────────────────────────────────────────────


def week_view(
    db: Memgraph,
    actor_id: str,
    start: str,
    end: str,
) -> list[dict[str, Any]]:
    """
    Cross-project weekly queue for an actor.

    Args:
        start: ISO datetime string for week start
        end: ISO datetime string for week end

    Returns work items assigned to the actor with due_at in [start, end),
    sorted by due_at then priority.
    """
    return list(db.execute_and_fetch(
        """
        MATCH (a:Actor {id: $actor_id})<-[:ASSIGNED_TO]-(w:WorkItem)
        WHERE w.state IN ["planned", "active"]
          AND w.due_at IS NOT NULL
          AND w.due_at >= datetime($start)
          AND w.due_at < datetime($end)
        RETURN w.id AS id, w.project_id AS project_id, w.title AS title,
               w.kind AS kind, w.state AS state, w.priority AS priority,
               w.due_at AS due_at
        ORDER BY w.due_at ASC, w.priority DESC
        """,
        {"actor_id": actor_id, "start": start, "end": end},
    ))


# ── GTD Next Actions ──────────────────────────────────────────────


def gtd_next_actions(db: Memgraph, actor_id: str) -> list[dict[str, Any]]:
    """
    GTD-style "next actions" for an actor.

    Returns work items that are:
      - assigned to the actor
      - in planned or active state
      - NOT blocked (no unresolved dependencies)
    """
    return list(db.execute_and_fetch(
        """
        MATCH (a:Actor {id: $actor_id})<-[:ASSIGNED_TO]-(w:WorkItem)
        WHERE w.state IN ["planned", "active"]
          AND NOT EXISTS {
            MATCH (w)-[:DEPENDS_ON]->(b:WorkItem)
            WHERE b.state <> "done"
          }
        RETURN w.id AS id, w.project_id AS project_id, w.title AS title,
               w.kind AS kind, w.state AS state, w.priority AS priority,
               w.due_at AS due_at
        ORDER BY w.priority DESC
        """,
        {"actor_id": actor_id},
    ))


# ── Blockers Report ───────────────────────────────────────────────


def blockers_report(db: Memgraph, project_id: str) -> list[dict[str, Any]]:
    """
    Find all blocked work items in a project and what blocks them.

    Returns:
        [{"item_id", "item_title", "blocked_by": [{"id", "title", "state"}]}]
    """
    rows = list(db.execute_and_fetch(
        """
        MATCH (w:WorkItem {project_id: $project_id})-[:DEPENDS_ON]->(b:WorkItem)
        WHERE b.state <> "done"
        RETURN w.id AS item_id, w.title AS item_title, w.priority AS priority,
               b.id AS blocker_id, b.title AS blocker_title, b.state AS blocker_state
        ORDER BY w.priority DESC
        """,
        {"project_id": project_id},
    ))
    # Group by blocked item
    grouped: dict[str, dict[str, Any]] = {}
    for r in rows:
        key = r["item_id"]
        if key not in grouped:
            grouped[key] = {
                "item_id": r["item_id"],
                "item_title": r["item_title"],
                "blocked_by": [],
            }
        grouped[key]["blocked_by"].append({
            "id": r["blocker_id"],
            "title": r["blocker_title"],
            "state": r["blocker_state"],
        })
    return list(grouped.values())


# ── Milestones at Risk ─────────────────────────────────────────────


def milestones_at_risk(
    db: Memgraph,
    project_id: str,
    threshold: float = 0.5,
) -> list[dict[str, Any]]:
    """
    Find milestones with low completion that have a due date approaching.

    Args:
        threshold: completion ratio below which a milestone is "at risk"

    Returns milestones with due_at set and completion_ratio < threshold.
    """
    return list(db.execute_and_fetch(
        """
        MATCH (m:WorkItem {project_id: $project_id, kind: "milestone"})
        WHERE m.due_at IS NOT NULL
        OPTIONAL MATCH (c:WorkItem)-[:CONTRIBUTES_TO]->(m)
        WITH m,
             count(c) AS total,
             sum(CASE WHEN c.state = "done" THEN 1 ELSE 0 END) AS done
        WITH m, total, done,
             CASE WHEN total = 0 THEN 0.0
                  ELSE (1.0 * done / total)
             END AS completion_ratio
        WHERE completion_ratio < $threshold
        RETURN m.id AS id, m.title AS title, m.due_at AS due_at,
               total, done, completion_ratio
        ORDER BY m.due_at ASC
        """,
        {"project_id": project_id, "threshold": threshold},
    ))
