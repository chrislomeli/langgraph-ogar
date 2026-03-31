"""
graph.goals — Intake graph: control → consult → apply_and_validate → loop.
"""

from .graph_builder import build_graph, IntakeState

__all__ = [
    "IntakeState",
    "build_graph",
]
