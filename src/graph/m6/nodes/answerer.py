"""
Answerer — stub node for non-creation intents.
Same as M5 — handles "refine" and "question" intents.
"""

from ..state import ParentState


def answerer(state: ParentState) -> dict:
    """Stub answerer — returns a simple response for non-creation intents."""
    intent = state.get("intent_type")
    msg = state["user_message"]
    return {"response": f"[Answerer] Received '{msg}' with intent={intent}"}
