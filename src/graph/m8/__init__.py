"""
graph.m8 — Milestone 8: The Refinement Loop.

Key concepts:
  - Graph CYCLES: refinement subgraph can loop back for iterative changes
  - Scoped recompilation: only recompile what changed
  - Merge assembler: preserve unchanged voices from previous compile_result
  - Refinement subgraph as a node in the parent graph
"""

from .state import ParentState, CreationState, RefinementState
from .graph_builder import build_music_graph

__all__ = [
    "ParentState",
    "CreationState",
    "RefinementState",
    "build_music_graph",
]
