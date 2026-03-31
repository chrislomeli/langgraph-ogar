"""
Intent Router — same keyword-matching approach from M5.
In a production system, this would be replaced with an LLM classifier.
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
        return "answerer"
    else:
        return "answerer"
