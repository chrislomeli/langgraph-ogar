"""
langgraph_ext — Reusable LangGraph infrastructure.

Three subsystems:
  1. instrumented_graph — InstrumentedGraph subclass + interceptor protocol
  2. tool_client — Transport-agnostic tool contracts (MCP-ready)
  3. planning — DAG-based plan orchestration for agentic workflows

This package has NO dependencies on symbolic_music or intent.
Only depends on: langgraph, langchain-core, pydantic.
"""

from framework.langgraph_ext.instrumented_graph import (
    Interceptor,
    InstrumentedGraph,
    Middleware,
)
from framework.langgraph_ext.tool_client import (
    LocalToolClient,
    ToolClient,
    ToolRegistry,
    ToolResultEnvelope,
    ToolResultMeta,
    ToolSpec,
)
from framework.langgraph_ext.planning import (
    AlwaysApprove,
    AlwaysReview,
    ApprovalPolicy,
    EventKind,
    OrchestratorEvent,
    PlanGraph,
    PlanOrchestrator,
    PlanPhase,
    RefinementRequest,
    ReviewStructuralChanges,
    ScopeRegistry,
    StepResult,
    SubPlan,
    SubPlanStatus,
)

__all__ = [
    "Interceptor",
    "InstrumentedGraph",
    "Middleware",
    "ToolSpec",
    "ToolRegistry",
    "ToolResultEnvelope",
    "ToolResultMeta",
    "ToolClient",
    "LocalToolClient",
    # Planning
    "SubPlanStatus",
    "PlanPhase",
    "SubPlan",
    "PlanGraph",
    "RefinementRequest",
    "ScopeRegistry",
    "ApprovalPolicy",
    "AlwaysApprove",
    "AlwaysReview",
    "ReviewStructuralChanges",
    "EventKind",
    "OrchestratorEvent",
    "PlanOrchestrator",
    "StepResult",
]
