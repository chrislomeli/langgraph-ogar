"""
Answerer — stub node for non-creation, non-refinement intents.
"""

from ..state import ParentState


def answerer(state: ParentState) -> dict:
    """Stub answerer — returns a simple response."""
    intent = state.get("intent_type")
    msg = state["user_message"]
    return {"response": f"[Answerer] Received '{msg}' with intent={intent}"}
