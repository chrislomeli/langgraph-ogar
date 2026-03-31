"""
call_the_ai — stub for the LLM interaction layer.

In production this calls an LLM (with tools, system prompt, conversation
history) and returns a structured ProjectPatch.

For now it returns deterministic mock patches so the graph can run
without any LLM dependency.
"""
from __future__ import annotations

from ogar.domain.consult.patches import ProjectPatch
from ogar.domain.models.project import Goal, Requirement, Project


def call_the_ai(project: Project, stage: str, human_reply: str) -> ProjectPatch:
    """
    Given the current project, the stage we're working on, and the
    human's free-text reply, produce a structured ProjectPatch.

    Parameters
    ----------
    project : Project
        Current project state.
    stage : str
        Which stage we're eliciting ("goals", "requirements", …).
    human_reply : str
        Raw text from the human.

    Returns
    -------
    ProjectPatch
        Structured changes to apply to the project.
    """
    # ---- STUB: replace with real LLM call later ----
    if stage == "goals":
        return _mock_goals_patch(project)

    if stage == "requirements":
        return _mock_requirements_patch(project)

    return ProjectPatch()


# ──────────────────────────────────────────────
# Mock helpers (deterministic, no LLM)
# ──────────────────────────────────────────────

def _mock_goals_patch(project: Project) -> ProjectPatch:
    """Return canned goals that mirror the dogfood project."""
    return ProjectPatch(
        title="Agentic Project Planner Demo",
        goals_upsert={
            "g_demo_tool": Goal(
                gid="g_demo_tool",
                statement="Build a working single-user agentic project planning tool.",
                success_metrics=[
                    "Create/edit/retrieve a project plan via CLI",
                    "Pause and resume execution after hours/days",
                    "Generate stale/blocker/orphan uncertainty reports",
                ],
                priority=0,
                status="active",
            ),
            "g_consistency": Goal(
                gid="g_consistency",
                statement="Enforce consistent collaboration workflow via schema and deterministic gating.",
                success_metrics=[
                    "Project-level uncertainty register",
                    "Deterministic validators catch missing links/fields",
                ],
                priority=1,
                status="active",
            ),
        },
    )


def _mock_requirements_patch(project: Project) -> ProjectPatch:
    """Return canned requirements linked to existing goals."""
    goal_ids = list(project.goals.keys())
    if not goal_ids:
        return ProjectPatch(suggested_questions=["Define goals before requirements."])

    return ProjectPatch(
        requirements_upsert={
            "r_interactive_planning": Requirement(
                rid="r_interactive_planning",
                type="functional",
                statement="User can outline goals and collaborate with system to produce a plan.",
                acceptance_criteria=[
                    "System drafts work items from goals",
                    "System asks clarification questions when blockers detected",
                ],
                source_goal_ids=goal_ids,
                status="draft",
            ),
            "r_persistence": Requirement(
                rid="r_persistence",
                type="functional",
                statement="Project plan is persisted and can be retrieved and modified.",
                acceptance_criteria=[
                    "Create → store → retrieve yields equivalent object",
                ],
                source_goal_ids=[goal_ids[0]],
                status="draft",
            ),
        },
    )
