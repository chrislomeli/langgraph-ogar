"""
graph.m10 — Milestone 10: InstrumentedGraph + StateMediator.

Key concepts:
  - InstrumentedGraph: StateGraph subclass with interceptor hooks + middleware
  - Interceptors: observe-only (LoggingInterceptor, MetricsInterceptor)
  - Middleware: transforms results (StateMediator routes tool envelopes → state patches)
  - Nodes return ToolResultEnvelope directly; mediator handles state routing
"""

from .state import ParentState, CreationState, RefinementState
from .graph_builder import build_music_graph

__all__ = [
    "ParentState",
    "CreationState",
    "RefinementState",
    "build_music_graph",
]
