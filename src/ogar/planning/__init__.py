"""
planning — Generic plan orchestration for agentic workflows.

Provides a DAG-based plan management layer:
  1. models    — SubPlan, PlanGraph, status lifecycle
  2. dag       — Topological sort, cycle detection, invalidation propagation
  3. registry  — Extension points for domain planners and executors
  4. approval  — Pluggable approval policies

This package has NO dependencies on symbolic_music or intent.
Only depends on: pydantic.
"""

from ogar.planning.models import (
    PlanGraph,
    PlanPhase,
    RefinementRequest,
    SubPlan,
    SubPlanStatus,
)
from ogar.planning.dag import (
    CycleError,
    downstream,
    invalidate_downstream,
    parallel_groups,
    ready_to_execute,
    roots,
    leaves,
    topological_sort,
    upstream,
)
from ogar.planning.registry import (
    PlanProposer,
    ScopeRegistry,
    SubPlanExecutor,
    SubPlanPlanner,
)
from ogar.planning.approval import (
    AlwaysApprove,
    AlwaysReview,
    ApprovalPolicy,
    ReviewStructuralChanges,
)
from ogar.planning.orchestrator import (
    EventKind,
    OrchestratorEvent,
    PlanOrchestrator,
    StepResult,
)

__all__ = [
    # Models
    "SubPlanStatus",
    "PlanPhase",
    "SubPlan",
    "PlanGraph",
    "RefinementRequest",
    # DAG operations
    "CycleError",
    "topological_sort",
    "roots",
    "leaves",
    "parallel_groups",
    "ready_to_execute",
    "downstream",
    "upstream",
    "invalidate_downstream",
    # Registry
    "PlanProposer",
    "SubPlanPlanner",
    "SubPlanExecutor",
    "ScopeRegistry",
    # Approval
    "ApprovalPolicy",
    "AlwaysApprove",
    "AlwaysReview",
    "ReviewStructuralChanges",
    # Orchestrator
    "EventKind",
    "OrchestratorEvent",
    "PlanOrchestrator",
    "StepResult",
]
