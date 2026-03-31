from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from starter.model.project import Project

"""

WARNING: This is a placeholder for now. we'll need to implement the actual goal elicitation logic.

"""


@dataclass
class ConsultingOutcome:
    project: Project
    questions_to_user: List[str]
    blockers: List[str]
    notes: List[str]


def goals_consulting_phase(
    project: Project,
    *,
    user_goal_bullets: Optional[List[str]] = None,
) -> ConsultingOutcome:
    """
    Consultant-style goal elicitation.

    Intended behavior:
      1) If user provides bullets, normalize them into Goal objects.
         - (LLM step) Convert bullets -> {gid, statement, success_metrics, priority}
      2) If goals are missing or not measurable, ask targeted questions.
      3) Record uncertainties for anything that blocks moving to requirements.

    Deterministic checks you should enforce:
      - At least 1 goal exists
      - Active goals have success metrics
      - Priorities are set (or at least a P0 exists)

    Implementation notes:
      - In LangGraph, this would be a node that may interrupt() for HITL Q&A.
    """
    questions: List[str] = []
    blockers: List[str] = []
    notes: List[str] = []

    # 1) If no goals exist, we need input.
    if not project.goals and not user_goal_bullets:
        blockers.append("No goals defined.")
        questions.append("List 2–4 goals for the project, each with at least one success metric.")
        return ConsultingOutcome(project, questions, blockers, notes)

    # 2) If bullets provided, normalize into goals (LLM-assisted).
    if user_goal_bullets:
        # TODO:
        # - call LLM to draft Goal objects
        # - validate with Pydantic
        # - insert into project.goals
        pass

    # 3) Ask for missing success metrics.
    for g in project.goals.values():
        if g.status == "active" and not g.success_metrics:
            questions.append(f"Add success metrics for goal: {g.statement}")

    # 4) Optional: ask for prioritization.
    # TODO: enforce at least one priority == 0
    notes.append("Consider asking user to pick a P0 goal for this iteration.")

    return ConsultingOutcome(project, questions, blockers, notes)