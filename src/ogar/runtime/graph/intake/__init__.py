"""
Intake subgraph — elicit goals and requirements from the human.

Topology: control → consult → apply_and_validate → (loop or done)
"""
from .intake_graph import build_graph as build_intake_graph, IntakeState

__all__ = ["build_intake_graph", "IntakeState"]
