"""
Intent Router — classifies user message and routes to the correct subgraph.

This is the parent graph's entry point. It sets intent_type in state,
then the routing function (route_by_intent) maps intent to a node name.

Reuses the keyword-matching approach from M2, but now routes to
subgraphs instead of stub nodes.
"""

from ..state import ParentState, IntentType


def intent_router(state: ParentState) -> dict:
    """Classify user message into an intent type."""
    msg = state["user_message"].lower()

    if any(kw in msg for kw in ["write", "create", "compose", "new"]):
        return {"intent_type": IntentType.NEW_SKETCH}
    elif any(kw in msg for kw in ["refine", "change", "make the", "modify"]):
        return {"intent_type": IntentType.REFINE_PLAN}
    else:
        return {"intent_type": IntentType.ANSWER_QUESTION}


def route_by_intent(state: ParentState) -> str:
    """Routing function: maps intent_type to the next node name."""
    intent = state.get("intent_type")
    if intent == IntentType.NEW_SKETCH:
        return "creation"
    elif intent == IntentType.REFINE_PLAN:
        return "answerer"  # Stub — M8 will add real refinement
    else:
        return "answerer"
