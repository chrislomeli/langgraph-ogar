"""
Registry — Extension points for domain planners and executors.

The framework dispatches to registered implementations based on
``scope_type``.  Domain code registers its planners and executors
at application startup.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from framework.langgraph_ext.planning.models import PlanGraph, SubPlan


# ── Abstract base classes ───────────────────────────────────────────


class PlanProposer(ABC):
    """
    Produces an initial PlanGraph from user intent.

    Domain implementations decide what sub-plans to create,
    what dependencies to declare, and what initial content to set.
    """

    @abstractmethod
    def propose(self, intent: str, context: Optional[dict[str, Any]] = None) -> "PlanGraph":
        """Turn user intent into a plan DAG."""


class SubPlanPlanner(ABC):
    """
    Produces content for a single sub-plan scope type.

    Called when a sub-plan needs (re-)planning — either during
    initial proposal or after invalidation.
    """

    @abstractmethod
    def plan(
        self,
        scope_id: str,
        plan: "PlanGraph",
        context: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Produce content for the given sub-plan.

        Args:
            scope_id: The sub-plan to produce content for.
            plan: The full plan graph (read upstream sub-plan content as needed).
            context: Optional additional context.

        Returns:
            Domain-specific content to store in ``SubPlan.content``.
        """


class SubPlanExecutor(ABC):
    """
    Executes an approved sub-plan and produces a result.

    Called by the orchestrator when a sub-plan is approved and
    all its dependencies are done.
    """

    @abstractmethod
    def execute(
        self,
        sub_plan: "SubPlan",
        plan: "PlanGraph",
        context: Optional[dict[str, Any]] = None,
    ) -> Any:
        """
        Execute the sub-plan and return a result.

        Args:
            sub_plan: The approved sub-plan to execute.
            plan: The full plan graph (read upstream results as needed).
            context: Optional additional context.

        Returns:
            Domain-specific result to store in ``SubPlan.result``.
        """


# ── Built-in no-ops ────────────────────────────────────────────────


class NoOpPlanner(SubPlanPlanner):
    """Planner that returns None.  Use for sub-plans that don't need planning."""

    def plan(self, scope_id, plan, context=None):
        return None


class NoOpExecutor(SubPlanExecutor):
    """Executor that returns None.  Use for sub-plans consumed by downstream executors."""

    def execute(self, sub_plan, plan, context=None):
        return None


# ── Scope Registration ──────────────────────────────────────────────


@dataclass
class _ScopeEntry:
    """Internal: a registered scope type with its engine and executor."""
    scope_type: str
    planner: SubPlanPlanner
    executor: SubPlanExecutor


class ScopeRegistry:
    """
    Maps scope_type strings to engine and executor implementations.

    The orchestrator uses this to dispatch planning and execution
    to the correct domain code.

    Usage:
        registry = ScopeRegistry()
        registry.register("harmony_plan", HarmonyPlanner(), NoOpExecutor())
        registry.register("compilation", NoOpPlanner(), PatternCompilerExecutor())

        engine = registry.get_planner("harmony_plan")
        executor = registry.get_executor("compilation")
    """

    def __init__(self) -> None:
        self._entries: dict[str, _ScopeEntry] = {}

    def register(
        self,
        scope_type: str,
        planner: SubPlanPlanner,
        executor: SubPlanExecutor,
    ) -> None:
        """Register a engine and executor for a scope type."""
        if scope_type in self._entries:
            raise ValueError(f"Scope type '{scope_type}' is already registered.")
        self._entries[scope_type] = _ScopeEntry(
            scope_type=scope_type,
            planner=planner,
            executor=executor,
        )

    def get_planner(self, scope_type: str) -> SubPlanPlanner:
        """Get the engine for a scope type."""
        entry = self._entries.get(scope_type)
        if entry is None:
            raise KeyError(f"No registration for scope type '{scope_type}'.")
        return entry.planner

    def get_executor(self, scope_type: str) -> SubPlanExecutor:
        """Get the executor for a scope type."""
        entry = self._entries.get(scope_type)
        if entry is None:
            raise KeyError(f"No registration for scope type '{scope_type}'.")
        return entry.executor

    def registered_types(self) -> list[str]:
        """Return sorted list of registered scope types."""
        return sorted(self._entries.keys())

    def has(self, scope_type: str) -> bool:
        """Check if a scope type is registered."""
        return scope_type in self._entries
