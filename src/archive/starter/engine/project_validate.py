from __future__ import annotations

from dataclasses import dataclass
from typing import List, Set

from starter.model.project import Project, Ref


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "error"  # or "warn"
    obj_type: str | None = None
    obj_id: str | None = None


def validate_project(project: Project) -> List[ValidationIssue]:
    """
    Deterministic project-level consistency checks.
    Keep this pure and unit-testable.
    """
    issues: List[ValidationIssue] = []

    goal_ids: Set[str] = set(project.goals.keys())
    req_ids: Set[str] = set(project.requirements.keys())
    wid_ids: Set[str] = set(project.work_items.keys())

    # --- Goals sanity ---
    if not project.goals:
        issues.append(ValidationIssue(
            code="NO_GOALS",
            message="Project has no goals.",
            obj_type="project",
            obj_id=project.pid,
        ))

    for g in project.goals.values():
        if g.status == "active" and not g.success_metrics:
            issues.append(ValidationIssue(
                code="GOAL_NO_METRICS",
                message=f"Goal '{g.gid}' is active but has no success_metrics.",
                severity="warn",
                obj_type="goal",
                obj_id=g.gid,
            ))

    # --- Requirements must reference existing goals (Requirement model enforces non-empty, here we enforce existence) ---
    for r in project.requirements.values():
        missing = [gid for gid in r.source_goal_ids if gid not in goal_ids]
        if missing:
            issues.append(ValidationIssue(
                code="REQ_MISSING_GOAL",
                message=f"Requirement '{r.rid}' references missing goals: {missing}",
                obj_type="requirement",
                obj_id=r.rid,
            ))
        if r.type == "functional" and not r.acceptance_criteria:
            issues.append(ValidationIssue(
                code="REQ_NO_ACCEPTANCE",
                message=f"Functional requirement '{r.rid}' has no acceptance_criteria.",
                severity="warn",
                obj_type="requirement",
                obj_id=r.rid,
            ))

    # --- Work item traces should point at real objects ---
    for w in project.work_items.values():
        if not w.traces_to:
            issues.append(ValidationIssue(
                code="WORK_NO_TRACE",
                message=f"Work item '{w.wid}' has no traces_to links (goal/requirement/decision).",
                severity="warn",
                obj_type="work_item",
                obj_id=w.wid,
            ))
        for ref in w.traces_to:
            issues.extend(_validate_ref(ref, goal_ids, req_ids, wid_ids, w.wid))

        # Validate work-item dependency references
        for dep in w.depends_on:
            if dep not in wid_ids:
                issues.append(ValidationIssue(
                    code="WORK_DEP_MISSING",
                    message=f"Work item '{w.wid}' depends_on missing work item '{dep}'.",
                    obj_type="work_item",
                    obj_id=w.wid,
                ))

    # --- Uncertainties should ideally be linked (or else likely too vague) ---
    for u in project.uncertainties.values():
        if u.status != "resolved" and len(u.links) == 0:
            issues.append(ValidationIssue(
                code="UNCERTAINTY_ORPHAN",
                message=f"Uncertainty '{u.uid}' has no links (likely too vague).",
                severity="warn",
                obj_type="uncertainty",
                obj_id=u.uid,
            ))

    return issues


def _validate_ref(ref: Ref, goal_ids: Set[str], req_ids: Set[str], wid_ids: Set[str], wid: str) -> List[ValidationIssue]:
    issues: List[ValidationIssue] = []
    if ref.type == "goal" and ref.id not in goal_ids:
        issues.append(ValidationIssue(
            code="TRACE_GOAL_MISSING",
            message=f"Work item '{wid}' traces_to missing goal '{ref.id}'.",
            obj_type="work_item",
            obj_id=wid,
        ))
    if ref.type == "requirement" and ref.id not in req_ids:
        issues.append(ValidationIssue(
            code="TRACE_REQ_MISSING",
            message=f"Work item '{wid}' traces_to missing requirement '{ref.id}'.",
            obj_type="work_item",
            obj_id=wid,
        ))
    if ref.type == "work_item" and ref.id not in wid_ids:
        issues.append(ValidationIssue(
            code="TRACE_WORK_MISSING",
            message=f"Work item '{wid}' traces_to missing work item '{ref.id}'.",
            obj_type="work_item",
            obj_id=wid,
        ))
    # decision/template_step/project types can be validated later when you add them
    return issues