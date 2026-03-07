"""
graph.m4 — Milestone 4: Fan-out / Fan-in.

Key concept: Send() spawns N parallel compile_voice nodes,
one per voice in the plan. Results accumulate via an Annotated
reducer, then the assembler merges them.
"""

from .state import MusicGraphState
from .graph_builder import build_music_graph

__all__ = [
    "MusicGraphState",
    "build_music_graph",
]
