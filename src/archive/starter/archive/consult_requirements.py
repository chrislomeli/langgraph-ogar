from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from starter.model.project import Project


@dataclass
class ConsultingOutcome:
    project: Project
    questions_to_user: List[str]
    blockers: List[str]
    notes: List[str]


def requirements_consulting_phase(
    project: Project,
    *,
    user_requirement_bullets: Optional[List[str]] = None,
) -> ConsultingOutcome:
    """
    Consultant-style requirements elicitation.

    Intended behavior:
      1) Preconditions: goals exist.
      2) Get initial requirements:
         - user provides bullets OR system drafts from goals (LLM-assisted).
      3) Normalize into Requirement objects:
         - functional vs nfr
         - statement testable
         - source_goal_ids populated
         - acceptance_criteria drafted (at least stubs)
      4) Identify ambiguities/assumptions:
         - create/append UncertaintyItems (project-level register)
         - mark blockers where they prevent acceptance criteria definition

    Deterministic checks:
      - each requirement links to >= 1 goal
      - functional requirements should have acceptance_criteria (warn if missing)
    """
    questions: List[str] = []
    blockers: List[str] = []
    notes: List[str] = []

    # 1) Preconditions
    if not project.goals:
        blockers.append("Cannot elicit requirements without goals.")
        questions.append("Define goals first (with success metrics).")
        return ConsultingOutcome(project, questions, blockers, notes)

    # 2) If user provided nothing, offer to draft.
    if not user_requirement_bullets and not project.requirements:
        questions.append("Provide initial requirement bullets, or should I draft requirements from the goals?")
        blockers.append("No requirements defined yet.")
        return ConsultingOutcome(project, questions, blockers, notes)

    # 3) Normalize bullets into Requirement objects (LLM-assisted)
    if user_requirement_bullets:
        # TODO:
        # - call LLM to convert bullets -> Requirement objects (draft)
        # - ensure each has source_goal_ids
        # - draft acceptance_criteria stubs
        # - insert into project.requirements
        pass

    # 4) Ask targeted questions for missing acceptance criteria
    for r in project.requirements.values():
        if r.type == "functional" and not r.acceptance_criteria:
            questions.append(f"Add acceptance criteria for requirement: {r.statement}")

    # 5) Notes: define “requirement” vs “design decision” guidance
    notes.append("Keep requirements testable; capture tech choices as DecisionRecords (later).")

    return ConsultingOutcome(project, questions, blockers, notes)