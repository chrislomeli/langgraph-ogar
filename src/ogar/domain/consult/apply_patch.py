from __future__ import annotations
from ogar.domain.models.project import Project
from ogar.domain.consult.patches import ProjectPatch

def apply_patch(project: Project, patch: ProjectPatch) -> Project:
    if patch.title:
        project.title = patch.title

    for gid, g in patch.goals_upsert.items():
        project.goals[gid] = g

    for rid, r in patch.requirements_upsert.items():
        project.requirements[rid] = r

    for uid, u in patch.uncertainties_upsert.items():
        project.uncertainties[uid] = u

    return project