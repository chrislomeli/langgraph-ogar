"""
Intent Router — M7 adds persistence intents: save, load, list.

Extends M6's keyword matching with three new intent types.
"""

import re
from ..state import ParentState, IntentType


def intent_router(state: ParentState) -> dict:
    """Classify user message into an intent type."""
    msg = state["user_message"].lower()

    if any(kw in msg for kw in ["save", "store"]):
        # Extract project title from "save as <title>" or "save <title>"
        title = _extract_title(state["user_message"], "save")
        return {
            "intent_type": IntentType.SAVE_PROJECT,
            "project_title": title,
        }
    elif any(kw in msg for kw in ["load", "open", "resume"]):
        title = _extract_title(state["user_message"], "load")
        return {
            "intent_type": IntentType.LOAD_PROJECT,
            "project_title": title,
        }
    elif any(kw in msg for kw in ["list", "show projects", "my projects"]):
        return {"intent_type": IntentType.LIST_PROJECTS}
    elif any(kw in msg for kw in ["write", "create", "compose", "new"]):
        return {"intent_type": IntentType.NEW_SKETCH}
    elif any(kw in msg for kw in ["refine", "change", "make the", "modify"]):
        return {"intent_type": IntentType.REFINE_PLAN}
    else:
        return {"intent_type": IntentType.ANSWER_QUESTION}


def _extract_title(msg: str, verb: str) -> str:
    """Extract project title from messages like 'save as My Rock Tune' or 'load My Rock Tune'."""
    # Try "save as <title>"
    match = re.search(rf'{verb}\s+as\s+"?([^"]+)"?', msg, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Try "save <title>" / "load <title>"
    match = re.search(rf'{verb}\s+"?([^"]+)"?', msg, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return "Untitled Project"


def route_by_intent(state: ParentState) -> str:
    """Routing function: maps intent_type to the next node name."""
    intent = state.get("intent_type")
    routes = {
        IntentType.NEW_SKETCH: "creation",
        IntentType.SAVE_PROJECT: "save_project",
        IntentType.LOAD_PROJECT: "load_project",
        IntentType.LIST_PROJECTS: "list_projects",
        IntentType.REFINE_PLAN: "answerer",
        IntentType.ANSWER_QUESTION: "answerer",
    }
    return routes.get(intent, "answerer")
