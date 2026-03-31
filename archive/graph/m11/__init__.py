"""
graph.m11 -- Milestone 11: PlanOrchestrator Integration.

Key concepts:
  - PlanGraph: DAG of SubPlans representing the composition pipeline
  - ScopeRegistry: maps scope_type to domain planners + executors
  - PlanOrchestrator: drives the DAG through its lifecycle
  - ApprovalPolicy: controls human-in-the-loop (AlwaysApprove for auto)
  - The creation pipeline becomes: sketch -> plan -> compile (as a DAG)
  - Refinement = targeted re-plan + automatic downstream invalidation
"""

from .state import ParentState, CreationState, RefinementState
from .graph_builder import build_music_graph

__all__ = [
    "ParentState",
    "CreationState",
    "RefinementState",
    "build_music_graph",
]
