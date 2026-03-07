from __future__ import annotations
from typing import List
from ogar.domain.models.project import Project

def blocking_questions_for_stage(project: Project, stage: str) -> List[str]:
    qs: List[str] = []

    if stage == "goals":
        if not project.title.strip():
            qs.append("What is the project title?")
        qs.append("List 2–4 starter goals. For each, include at least one success metric.")

    if stage == "requirements":
        qs.append("Provide 5–10 requirement bullets (messy is fine), or write: 'draft from goals'.")

    return qs