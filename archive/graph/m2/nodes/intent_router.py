"""
Intent Router — classifies user messages and routes to the right path.

YOUR JOB (M2):
  Write a function called `intent_router` that:
    - Takes state (reads 'user_message')
    - Returns a dict with 'intent_type' key
    - Classifies intent using keyword matching (not LLM)

  Intents to detect:
    - "new_sketch" for creation requests ("write me", "create a", "make a new")
    - "plan_refine" for refinement requests ("make the", "change the", "adjust")
    - "save_project" for save requests ("save", "keep")
    - "load_project" for load requests ("load", "open")
    - "answer_question" for questions ("what", "how", "why", "where")

  Signature:
    def intent_router(state: MusicGraphState) -> dict:
        ...

  Hint: Use simple string matching. Lowercase the message and check for keywords.
"""
from graph.m2.state import MusicGraphState, IntentType

INTENT_ROUTE_MAP = {
    IntentType.NEW_SKETCH: "new_sketch",
    IntentType.REFINE_PLAN: "refine_plan",
    IntentType.SAVE_PROJECT: "save_project",
    IntentType.LOAD_REQUESTS: "load_requests",
    IntentType.ANSWER_QUESTION: "answer_question"
}


def intent_router(state: MusicGraphState) -> dict:
    msg = state["user_message"].lower()

    if any(word in msg for word in ["write me", "create a", "make a new"]):
        return {"intent_type": IntentType.NEW_SKETCH}
    elif any(word in msg for word in ["make the", "change the", "adjust"]):
        return {"intent_type": IntentType.REFINE_PLAN}
    elif any(word in msg for word in ["save", "keep"]):
        return {"intent_type": IntentType.SAVE_PROJECT}
    elif any(word in msg for word in ["load", "open"]):
        return {"intent_type": IntentType.LOAD_REQUESTS}
    elif any(word in msg for word in ["what", "how", "why", "where"]):
        return {"intent_type": IntentType.ANSWER_QUESTION}

    return {"intent_type": IntentType.ANSWER_QUESTION}  # partial state?

def route_from_intent(state: MusicGraphState):
    result =  INTENT_ROUTE_MAP[state["intent_type"]]
    return result