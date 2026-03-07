"""
graph.m9 — Milestone 9: ToolSpec + Registry — Wire the Tool Library.

Key concepts:
  - ToolSpec: frozen contract with Pydantic in/out models + handler
  - ToolRegistry: central catalog of all tools
  - LocalToolClient: validates inputs/outputs, wraps results in ToolResultEnvelope
  - Graph nodes call tools through LocalToolClient instead of directly
"""

from .state import ParentState, CreationState, RefinementState
from .graph_builder import build_music_graph

__all__ = [
    "ParentState",
    "CreationState",
    "RefinementState",
    "build_music_graph",
]
