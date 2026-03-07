"""
Stub destination nodes for M2 routing tests.

These are placeholder nodes that just return markers.
You don't need to modify these — they're here so the router has
something to route to. Future milestones will replace these with real nodes.
"""

from graph.m2.state import MusicGraphState


def new_sketch(state: MusicGraphState) -> dict:
    """Stub for the creation path."""
    return {"path": "creation"}


def refine_plan(state: MusicGraphState) -> dict:
    """Stub for the refinement path."""
    return {"path": "refinement"}


def save_project(state: MusicGraphState) -> dict:
    """Stub for the save path."""
    return {"path": "save"}


def load_requests(state: MusicGraphState) -> dict:
    """Stub for the load path."""
    return {"path": "load"}


def answer_question(state: MusicGraphState) -> dict:
    """Stub for the answerer path."""
    return {"path": "answerer"}
