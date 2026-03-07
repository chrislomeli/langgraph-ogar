"""
graph.m12 -- Milestone 12: Prompt Templates + LLM Swap.

Key concepts:
  - PromptTemplate: structured prompt with system/user messages
  - PlannerStrategy ABC: pluggable engine (deterministic or LLM-backed)
  - DeterministicStrategy: wraps existing DeterministicPlanner
  - LLMStrategy (stub): placeholder for real LLM calls
  - DeterministicFallback: tries LLM first, falls back to deterministic
  - Same graph topology as M11 -- the swap is in how planning happens
"""

from .state import ParentState, CreationState, RefinementState
from .graph_builder import build_music_graph

__all__ = [
    "ParentState",
    "CreationState",
    "RefinementState",
    "build_music_graph",
]
