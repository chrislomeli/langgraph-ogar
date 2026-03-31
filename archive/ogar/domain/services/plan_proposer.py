"""
plan_proposer — Builds a PlanGraph from a Project's goals and requirements.

This is the bridge between the domain layer (Project) and the planning
framework (PlanGraph, SubPlan).  It implements PlanProposer so the
PlanOrchestrator can use it.

The proposer creates one sub-plan per goal, plus a "validate" sub-plan
that depends on all goals, plus a "report" sub-plan that depends on validate.

    goal_1 ─┐
    goal_2 ─┼── validate ── report
    goal_3 ─┘

Each sub-plan has a scope_type that routes to the correct planner/executor
in the ScopeRegistry.
"""
from __future__ import annotations

from typing import Any, Optional

from ogar.domain.models.project import Project
from ogar.planning.models import PlanGraph, SubPlan
from ogar.planning.registry import PlanProposer


class ProjectPlanProposer(PlanProposer):
    """
    Turn a Project (with goals + requirements) into a PlanGraph.

    Each goal becomes a sub-plan of type "goal_work".
    A "validate" sub-plan depends on all goal sub-plans.
    A "report" sub-plan depends on validate.
    """

    def propose(
        self,
        intent: str,
        context: Optional[dict[str, Any]] = None,
    ) -> PlanGraph:
        project: Project = context["project"]

        plan = PlanGraph(
            title=f"Execution plan for: {project.title}",
            intent_summary=intent,
        )

        # One sub-plan per goal
        goal_scope_ids = []
        for gid, goal in project.goals.items():
            scope_id = f"work_{gid}"
            goal_scope_ids.append(scope_id)
            plan.sub_plans[scope_id] = SubPlan(
                scope_id=scope_id,
                scope_type="goal_work",
                content={
                    "goal_id": gid,
                    "goal_statement": goal.statement,
                    "success_metrics": goal.success_metrics,
                    "related_requirements": [
                        rid for rid, r in project.requirements.items()
                        if gid in r.source_goal_ids
                    ],
                },
            )
            plan.dependencies[scope_id] = set()

        # Validate sub-plan depends on all goal work
        plan.sub_plans["validate"] = SubPlan(
            scope_id="validate",
            scope_type="validate",
            content={"check": "project_consistency"},
        )
        plan.dependencies["validate"] = set(goal_scope_ids)

        # Report sub-plan depends on validate
        plan.sub_plans["report"] = SubPlan(
            scope_id="report",
            scope_type="report",
            content={"report_type": "uncertainty_summary"},
        )
        plan.dependencies["report"] = {"validate"}

        return plan
