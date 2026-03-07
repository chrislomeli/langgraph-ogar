"""
Answerer — stub node for non-creation intents.

Handles "refine" and "question" intents with a simple response.
In M8, the refine path will be replaced with a real refinement subgraph.
"""

from ..state import ParentState


def answerer(state: ParentState) -> dict:
    """Stub answerer — returns a simple response for non-creation intents."""
    intent = state.get("intent_type")
    msg = state["user_message"]
    return {"response": f"[Answerer] Received '{msg}' with intent={intent}"}
