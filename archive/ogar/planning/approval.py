"""
Approval policies — Pluggable strategies for human-in-the-loop control.

The orchestrator consults the active policy to decide whether a
sub-plan needs human approval or can be auto-approved.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ogar.planning.models import PlanGraph, SubPlan


class ApprovalPolicy(ABC):
    """Determines whether a sub-plan needs human approval."""

    @abstractmethod
    def needs_approval(self, sub_plan: "SubPlan", plan: "PlanGraph") -> bool:
        """Return True if this sub-plan requires human sign-off."""


class AlwaysApprove(ApprovalPolicy):
    """Auto-approve everything (fully autonomous mode)."""

    def needs_approval(self, sub_plan, plan):
        return False


class AlwaysReview(ApprovalPolicy):
    """Human reviews every sub-plan (maximum control)."""

    def needs_approval(self, sub_plan, plan):
        return True


class ReviewStructuralChanges(ApprovalPolicy):
    """
    Auto-approve re-planned content; review new sub-plans.

    A sub-plan at version 1 is new (structural change) and needs review.
    Higher versions are re-plans of existing scopes and are auto-approved.
    """

    def needs_approval(self, sub_plan, plan):
        return sub_plan.version == 1
