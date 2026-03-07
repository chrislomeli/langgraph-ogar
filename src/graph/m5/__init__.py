"""
graph.m5 — Milestone 5: Subgraphs.

Key concept: A compiled subgraph can be used as a node in a parent graph.
The creation pipeline (engine → review → compile → assemble) is extracted
into its own subgraph, and the parent graph routes to it based on intent.
"""

from .state import ParentState, CreationState
from .graph_builder import build_music_graph, build_creation_subgraph

__all__ = [
    "ParentState",
    "CreationState",
    "build_music_graph",
    "build_creation_subgraph",
]
