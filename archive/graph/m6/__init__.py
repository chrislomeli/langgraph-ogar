"""
graph.m6 — Milestone 6: Wire in the Real Tools.

Key concept: Replace stub nodes with real implementations.
The graph structure stays the same — only the node internals change.

Real tools wired in:
  - DeterministicPlanner (Sketch → PlanBundle)
  - PatternCompiler (PlanBundle → CompileResult)
  - render_composition (CompositionSpec → music21 Score)
"""

from .state import ParentState, CreationState
from .graph_builder import build_music_graph, build_creation_subgraph

__all__ = [
    "ParentState",
    "CreationState",
    "build_music_graph",
    "build_creation_subgraph",
]
